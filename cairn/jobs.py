"""Background work: import from the Pocket, transcribe, summarize. One job at a time."""

import os
import threading
import time
from pathlib import Path

from . import config, llm, pocket, speech
from .notes import guess_date, make_id


class Busy(RuntimeError):
    pass


class Jobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self._state = {"running": False, "kind": "", "step": "", "id": None, "done": 0, "total": 0, "pct": None, "errors": []}
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
        threading.Thread(target=self._guard, args=(target,) + args, daemon=True).start()

    def _guard(self, target, *args):
        try:
            target(*args)
        except Exception as error:  # a job must never leave the state stuck
            self._fail(str(error))
        finally:
            self._set(running=False, step="", id=None, pct=None)

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
        pending = [n for n in self.store.all() if n.get("status") in ("waiting", "error") and os.path.exists(n.get("audio", ""))]
        pending.sort(key=lambda n: n.get("date") or "")
        self._set(step="", done=0, total=len(pending))
        for index, note in enumerate(pending):
            self._set(done=index, id=note["id"])
            try:
                self._process(note["id"], settings)
            except Exception as error:  # keep going with the next recording
                self._fail("%s: %s" % (note.get("title") or note["id"], error))

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
        lang = settings["tr"] or "en"
        level = settings["level"]

        def step(name):
            note["status"], note["step"] = name, name
            self.store.save(note)
            self._set(step=name, pct=0 if name in ("transcribing", "cleaning") else None)

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
            if settings.get("polish"):
                step("cleaning")
            lines = speech.raw_lines(result["segments"])
            if settings.get("polish") and lines:
                note["clean"] = llm.clean(lines, lang, progress=pct)
            else:  # fast path: the recognized text is already punctuated, skip the slow rewriting pass
                note["clean"] = "\n\n".join(lines)
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

    # Rerun the summary at another level (no new transcription)

    def start_rerun(self, note_id, level):
        self.store.get(note_id)
        self._start("rerun", self._rerun, note_id, level)

    def _rerun(self, note_id, level):
        settings = config.load_settings()
        note = self.store.get(note_id)
        self._set(id=note_id, step="summarizing", total=1)
        lang = settings["tr"] or note.get("lang") or "en"
        try:
            if not note.get("clean") and note.get("segments"):
                lines = speech.raw_lines(note["segments"])
                note["clean"] = llm.clean(lines, lang) if settings.get("polish") else "\n\n".join(lines)
            self._summarize(note, level, lang)
            note.update(status="done", level=level, error="", step="")
            self.store.save(note)
        except Exception as error:
            note.update(error=str(error))
            self.store.save(note)
            raise
