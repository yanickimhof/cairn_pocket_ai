"""Notes store: one JSON file per recording under ~/Cairn/Texts."""

import hashlib
import re
import threading
from datetime import datetime
from pathlib import Path

from . import config, score

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
LIGHT = ("id", "title", "date", "duration", "status", "quality", "fidelity", "passages", "level", "lang", "error", "step")


def make_id(rel):
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", rel)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_.-") or "recording"
    return "%s-%s" % (slug[:100], hashlib.sha256(rel.encode("utf-8")).hexdigest()[:6])


def guess_date(path, mtime):
    """ISO date: from a timestamp in the file name when there is one, else the file time."""
    match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_ T]?(\d{2})[-_:]?(\d{2})[-_:]?(\d{2})", Path(path).name)
    if match:
        try:
            return datetime(*[int(g) for g in match.groups()]).isoformat(timespec="seconds")
        except ValueError:
            pass
    return datetime.fromtimestamp(mtime).isoformat(timespec="seconds")


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, note_id):
        if not ID_RE.fullmatch(note_id or ""):
            raise KeyError(note_id)
        return self.folder / (note_id + ".json")

    def get(self, note_id):
        with self.lock:
            data = config.read_json(self._path(note_id), default=None)
        if not data:
            raise KeyError(note_id)
        return data

    def save(self, note):
        with self.lock:
            config.write_json(self._path(note["id"]), note)

    def delete(self, note_id):
        with self.lock:
            try:
                self._path(note_id).unlink()
            except FileNotFoundError:
                pass

    def all(self):
        with self.lock:
            files = sorted(self.folder.glob("*.json"))
            notes = [config.read_json(f, default=None) for f in files]
        return [n for n in notes if n and n.get("id")]

    # Recordings the person deleted on this computer only: they stay on the Pocket but are never imported again.

    def ignored(self):
        try:
            return {x for x in (self.folder / "ignored.txt").read_text(encoding="utf-8").splitlines() if x}
        except OSError:
            return set()

    def ignore(self, rel, on=True):
        with self.lock:
            items = self.ignored()
            items.add(rel) if on else items.discard(rel)
            (self.folder / "ignored.txt").write_text("\n".join(sorted(items)), encoding="utf-8")

    def light(self):
        rows = []
        for n in self.all():
            row = {k: n.get(k) for k in LIGHT}
            if row["fidelity"] is None and n.get("status") == "done":
                row["fidelity"] = score.fidelity(n.get("summary"), n.get("clean"))  # notes made before this score existed
            row["done"] = row["status"] == "done"
            rows.append(row)
        return sorted(rows, key=lambda r: r.get("date") or "", reverse=True)

    def find_source(self, rel):
        for note in self.all():
            if note.get("source") == rel:
                return note
        return None

    def reset_interrupted(self):
        """Recordings left in the middle of processing by a previous run go back to waiting."""
        for note in self.all():
            if note.get("status") in ("transcribing", "cleaning", "summarizing"):
                note["status"] = "waiting"
                note["step"] = ""
                self.save(note)
