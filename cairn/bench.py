"""Test bench: how fast, how heavy and how different the installed speech models are, on recordings of your own.

    cairn bench [AUDIO ...] [--max 3]

With no file, it takes up to three of your most recent recordings (not when the lock is on: they are sealed, so give files). Each
installed speech model transcribes each file in turn, after a warm-up so that loading the model is not counted. A file with a text
beside it (talk.m4a and talk.m4a.ref.txt) is also scored against that text. The report holds numbers only, never a word of a
recording, and is written to ~/Cairn/Exports. Everything runs on this computer."""
import contextlib
import datetime
import difflib
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from . import config, lock, models, speech

_WORDS = re.compile(r"[\w']+", re.UNICODE)


def words(text):
    return _WORDS.findall(str(text).lower())


def difference(reference, other):
    """Share of words that differ between two texts (substitutions, insertions and deletions counted from a longest-match alignment).
    An estimate of the word error rate, a little high where the best alignment is not the one found; 0 = identical."""
    a, b = words(reference), words(other)
    if not a:
        return None
    matched = sum(block.size for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(max(len(a), len(b)) - matched, 0) / len(a)


def _rss_mb(pid):
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5, check=False).stdout.strip()  # nosec B603
        return int(out) / 1024.0 if out else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class Peak(threading.Thread):
    """Samples the memory of the speech process while it works."""

    def __init__(self):
        super().__init__(daemon=True)
        self.mb, self.stop_flag = 0.0, threading.Event()

    def run(self):
        while not self.stop_flag.is_set():
            proc = speech._WORKER.get("proc")
            if proc is not None and proc.poll() is None:
                self.mb = max(self.mb, _rss_mb(proc.pid) or 0.0)
            self.stop_flag.wait(0.5)


def _silence(path, seconds=1):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(struct.pack("<h", 0) * 16000 * seconds)


def installed_models():
    """(label, engine, model_dir) for every speech model that is installed."""
    cfg = config.install_config()
    found = []
    for entry in models.speech_entries():
        folder = models.speech_dir(entry["id"])
        if (folder / models.MARK).exists():
            found.append((entry["label"], entry.get("engine") or cfg.get("engine"), str(folder)))
    if not found and Path(cfg["whisper_model"]).is_dir():
        found.append(("Whisper", cfg.get("engine"), cfg["whisper_model"]))
    return found


def measure(label, engine, model_dir, audio, language=None):
    """One model on one file: seconds, speed, memory, confidence, and the text kept for comparison only."""
    with tempfile.TemporaryDirectory(dir=lock.tmpdir()) as tmp:
        warm = Path(tmp) / "warm.wav"
        _silence(warm)
        with contextlib.suppress(Exception):
            speech.transcribe(str(warm), engine=engine, model_dir=model_dir)  # loading the model is not part of the measure
    peak = Peak()
    peak.start()
    began = time.time()
    try:
        result = speech.transcribe(str(audio), engine=engine, model_dir=model_dir, language=language)
    finally:
        wall = time.time() - began
        peak.stop_flag.set()
        speech.shutdown()
    quality, _ = speech.assess(result["segments"])
    shares, mixed = speech.language_mix(result["segments"])
    text = " ".join(s["text"] for s in result["segments"])
    audio_seconds = result.get("duration") or 0.0
    return {"label": label, "seconds": round(wall, 1), "audio": round(audio_seconds, 1), "speed": round(audio_seconds / wall, 1) if wall else None,
            "memory_mb": round(peak.mb) if peak.mb else None, "quality": quality, "words": len(words(text)), "languages": shares, "mixed": mixed, "text": text}


def recordings(limit):
    if lock.enabled():
        raise SystemExit("The lock is on, so the recordings are sealed: give the audio files to measure on the command line.")
    found = sorted(lock.audio_files(), key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:limit]


def report(rows, when=None):
    """The report, in Markdown: numbers only."""
    when = when or datetime.datetime.now()
    lines = ["# Cairn test bench", "", "%s · Cairn %s · %s" % (when.strftime("%Y-%m-%d %H:%M"), config.VERSION, sys.platform), "",
             "Numbers only: no recording and no word of one is in this report.", ""]
    by_file = {}
    for row in rows:
        by_file.setdefault(row["file"], []).append(row)
    for name, items in by_file.items():
        lines += ["## %s" % name, "", "| Model | Time (s) | Speed (x real time) | Memory (MB) | Confidence | Words | fr / en | Difference vs reference |", "|---|---|---|---|---|---|---|---|"]
        for r in items:
            shares = r["languages"] or {}
            spoken = " / ".join("%d%%" % round(100 * shares.get(k, 0)) for k in ("fr", "en")) if shares else "-"
            ref = "-" if r.get("reference") is None else "%.1f%%" % (100 * r["reference"])
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (r["label"], r["seconds"], r["speed"], r["memory_mb"] or "-", ("%s%%" % r["quality"]) if r["quality"] is not None else "-", r["words"], spoken, ref))
        if len(items) > 1:
            lines += ["", "Difference between models (share of words that differ, a guide to where they disagree, not a measure of accuracy):", ""]
            for i, a in enumerate(items):
                for b in items[i + 1:]:
                    d = difference(a["text"], b["text"])
                    lines.append("- %s and %s: %s" % (a["label"], b["label"], "-" if d is None else "%.1f%%" % (100 * d)))
        lines.append("")
    lines += ["Reading it: speed is audio length divided by processing time; confidence is each model's own and is not comparable between models;",
              "a recording that mixes two languages shows in the fr / en split, and a model that drops one of them shows there too.", ""]
    return "\n".join(lines)


def run(paths=None, limit=3, out=None):
    files = [Path(p) for p in paths] if paths else recordings(limit)
    if not files:
        raise SystemExit("No recording to measure: give audio files, or record something first.")
    candidates = installed_models()
    if not candidates:
        raise SystemExit("No speech model is installed.")
    rows = []
    for audio in files:
        ref = Path(str(audio) + ".ref.txt")
        reference = ref.read_text(encoding="utf-8") if ref.is_file() else None
        for label, engine, model_dir in candidates:
            print("%s on %s ..." % (label, audio.name), flush=True)
            with lock.plain(audio) as plain:
                row = measure(label, engine, model_dir, plain)
            row["file"] = audio.name
            row["reference"] = difference(reference, row["text"]) if reference else None
            rows.append(row)
    text = report(rows)
    out = Path(out) if out else config.home() / "Exports" / ("bench-%s.md" % datetime.datetime.now().strftime("%Y-%m-%d-%H%M"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print("Written to %s" % out)
    return out
