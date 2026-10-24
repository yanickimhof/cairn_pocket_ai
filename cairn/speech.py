"""Transcription through the local speech engine, with a reliability estimate."""

import json
import math
import os
import subprocess
import sys
import tempfile

from . import config

DOUBTFUL_LOGPROB = -0.8
DOUBTFUL_COMPRESSION = 2.4


def transcribe(audio_path):
    """Run the speech engine on one file. Returns {language, segments, duration}."""
    cfg = config.install_config()
    engine, model_dir = cfg.get("engine"), cfg.get("whisper_model")
    if engine not in ("mlx", "faster"):
        raise RuntimeError("No speech engine configured. Run the installer again.")
    if not model_dir or not os.path.isdir(model_dir):
        raise RuntimeError("Speech model not found. Run the installer again.")
    with tempfile.TemporaryDirectory() as tmp:
        output = os.path.join(tmp, "out.json")
        env = dict(os.environ, HF_HUB_OFFLINE="1", DO_NOT_TRACK="1", PYTHONIOENCODING="utf-8")
        home_bin = str(config.home() / "bin")
        env["PATH"] = home_bin + os.pathsep + env.get("PATH", "")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        done = subprocess.run(
            [sys.executable, "-m", "cairn.speech_worker", engine, model_dir, str(audio_path), output],
            env=env, capture_output=True, text=True, creationflags=flags, check=False,
        )
        if done.returncode != 0 or not os.path.exists(output):
            tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
            raise RuntimeError("Transcription failed. " + " ".join(tail))
        with open(output, encoding="utf-8") as handle:
            data = json.load(handle)
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
