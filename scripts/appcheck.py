"""End-to-end check of an installed Cairn, with the real speech engine and the real local model.

It simulates a Pocket (a temporary folder with one recording), starts the app the way a user does,
then drives it through its API: import, transcribe, summarize, export, rename, empty the Pocket, delete.

    python scripts/appcheck.py --audio speech.mp3 --expect launch,march
"""

import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def fail(message):
    print("FAIL:", message, flush=True)
    sys.exit(1)


class Client:
    def __init__(self, url):
        match = re.match(r"http://127\.0\.0\.1:(\d+)/\?k=(\S+)", url)
        self.port, self.token = int(match.group(1)), match.group(2)
        self.cookie = "cairn_session=" + self.token

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        headers = {"Cookie": self.cookie}
        if method == "POST":
            headers.update({"Content-Type": "application/json", "X-Cairn": "1"})
        conn.request(method, path, json.dumps(body or {}) if method == "POST" else None, headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8", "replace")
        conn.close()
        try:
            return response.status, json.loads(raw)
        except ValueError:
            return response.status, raw


def start_app(home, pocket):
    config = json.loads((home / "config.json").read_text(encoding="utf-8"))
    python = home / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    env = dict(
        os.environ, CAIRN_HOME=str(home), PYTHONPATH=config["app_dir"], CAIRN_POCKET_DIR=str(pocket),
        CAIRN_NO_BROWSER="1", CAIRN_PORT="8799", PYTHONUNBUFFERED="1", HF_HUB_OFFLINE="1", DO_NOT_TRACK="1",
    )
    env["PATH"] = str(home / "bin") + os.pathsep + env.get("PATH", "")
    process = subprocess.Popen([str(python), "-m", "cairn"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, found = [], []

    def pump():
        for line in process.stdout:
            lines.append(line)
            match = re.search(r"Open: (http://127\.0\.0\.1:\d+/\?k=\S+)", line)
            if match:
                found.append(match.group(1))

    threading.Thread(target=pump, daemon=True).start()
    for _ in range(120):
        if found:
            return process, found[0], lines
        if process.poll() is not None:
            fail("the app stopped at start: " + "".join(lines)[-500:])
        time.sleep(1)
    fail("the app did not print its address")


def stop(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, check=False)
    else:
        process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, help="a recording with speech")
    parser.add_argument("--expect", default="", help="comma separated words that must be heard")
    parser.add_argument("--home", default=os.environ.get("CAIRN_HOME") or str(Path.home() / "Cairn"))
    parser.add_argument("--timeout", type=int, default=1500)
    args = parser.parse_args()
    home = Path(args.home)
    for launcher in ("Cairn.command", "bin/cairn") if os.name != "nt" else ("Cairn.cmd",):
        if not (home / launcher).is_file():
            fail("launcher missing: %s" % launcher)

    work = Path(tempfile.mkdtemp(prefix="cairn-check-"))
    pocket = work / "RECORD"
    (pocket / "2026-10-08").mkdir(parents=True)
    shutil.copy(args.audio, pocket / "2026-10-08" / ("20261008_080600" + Path(args.audio).suffix))
    process, url, lines = start_app(home, pocket)
    try:
        client = Client(url)
        status, state = client.call("GET", "/api/state")
        if status != 200 or not state["pocket"]["connected"] or state["pocket"]["count"] != 1:
            fail("state: %s %s" % (status, state))
        if not state["ollama"]:
            fail("the local model server is not running")
        print("OK: app started, Pocket detected, model server up", flush=True)

        if client.call("POST", "/api/import")[0] != 202:
            fail("import was not accepted")
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            time.sleep(3)
            state = client.call("GET", "/api/state")[1]
            if not state["job"]["running"]:
                break
        else:
            fail("the import did not finish in time")
        if state["job"]["errors"]:
            fail("job errors: %s" % state["job"]["errors"])
        notes = state["notes"]
        if len(notes) != 1 or notes[0]["status"] != "done":
            fail("note not done: %s" % notes)
        note = client.call("GET", "/api/note/" + notes[0]["id"])[1]
        heard = " ".join(s["text"] for s in note["segments"]).lower()
        print("Heard:", heard, flush=True)
        print("Title:", note["title"], "| reliability:", note["quality"], "| passages:", note["passages"], flush=True)
        for word in [w.strip().lower() for w in args.expect.split(",") if w.strip()]:
            if word not in heard:
                fail("expected %r in the transcript" % word)
        if not isinstance(note.get("summary"), dict) or "tldr" not in note["summary"]:
            fail("no summary")
        print("OK: imported, transcribed, summarized locally", flush=True)

        for fmt, marker in (("md", "# "), ("html", "<!doctype html>"), ("text", "")):
            status, body = client.call("GET", "/api/note/%s/export?fmt=%s" % (note["id"], fmt))
            if status != 200 or marker not in body:
                fail("export %s" % fmt)
        if client.call("POST", "/api/note/%s/rename" % note["id"], {"title": "Check"})[0] != 200:
            fail("rename")
        if not any((home / "Audio").rglob("*" + Path(args.audio).suffix)):
            fail("the audio copy is missing")
        verify = client.call("GET", "/api/pocket/verify")[1]
        if (verify["total"], verify["verified"]) != (1, 1):
            fail("verify: %s" % verify)
        if client.call("POST", "/api/pocket/empty", {"confirm": True})[1].get("deleted") != 1:
            fail("empty the Pocket")
        if client.call("POST", "/api/note/%s/delete" % note["id"])[0] != 200:
            fail("delete")
        print("OK: export, rename, verified copy, emptied the simulated Pocket, delete", flush=True)
    finally:
        stop(process)
        shutil.rmtree(work, ignore_errors=True)
    print("App check passed.")


if __name__ == "__main__":
    main()
