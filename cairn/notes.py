"""Notes store: one JSON file per recording under ~/Cairn/Texts."""

import hashlib
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from . import config, lock, score, tags

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,150}")
HEAVY = ("segments", "clean", "doubtful", "summary")  # what makes a note large: left out of the listing copy
LIGHT = ("id", "title", "date", "duration", "status", "quality", "fidelity", "fidelity_basis", "speech_lang", "heard", "mixed", "passages", "level", "lang", "error", "step", "tags", "tag_suggestions")


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
        lock.on_lock(self._cache.clear)  # locked, it forgets what it read

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

    def iter_notes(self):
        """Every note, one file at a time, without holding the lock while a big transcript is read: (signature, note)."""
        for path in sorted(self.folder.glob("*.json")):
            try:
                stat = path.stat()
            except OSError:
                continue
            note = config.read_json_safe(path, default=None)
            if note and note.get("id"):
                yield (stat.st_mtime_ns, stat.st_size, stat.st_ino), note

    def all(self):
        """Every note, complete. Reads each file: for the listing and the queue, use slim()."""
        with self.lock:
            files = sorted(self.folder.glob("*.json"))
            notes = [config.read_json_safe(f, default=None) for f in files]
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
                sig = (stat.st_mtime_ns, stat.st_size, stat.st_ino)  # a note is rewritten as a new file: the inode tells a rewrite that left the size and a coarse timestamp unchanged
                seen.add(path)
                cached = self._cache.get(path)
                if not cached or cached[0] != sig:
                    note = config.read_json_safe(path, default=None)
                    row = {k: v for k, v in note.items() if k not in HEAVY} if note and note.get("id") else None
                    cached = self._cache[path] = (sig, row)
                if cached[1]:
                    rows.append(dict(cached[1]))
            for gone in set(self._cache) - seen:
                del self._cache[gone]
            return rows

    def signature(self):
        """A short value that changes whenever a note is written, added or removed (a cheap look at the files, nothing is read)."""
        digest = hashlib.sha1(usedforsecurity=False)
        with self.lock:
            for path in sorted(self.folder.glob("*.json")):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                digest.update(("%s:%d:%d:%d;" % (path.name, stat.st_mtime_ns, stat.st_size, stat.st_ino)).encode("utf-8"))
        return digest.hexdigest()

    # Recordings the person deleted on this computer only: they stay on the Pocket but are never imported again.

    def ignored_files(self):
        """{name: (size, mtime) or None}: the deleted recordings, and which file each one was when it was deleted."""
        out = {}
        try:
            lines = (self.folder / "ignored.txt").read_text(encoding="utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            name, _tab, rest = line.partition("\t")
            if not name:
                continue
            try:
                size, mtime = rest.split("\t")
                out[name] = (int(size), int(mtime))
            except ValueError:
                out[name] = None
        return out

    def ignored(self):
        return set(self.ignored_files())

    def is_ignored(self, rel, size, mtime):
        """Whether this file is a recording the person deleted. A name used again by another recording is not."""
        files = self.ignored_files()
        if rel not in files:
            return False
        return files[rel] is None or files[rel] == (size, mtime)

    def ignore(self, rel, on=True, size=None, mtime=None):
        with self.lock:
            items = self.ignored_files()
            if on:
                items[rel] = (size, mtime) if size is not None and mtime is not None else items.get(rel)
            else:
                items.pop(rel, None)
            fd, tmp = tempfile.mkstemp(dir=str(self.folder), prefix="ignored.", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(name + ("\t%d\t%d" % items[name] if items[name] else "") for name in sorted(items)))
            os.replace(tmp, self.folder / "ignored.txt")  # atomic: a crash cannot empty the list

    def tag_counts(self):
        return tags.counts(self.slim())

    def light(self):
        rows = []
        for n in self.slim():
            needs_score = n.get("fidelity") is None and n.get("fidelity_na") != score.VERSION
            if n.get("status") == "done" and (needs_score or "languages" not in n):
                n = self._backfill(n["id"]) or n  # notes made before these indicators existed: read once, then kept with the note
            row = {k: n.get(k) for k in LIGHT}
            row["done"] = row["status"] == "done"
            rows.append(row)
        return sorted(rows, key=lambda r: r.get("date") or "", reverse=True)

    def _backfill(self, note_id):
        """Compute what an older note lacks (fidelity, languages) and keep it with the note, so the listing
        never reads its transcript again. Returns the note without its transcript."""
        try:
            note = self.get(note_id)
        except KeyError:
            return None
        heard = note.get("heard")
        if note.get("fidelity") is None and note.get("fidelity_na") != score.VERSION:
            value, basis = score.fidelity_detail(note.get("summary"), note.get("clean"), words_ok=heard in (None, note.get("lang")))
            note["fidelity_basis"] = basis
            if value is None:
                note["fidelity_na"] = score.VERSION  # nothing to check with this method: not tried again until it changes
            else:
                note["fidelity"] = value
        if "languages" not in note:
            from . import speech

            note["languages"], note["mixed"] = speech.language_mix(note.get("segments"))
        self.save(note)
        return {k: v for k, v in note.items() if k not in HEAVY}

    def find_source(self, rel, size=None, mtime=None, light=False):
        """The note of the recording called rel. When size and date are given, the note of exactly that file comes first: a name
        can be used again by another recording. `light` gives the listing copy (no transcript): enough to compare, and quick."""
        same = [n for n in self.slim() if n.get("source") == rel]
        if size is not None:
            exact = [n for n in same if n.get("size") == size and n.get("mtime") == mtime]
            same = exact or same
        if not same:
            return None
        return same[0] if light else self.get(same[0]["id"])

    def sources(self, rel):
        """Every note made from a recording called rel."""
        return [self.get(n["id"]) for n in self.slim() if n.get("source") == rel]

    def reset_interrupted(self):
        """Recordings left in the middle of processing by a previous run go back to waiting."""
        for row in self.slim():
            if row.get("status") in ("transcribing", "diarizing", "cleaning", "summarizing"):
                note = self.get(row["id"])
                note["status"] = "waiting"
                note["step"] = ""
                self.save(note)
