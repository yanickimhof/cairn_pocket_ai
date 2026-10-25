"""Notes store: one JSON file per recording under ~/Cairn/Texts."""

import hashlib
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from . import config, score

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
HEAVY = ("segments", "clean", "doubtful", "summary")  # what makes a note large: left out of the listing copy
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
        self._cache = {}  # file -> (signature, listing copy): only a note that changed is read again

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

    def exists(self, note_id):
        try:
            return self._path(note_id).is_file()
        except KeyError:
            return False

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
        """Every note, complete. Reads each file: for the listing and the queue, use slim()."""
        with self.lock:
            files = sorted(self.folder.glob("*.json"))
            notes = [config.read_json(f, default=None) for f in files]
        return [n for n in notes if n and n.get("id")]

    def slim(self):
        """Every note without its transcript and summary, from a cache that re-reads only the files that changed.
        The listing is polled every second: parsing hours of transcripts each time would not scale."""
        with self.lock:
            files = sorted(self.folder.glob("*.json"))
            seen, rows = set(), []
            for path in files:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                sig = (stat.st_mtime_ns, stat.st_size)
                seen.add(path)
                cached = self._cache.get(path)
                if not cached or cached[0] != sig:
                    note = config.read_json(path, default=None)
                    row = {k: v for k, v in note.items() if k not in HEAVY} if note and note.get("id") else None
                    cached = self._cache[path] = (sig, row)
                if cached[1]:
                    rows.append(dict(cached[1]))
            for gone in set(self._cache) - seen:
                del self._cache[gone]
            return rows

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
            fd, tmp = tempfile.mkstemp(dir=str(self.folder), prefix="ignored.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(sorted(items)))
            os.replace(tmp, self.folder / "ignored.txt")  # atomic: a crash cannot empty the list

    def light(self):
        rows = []
        for n in self.slim():
            row = {k: n.get(k) for k in LIGHT}
            if row["fidelity"] is None and n.get("status") == "done" and not n.get("fidelity_na"):
                row["fidelity"] = self._backfill_fidelity(n["id"])  # notes made before this score existed
            row["done"] = row["status"] == "done"
            rows.append(row)
        return sorted(rows, key=lambda r: r.get("date") or "", reverse=True)

    def _backfill_fidelity(self, note_id):
        """Score an older note once and keep the result with it, so the listing never reads its transcript again."""
        try:
            note = self.get(note_id)
        except KeyError:
            return None
        value = score.fidelity(note.get("summary"), note.get("clean"))
        if value is None:
            note["fidelity_na"] = True  # too few numbers and names to tell
        else:
            note["fidelity"] = value
        self.save(note)
        return value

    def find_source(self, rel):
        for note in self.slim():
            if note.get("source") == rel:
                return self.get(note["id"])
        return None

    def reset_interrupted(self):
        """Recordings left in the middle of processing by a previous run go back to waiting."""
        for row in self.slim():
            if row.get("status") in ("transcribing", "cleaning", "summarizing"):
                note = self.get(row["id"])
                note["status"] = "waiting"
                note["step"] = ""
                self.save(note)
