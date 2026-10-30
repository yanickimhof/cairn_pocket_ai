"""End-to-end check of an installed Cairn, with the real speech engine and the real local model.

It simulates a Pocket (a temporary folder with one recording), starts the app the way a user does,
then drives it through its API: import, transcribe, summarize, export, rename, delete everywhere.

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
        out = client.call("POST", "/api/note/%s/delete" % note["id"])
        if out[0] != 200 or out[1].get("pocket") is not True:
            fail("delete")
        if list(pocket.rglob("*" + Path(args.audio).suffix)):
            fail("the recording is still on the simulated Pocket")
        if any((home / "Audio").rglob("*" + Path(args.audio).suffix)):
            fail("the audio copy is still on the computer")
        print("OK: export, rename, delete everywhere (simulated Pocket and computer)", flush=True)

        # The Pocket vault: secure the simulated Pocket, check nothing readable is left, lock it, unlock it, delete from it
        suffix = Path(args.audio).suffix
        (pocket / "2026-10-09").mkdir(parents=True, exist_ok=True)
        shutil.copy(args.audio, pocket / "2026-10-09" / ("20261009_090000" + suffix))
        state = client.call("GET", "/api/state?list=0")[1]
        if state["pocket"].get("vault", {}).get("available") is not True:
            fail("the encryption library is not available: %s" % state["pocket"].get("vault"))
        password = "check-password-for-the-vault"
        if client.call("POST", "/api/vault/create", {"password": "short"})[0] != 400:
            fail("a short password must be refused")
        if client.call("POST", "/api/vault/create", {"password": password, "trust": False})[0] != 202:
            fail("the vault was not created")
        for _ in range(120):
            time.sleep(2)
            state = client.call("GET", "/api/state?list=0")[1]
            # another job may hold the engine for a moment: the request is kept and done as soon as it is free
            if not state["job"]["running"] and (state["pocket"]["vault"]["state"] == "secured" or state["job"]["errors"]):
                break
        if state["job"]["errors"]:
            fail("securing failed: %s" % state["job"]["errors"])
        vault = state["pocket"]["vault"]
        if (vault["state"], vault["plain"], vault["sealed"]) != ("secured", 0, 1):
            listing = sorted(str(x.relative_to(pocket)) for x in pocket.rglob("*"))
            fail("the Pocket is not secured: %s | job: %s | pocket: %s" % (vault, state["job"], listing))
        if list(pocket.rglob("*" + suffix)):
            fail("a readable recording is still on the Pocket")
        if len(list(pocket.glob("*.cairn"))) != 1 or not (pocket / ".cairn-vault").is_file():
            fail("the encrypted file or the vault header is missing")
        if args.audio and Path(args.audio).read_bytes()[:64] in b"".join(p.read_bytes() for p in pocket.glob("*.cairn")):
            fail("the recording can be read in the encrypted file")
        if client.call("POST", "/api/vault/forget")[0] != 200:
            fail("forget")
        if client.call("GET", "/api/state?list=0")[1]["pocket"]["vault"]["state"] != "locked":
            fail("the Pocket must be locked once the key is forgotten")
        if client.call("POST", "/api/vault/unlock", {"password": "the wrong password"})[0] != 403:
            fail("a wrong password must be refused")
        if client.call("POST", "/api/vault/unlock", {"password": password, "trust": False})[0] != 202:
            fail("the right password was refused")
        for _ in range(120):
            time.sleep(2)
            state = client.call("GET", "/api/state?list=0")[1]
            # another job may hold the engine for a moment: the request is kept and done as soon as it is free
            if not state["job"]["running"] and (state["pocket"]["vault"]["state"] == "secured" or state["job"]["errors"]):
                break
        if state["pocket"]["vault"]["state"] != "secured" or state["job"]["errors"]:
            fail("unlock: %s %s" % (state["pocket"]["vault"], state["job"]["errors"]))
        notes = client.call("GET", "/api/state")[1]["notes"]
        if len(notes) != 1:
            fail("the recording must have come in from the encrypted Pocket: %s" % notes)
        out = client.call("POST", "/api/note/%s/delete" % notes[0]["id"])
        if out[0] != 200 or out[1].get("pocket") is not True or list(pocket.glob("*.cairn")):
            fail("deleting must erase the encrypted file from the Pocket")
        print("OK: Pocket vault (secured, locked, unlocked, read, deleted)", flush=True)

        if client.call("POST", "/api/privacy/check")[0] != 202:
            fail("the privacy check was not accepted")
        for _ in range(120):
            time.sleep(2)
            if not client.call("GET", "/api/state")[1]["job"]["running"]:
                break
        report = client.call("GET", "/api/privacy")[1]["report"] or {}
        print("Privacy check:", json.dumps(report), flush=True)
        if report.get("external") or report.get("blocked"):
            fail("outgoing connections detected: %s %s" % (report.get("external"), report.get("blocked")))
        if report.get("leftover"):
            print("Note: connections already open before the test (earlier download):", report["leftover"], flush=True)
        if report.get("errors"):
            fail("the privacy check could not exercise the engines: %s" % report["errors"])
        if not report.get("model_server_seen"):
            fail("the privacy check did not see the local model server")
        print("OK: no connection leaves this computer (Cairn, speech engine, model server)", flush=True)
    finally:
        stop(process)
        shutil.rmtree(work, ignore_errors=True)
    print("App check passed.")


if __name__ == "__main__":
    main()
