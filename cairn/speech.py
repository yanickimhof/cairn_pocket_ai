"""Transcription through the local speech engine, with a reliability estimate."""

import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

from . import config

DOUBTFUL_LOGPROB = -0.8
DOUBTFUL_COMPRESSION = 2.4

IDLE_SECONDS = 300
KEEP_MIN_GB = 24  # the speech engine stays loaded between recordings only on a computer with this much memory
STALL_SECONDS = 300      # no progress at all for this long: the speech engine is taken for stuck
NO_PROGRESS_CAP = 3600   # an engine that never reports progress gets this long in all
_LOCK = threading.Lock()
_WORKER = {"proc": None, "key": None, "timer": None, "lines": None}


def _stop_worker():
    proc = _WORKER["proc"]
    _WORKER["proc"] = None
    if _WORKER["timer"]:
        _WORKER["timer"].cancel()
        _WORKER["timer"] = None
    if proc and proc.poll() is None:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def _idle_stop():
    with _LOCK:
        _stop_worker()  # frees the model memory after a quiet period


def _worker(engine, model_dir):
    """The long-lived speech process; the model stays loaded between recordings."""
    key = (engine, model_dir)
    proc = _WORKER["proc"]
    if proc and proc.poll() is None and _WORKER["key"] == key:
        return proc
    _stop_worker()
    env = dict(os.environ, HF_HUB_OFFLINE="1", DO_NOT_TRACK="1", PYTHONIOENCODING="utf-8")
    env["PATH"] = str(config.home() / "bin") + os.pathsep + env.get("PATH", "")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(  # nosec B603
        [sys.executable, "-m", "cairn.speech_worker", "--serve", engine, model_dir],
        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", bufsize=1, creationflags=flags,
    )
    _WORKER.update(proc=proc, key=key, lines=[])
    return proc


def _read_mark(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return float(handle.read())
    except (OSError, ValueError):
        return None


def _run(engine, model_dir, audio, output, mark, progress, language=None):
    proc = _worker(engine, model_dir)
    if _WORKER["timer"]:
        _WORKER["timer"].cancel()
    replies, chatter = [], []

    def read():
        for line in proc.stdout:
            if line.startswith("@@CAIRN "):
                replies.append(line[8:].strip())
                return
            chatter.append(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        proc.stdin.write(json.dumps({"audio": audio, "output": output, "progress": mark, "language": language}) + "\n")
        proc.stdin.flush()
    except OSError:
        pass
    began = last_move = time.time()
    last_value = None
    while reader.is_alive():
        value = _read_mark(mark)
        if value is not None:
            if progress:
                progress(int(100 * value))
            if value != last_value:
                last_value, last_move = value, time.time()
        now = time.time()
        if (last_value is not None and now - last_move > STALL_SECONDS) or (last_value is None and now - began > NO_PROGRESS_CAP):
            _stop_worker()
            raise RuntimeError("Transcription stopped: the speech engine did not answer for %d minutes." % ((now - last_move) // 60))
        reader.join(timeout=0.4)
    if not replies or replies[0] != "ok" or not os.path.exists(output):
        reason = replies[0] if replies else " ".join("".join(chatter).strip().splitlines()[-3:])
        _stop_worker()
        raise RuntimeError("Transcription failed. " + reason)
    with open(output, encoding="utf-8") as handle:
        data = json.load(handle)
    _WORKER["timer"] = threading.Timer(IDLE_SECONDS, _idle_stop)
    _WORKER["timer"].daemon = True
    _WORKER["timer"].start()
    return data


def abort():
    """Kill the speech process right now (a transcription in progress then fails and is stopped)."""
    proc = _WORKER["proc"]
    if proc and proc.poll() is None:
        proc.kill()


def shutdown():
    with _LOCK:
        _stop_worker()


def transcribe(audio_path, progress=None, language=None, engine=None, model_dir=None):
    """Run the speech engine on one file. Returns {language, segments, duration}.

    progress, if given, is called with a number from 0 to 100 while the engine works.
    language ("fr", "en") forces the language of the recording; None lets the engine detect it, once, from the start.
    """
    cfg = config.install_config()
    engine, model_dir = engine or cfg.get("speech_engine") or cfg.get("engine"), model_dir or cfg.get("whisper_model")
    if engine not in ("mlx", "faster", "parakeet"):
        raise RuntimeError("No speech engine configured. Run the installer again.")
    if not model_dir or not os.path.isdir(model_dir):
        raise RuntimeError("Speech model not found. Run the installer again.")
    with tempfile.TemporaryDirectory() as tmp:
        output = os.path.join(tmp, "out.json")
        mark = os.path.join(tmp, "progress")
        with _LOCK:
            data = _run(engine, model_dir, str(audio_path), output, mark, progress, language)
    segments = [s for s in data.get("segments", []) if s.get("text")]
    data["segments"] = segments
    data["duration"] = max((s["end"] for s in segments), default=0.0)
    if not data.get("language"):  # an engine that does not say which language it heard: the words say it
        shares, _ = language_mix(segments)
        data["language"] = max(shares, key=shares.get) if shares else None
    return data


def assess(segments):
    """Reliability (0 to 100, or None) and the passages worth checking.

    The estimate comes from the speech engine's own confidence: duration weighted
    mean of exp(avg log probability). It is a guide, not a measurement of accuracy.
    """
    total, weighted, doubtful = 0.0, 0.0, []
    for s in segments:
        length = max(float(s["end"]) - float(s["start"]), 0.01)
        confidence = max(0.0, min(1.0, math.exp(min(float(s.get("logprob", -1.0)), 0.0))))
        total += length
        weighted += confidence * length
        weak = float(s.get("logprob", -1.0)) < DOUBTFUL_LOGPROB
        weak = weak or float(s.get("compression", 1.0)) > DOUBTFUL_COMPRESSION
        weak = weak or float(s.get("no_speech", 0.0)) > 0.6
        if weak:
            doubtful.append({"start": float(s["start"]), "text": s["text"]})
    quality = round(100 * weighted / total) if total else None
    return quality, doubtful


def raw_lines(segments):
    return [
        "[%02d:%02d] %s%s" % (int(s["start"]) // 60, int(s["start"]) % 60, (s["speaker"] + ": ") if s.get("speaker") else "", s["text"])
        for s in segments
    ]


def model_key():
    """What identifies the speech model in use, for telling whether a transcript was made with it."""
    from . import models

    cfg = config.install_config()
    return "%s:%s" % (cfg.get("speech_engine") or cfg.get("engine"), models.selected_speech() or cfg.get("whisper_repo") or "")


def model_name():
    """A readable name for the speech model in use, for the note's footer."""
    from . import models

    chosen = models.selected_speech()
    for entry in models.speech_entries():
        if entry["id"] == chosen:
            return entry["label"]
    return "Whisper"


_FR = frozenset("le la les des une est que qui dans pour pas nous vous je il elle ce cette sur avec du au aux mais ou donc très ça et être avoir fait c est j ai qu".split())
_EN = frozenset("the and is are that this with for you we it of to in have not be was they what there but will would about so just like can do i my your".split())
_WORDS = re.compile(r"[a-zà-ÿ]+")
MIX_SHARE = 0.15  # the other language holds at least this share of the recognised speech
MIX_MIN_SEGMENTS = 3


def language_mix(segments):
    """Which of French and English the segments are written in: ({"fr": share, "en": share}, mixed).

    The engine detects one language for the whole file, so a passage in the other language comes out
    garbled or translated. Counting everyday words per segment shows when a recording holds two languages.
    Nothing is reported for a recording too short, or in a language this check does not know."""
    weight, count = {"fr": 0.0, "en": 0.0}, {"fr": 0, "en": 0}
    for s in segments or []:
        words = _WORDS.findall(str(s.get("text", "")).lower())
        fr, en = sum(w in _FR for w in words), sum(w in _EN for w in words)
        kind = "fr" if fr >= 2 and fr > 1.5 * en else "en" if en >= 2 and en > 1.5 * fr else None
        if kind:
            weight[kind] += max(float(s.get("end", 0)) - float(s.get("start", 0)), 0.01)
            count[kind] += 1
    total = weight["fr"] + weight["en"]
    if total < 30:
        return {}, False
    shares = {k: round(weight[k] / total, 2) for k in weight}
    minor = min(weight, key=weight.get)
    return shares, shares[minor] >= MIX_SHARE and count[minor] >= MIX_MIN_SEGMENTS
