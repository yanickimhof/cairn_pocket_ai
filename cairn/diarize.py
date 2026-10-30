"""Speaker diarization: who spoke when, from the local pyannote model. Off by default, and only used once
the model has been installed (Settings > Models) and the feature turned on (the toggle next to the
Hugging Face token in Settings).

Runs fully offline once installed: inference reads only the model cached inside Cairn's own folder
(HF_HUB_OFFLINE is set), nothing is sent anywhere. A failure here never fails the recording: the note is
simply written without speaker labels, same as before this feature existed.
"""

import json
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

from . import config, models

TIMEOUT = 1800  # a long recording can take a while the first time the model loads


def timeout_for(duration):
    """Seconds a pass may take: three times the recording plus five minutes, never under fifteen minutes."""
    return max(900, int(3 * (duration or 0)) + 300)


def available():
    return models.diar_installed()


_ACTIVE = set()
def abort():
    """Stop every speaker pass in progress, right now."""
    for proc in list(_ACTIVE):
        try:
            proc.kill()
        except OSError:
            pass


def run(audio_path, timeout=TIMEOUT):
    """One diarization pass: ("ok", [turns]), ("missing", None) if not installed/importable, else ("none", None).
    Each turn is {"start": float, "end": float, "speaker": "SPEAKER_00"}."""
    state, payload = _exec(audio_path, timeout, False)
    return state, (payload["turns"] if state == "ok" else None)


def run_with_voices(audio_path, timeout=TIMEOUT):
    """The same pass, with the voiceprint of every speaker: ("ok", turns, {"SPEAKER_00": [floats]}), else (state, None, {})."""
    state, payload = _exec(audio_path, timeout, True)
    return (state, payload["turns"], payload["voices"]) if state == "ok" else (state, None, {})


def _exec(audio_path, timeout, voices):
    if not available():
        return "missing", None
    device = config.load_settings().get("diarize_device", "auto")
    env = dict(os.environ, CAIRN_DIARIZE_DEVICE=device if device in ("auto", "cpu") else "auto", CAIRN_VOICES="1" if voices else "0")
    try:
        proc = subprocess.Popen(  # nosec B603
            [sys.executable, "-m", "cairn.diarize_worker", str(audio_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(Path(__file__).resolve().parent.parent), env=env,
        )
    except OSError:
        return "none", None
    _ACTIVE.add(proc)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            print("diarize: no result (took more than %d minutes)" % (timeout // 60), file=sys.stderr, flush=True)
            return "none", None
        except (OSError, subprocess.SubprocessError):
            return "none", None
    finally:
        _ACTIVE.discard(proc)
    if proc.returncode == 3:
        return "missing", None
    if proc.returncode == 0 and (out or "").strip():
        try:
            data = json.loads(out.strip())
        except ValueError:
            return "none", None
        if isinstance(data, list):
            return "ok", {"turns": data, "voices": {}}
        if isinstance(data, dict) and isinstance(data.get("turns"), list):
            prints = data.get("voices") if isinstance(data.get("voices"), dict) else {}
            return "ok", {"turns": data["turns"], "voices": prints}
        return "none", None
    detail = (err or "").strip().splitlines()[-1:] or ["exit %d" % proc.returncode]
    print("diarize: no result (%s)" % detail[0][:160], file=sys.stderr, flush=True)
    return "none", None


def label(index, lang):
    names = {"fr": "Interlocuteur %d", "en": "Speaker %d"}
    return (names.get(lang) or names["en"]) % (index + 1)


def _order(segments, turns):
    """The raw labels of the turns in the order the speakers first speak."""
    order = []
    for segment in segments:
        mid = (float(segment.get("start", 0)) + float(segment.get("end", 0))) / 2
        turn = next((t for t in turns if t["start"] <= mid < t["end"]), None)
        if turn is not None and turn["speaker"] not in order:
            order.append(turn["speaker"])
    return order


def label_voices(segments, turns, prints, lang):
    """The voiceprints under the readable labels that assign() gave the speakers: {"Speaker 1": [floats]}."""
    return {label(i, lang): prints[raw] for i, raw in enumerate(_order(segments, turns)) if raw in (prints or {})}


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
