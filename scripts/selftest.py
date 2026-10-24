"""Cairn self test: one short audio file through the speech engine, one question to the local model.

Everything runs locally. Reads its settings from environment variables set by the installer.
"""
import json
import math
import os
import re
import struct
import sys
import tempfile
import urllib.request
import wave

ENGINE = os.environ.get("CAIRN_ENGINE", "")
MODEL_DIR = os.environ.get("CAIRN_WHISPER_MODEL", "")
LLM = os.environ.get("CAIRN_LLM", "qwen3:4b")
HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")


def fail(message):
    print("FAIL:", message)
    sys.exit(1)


def make_wav(path, seconds=2, rate=16000):
    """A short mono 16 kHz tone, the same format as the Pocket recordings."""
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * n / rate)))
        for n in range(seconds * rate)
    )
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def test_speech(path):
    if not MODEL_DIR or not os.path.isdir(MODEL_DIR):
        fail("speech model folder not found: %r" % MODEL_DIR)
    if ENGINE == "mlx":
        import mlx_whisper

        mlx_whisper.transcribe(path, path_or_hf_repo=MODEL_DIR)
    elif ENGINE == "faster":
        from faster_whisper import WhisperModel

        model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(path)
        list(segments)
    else:
        fail("unknown speech engine: %r" % ENGINE)
    print("OK: speech engine (%s) ran on a test file" % ENGINE)


def test_llm():
    if not re.fullmatch(r"127\.0\.0\.1:\d{2,5}", HOST):
        fail("the model server must listen on 127.0.0.1, found %r" % HOST)
    body = json.dumps(
        {
            "model": LLM,
            "prompt": "Reply with the single word OK.",
            "stream": False,
            "options": {"temperature": 0, "num_predict": 64},
        }
    ).encode()
    request = urllib.request.Request(
        "http://%s/api/generate" % HOST, data=body, headers={"Content-Type": "application/json"}
    )
    # The address is validated above: loopback only, plain http, fixed scheme.
    with urllib.request.urlopen(request, timeout=300) as response:  # nosec B310
        data = json.load(response)
    if "response" not in data:
        fail("unexpected answer from the model server")
    print("OK: language model (%s) answered locally" % LLM)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.wav")
        make_wav(path)
        test_speech(path)
    test_llm()
    print("Self test passed.")


if __name__ == "__main__":
    main()
