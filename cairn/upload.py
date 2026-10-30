"""Audio files added by hand: any recording the person drops on Cairn becomes a note, with or without a Pocket.

The file is received as a stream (never held whole in memory), written under a temporary name, hashed on the way and
checked before it takes its place in the audio folder. Nothing in the name, the size or the type is taken on trust."""
import hashlib
import os
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

from . import config, pocket
from .notes import guess_date, make_id

MAX_BYTES = 4 << 30  # four hours of lossless audio fit well below this
CHUNK = 1 << 20
FOLDER = "Imported"
_RESERVED = frozenset("con prn aux nul com1 com2 com3 com4 com5 com6 com7 com8 com9 lpt1 lpt2 lpt3 lpt4 lpt5 lpt6 lpt7 lpt8 lpt9".split())
# the first bytes of each kind of file Cairn reads: a file that is not audio is refused whatever its name says
MAGIC = {
    ".wav": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WAVE",
    ".mp3": lambda h: h[:3] == b"ID3" or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0),
    ".m4a": lambda h: h[4:8] == b"ftyp",
    ".ogg": lambda h: h[:4] == b"OggS",
    ".opus": lambda h: h[:4] == b"OggS",
    ".flac": lambda h: h[:4] == b"fLaC",
}


class Rejected(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def safe_name(raw):
    """An ordinary file name that stays inside the audio folder on every system, or '' when there is none."""
    name = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|]+", "_", str(raw or "")).strip(" .")
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or "." + ext.lower() not in config.AUDIO_EXT:
        return ""
    if stem.strip(" .").lower() in _RESERVED:
        stem = "_" + stem
    return (stem.strip(" .")[:120] or "recording") + "." + ext.lower()


def received_at(modified_ms):
    """When the recording was made, as far as its file tells: the date in its name, else its last change."""
    try:
        seconds = int(modified_ms) / 1000.0
        if not 0 < seconds < time.time() + 86400:
            raise ValueError
    except (TypeError, ValueError):
        seconds = time.time()
    return seconds


def receive(store, rfile, length, filename, modified_ms, audio_dir):
    """Store one audio file and make its note (waiting for the transcription). Returns (note, duplicate)."""
    name = safe_name(filename)
    if not name:
        raise Rejected(415, "bad_type")
    if length <= 0:
        raise Rejected(400, "empty")
    if length > MAX_BYTES:
        raise Rejected(413, "too_large")
    folder = Path(audio_dir) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / (".upload-%s.part" % secrets.token_hex(6))
    digest, left, head = hashlib.sha256(), length, b""
    try:
        with open(part, "wb") as out:
            while left > 0:
                chunk = rfile.read(min(CHUNK, left))
                if not chunk:
                    raise Rejected(400, "incomplete")
                if len(head) < 16:
                    head = (head + chunk)[:16]
                out.write(chunk)
                digest.update(chunk)
                left -= len(chunk)
        suffix = Path(name).suffix.lower()
        if not MAGIC[suffix](head):
            raise Rejected(415, "not_audio")
        sha = digest.hexdigest()
        for known in store.slim():
            if known.get("sha256") == sha:
                return known, True  # the same recording is already here: it is not added twice
        target = folder / name
        if target.exists():
            target = folder / ("%s-%s%s" % (target.stem, sha[:8], target.suffix))
        os.replace(part, target)
    finally:
        if part.exists():
            part.unlink()
    seconds = received_at(modified_ms)
    note = {
        "id": make_id("file-" + sha), "origin": "file", "file_name": name, "status": "waiting", "title": "", "level": None,
        "audio": str(target), "sha256": sha, "size": length, "mtime": int(seconds),
        "date": guess_date(target, seconds), "duration": pocket.estimate_duration(target),
    }
    store.save(note)
    return note, False
