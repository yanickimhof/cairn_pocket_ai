"""Background work: import from the Pocket, transcribe, summarize. One job at a time."""

import math
import copy
import os
import sys
import threading
import time
from pathlib import Path

from . import awake, config, diarize, embed, llm, lock, pocket, privacy, score, speech, system, templates, vault, vocab, voices
from .notes import guess_date, make_id


AUTO_ATTEMPTS = 3   # a recording that fails is retried by itself until it has failed this many times in all
RETRY_DELAY = 300   # seconds, multiplied by the number of failures: the wait before an automatic retry


class Busy(RuntimeError):
    pass


class Gone(RuntimeError):
    """The recording was deleted while it was being processed."""


class Jobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self._state = {"running": False, "kind": "", "step": "", "id": None, "done": 0, "total": 0, "pct": None, "part": 0, "parts": 0, "errors": []}
        self.cancelled = False
        self.paused = False  # set by Stop: automatic processing waits for new recordings or a manual start
        self.secure_wanted = False  # the person asked to secure the Pocket while another job was running
        self.llm_blocked_until = 0.0  # after a failed check of the model server, automatic processing waits a little
        self.store.reset_interrupted()

    def snapshot(self):
        with self.lock:
            data = dict(self._state, errors=list(self._state["errors"]))
        call = data.pop("call", None)
        if call and data.get("step") == "summarizing":
            # The model reports nothing while it works, so the bar moves with the time a call usually takes
            index, total, started, usual = call
            fraction = 1 - math.exp(-(time.time() - started) / usual)
            data["pct"] = min(99, round(100 * (index + 0.9 * fraction) / total))
        return data

    def _set(self, **changes):
        with self.lock:
            self._state.update(changes)

    def _fail(self, message):
        with self.lock:
            self._state["errors"].append(message)

    def _start(self, kind, target, *args):
        for attempt in range(2):
            with self.lock:
                if self._state["running"] and self._state["kind"] == "index" and kind != "index" and attempt == 0:
                    self.cancelled = True  # reading the notes for the search gives way to what the person asks for
                elif self._state["running"]:
                    raise Busy("A job is already running.")
                else:
                    self._state.update(running=True, kind=kind, step="", id=None, done=0, total=0, pct=None, part=0, parts=0, errors=[])
                    self.cancelled = False
                    if kind == "import":
                        self.paused = False
                    break
            for _ in range(100):  # up to ten seconds for the index to step aside
                time.sleep(0.1)
                if not self._state["running"]:
                    break
        threading.Thread(target=self._guard, args=(target,) + args, daemon=True).start()

    def _guard(self, target, *args):
        awake.hold()  # a long batch is not cut short by the computer falling asleep
        try:
            target(*args)
        except Gone:
            pass  # the person deleted the note meanwhile: nothing to report, nothing to bring back
        except Exception as error:  # a job must never leave the state stuck
            self._fail(str(error))
        finally:
            awake.release()
            self._set(running=False, step="", id=None, pct=None)

    def _ready(self):
        """Check the summary model before any long work. False, with the reason recorded, when a note cannot be written
        now: the recordings are left as they are and automatic processing waits two minutes before trying again."""
        try:
            llm.preflight()
            return True
        except llm.LLMError as error:
            self._fail(str(error))
            self.llm_blocked_until = time.time() + 120
            return False

    def cancel(self):
        """Stop after the step in progress; a transcription is interrupted at once."""
        with self.lock:
            if not self._state["running"]:
                return
            self.cancelled = True
            self.paused = True
        speech.abort()
        diarize.abort()

    def start_privacy(self):
        """Run the privacy check: a tiny transcription and question, watching the network."""
        self._start("privacy", self._privacy)

    def _privacy(self):
        self._set(step="privacy", total=1, done=0)
        privacy.run_check()

    def skip(self, note_id):
        """Leave a recording out of the queue (it stays available and can be put back)."""
        note = self.store.get(note_id)
        if note.get("status") in ("waiting", "error"):
            note.update(status="skipped", step="", error="")
            self.store.save(note)

    def restore(self, note_id):
        note = self.store.get(note_id)
        if note.get("status") == "skipped":
            note["status"] = "waiting"
            self.store.save(note)

    def set_options(self, note_id, level=None, lang=None, speech_lang=None):
        """Choose the level of detail and the language of one recording (the interface language until chosen),
        and the language of its audio ("auto" lets the speech engine detect it)."""
        if (level is not None and level not in config.LEVELS) or (lang is not None and lang not in config.LANGS):
            raise ValueError("bad_option")
        if speech_lang is not None and speech_lang != "auto" and speech_lang not in config.LANGS:
            raise ValueError("bad_option")
        note = self.store.get(note_id)
        if level is not None:
            note["level"] = level
        if lang is not None:
            note["lang"] = lang
        if speech_lang is not None:
            note["speech_lang"] = None if speech_lang == "auto" else speech_lang
        self.store.save(note)

    @staticmethod
    def _lang(note, settings):
        if note.get("lang") in config.LANGS:
            return note["lang"]
        return settings["ui"] if settings.get("ui") in config.LANGS else "en"

    def start_process(self, note_id):
        """Process one chosen recording now."""
        note = self.store.get(note_id)
        if note.get("status") == "done" or not os.path.exists(note.get("audio", "")):
            raise ValueError("not_processable")
        self._start("import", self._one, note_id)

    def _one(self, note_id):
        """Process the chosen recording. The others that are waiting follow only if automatic processing is on:
        with it off, nothing is processed that the person did not ask for."""
        settings = config.load_settings()
        attempted = {note_id}
        self._set(total=1, done=0, id=note_id)
        if self._try(note_id, settings) and settings.get("autoprocess", False):
            self._drain(settings, attempted, automatic=True)

    def _try(self, note_id, settings):
        """Process one recording and keep going if it fails. Returns False when the job was cancelled
        or when the summary model cannot be used (nothing is started then)."""
        if not self._ready():
            return False
        try:
            self._process(note_id, settings)
        except Gone:
            return not self.cancelled
        except Exception as error:
            if self.cancelled:
                self._reset(note_id)
                return False
            note = self.store.get(note_id)
            self._fail("%s: %s" % (note.get("title") or note_id, error))
        return not self.cancelled

    @staticmethod
    def _due(note, automatic, now):
        """A failed recording is retried by itself only a few times and not at once; asking for it by hand always works."""
        if note.get("status") != "error" or not automatic:
            return True
        return int(note.get("attempts") or 0) < AUTO_ATTEMPTS and now >= float(note.get("retry_after") or 0)

    def _drain(self, settings, attempted=None, automatic=False):
        """Process the waiting recordings, newest first. The queue is read again after each one,
        so recordings put back while the job runs are picked up too. When it was not asked for by hand
        (automatic), a recording that keeps failing is left alone after a few tries."""
        attempted = set() if attempted is None else attempted
        while not self.cancelled:
            now = time.time()
            pending = [n for n in self.store.slim()
                       if n.get("status") in ("waiting", "error") and n["id"] not in attempted and os.path.exists(n.get("audio", ""))
                       and self._due(n, automatic, now)]
            if not pending:
                break
            pending.sort(key=lambda n: n.get("date") or "", reverse=True)
            note = pending[0]
            done = len(attempted)
            attempted.add(note["id"])
            self._set(id=note["id"], done=done, total=done + len(pending))
            if not self._try(note["id"], settings):
                break

    def _reset(self, note_id):
        note = self.store.get(note_id)
        note.update(status="waiting", step="", error="")
        self.store.save(note)

    # Import

    def start_import(self):
        self._start("import", self._import)

    def start_sync(self):
        """Copy the new recordings from the Pocket without processing them: the person sees them all and decides."""
        self._start("sync", self._import, False)

    def start_queue(self):
        """Process the recordings that are waiting (automatic processing)."""
        self._start("queue", self._queue)

    def _queue(self):
        self._drain(config.load_settings(), automatic=True)

    def start_index(self, model):
        """Index the notes for the search by meaning (new and changed notes only)."""
        self._start("index", self._index, model)

    def _index(self, model):
        self._set(step="indexing", total=0, done=0)

        def progress(done, total):
            self._set(done=done, total=total)

        before = self.store.signature()  # a note written while indexing is looked at by the next pass
        embed.build(self.store, model, progress, lambda: self.cancelled)
        if not self.cancelled:
            embed.built[model] = before

    def start_seal(self):
        """Seal what is already on disk after the lock was switched on (or after an interrupted pass)."""
        self._start("seal", self._seal)

    def _seal(self):
        self._set(step="sealing", total=1, done=0)
        lock.migrate(True, progress=lambda done, total: self._set(done=done, total=total))
        self._set(step="", done=0, total=0)

    def start_unseal(self):
        """Open every sealed file again, then remove the lock."""
        self._start("unseal", self._unseal)

    def _unseal(self):
        self._set(step="opening", total=1, done=0)
        lock.migrate(False, progress=lambda done, total: self._set(done=done, total=total))
        lock.finish_disable()
        self._set(step="", done=0, total=0)

    def start_secure(self):
        """Copy what is new on the Pocket, then encrypt every recording on it."""
        self._start("secure", self._import, False, True)

    def _import(self, process=True, secure=False):
        settings = config.load_settings()
        source = pocket.find_pocket()
        if source:
            listing = pocket.scan(source)
            wanted = secure or self.secure_wanted or settings.get("pocket_secure_auto", False)
            files = [e for e in listing.readable if not self.store.is_ignored(e.rel, e.size, e.mtime)]
            self._set(step="copying", total=len(files), done=0)
            audio_dir = Path(settings["audio_dir"])
            for index, entry in enumerate(files):
                self._set(done=index)
                try:
                    self._copy_one(entry, audio_dir, listing.key)
                except OSError as error:
                    self._fail("%s: %s" % (entry.rel, error))
                    if not source.exists():  # the Pocket was unplugged: the rest will be copied at the next connection
                        break
            if wanted and listing.header and listing.key and source.exists():
                self.secure_wanted = False
                self._seal_all(source, listing, audio_dir)
            elif secure:
                self.secure_wanted = False
                self._fail("The Pocket is locked: enter its password first." if listing.header else "The Pocket has no vault yet.")
        self._set(step="", done=0, total=0)
        if process:
            self._drain(settings)
        elif settings.get("autoprocess", False) and not self.paused:
            self._drain(settings, automatic=True)  # automatic processing starts as soon as the copy is done, not at the next check

    def _seal_all(self, source, listing, audio_dir):
        """Encrypt the plain recordings of the Pocket. Each one is already on this computer, byte for byte (checked
        again here) before its plain version is replaced."""
        pocket.clean_leftovers(source)
        twins = {(e.rel, e.size, e.mtime) for e in listing.sealed}
        for entry in [e for e in listing.plain if (e.rel, e.size, e.mtime) in twins]:  # a crash left the same recording twice: one is enough
            try:
                pocket.shred(entry.path, entry.size)
                entry.path.unlink()
            except OSError as error:
                self._fail("%s: %s" % (entry.rel, error))
        todo = [e for e in listing.plain if (e.rel, e.size, e.mtime) not in twins and self.store.find_source(e.rel, e.size, e.mtime, light=True)]
        self._set(step="securing", total=len(todo), done=0)
        index = vault.load_index(listing.header["id"])
        for position, entry in enumerate(todo):
            if self.cancelled or not source.exists():
                break
            self._set(done=position)
            note = self.store.find_source(entry.rel, entry.size, entry.mtime, light=True)
            if not note or not note.get("sha256") or not os.path.exists(note.get("audio", "")):
                continue
            try:
                if lock.audio_sha256(note["audio"]) != note["sha256"]:  # the copy on this computer must still be the recording
                    raise OSError("the copy on this computer no longer matches: it is copied again first")

                fid, info = pocket.seal_entry(source, entry, listing.key, note["sha256"])
                index[fid] = info
                vault.save_index(listing.header["id"], index)
            except OSError as error:
                self._fail("%s: %s" % (entry.rel, error))
                if not source.exists():
                    break

    def _copy_one(self, entry, audio_dir, key=None):
        rel = entry.rel
        existing = self.store.find_source(rel, entry.size, entry.mtime, light=True)
        target = audio_dir / rel
        if (
            existing
            and existing.get("sha256")
            and existing.get("size") == entry.size
            and existing.get("mtime") == entry.mtime
            and os.path.exists(existing.get("audio", ""))
        ):
            return
        existing = self.store.get(existing["id"]) if existing else None
        note_id = make_id(rel)
        if existing and existing.get("size") is not None and (existing.get("size"), existing.get("mtime")) != (entry.size, entry.mtime) \
                and existing.get("status") not in ("waiting", "error", "skipped"):
            # the Pocket reuses a name for another recording: the finished note and its audio are left alone, this one is a new note
            note_id = make_id("%s#%d-%d" % (rel, entry.size, entry.mtime))
            target = target.with_name("%s-%d%s" % (target.stem, entry.mtime, target.suffix))
            existing = self.store.get(note_id) if self.store.exists(note_id) else None
        digest = pocket.fetch(entry, target, key)
        note = existing or {"id": note_id, "source": rel, "status": "waiting", "title": "", "level": None}
        note.update(
            audio=str(target), sha256=digest, size=entry.size, mtime=entry.mtime,
            date=note.get("date") or guess_date(target, entry.mtime),
            duration=note.get("duration") or pocket.estimate_duration(target),
        )
        self.store.save(note)
        lock.seal_audio(target)  # with the lock on, a recording is sealed as soon as it is here

    # Processing

    def _process(self, note_id, settings):
        note = self.store.get(note_id)
        lang = self._lang(note, settings)
        level = note.get("level") if note.get("level") in config.LEVELS else "mid"  # chosen per recording

        def keep():
            """Save the note, unless the person deleted it meanwhile: a deleted recording must not come back."""
            if not self.store.exists(note_id):
                raise Gone(note_id)
            self.store.save(note)

        def step(name):
            note["status"], note["step"] = name, name
            keep()
            self._set(step=name, pct=0 if name == "transcribing" else None, part=0, parts=0, call=None)

        def pct(value):
            self._set(pct=value)

        started = time.time()
        timings, reused = {}, []
        try:
            spoken = note.get("speech_lang") if note.get("speech_lang") in config.LANGS else None  # None: the engine detects it
            key = speech.model_key()
            if self._transcript_current(note, spoken, key):
                reused.append("transcribing")  # already transcribed with this model and language: that work is never redone
            else:
                step("transcribing")
                began = time.time()
                with lock.plain(note["audio"]) as audio_file:
                    result = speech.transcribe(audio_file, progress=pct, **({"language": spoken} if spoken else {}))
                timings["transcribing"] = round(time.time() - began, 1)
                quality, doubtful = speech.assess(result["segments"])
                shares, mixed = speech.language_mix(result["segments"])
                note.update(speech_lang_used=spoken, languages=shares, mixed=mixed,
                    segments=result["segments"], quality=quality, doubtful=doubtful, passages=len(doubtful),
                    duration=result["duration"] or note.get("duration"), lang=lang, heard=result.get("language"), error="",
                    transcribed_key=key, transcribed_lang=spoken or "", diarized=False,
                )
                keep()
                if system.ram_gb() < speech.KEEP_MIN_GB:
                    speech.shutdown()  # reloading it costs 1 or 2 s; kept beside the speaker and summary models it slowed them on 16 GB
            if settings.get("diarize") and diarize.available():
                if note.get("diarized"):
                    reused.append("diarizing")
                else:
                    step("diarizing")
                    began = time.time()
                    prints = {}
                    with lock.plain(note["audio"]) as audio_file:
                        if settings.get("voices"):
                            state, turns, prints = diarize.run_with_voices(audio_file, timeout=diarize.timeout_for(note.get("duration")))
                        else:
                            state, turns = diarize.run(audio_file, timeout=diarize.timeout_for(note.get("duration")))
                    timings["diarizing"] = round(time.time() - began, 1)
                    if state == "ok":
                        diarize.assign(note["segments"], turns, lang)
                        self._remember_voices(note, turns, prints, lang)
                        note["diarized"] = True
                        keep()
            self._apply_vocab(note, settings)
            step("summarizing")
            began = time.time()
            self._summarize(note, level, lang)
            timings["summarizing"] = round(time.time() - began, 1)
            if reused:
                timings["reused"] = reused
            cfg = config.install_config()
            note.update(
                status="done", step="", error="", level=level, processed=time.strftime("%Y-%m-%dT%H:%M:%S"),
                elapsed=int(time.time() - started), models={"speech": speech.model_name(), "llm": cfg["llm"]}, timings=timings,
            )
            note.pop("attempts", None)
            note.pop("retry_after", None)
            keep()
            spent = " ".join("%s=%ss" % (k, v) for k, v in timings.items() if isinstance(v, (int, float)))
            print("timing: %s audio=%ds %s%s" % (str(note_id)[:14], int(note.get("duration") or 0), spent,
                                               " reused=" + ",".join(reused) if reused else ""), file=sys.stderr, flush=True)
        except Gone:
            raise
        except Exception as error:
            if not self.store.exists(note_id):  # deleted while it was being processed
                raise Gone(note_id) from error
            attempts = int(note.get("attempts") or 0) + 1
            note.update(status="error", step="", error=str(error), attempts=attempts,
                        retry_after=time.time() + RETRY_DELAY * attempts, timings=timings)
            self.store.save(note)
            raise

    @staticmethod
    def _transcript_current(note, spoken, key):
        """Was the transcript kept with the note made with the speech model and language in use now?"""
        if not note.get("segments"):
            return False
        if note.get("transcribed_key"):
            return note["transcribed_key"] == key and (note.get("transcribed_lang") or None) == spoken
        made_with = (note.get("models") or {}).get("speech")  # a finished note from before this was recorded
        return bool(made_with and made_with == speech.model_name() and (note.get("speech_lang_used") or None) == spoken)

    def _summarize(self, note, level, lang):
        text = note.get("clean") or ""
        total = llm.parts_of(text)

        starts = []

        def progress(index):  # which call of the model is running, so the person sees the note being written
            starts.append(time.time())
            usual = (starts[-1] - starts[0]) / index if index else 120.0  # seconds a call takes: a guess, then measured
            self._set(part=index + 1, parts=total, call=(index, total, starts[-1], max(usual, 5.0)) if total > 1 else None,
                      pct=0 if total > 1 else None)

        settings = config.load_settings()
        custom = templates.find(settings.get("templates"), note.get("template") or settings.get("template_default"))
        summary = llm.summarize(text, level, lang, progress, vocabulary=vocab.spellings(settings.get("vocabulary")),
                                instructions=custom["prompt"] if custom else None)
        vocab.fix_summary(summary, settings.get("vocabulary"))  # the title, the TL;DR and the rest spell the names as the vocabulary says
        note["summary"], note["lang"] = summary, lang
        heard = note.get("heard")
        note["fidelity"], note["fidelity_basis"] = score.fidelity_detail(summary, text, words_ok=heard in (None, lang))
        if custom:
            summary["custom"], summary["template_name"] = custom["id"], custom["name"]
        elif note.get("template") in llm.TEMPLATES:
            summary["template"] = note["template"]
        if summary.get("title") and not note.get("renamed"):
            note["title"] = summary["title"]
        if not note.get("title"):
            note["title"] = note["date"].replace("T", " ")[:16] if note.get("date") else note["id"]
        if settings.get("tags_suggest"):
            try:  # a suggestion is a convenience: it never makes a note fail
                note["tag_suggestions"] = llm.suggest_tags(note, self.store.tag_counts())
            except Exception:
                note.pop("tag_suggestions", None)

    # Redo a finished recording at the chosen level

    def start_rerun(self, note_id, level, lang=None, speech_lang=None):
        """Redo a finished note at the chosen level. The audio is transcribed again only when the speech
        model has changed since the note was made, or the language of the audio was changed; otherwise the
        transcript is kept and only the summary is rewritten. Returns True when the audio is transcribed again."""
        note = self.store.get(note_id)
        made_with = (note.get("models") or {}).get("speech")
        self.set_options(note_id, level, lang, speech_lang)
        note = self.store.get(note_id)
        spoken_changed = note.get("speech_lang") != note.get("speech_lang_used")
        again = ((bool(made_with) and made_with != speech.model_name()) or spoken_changed) and os.path.exists(note.get("audio", ""))
        if again:  # the transcript and the speakers are kept unless the speech model or language changed
            self._start("import", self._one, note_id)
        else:  # a changed vocabulary needs no audio: the words are corrected in the kept transcript, then the note is written again
            self._start("rerun", self._rerun, note_id, level)
        return again

    def _rerun(self, note_id, level):
        settings = config.load_settings()
        note = self.store.get(note_id)
        self._set(id=note_id, step="summarizing", total=1)
        llm.preflight()
        self._rewrite(note, level, self._lang(note, settings), settings)

    OWNED = ("summary", "lang", "fidelity", "fidelity_basis", "tag_suggestions", "status", "level", "error", "step")

    def _commit(self, note, keys):
        """Write what a job produced onto the note as it is now: what the person changed meanwhile (a correction, a name, a tag) is
        kept, and a note that was deleted stays deleted."""
        with self.store.lock:
            if not self.store.exists(note["id"]):
                raise Gone(note["id"])
            fresh = self.store.get(note["id"])
            for key in keys:
                if key == "title":
                    continue
                if key in note:
                    fresh[key] = note[key]
                else:
                    fresh.pop(key, None)
            if not fresh.get("renamed") and note.get("title") and "title" in keys:
                fresh["title"] = note["title"]
            self.store.save(fresh)
            return fresh

    def _rewrite(self, note, level, lang, settings):
        """Correct the words from the current vocabulary, then write the note again from the kept transcript."""
        before = note.get("vocab_key")
        try:
            if note.get("segments"):
                self._apply_vocab(note, settings)
            self._summarize(note, level, lang)
            note.update(status="done", level=level, error="", step="")
            fresh = self._commit(note, self.OWNED + ("title",))
            if fresh.get("segments"):  # the words are corrected again on the note as it is now, corrections by hand included
                self._apply_vocab(fresh, settings)
                self.store.save(fresh)
        except Gone:
            raise
        except Exception as error:
            note.update(error=str(error))
            if before is None:  # the summary was not written again: the note must not pass for up to date
                note.pop("vocab_key", None)
            else:
                note["vocab_key"] = before
            try:
                self._commit(note, ("error", "vocab_key"))
            except Gone:
                pass
            raise

    def _apply_vocab(self, note, settings):
        terms = settings.get("vocabulary") or []
        fixes = vocab.apply(note["segments"], terms)  # always run: it puts the original word back when an entry was removed
        note["vocab_key"] = vocab.key(terms)
        if fixes:
            note["vocab_fixes"] = fixes
        else:
            note.pop("vocab_fixes", None)
        names = note.get("speaker_names") or {}
        note["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(note["segments"], names) if names else note["segments"]))

    # Bring several finished notes up to date with the vocabulary

    def start_vocab(self, ids, force=True):
        self._start("rerun", self._vocab_batch, ids, force)

    def _vocab_batch(self, ids, force=True):
        """Write the notes again with the current vocabulary. Without `force`, a note whose words the vocabulary would not change
        is only marked as up to date: its summary is not written again for nothing."""
        settings = config.load_settings()
        terms = settings.get("vocabulary") or []
        self._set(total=len(ids), done=0)
        llm.preflight()
        for index, note_id in enumerate(ids):
            if self.cancelled:
                break
            self._set(id=note_id, step="summarizing", done=index, pct=None, part=0, parts=0, call=None)
            try:
                note = self.store.get(note_id)
                if not force:
                    probe = copy.deepcopy(note.get("segments") or [])
                    if (vocab.apply(probe, terms) or None) == (note.get("vocab_fixes") or None):
                        note["vocab_key"] = vocab.key(terms)
                        self._commit(note, ("vocab_key",))
                        continue
                level = note.get("level") if note.get("level") in config.LEVELS else "mid"
                self._rewrite(note, level, self._lang(note, settings), settings)
            except Gone:
                continue  # deleted meanwhile
            except Exception as error:  # one note failing does not stop the others
                self._fail("%s: %s" % (note_id, error))
        self._set(done=len(ids))

    # Redo only the speaker identification on an already-processed recording

    def start_rediarize(self, note_id):
        """Redo speaker identification on a finished recording, keeping its transcript and summary.
        Any names already given to speakers are cleared: a fresh pass may not number them the same way."""
        note = self.store.get(note_id)
        if note.get("status") != "done" or not note.get("segments") or not os.path.exists(note.get("audio", "")):
            raise ValueError("not_processable")
        if not diarize.available():
            raise ValueError("diar_unavailable")
        self._start("rerun", self._rediarize, note_id)

    @staticmethod
    def _remember_voices(note, turns, prints, lang):
        """Keep the voiceprints of this recording with the note and name the voices that are known. Without voice memory nothing is kept."""
        note.pop("voices", None)
        if prints:
            note["voices"] = diarize.label_voices(note["segments"], turns, prints, lang)
            voices.recognise(note)

    def _rediarize(self, note_id):
        note = self.store.get(note_id)
        self._set(id=note_id, step="diarizing", total=1)
        settings = config.load_settings()
        lang = self._lang(note, settings)
        try:
            prints = {}
            with lock.plain(note["audio"]) as audio_file:
                if settings.get("voices"):
                    state, turns, prints = diarize.run_with_voices(audio_file)
                else:
                    state, turns = diarize.run(audio_file)
            if state == "missing":
                raise RuntimeError("Diarization model missing. Install it again from Settings > Models.")
            if state != "ok":
                raise RuntimeError("Speaker identification produced no result.")
            diarize.assign(note["segments"], turns, lang)
            note["speaker_names"] = {}
            note.pop("speaker_auto", None)
            self._remember_voices(note, turns, prints, lang)
            names = note.get("speaker_names") or {}
            note["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(note["segments"], names) if names else note["segments"]))
            note.update(status="done", error="", step="")
            with self.store.lock:  # the labels go onto the lines as they are now: a correction made meanwhile stays
                if not self.store.exists(note_id):
                    raise Gone(note_id)
                fresh = self.store.get(note_id)
                if len(fresh.get("segments") or []) == len(note["segments"]):
                    for line, labelled in zip(fresh["segments"], note["segments"]):
                        if labelled.get("speaker"):
                            line["speaker"] = labelled["speaker"]
                        else:
                            line.pop("speaker", None)
                else:
                    fresh["segments"] = note["segments"]
                for key in ("speaker_names", "speaker_auto", "voices", "status", "error", "step"):
                    if key in note:
                        fresh[key] = note[key]
                    else:
                        fresh.pop(key, None)
                names = fresh.get("speaker_names") or {}
                fresh["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(fresh["segments"], names) if names else fresh["segments"]))
                self.store.save(fresh)
        except Gone:
            raise
        except Exception as error:
            note.update(error=str(error))
            try:
                self._commit(note, ("error",))
            except Gone:
                pass
            raise
