"""Speaker diarization: who spoke when, from the local pyannote model. Off by default, and only used once
the model has been installed (Settings > Models) and the feature turned on (the toggle next to the
Hugging Face token in Settings).

Runs fully offline once installed: inference reads only the model cached inside Cairn's own folder
(HF_HUB_OFFLINE is set), nothing is sent anywhere. A failure here never fails the recording: the note is
simply written without speaker labels, same as before this feature existed.
"""

import json
import subprocess  # nosec B404
import sys
from pathlib import Path

from . import models

TIMEOUT = 1800  # a long recording can take a while the first time the model loads


def available():
    return models.diar_installed()


def run(audio_path, timeout=TIMEOUT):
    """One diarization pass: ("ok", [turns]), ("missing", None) if not installed/importable, else ("none", None).
    Each turn is {"start": float, "end": float, "speaker": "SPEAKER_00"}."""
    if not available():
        return "missing", None
    try:
        done = subprocess.run(  # nosec B603
            [sys.executable, "-m", "cairn.diarize_worker", str(audio_path)], capture_output=True, text=True,
            timeout=timeout, cwd=str(Path(__file__).resolve().parent.parent), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "none", None
    if done.returncode == 3:
        return "missing", None
    if done.returncode == 0 and done.stdout.strip():
        try:
            return "ok", json.loads(done.stdout.strip())
        except ValueError:
            return "none", None
    detail = (done.stderr or "").strip().splitlines()[-1:] or ["exit %d" % done.returncode]
    print("diarize: no result (%s)" % detail[0][:160], file=sys.stderr, flush=True)
    return "none", None


def label(index, lang):
    names = {"fr": "Interlocuteur %d", "en": "Speaker %d"}
    return (names.get(lang) or names["en"]) % (index + 1)


def assign(segments, turns, lang):
    """Adds a readable "speaker" field to each segment, from the turn whose interval covers its midpoint.
    Speakers are numbered in the order they first speak, not by pyannote's own internal label. Any label
    left over from an earlier pass is cleared first, so a segment that no longer matches a turn stays unlabeled
    rather than keeping a stale speaker."""
    for segment in segments:
        segment.pop("speaker", None)
    if not turns:
        return segments
    order = []
    for segment in segments:
        mid = (float(segment.get("start", 0)) + float(segment.get("end", 0))) / 2
        turn = next((t for t in turns if t["start"] <= mid < t["end"]), None)
        if turn is None:
            continue
        raw = turn["speaker"]
        if raw not in order:
            order.append(raw)
        segment["speaker"] = label(order.index(raw), lang)
    return segments


def renamed(segments, names):
    """Segments with each one's speaker label swapped for its custom name, where the person set one.
    Leaves the segments themselves untouched: the note keeps the generated label (e.g. "Speaker 1") as the
    stable key, and only this rendered copy carries the name chosen for it."""
    if not names:
        return segments
    return [dict(s, speaker=names[s["speaker"]]) if s.get("speaker") in names else s for s in segments]
