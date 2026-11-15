"""Cairn self test: one short audio file through the speech engine, one question to the local model.

Everything runs locally. Reads its settings from environment variables set by the installer.
"""
import json
import math
import os
import re
import socket
import struct
import sys
import tempfile
import urllib.request
import wave

ENGINE = os.environ.get("CAIRN_ENGINE", "")
MODEL_DIR = os.environ.get("CAIRN_WHISPER_MODEL", "")
LLM = os.environ.get("CAIRN_LLM", "qwen3:4b")
HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
# a slow first answer is a warning on a computer (another model may hold the memory), a failure in the automatic tests
LLM_TIMEOUT = int(os.environ.get("CAIRN_SELFTEST_TIMEOUT", "300" if os.environ.get("CI") else "150"))


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


def unload_others():
    """Another model kept in memory by the model server (a larger Qwen3, for instance) can make the first answer very slow
    on a small Mac: ask the server to let it go. It is loaded again when Cairn needs it."""
    try:
        with urllib.request.urlopen("http://%s/api/ps" % HOST, timeout=10) as response:  # nosec B310
            running = json.load(response).get("models") or []
        for item in running:
            name = item.get("name") or item.get("model")
            if name and name != LLM:
                body = json.dumps({"model": name, "keep_alive": 0}).encode()
                request = urllib.request.Request("http://%s/api/generate" % HOST, data=body, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(request, timeout=30).read()  # nosec B310
                print("Freed memory: %s was unloaded (it loads again when Cairn needs it)" % name)
    except Exception:  # nosec B110 (best effort: the test goes on without it)
        pass


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
    unload_others()
    # The address is validated above: loopback only, plain http, fixed scheme.
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:  # nosec B310
            data = json.load(response)
    except (TimeoutError, socket.timeout):
        if os.environ.get("CI"):
            fail("the language model did not answer in %d seconds" % LLM_TIMEOUT)
        print("WARNING: the language model (%s) did not answer in %d seconds." % (LLM, LLM_TIMEOUT))
        print("Another model may be holding the memory: run `ollama ps`, then `ollama stop <name>`, and open Cairn again.")
        return False
    if "response" not in data:
        fail("unexpected answer from the model server")
    print("OK: language model (%s) answered locally" % LLM)
    return True


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.wav")
        make_wav(path)
        test_speech(path)
    if test_llm():
        print("Self test passed.")
    else:
        print("Self test: the speech engine works, the language model was too slow to answer (see above). The installation goes on.")


if __name__ == "__main__":
    main()
