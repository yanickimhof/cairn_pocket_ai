"""Transcription through the local speech engine, with a reliability estimate."""

import json
import math
import os
import subprocess
import sys
import tempfile
import threading

from . import config

DOUBTFUL_LOGPROB = -0.8
DOUBTFUL_COMPRESSION = 2.4

IDLE_SECONDS = 300
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


def _run(engine, model_dir, audio, output, mark, progress):
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
        proc.stdin.write(json.dumps({"audio": audio, "output": output, "progress": mark}) + "\n")
        proc.stdin.flush()
    except OSError:
        pass
    while reader.is_alive():
        if progress:
            try:
                with open(mark, encoding="utf-8") as handle:
                    progress(int(100 * float(handle.read())))
            except (OSError, ValueError):
                pass
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


def transcribe(audio_path, progress=None):
    """Run the speech engine on one file. Returns {language, segments, duration}.

    progress, if given, is called with a number from 0 to 100 while the engine works.
    """
    cfg = config.install_config()
    engine, model_dir = cfg.get("engine"), cfg.get("whisper_model")
    if engine not in ("mlx", "faster"):
        raise RuntimeError("No speech engine configured. Run the installer again.")
    if not model_dir or not os.path.isdir(model_dir):
        raise RuntimeError("Speech model not found. Run the installer again.")
    with tempfile.TemporaryDirectory() as tmp:
        output = os.path.join(tmp, "out.json")
        mark = os.path.join(tmp, "progress")
        with _LOCK:
            data = _run(engine, model_dir, str(audio_path), output, mark, progress)
    segments = [s for s in data.get("segments", []) if s.get("text")]
    data["segments"] = segments
    data["duration"] = max((s["end"] for s in segments), default=0.0)
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
    return ["[%02d:%02d] %s" % (int(s["start"]) // 60, int(s["start"]) % 60, s["text"]) for s in segments]


def model_name():
    """A readable name for the speech model in use, for the note's footer."""
    from . import models

    chosen = models.selected_speech()
    for entry in models.speech_entries():
        if entry["id"] == chosen:
            return entry["label"]
    return "Whisper"
