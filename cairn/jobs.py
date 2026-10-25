"""Background work: import from the Pocket, transcribe, summarize. One job at a time."""

import os
import threading
import time
from pathlib import Path

from . import config, llm, pocket, privacy, speech
from .notes import guess_date, make_id


class Busy(RuntimeError):
    pass


class Jobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self._state = {"running": False, "kind": "", "step": "", "id": None, "done": 0, "total": 0, "pct": None, "errors": []}
        self.cancelled = False
        self.store.reset_interrupted()

    def snapshot(self):
        with self.lock:
            return dict(self._state, errors=list(self._state["errors"]))

    def _set(self, **changes):
        with self.lock:
            self._state.update(changes)

    def _fail(self, message):
        with self.lock:
            self._state["errors"].append(message)

    def _start(self, kind, target, *args):
        with self.lock:
            if self._state["running"]:
                raise Busy("A job is already running.")
            self._state.update(running=True, kind=kind, step="", id=None, done=0, total=0, pct=None, errors=[])
            self.cancelled = False
        threading.Thread(target=self._guard, args=(target,) + args, daemon=True).start()

    def _guard(self, target, *args):
        try:
            target(*args)
        except Exception as error:  # a job must never leave the state stuck
            self._fail(str(error))
        finally:
            self._set(running=False, step="", id=None, pct=None)

    def cancel(self):
        """Stop after the step in progress; a transcription is interrupted at once."""
        with self.lock:
            if not self._state["running"]:
                return
            self.cancelled = True
        speech.abort()

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

    def set_options(self, note_id, level=None, lang=None):
        """Choose the level of detail and the language of one recording (the interface language until chosen)."""
        if (level is not None and level not in config.LEVELS) or (lang is not None and lang not in config.LANGS):
            raise ValueError("bad_option")
        note = self.store.get(note_id)
        if level is not None:
            note["level"] = level
        if lang is not None:
            note["lang"] = lang
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
        """Process the chosen recording first, then carry on with the others that are waiting."""
        settings = config.load_settings()
        attempted = {note_id}
        self._set(total=1, done=0, id=note_id)
        if self._try(note_id, settings):
            self._drain(settings, attempted)

    def _try(self, note_id, settings):
        """Process one recording and keep going if it fails. Returns False when the job was cancelled."""
        try:
            self._process(note_id, settings)
        except Exception as error:
            if self.cancelled:
                self._reset(note_id)
                return False
            note = self.store.get(note_id)
            self._fail("%s: %s" % (note.get("title") or note_id, error))
        return not self.cancelled

    def _drain(self, settings, attempted=None):
        """Process the waiting recordings, newest first. The queue is read again after each one,
        so recordings put back while the job runs are picked up too."""
        attempted = set() if attempted is None else attempted
        while not self.cancelled:
            pending = [n for n in self.store.all()
                       if n.get("status") in ("waiting", "error") and n["id"] not in attempted and os.path.exists(n.get("audio", ""))]
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

    def _import(self):
        settings = config.load_settings()
        source = pocket.find_pocket()
        if source:
            files = pocket.list_recordings(source)
            self._set(step="copying", total=len(files), done=0)
            audio_dir = Path(settings["audio_dir"])
            for index, path in enumerate(files):
                self._set(done=index)
                try:
                    self._copy_one(source, path, audio_dir)
                except OSError as error:
                    self._fail("%s: %s" % (path.name, error))
        self._set(step="", done=0, total=0)
        self._drain(settings)

    def _copy_one(self, source, path, audio_dir):
        rel = path.relative_to(source).as_posix()
        stat = path.stat()
        existing = self.store.find_source(rel)
        target = audio_dir / rel
        if (
            existing
            and existing.get("sha256")
            and existing.get("size") == stat.st_size
            and existing.get("mtime") == int(stat.st_mtime)
            and os.path.exists(existing.get("audio", ""))
        ):
            return
        digest = pocket.copy_verified(path, target)
        note = existing or {"id": make_id(rel), "source": rel, "status": "waiting", "title": "", "level": None}
        note.update(
            audio=str(target), sha256=digest, size=stat.st_size, mtime=int(stat.st_mtime),
            date=note.get("date") or guess_date(path, stat.st_mtime),
            duration=note.get("duration") or pocket.estimate_duration(target),
        )
        self.store.save(note)

    # Processing

    def _process(self, note_id, settings):
        note = self.store.get(note_id)
        lang = self._lang(note, settings)
        level = note.get("level") if note.get("level") in config.LEVELS else "mid"  # chosen per recording

        def step(name):
            note["status"], note["step"] = name, name
            self.store.save(note)
            self._set(step=name, pct=0 if name == "transcribing" else None)

        def pct(value):
            self._set(pct=value)

        started = time.time()
        try:
            step("transcribing")
            result = speech.transcribe(note["audio"], progress=pct)
            quality, doubtful = speech.assess(result["segments"])
            note.update(
                segments=result["segments"], quality=quality, doubtful=doubtful, passages=len(doubtful),
                duration=result["duration"] or note.get("duration"), lang=lang, heard=result.get("language"), error="",
            )
            self.store.save(note)
            note["clean"] = "\n\n".join(speech.raw_lines(result["segments"]))  # the recognized text is already punctuated
            step("summarizing")
            self._summarize(note, level, lang)
            cfg = config.install_config()
            note.update(
                status="done", step="", level=level, processed=time.strftime("%Y-%m-%dT%H:%M:%S"),
                elapsed=int(time.time() - started), models={"speech": speech.model_name(), "llm": cfg["llm"]},
            )
            self.store.save(note)
        except Exception as error:
            note.update(status="error", step="", error=str(error))
            self.store.save(note)
            raise

    def _summarize(self, note, level, lang):
        text = note.get("clean") or ""
        summary = llm.summarize(text, level, lang)
        note["summary"], note["lang"] = summary, lang
        if summary.get("title") and not note.get("renamed"):
            note["title"] = summary["title"]
        if not note.get("title"):
            note["title"] = note["date"].replace("T", " ")[:16] if note.get("date") else note["id"]

    # Redo a finished recording at the chosen level

    def start_rerun(self, note_id, level, lang=None):
        """Redo a finished note at the chosen level. The audio is transcribed again only when the speech
        model has changed since the note was made; otherwise the transcript is kept and only the summary
        is rewritten. Returns True when the audio is transcribed again."""
        note = self.store.get(note_id)
        made_with = (note.get("models") or {}).get("speech")
        again = bool(made_with) and made_with != speech.model_name() and os.path.exists(note.get("audio", ""))
        self.set_options(note_id, level, lang)
        if again:
            self._start("import", self._one, note_id)
        else:
            self._start("rerun", self._rerun, note_id, level)
        return again

    def _rerun(self, note_id, level):
        settings = config.load_settings()
        note = self.store.get(note_id)
        self._set(id=note_id, step="summarizing", total=1)
        lang = self._lang(note, settings)
        try:
            if not note.get("clean") and note.get("segments"):
                note["clean"] = "\n\n".join(speech.raw_lines(note["segments"]))
            self._summarize(note, level, lang)
            note.update(status="done", level=level, error="", step="")
            self.store.save(note)
        except Exception as error:
            note.update(error=str(error))
            self.store.save(note)
            raise
