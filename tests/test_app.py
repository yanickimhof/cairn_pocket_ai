"""End-to-end tests of the Cairn app with a stub speech engine and a stub model server.

No network, no model: run with `python -m unittest discover -s tests`.
"""

import http.client
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SUMMARY = {
    "template": "meeting", "title": "Project check-in", "tldr": "The launch moves to March.",
    "actions": [{"what": "Send the plan", "who": "Anna", "when": "Friday"}],
    "context": "Weekly sync.", "key_points": ["Budget approved"], "decisions": ["Launch in March"],
    "topics": [{"name": "Launch", "summary": "Moved by two weeks."}],
}


class StubModel(BaseHTTPRequestHandler):
    calls = []
    pulled = []

    def log_message(self, *args):
        pass

    def _send(self, data):
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        names = ["stub:1b"] + StubModel.pulled
        self._send({"version": "0"} if self.path == "/api/version" else {"models": [{"name": n, "size": 1500000000} for n in names]})

    def do_DELETE(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["model"] in StubModel.pulled:
            StubModel.pulled.remove(body["model"])
        self._send({})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/pull":
            StubModel.pulled.append(body["model"])
            raw = b'{"status":"pulling","total":100,"completed":40}\n{"status":"success","total":100,"completed":100}\n'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        StubModel.calls.append(body)
        content = json.dumps(SUMMARY) if "format" in body else "[00:00] Hello team. We move the launch to March."
        self._send({"message": {"content": content}})


def tone(path, seconds=2, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(n / 20))) for n in range(seconds * rate)))


class Client:
    def __init__(self, app, httpd):
        self.app, self.port = app, app.port
        self.cookie = "cairn_session=" + app.token

    def call(self, method, path, body=None, headers=None, cookie=True, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        hdr = {"Host": host or "127.0.0.1:%d" % self.port}
        if cookie:
            hdr["Cookie"] = self.cookie
        if method == "POST":
            hdr.update({"Content-Type": "application/json", "X-Cairn": "1"})
        hdr.update(headers or {})
        conn.request(method, path, json.dumps(body or {}) if method == "POST" else None, hdr)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, raw.decode("utf-8", "replace")


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.pocket = root / "Pocket" / "RECORD"
        (cls.pocket / "2026-10-08").mkdir(parents=True)
        tone(cls.pocket / "2026-10-08" / "20261008_080600.wav")
        tone(cls.pocket / "2026-10-08" / "20261007_075500.wav", seconds=1)
        cls.model = ThreadingHTTPServer(("127.0.0.1", 0), StubModel)
        threading.Thread(target=cls.model.serve_forever, daemon=True).start()
        os.environ.update(
            CAIRN_HOME=str(root / "Cairn"), CAIRN_POCKET_DIR=str(cls.pocket), CAIRN_ENGINE="mlx",
            CAIRN_LLM="stub:1b", OLLAMA_HOST="127.0.0.1:%d" % cls.model.server_address[1],
            CAIRN_WHISPER_MODEL=str(root),
        )
        from cairn import server, speech

        def fake(path, progress=None):
            segs = [
                {"start": 0.0, "end": 3.0, "text": "Hello team.", "logprob": -0.1, "no_speech": 0.0, "compression": 1.2},
                {"start": 3.0, "end": 6.0, "text": "We move the launch to March.", "logprob": -1.1, "no_speech": 0.0, "compression": 1.2},
            ]
            return {"language": "en", "segments": segs, "duration": 6.0}

        speech.transcribe = fake
        cls.app, cls.httpd = server.make_server(18765)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app, cls.httpd)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.model.shutdown()
        cls.tmp.cleanup()

    def wait_idle(self):
        for _ in range(100):
            time.sleep(0.1)
            if not self.c.call("GET", "/api/state")[1]["job"]["running"]:
                return
        self.fail("job did not finish")

    def test_01_security(self):
        self.assertEqual(self.c.call("GET", "/api/state", cookie=False)[0], 403)
        self.assertEqual(self.c.call("GET", "/api/state", host="evil.example:%d" % self.c.port)[0], 403)
        self.assertEqual(self.c.call("POST", "/api/import", headers={"X-Cairn": "0"})[0], 403)
        self.assertEqual(self.c.call("GET", "/", cookie=False)[0], 403)
        self.assertEqual(self.c.call("GET", "/api/note/..%2F..%2Fetc%2Fpasswd")[0], 404)

    def test_02_token_cookie(self):
        status, _ = self.c.call("GET", "/?k=" + self.app.token, cookie=False)
        self.assertEqual(status, 303)
        status, body = self.c.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Cairn", body)

    def test_03_state_and_pocket(self):
        _, st = self.c.call("GET", "/api/state")
        self.assertTrue(st["pocket"]["connected"])
        self.assertEqual(st["pocket"]["count"], 2)
        self.assertTrue(st["ollama"])
        _, hidden = self.c.call("GET", "/api/state?list=0")
        self.assertNotIn("notes", hidden)

    def test_04_import_process_export(self):
        self.assertEqual(self.c.call("POST", "/api/import")[0], 202)
        self.wait_idle()
        _, st = self.c.call("GET", "/api/state")
        self.assertEqual(st["job"]["errors"], [])
        self.assertEqual(len(st["notes"]), 2)
        self.assertTrue(all(n["status"] == "done" for n in st["notes"]))
        n = st["notes"][0]
        self.assertEqual(n["title"], "Project check-in")
        self.assertEqual(n["quality"], round(100 * (math.exp(-0.1) + math.exp(-1.1)) / 2))
        self.assertEqual(n["passages"], 1)
        _, full = self.c.call("GET", "/api/note/" + n["id"])
        self.assertEqual(full["doubtful"][0]["text"], "We move the launch to March.")
        _, md = self.c.call("GET", "/api/note/%s/export?fmt=md" % n["id"])
        self.assertIn("## TL;DR", md)
        self.assertIn("Send the plan (Anna Friday)", md)
        _, html = self.c.call("GET", "/api/note/%s/export?fmt=html" % n["id"])
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
        _, frag = self.c.call("GET", "/api/note/%s/export?fmt=html&fragment=1&transcript=0" % n["id"])
        self.assertNotIn("<html", frag)
        _, text = self.c.call("GET", "/api/note/%s/export?fmt=doubtful" % n["id"])
        self.assertIn("[00:03]", text)
        self.assertTrue(any((Path(os.environ["CAIRN_HOME"]) / "Audio").rglob("*.wav")))

    def test_05_import_is_resumable(self):
        before = len(StubModel.calls)
        self.c.call("POST", "/api/import")
        self.wait_idle()
        self.assertEqual(len(StubModel.calls), before)  # nothing new to process

    def test_06b_note_type_is_chosen_per_recording_and_survives_a_redo(self):
        _, st = self.c.call("GET", "/api/state")
        note_id = st["notes"][0]["id"]
        self.assertEqual(self.c.call("POST", "/api/note/%s/template" % note_id, {"template": "idea"})[0], 200)
        self.assertEqual(self.c.call("POST", "/api/note/%s/template" % note_id, {"template": "nope"})[0], 400)
        _, full = self.c.call("GET", "/api/note/" + note_id)
        self.assertEqual(full["summary"]["template"], "idea")
        self.assertEqual(self.c.call("POST", "/api/note/%s/rerun" % note_id, {"level": "mid"})[0], 202)
        self.wait_idle()
        _, full = self.c.call("GET", "/api/note/" + note_id)
        self.assertEqual(full["summary"]["template"], "idea")  # the model's own guess does not overwrite the choice

    def test_06_rename_rerun_levels(self):
        _, st = self.c.call("GET", "/api/state")
        note_id = st["notes"][0]["id"]
        self.assertEqual(self.c.call("POST", "/api/note/%s/rename" % note_id, {"title": "Mon titre"})[0], 200)
        self.assertEqual(self.c.call("POST", "/api/note/%s/rerun" % note_id, {"level": "short"})[0], 202)
        self.wait_idle()
        _, full = self.c.call("GET", "/api/note/" + note_id)
        self.assertEqual(full["title"], "Mon titre")  # a chosen name survives a rerun
        self.assertEqual(full["level"], "short")
        self.assertEqual(self.c.call("POST", "/api/note/%s/rerun" % note_id, {"level": "nope"})[0], 400)
        # the level belongs to the recording; Redo only transcribes again when the speech model has changed
        self.assertEqual(self.c.call("POST", "/api/note/%s/options" % note_id, {"level": "full", "lang": "fr"})[0], 200)
        self.assertEqual(self.c.call("POST", "/api/note/%s/options" % note_id, {"level": "nope"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/note/%s/options" % note_id, {"lang": "xx"})[0], 400)
        before = len(StubModel.calls)
        code, answer = self.c.call("POST", "/api/note/%s/rerun" % note_id, {"level": "mid", "lang": "en"})
        self.assertEqual((code, answer["transcribe"]), (202, False))
        self.wait_idle()
        from unittest import mock
        from cairn import speech
        with mock.patch.object(speech, "model_name", return_value="another speech model"):
            code, answer = self.c.call("POST", "/api/note/%s/rerun" % note_id, {"level": "short"})
            self.assertEqual((code, answer["transcribe"]), (202, True))
            self.wait_idle()
        _, full = self.c.call("GET", "/api/note/" + note_id)
        self.assertEqual((full["status"], full["level"], full["title"], full["lang"]), ("done", "short", "Mon titre", "en"))
        self.assertEqual(full["models"]["speech"], "another speech model")
        self.assertGreater(len(StubModel.calls), before)

    def test_07_settings(self):
        self.assertEqual(self.c.call("POST", "/api/settings", {"ui": "fr"})[0], 200)
        _, st = self.c.call("GET", "/api/state")
        self.assertEqual(st["settings"]["ui"], "fr")
        self.assertEqual(self.c.call("POST", "/api/settings", {"tr": "en"})[0], 400)  # the language belongs to each recording
        self.assertEqual(self.c.call("POST", "/api/settings", {"level": "full"})[0], 400)  # no global level any more
        self.assertEqual(self.c.call("POST", "/api/settings", {"ui": "xx"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/settings", {"audio_dir": "relative/path"})[0], 400)

    def test_watcher_processes_the_queue_only_when_asked_and_not_after_a_stop(self):
        from types import SimpleNamespace
        from unittest import mock

        from cairn import watch

        calls = []
        jobs_ns = SimpleNamespace(snapshot=lambda: {"running": False}, start_privacy=lambda: None, start_sync=lambda: None,
                                  start_queue=lambda: calls.append("queue"), paused=False)
        app = SimpleNamespace(jobs=jobs_ns, pocket_state=lambda: {"new": 0}, waiting_count=lambda: 3, purge_pocket=lambda: 0,
                              check_update=lambda: {"available": False}, update_info=None)
        fresh = {"when": "2999-01-01T00:00:00"}
        with mock.patch.object(watch.privacy, "last_report", return_value=fresh):
            with mock.patch.object(watch.config, "load_settings", return_value={"autoimport": True, "autocheck": False}):
                watch.Watcher(app).tick(now=10**9)
            self.assertEqual(calls, [])  # off by default
            with mock.patch.object(watch.config, "load_settings", return_value={"autoimport": True, "autocheck": False, "autoprocess": True}):
                watcher = watch.Watcher(app)
                watcher.tick(now=10**9)
                self.assertEqual(calls, ["queue"])
                jobs_ns.paused = True  # the person pressed Stop
                watcher.tick(now=10**9 + 500)
                self.assertEqual(calls, ["queue"])

    def test_08c_sync_copies_without_processing_and_the_badge_counts_what_is_new(self):
        extra = self.pocket / "2026-10-12"
        extra.mkdir(exist_ok=True)
        tone(extra / "fresh.wav", seconds=1)
        _, st = self.c.call("GET", "/api/state")
        self.assertGreaterEqual(st["pocket"]["new"], 1)
        self.app.jobs.start_sync()
        self.wait_idle()
        _, st = self.c.call("GET", "/api/state")
        self.assertEqual(st["pocket"]["new"], 0)
        row = [n for n in st["notes"] if (self.c.call("GET", "/api/note/" + n["id"])[1].get("source") or "").endswith("fresh.wav")][0]
        self.assertEqual(row["status"], "waiting")  # copied and visible, not processed
        self.c.call("POST", "/api/note/%s/delete" % row["id"], {"pocket": True})

    def test_08b_delete_erases_everywhere_and_waits_for_a_disconnected_pocket(self):
        from unittest import mock

        from cairn import pocket as pocket_module

        extra_dir = self.pocket / "2026-10-09"
        extra_dir.mkdir(exist_ok=True)
        now, later = extra_dir / "now.wav", extra_dir / "later.wav"
        tone(now, seconds=1)
        tone(later, seconds=1)
        self.assertEqual(self.c.call("POST", "/api/import")[0], 202)
        self.wait_idle()
        _, st = self.c.call("GET", "/api/state")
        sources = {i: self.c.call("GET", "/api/note/" + i)[1] for i in [n["id"] for n in st["notes"]]}
        now_id = [i for i, n in sources.items() if n["source"].endswith("now.wav")][0]
        later_id = [i for i, n in sources.items() if n["source"].endswith("later.wav")][0]
        audio_now, audio_later = sources[now_id]["audio"], sources[later_id]["audio"]
        # Pocket connected: the file, the local copy and the note are all gone at once
        code, out = self.c.call("POST", "/api/note/%s/delete" % now_id)
        self.assertEqual((code, out["pocket"]), (200, True))
        self.assertFalse(now.exists())
        self.assertFalse(os.path.exists(audio_now))
        self.assertEqual(self.c.call("GET", "/api/note/" + now_id)[0], 404)
        # Pocket not connected: the note and local copy go now, the Pocket file at the next connection
        with mock.patch.object(pocket_module, "find_pocket", return_value=None):
            code, out = self.c.call("POST", "/api/note/%s/delete" % later_id)
            self.assertEqual((code, out["pocket"]), (200, False))
        self.assertTrue(later.exists())
        self.assertFalse(os.path.exists(audio_later))
        self.assertFalse(Path(audio_later).parent.exists())  # the dated folder goes with its last recording
        self.assertTrue(Path(audio_now).parent.parent.is_dir())  # the Audio folder itself stays
        self.assertEqual(self.app.purge_pocket(), 1)  # the Pocket is connected again
        self.assertFalse(later.exists())
        self.assertEqual(self.app.store.ignored(), set())
        self.assertEqual(self.c.call("POST", "/api/import")[0], 202)
        self.wait_idle()
        _, st = self.c.call("GET", "/api/state")
        self.assertFalse([n for n in st["notes"] if n["id"] in (now_id, later_id)])  # nothing comes back

    def test_08_pocket_is_never_emptied_in_bulk(self):
        for method, path in (("GET", "/api/pocket/verify"), ("POST", "/api/pocket/empty")):
            self.assertEqual(self.c.call(method, path, {"confirm": True})[0], 404)

    def test_09_delete_note(self):
        _, st = self.c.call("GET", "/api/state")
        note_id = st["notes"][0]["id"]
        audio = Path(self.c.call("GET", "/api/note/" + note_id)[1]["audio"])
        self.assertEqual(self.c.call("POST", "/api/note/%s/delete" % note_id)[0], 200)
        self.assertFalse(audio.exists())
        self.assertEqual(self.c.call("GET", "/api/note/" + note_id)[0], 404)


    def test_10_models_on_demand(self):
        status, listing = self.c.call("GET", "/api/models")
        self.assertEqual(status, 200)
        self.assertEqual([m["id"] for m in listing["llm"]], ["qwen3:4b", "qwen3:8b", "qwen3:14b"])
        self.assertEqual([m["id"] for m in listing["speech"]], ["turbo", "large"])
        self.assertFalse(any(m["installed"] for m in listing["llm"]))
        # nothing is downloaded without an explicit confirmation
        self.assertEqual(self.c.call("POST", "/api/models/install", {"kind": "llm", "id": "qwen3:4b"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/install", {"kind": "llm", "id": "tiny:0.6b", "confirm": True})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/select", {"kind": "llm", "id": "qwen3:4b"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/select", {"kind": "speech", "id": "large"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/install", {"kind": "llm", "id": "qwen3:4b", "confirm": True})[0], 202)
        for _ in range(50):
            job = self.c.call("GET", "/api/models")[1]["job"]
            if job["state"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(job["state"], "done")
        self.assertTrue([m for m in self.c.call("GET", "/api/models")[1]["llm"] if m["id"] == "qwen3:4b"][0]["installed"])
        status, settings = self.c.call("POST", "/api/models/select", {"kind": "llm", "id": "qwen3:4b"})
        self.assertEqual((status, settings["llm"]), (200, "qwen3:4b"))
        self.assertEqual(self.c.call("POST", "/api/settings", {"llm": "anything:1b"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/install", {"kind": "llm", "id": "qwen3:4b"}, cookie=False)[0], 403)
        # removal needs a confirmation and a model that is installed
        self.assertEqual(self.c.call("POST", "/api/models/remove", {"kind": "llm", "id": "qwen3:4b"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/remove", {"kind": "llm", "id": "qwen3:14b", "confirm": True})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/models/remove", {"kind": "llm", "id": "qwen3:4b", "confirm": True})[0], 200)
        self.assertFalse([m for m in self.c.call("GET", "/api/models")[1]["llm"] if m["id"] == "qwen3:4b"][0]["installed"])


    def test_10b_a_model_needing_a_newer_ollama_is_refused_clearly(self):
        from unittest import mock

        from cairn import llm, models

        for found, minimum, expected in (("0.40.11", "0.17.5", True), ("0.17.5", "0.17.5", True), ("0.17.5-rc1", "0.17.5", True),
                                         ("0.9.0", "0.17.5", False), ("0", "0.17.5", False), ("", "0.17.5", True)):
            self.assertEqual(llm.at_least(found, minimum), expected, (found, minimum))
        downloader = models.Downloader()
        downloader.job = {"state": "running", "pct": 0}
        with mock.patch.object(llm, "version", return_value="0.40.11"), mock.patch.object(models.urllib.request, "urlopen") as opened:
            downloader._pull_llm({"id": "x:9b", "label": "X 9B", "min_ollama": "999.0"})
        self.assertEqual(downloader.job["state"], "error")
        self.assertIn("Ollama 999.0 or newer", downloader.job["error"])
        opened.assert_not_called()  # nothing was downloaded

    def test_12_skip_and_process_one(self):
        notes = self.c.call("GET", "/api/state")[1]["notes"]
        nid = notes[0]["id"]
        self.assertEqual(self.c.call("POST", "/api/note/%s/process" % nid)[0] in (202, 400), True)
        self.wait_idle()
        waiting = {"id": "w-test", "source": "w.wav", "status": "waiting", "title": "", "date": "2026-01-01T10:00:00", "audio": str(self.pocket / "none.wav")}
        self.app.store.save(waiting)
        self.assertEqual(self.c.call("POST", "/api/note/w-test/skip")[0], 200)
        state = self.c.call("GET", "/api/state")[1]
        self.assertEqual([n["status"] for n in state["notes"] if n["id"] == "w-test"], ["skipped"])
        self.assertNotIn("w-test", [n["id"] for n in self.app.store.all() if n["status"] in ("waiting", "error")])
        self.assertEqual(self.c.call("POST", "/api/note/w-test/restore")[0], 200)
        self.assertEqual(self.app.store.get("w-test")["status"], "waiting")
        self.assertEqual(self.c.call("POST", "/api/cancel")[0], 200)
        self.app.store.delete("w-test")

    def test_99_web_page_boots_and_reacts(self):
        """The page is loaded in Node and driven with fake clicks, so a broken script fails here."""
        import shutil
        import subprocess

        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not installed")
        _, state = self.c.call("GET", "/api/state")
        done = [n for n in state["notes"] if n["status"] == "done"]
        self.assertTrue(done)
        _, note = self.c.call("GET", "/api/note/" + done[0]["id"])
        state["notes"].append({"id": "w1", "status": "waiting", "title": "", "date": "2026-10-08T07:00:00", "duration": 61, "level": None, "lang": None})
        fixture = Path(self.tmp.name) / "web_fixture.json"
        fixture.write_text(json.dumps({"state": state, "note": note}), encoding="utf-8")
        root = Path(__file__).resolve().parent
        result = subprocess.run(
            [node, str(root / "web_boot.js"), str(root.parent / "cairn" / "web" / "app.js"), str(fixture)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_13_web_app_files(self):
        status, _ = self.c.call("GET", "/manifest.webmanifest", cookie=False)
        self.assertEqual(status, 200)
        self.assertEqual(self.c.call("GET", "/icon-192.png", cookie=False)[0], 200)
        self.assertEqual(self.c.call("GET", "/app.js", cookie=False)[0], 403)  # the app itself still needs the session
        from cairn import server

        self.assertEqual(server.session_key(), server.session_key())

    def test_14_privacy_check(self):
        self.assertEqual(self.c.call("POST", "/api/privacy/check")[0], 202)
        self.wait_idle()
        status, data = self.c.call("GET", "/api/privacy")
        self.assertEqual(status, 200)
        report = data["report"]
        self.assertEqual(report["external"], [])
        self.assertTrue(report["ok"], report)

    def test_11_about_components(self):
        status, data = self.c.call("GET", "/api/about")
        self.assertEqual(status, 200)
        names = [c["name"] for c in data["components"]]
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertTrue(all({"name", "ver", "size", "ok"} <= set(c) for c in data["components"]))
        self.assertTrue(data["referral"].startswith("https://referral.heypocketai.com/"))
        self.assertEqual(self.c.call("GET", "/referral-qr.svg")[0], 404)
        self.assertNotIn("Diarization", names)  # not installed in this fixture

    def test_12_about_lists_diarization_once_its_model_is_installed(self):
        from cairn import models

        diar_dir = models.diar_dir()
        diar_dir.mkdir(parents=True, exist_ok=True)
        (diar_dir / models.MARK).write_text("ok", encoding="utf-8")
        try:
            status, data = self.c.call("GET", "/api/about")
            self.assertEqual(status, 200)
            diar = next((c for c in data["components"] if c["name"] == "Diarization"), None)
            self.assertIsNotNone(diar, "the installed diarization model must be visible in About")
            self.assertTrue(diar["ok"])
            self.assertEqual(diar["ver"], "pyannote 3.1")
        finally:
            shutil.rmtree(diar_dir, ignore_errors=True)


class HardeningTest(unittest.TestCase):
    """Defects found by the audit of October 2026, each kept as a regression test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ.setdefault("CAIRN_HOME", str(self.root / "Cairn"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_listing_reads_only_the_notes_that_changed(self):
        from unittest import mock

        from cairn import config, notes

        store = notes.Store(self.root / "Texts")
        for name in ("a", "b"):
            store.save({"id": name, "status": "done", "clean": "word " * 50000, "segments": [{"text": "x"}], "summary": {"tldr": "t"}, "fidelity": 90})
        rows = store.slim()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("clean" not in r and "segments" not in r and "summary" not in r for r in rows))
        store.light()  # older notes are completed once (languages), then kept with the note
        store.light()
        with mock.patch.object(config, "read_json", wraps=config.read_json) as reader:
            store.slim()
            store.light()
            self.assertEqual(reader.call_count, 0, "unchanged notes must not be parsed again")
            note = store.get("a")
            note["title"] = "changed"
            store.save(note)
            reader.reset_mock()
            self.assertEqual({r["id"]: r.get("title") for r in store.slim()}["a"], "changed")
            self.assertEqual(reader.call_count, 1)

    def test_old_note_is_scored_once_then_never_read_again_by_the_listing(self):
        from unittest import mock

        from cairn import config, notes

        store = notes.Store(self.root / "Texts")
        summary = {"tldr": "Anna sends 12 files to Paris on 15 March.", "key_points": ["Budget of 300 approved by Marc"]}
        store.save({"id": "old", "status": "done", "summary": summary, "clean": "Anna sends 12 files to Paris on 15 March. Budget of 300 approved by Marc."})
        first = store.light()[0]["fidelity"]
        self.assertIsNotNone(first)
        store.light()  # the score was saved with the note: this pass reads that file once more, then nothing
        with mock.patch.object(config, "read_json", wraps=config.read_json) as reader:
            self.assertEqual(store.light()[0]["fidelity"], first)
            self.assertEqual(reader.call_count, 0)

    def test_a_link_on_the_pocket_is_never_followed(self):
        from cairn import pocket

        folder = self.root / "RECORD"
        folder.mkdir()
        tone(folder / "real.wav", seconds=1)
        secret = self.root / "secret.txt"
        secret.write_text("private")
        try:
            os.symlink(secret, folder / "evil.mp3")
        except (OSError, NotImplementedError):
            self.skipTest("links are not available here")
        self.assertEqual([p.name for p in pocket.list_recordings(folder)], ["real.wav"])

    def test_copy_of_a_file_that_vanished_fails_at_once(self):
        from cairn import pocket

        started = time.time()
        with self.assertRaises(OSError):
            pocket.copy_verified(self.root / "gone.wav", self.root / "out" / "gone.wav")
        self.assertLess(time.time() - started, 2)

    def test_html_export_escapes_the_language_attribute(self):
        from cairn import render

        page = render.to_html({"id": "x", "title": "t", "lang": 'en"><script>1</script>', "summary": {}, "date": "2026-10-01T10:00:00"})
        self.assertNotIn("<script>", page)
        self.assertIn('<html lang="en">', page)

    def test_markdown_export_does_not_carry_html_tags(self):
        from cairn import render

        evil = "<img src=x onerror=alert(1)> and <script>1</script>"
        text = render.to_markdown({"id": "x", "title": evil, "summary": {"tldr": evil, "key_points": [evil]}, "clean": evil, "date": "2026-10-01T10:00:00"})
        self.assertNotIn("<img", text)
        self.assertNotIn("<script", text)
        self.assertIn("&lt;img", text)
        self.assertIn("3 < 5", render.to_markdown({"id": "x", "title": "t", "summary": {"tldr": "3 < 5"}}))

    def test_a_general_note_is_measured_on_its_key_terms(self):
        from cairn import score

        summary = {"tldr": "The course covers community management, educational leadership and volunteer engagement.",
                   "key_points": ["Stakeholders expect transparent communication", "Mentoring improves retention of volunteers"],
                   "context": "A lecture about organisational governance and participation."}
        faithful = ("We talk about community management and educational leadership, how volunteer engagement works, "
                    "stakeholders and transparent communication, mentoring and retention, organisational governance, participation.")
        self.assertEqual(score.fidelity_detail(summary, faithful)[1], "terms")
        self.assertGreaterEqual(score.fidelity(summary, faithful), 80)
        invented = "We discuss the weather forecast and a recipe for chocolate cake with some friends tonight."
        self.assertLess(score.fidelity(summary, invented), 30)
        self.assertEqual(score.fidelity_detail(summary, faithful, words_ok=False), (None, "language"))  # note and audio in two languages
        self.assertEqual(score.fidelity_detail({"tldr": "Short."}, faithful), (None, "few"))  # nothing to check

    def test_facts_still_come_first(self):
        from cairn import score

        summary = {"tldr": "Anna sends 12 files to Paris on 15 March.", "key_points": ["Budget of 300 approved by Marc"]}
        self.assertEqual(score.fidelity_detail(summary, "Anna sends 12 files to Paris on 15 March. Budget of 300 approved by Marc.")[1], "facts")

    def test_a_recording_deleted_while_it_is_processed_does_not_come_back(self):
        from unittest import mock

        from cairn import jobs, notes, speech

        store = notes.Store(self.root / "Texts")
        audio = self.root / "a.wav"
        tone(audio, seconds=1)
        store.save({"id": "gone", "status": "waiting", "audio": str(audio), "date": "2026-10-01T10:00:00", "title": ""})
        queue = jobs.Jobs(store)

        def deleted_meanwhile(path, progress=None):
            store.delete("gone")
            return {"language": "en", "segments": [{"start": 0.0, "end": 1.0, "text": "Hello there everyone.", "logprob": -0.1, "no_speech": 0.0, "compression": 1.2}], "duration": 1.0}

        with mock.patch.object(speech, "transcribe", deleted_meanwhile):
            self.assertTrue(queue._try("gone", {"ui": "en"}))
        self.assertFalse(store.exists("gone"))
        self.assertEqual(queue.snapshot()["errors"], [])

    def test_malformed_request_lengths_are_refused(self):
        import socket

        from cairn import server

        app, httpd = server.make_server(18790)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            for length, expected in (("abc", b" 400 "), ("-5", b" 400 ")):
                with socket.create_connection(("127.0.0.1", app.port), timeout=5) as conn:
                    conn.sendall(
                        ("POST /api/cancel HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nCookie: cairn_session=%s\r\nContent-Type: application/json\r\n"
                         "X-Cairn: 1\r\nContent-Length: %s\r\n\r\n" % (app.port, app.token, length)).encode()
                    )
                    self.assertIn(expected, conn.recv(200).split(b"\r\n")[0] + b" ")
        finally:
            httpd.shutdown()
            httpd.server_close()


class LanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ.setdefault("CAIRN_HOME", str(self.root / "Cairn"))

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def segs(*texts):
        return [{"start": i * 10.0, "end": i * 10.0 + 9.0, "text": x, "logprob": -0.2, "no_speech": 0.0, "compression": 1.2} for i, x in enumerate(texts)]

    def test_two_languages_in_one_recording_are_noticed(self):
        from cairn import speech

        french = ["Nous allons parler de la réunion et de ce que nous avons fait dans le projet.",
                  "Il est important que vous soyez là pour la présentation avec le client."]
        english = ["So this is what we have to do for the next release and it is not easy.",
                   "I think that we will have the budget but there is a risk with the plan.",
                   "We can do it if you are with us and the team is ready for that."]
        shares, mixed = speech.language_mix(self.segs(*(french * 3 + english)))
        self.assertTrue(mixed)
        self.assertGreater(shares["fr"], shares["en"])
        shares, mixed = speech.language_mix(self.segs(*(french * 6)))
        self.assertFalse(mixed)
        self.assertEqual(speech.language_mix(self.segs("Hello"))[0], {})  # too short to say

    def test_the_language_of_the_audio_is_passed_to_the_engine_and_a_change_transcribes_again(self):
        from unittest import mock

        from cairn import jobs, notes, speech

        store = notes.Store(self.root / "Texts")
        audio = self.root / "a.wav"
        tone(audio, seconds=1)
        store.save({"id": "n1", "status": "waiting", "audio": str(audio), "date": "2026-10-01T10:00:00", "title": ""})
        queue = jobs.Jobs(store)
        seen = []

        def fake(path, progress=None, language=None):
            seen.append(language)
            return {"language": language or "fr", "segments": self.segs("Bonjour tout le monde, nous allons commencer la réunion."), "duration": 9.0}

        summary = {"template": "other", "title": "T", "tldr": "x", "actions": []}
        with mock.patch.object(speech, "transcribe", fake), mock.patch.object(speech, "model_name", lambda: "stub"), \
                mock.patch("cairn.llm.summarize", lambda *a, **k: dict(summary)):
            queue._process("n1", {"ui": "fr"})
            self.assertEqual(seen, [None])  # auto: the engine detects it
            note = store.get("n1")
            self.assertIsNone(note["speech_lang_used"])
            self.assertIn("languages", note)
            # same language of the audio: only the summary is rewritten
            with mock.patch.object(queue, "_start") as start:
                self.assertFalse(queue.start_rerun("n1", "mid", "fr", "auto"))
                self.assertEqual(start.call_args[0][0], "rerun")
            # another language of the audio: the audio is transcribed again with it
            with mock.patch.object(queue, "_start") as start:
                self.assertTrue(queue.start_rerun("n1", "mid", "fr", "en"))
                self.assertEqual(start.call_args[0][0], "import")
            queue._process("n1", {"ui": "fr"})
            self.assertEqual(seen, [None, "en"])
            self.assertEqual(store.get("n1")["speech_lang_used"], "en")

    def test_choosing_the_audio_language_is_validated_and_kept(self):
        from cairn import jobs, notes

        store = notes.Store(self.root / "Texts")
        store.save({"id": "n2", "status": "waiting", "audio": "", "title": ""})
        queue = jobs.Jobs(store)
        queue.set_options("n2", speech_lang="fr")
        self.assertEqual(store.get("n2")["speech_lang"], "fr")
        queue.set_options("n2", speech_lang="auto")
        self.assertIsNone(store.get("n2")["speech_lang"])
        with self.assertRaises(ValueError):
            queue.set_options("n2", speech_lang="de")


class BatteryTest(unittest.TestCase):
    def test_a_reading_runs_in_the_background_and_only_fresh_values_are_shown(self):
        import time
        from unittest import mock

        from cairn import battery

        gauge = battery.Gauge(reader=lambda: ("ok", 64))
        with mock.patch.object(battery, "available", return_value=True):
            self.assertTrue(gauge.poll(now=1000.0))
            for _ in range(100):
                if not gauge.busy:
                    break
                time.sleep(0.02)
            self.assertEqual(gauge.snapshot(), {"available": True, "level": 64, "state": "ok"})
            self.assertFalse(gauge.poll(now=1000.0 + battery.REFRESH - 1))  # not before the next due time
            gauge.when -= battery.STALE + 1  # an old value is no longer shown
            self.assertIsNone(gauge.snapshot()["level"])
        slow = battery.Gauge(reader=lambda: ("none", None))
        slow.state, slow.tried = "none", 1000.0
        self.assertFalse(slow.poll(now=1000.0 + battery.RETRY - 1))  # nothing read: tries less often
        self.assertTrue(slow.poll(now=1000.0 + battery.RETRY + 1))
        absent = battery.Gauge()
        absent.state = "missing"
        self.assertFalse(absent.poll(now=10 ** 9))  # component not installed: never tries
        with mock.patch.object(battery, "available", return_value=False):
            self.assertEqual(gauge.snapshot(), {"available": False})

    def test_reading_is_read_only_and_survives_failures(self):
        import subprocess
        from unittest import mock

        from cairn import battery

        def run(code, out=""):
            return mock.patch.object(battery.subprocess, "run", return_value=subprocess.CompletedProcess([], code, out, ""))

        with run(0, "87\n"):
            self.assertEqual(battery.read(), ("ok", 87))
        with run(3):
            self.assertEqual(battery.read(), ("missing", None))
        with run(1):
            self.assertEqual(battery.read(), ("none", None))
        with run(0, "250\n"):
            self.assertEqual(battery.read(), ("none", None))  # not a percentage
        with mock.patch.object(battery.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(battery.read(), ("none", None))
        source = open(battery.__file__.replace("battery.py", "battery_worker.py"), encoding="utf-8").read()
        self.assertNotIn("write_gatt_char", source)  # the worker never writes to the Pocket
        self.assertNotIn("pair", source.lower().replace("pairs with nothing", ""))

    def test_no_setting_and_an_old_settings_file_with_the_key_still_loads(self):
        import json
        import tempfile
        from unittest import mock

        from cairn import config

        self.assertNotIn("pocketbattery", config.DEFAULT_SETTINGS)
        folder = Path(tempfile.mkdtemp())
        (folder / "settings.json").write_text(json.dumps({"ui": "fr", "pocketbattery": True}), encoding="utf-8")
        with mock.patch.object(config, "home", return_value=folder):
            self.assertEqual(config.load_settings()["ui"], "fr")


class PocketStatusTest(unittest.TestCase):
    def test_key_setting_is_validated_and_never_logged_on_a_wrong_length(self):
        import tempfile
        from unittest import mock

        from cairn import config

        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(config, "home", return_value=folder):
            self.assertEqual(config.save_settings({"pocket_key": "FakeKey1234567AB"})["pocket_key"], "FakeKey1234567AB")
            self.assertIsNone(config.save_settings({"pocket_key": ""})["pocket_key"])
            self.assertIsNone(config.save_settings({"pocket_key": None})["pocket_key"])
            with self.assertRaises(ValueError):
                config.save_settings({"pocket_key": "tooshort"})
            with self.assertRaises(ValueError):
                config.save_settings({"pocket_key": "has a space here"})

    def test_a_reading_is_only_tried_with_a_full_length_key_and_only_fresh_data_is_shown(self):
        import time
        from unittest import mock

        from cairn import pocket_status

        gauge = pocket_status.StatusGauge(reader=lambda key: ("ok", {"firmware": "1.8", "state": 0, "used_kb": 100, "total_kb": 1000}))
        self.assertFalse(gauge.poll("short", now=1000.0))  # never tried with an invalid-length key
        self.assertTrue(gauge.poll("FakeKey1234567AB", now=1000.0))
        for _ in range(100):
            if not gauge.busy:
                break
            time.sleep(0.02)
        self.assertEqual(gauge.snapshot(), {"state": "ok", "data": {"firmware": "1.8", "state": 0, "used_kb": 100, "total_kb": 1000}})
        self.assertFalse(gauge.poll("FakeKey1234567AB", now=1000.0 + pocket_status.REFRESH - 1))
        gauge.when -= pocket_status.STALE + 1
        self.assertIsNone(gauge.snapshot()["data"])
        rejected = pocket_status.StatusGauge(reader=lambda key: ("rejected", None))
        rejected.state, rejected.tried = "rejected", 1000.0
        self.assertFalse(rejected.poll("FakeKey1234567AB", now=1000.0 + pocket_status.RETRY - 1))
        self.assertTrue(rejected.poll("FakeKey1234567AB", now=1000.0 + pocket_status.RETRY + 1))
        absent = pocket_status.StatusGauge()
        absent.state = "missing"
        self.assertFalse(absent.poll("FakeKey1234567AB", now=10 ** 9))  # component not installed: never tries

    def test_read_only_parses_known_responses_and_the_worker_sends_no_write_command(self):
        import subprocess
        from unittest import mock

        from cairn import pocket_status

        def run(code, out=""):
            return mock.patch.object(pocket_status.subprocess, "run", return_value=subprocess.CompletedProcess([], code, out, ""))

        with run(0, '{"firmware": "1.8", "state": 0, "used_kb": 100, "total_kb": 1000}\n'):
            self.assertEqual(pocket_status.read("FakeKey1234567AB"), ("ok", {"firmware": "1.8", "state": 0, "used_kb": 100, "total_kb": 1000}))
        with run(3):
            self.assertEqual(pocket_status.read("FakeKey1234567AB"), ("missing", None))
        with run(2):
            self.assertEqual(pocket_status.read("FakeKey1234567AB"), ("rejected", None))
        with run(1):
            self.assertEqual(pocket_status.read("FakeKey1234567AB"), ("none", None))
        with mock.patch.object(pocket_status.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(pocket_status.read("FakeKey1234567AB"), ("none", None))
        source = open(pocket_status.__file__.replace("pocket_status.py", "pocket_status_worker.py"), encoding="utf-8").read()
        for forbidden in ("APP&T&", "WIFI"):
            self.assertNotIn(forbidden, source)  # no clock set, no WiFi command: read-only, as promised

    def test_worker_parses_the_documented_response_format(self):
        from cairn import pocket_status_worker as w

        result = {}
        w._parse("MCU&FW&1.8", result)
        w._parse("MCU&STE&0", result)
        w._parse("MCU&SPA&060846&061032", result)
        w._parse("MCU&SOMETHING&unrelated", result)  # unknown lines are ignored, not guessed at
        self.assertEqual(result, {"firmware": "1.8", "state": 0, "used_kb": 60846, "total_kb": 61032})


class DiarizationTest(unittest.TestCase):
    def test_settings_are_validated_and_off_by_default(self):
        import tempfile
        from unittest import mock

        from cairn import config

        self.assertFalse(config.DEFAULT_SETTINGS["diarize"])
        self.assertIsNone(config.DEFAULT_SETTINGS["hf_token"])
        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(config, "home", return_value=folder):
            self.assertTrue(config.save_settings({"diarize": True})["diarize"])
            self.assertEqual(config.save_settings({"hf_token": "hf_abcdefgh12345"})["hf_token"], "hf_abcdefgh12345")
            self.assertIsNone(config.save_settings({"hf_token": ""})["hf_token"])
            with self.assertRaises(ValueError):
                config.save_settings({"hf_token": "short"})
            with self.assertRaises(ValueError):
                config.save_settings({"diarize": "yes"})

    def test_speakers_are_numbered_by_order_of_first_speech_not_by_the_raw_label(self):
        from cairn import diarize

        segments = [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}, {"start": 4.0, "end": 6.0}]
        turns = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_01"}, {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_00"},
                 {"start": 4.0, "end": 6.0, "speaker": "SPEAKER_01"}]
        out = diarize.assign(segments, turns, "en")
        self.assertEqual([s["speaker"] for s in out], ["Speaker 1", "Speaker 2", "Speaker 1"])
        self.assertEqual(diarize.assign(list(segments), [], "en"), segments)  # no turns: nothing added, no crash

    def test_assign_clears_a_label_left_over_from_an_earlier_pass(self):
        from cairn import diarize

        segments = [{"start": 0.0, "end": 2.0, "speaker": "Speaker 1"}, {"start": 10.0, "end": 12.0, "speaker": "Speaker 2"}]
        out = diarize.assign(segments, [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}], "en")
        self.assertEqual(out[0]["speaker"], "Speaker 1")  # re-matched
        self.assertNotIn("speaker", out[1])  # no turn covers it any more: the stale label is gone, not kept

    def test_renamed_segments_swap_the_label_only_where_a_name_was_given(self):
        from cairn import diarize

        segments = [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "Speaker 1"}, {"start": 1.0, "end": 2.0, "text": "Yo", "speaker": "Speaker 2"}]
        out = diarize.renamed(segments, {"Speaker 1": "Sophie"})
        self.assertEqual([s["speaker"] for s in out], ["Sophie", "Speaker 2"])
        self.assertEqual(segments[0]["speaker"], "Speaker 1")  # the original segments are untouched
        self.assertEqual(diarize.renamed(segments, {}), segments)

    def test_raw_lines_carries_the_speaker_label_only_when_one_was_assigned(self):
        from cairn import speech

        segments = [{"start": 1.0, "end": 2.0, "text": "Hello"}, {"start": 65.0, "end": 66.0, "text": "there", "speaker": "Speaker 2"}]
        self.assertEqual(speech.raw_lines(segments), ["[00:01] Hello", "[01:05] Speaker 2: there"])

    def test_a_result_is_only_trusted_from_an_installed_model_and_the_worker_sends_nothing_over_the_network(self):
        import subprocess
        from unittest import mock

        from cairn import diarize

        with mock.patch.object(diarize.models, "diar_installed", return_value=False):
            self.assertEqual(diarize.run("x.mp3"), ("missing", None))
        def popen(code, out, err):
            class Fake:
                returncode = code

                def __init__(self, *args, **kwargs):
                    pass

                def communicate(self, timeout=None):
                    return out, err

            return Fake

        with mock.patch.object(diarize.models, "diar_installed", return_value=True):
            with mock.patch.object(diarize.subprocess, "Popen", popen(0, '[{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]\n', "")):
                self.assertEqual(diarize.run("x.mp3"), ("ok", [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]))
            with mock.patch.object(diarize.subprocess, "Popen", popen(3, "", "")):
                self.assertEqual(diarize.run("x.mp3"), ("missing", None))
            with mock.patch.object(diarize.subprocess, "Popen", popen(1, "", "boom")):
                self.assertEqual(diarize.run("x.mp3"), ("none", None))
        source = open(diarize.__file__.replace("diarize.py", "diarize_worker.py"), encoding="utf-8").read()
        self.assertIn("HF_HUB_OFFLINE", source)  # inference never reaches the network
        self.assertNotIn("requests.", source)

    def test_catalog_lists_one_gated_diarization_model(self):
        from cairn import catalog

        self.assertEqual(len(catalog.DIAR), 1)
        self.assertTrue(catalog.DIAR[0]["gated"])
        self.assertEqual(catalog.DIAR_IDS, ("pyannote-3.1",))

    def test_rediarize_redoes_only_the_speakers_and_clears_any_custom_names(self):
        import tempfile
        from unittest import mock

        from cairn import diarize, jobs, notes

        folder = Path(tempfile.mkdtemp())
        store = notes.Store(folder / "Texts")
        audio = folder / "a.wav"
        audio.write_bytes(b"x")
        note = {
            "id": "n1", "status": "done", "audio": str(audio), "lang": "en", "title": "T",
            "segments": [{"start": 0.0, "end": 2.0, "text": "Hi there.", "speaker": "Speaker 1"}],
            "clean": "[00:00] Speaker 1: Hi there.", "speaker_names": {"Speaker 1": "Marc"},
        }
        store.save(note)
        queue = jobs.Jobs(store)

        # not processable: no segments, no audio, still waiting
        store.save({"id": "n0", "status": "waiting", "title": ""})
        with self.assertRaises(ValueError):
            queue.start_rediarize("n0")
        # the model is not installed: refused before any job starts
        with mock.patch.object(diarize, "available", return_value=False):
            with self.assertRaises(ValueError):
                queue.start_rediarize("n1")

        turns = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_03"}]
        with mock.patch.object(diarize, "available", return_value=True), mock.patch.object(diarize, "run", return_value=("ok", turns)):
            queue._rediarize("n1")
        saved = store.get("n1")
        self.assertEqual(saved["segments"][0]["speaker"], "Speaker 1")  # re-numbered from scratch, same order
        self.assertEqual(saved["speaker_names"], {})  # a custom name from the previous pass does not survive
        self.assertEqual(saved["clean"], "[00:00] Speaker 1: Hi there.")
        self.assertEqual(saved["status"], "done")

        # no turns found: the note is marked with an error, not silently left as if nothing happened
        with mock.patch.object(diarize, "available", return_value=True), mock.patch.object(diarize, "run", return_value=("none", None)):
            with self.assertRaises(RuntimeError):
                queue._rediarize("n1")
        self.assertTrue(store.get("n1")["error"])

    def test_renaming_a_speaker_regenerates_the_clean_transcript(self):
        import tempfile
        import threading

        from cairn import server

        root = Path(tempfile.mkdtemp())
        os.environ["CAIRN_HOME"] = str(root / "Cairn")
        app, httpd = server.make_server(18791)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        client = Client(app, httpd)
        try:
            app.store.save({
                "id": "n1", "status": "done", "title": "T", "lang": "en",
                "segments": [{"start": 0.0, "end": 2.0, "text": "Hi there.", "speaker": "Speaker 1"}],
                "clean": "[00:00] Speaker 1: Hi there.",
            })
            status, data = client.call("POST", "/api/note/n1/speaker", {"from": "Speaker 1", "name": "Marc"})
            self.assertEqual((status, data), (200, {"ok": True}))
            saved = app.store.get("n1")
            self.assertEqual(saved["speaker_names"], {"Speaker 1": "Marc"})
            self.assertEqual(saved["clean"], "[00:00] Marc: Hi there.")
            self.assertEqual(saved["segments"][0]["speaker"], "Speaker 1")  # the stable key is kept on the segment itself
            # clearing the name falls back to the generated label again
            client.call("POST", "/api/note/n1/speaker", {"from": "Speaker 1", "name": ""})
            self.assertEqual(app.store.get("n1")["speaker_names"], {})
            self.assertEqual(app.store.get("n1")["clean"], "[00:00] Speaker 1: Hi there.")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_install_requires_a_token_and_removal_is_blocked_while_the_feature_is_on(self):
        import tempfile
        from unittest import mock

        from cairn import config, models

        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(config, "home", return_value=folder):
            downloads = models.Downloader()
            with self.assertRaises(ValueError):
                downloads.start("diar", "pyannote-3.1")  # no token set yet
            config.save_settings({"hf_token": "hf_abcdefgh12345"})
            with mock.patch.object(models, "diar_installed", return_value=True):
                config.save_settings({"diarize": True})
                with self.assertRaises(ValueError):
                    models.remove("diar", "pyannote-3.1")  # must turn the feature off first
                config.save_settings({"diarize": False})
            with mock.patch.object(models, "diar_dir", return_value=folder / "models" / "diar"):
                (folder / "models" / "diar").mkdir(parents=True)
                (folder / "models" / "diar" / models.MARK).write_text("ok", encoding="utf-8")
                self.assertEqual(models.remove("diar", "pyannote-3.1"), {"ok": True})


class SimpleNamespaceStore:
    def reset_interrupted(self):
        pass


class UnitTest(unittest.TestCase):
    def _queue_with_one_put_back(self, autoprocess):
        import tempfile
        from unittest import mock

        from cairn import jobs, notes

        folder = Path(tempfile.mkdtemp())
        store = notes.Store(folder / "Texts")
        for name, status, date in (("a", "waiting", "2026-10-08T17:00"), ("b", "skipped", "2026-10-08T16:00"),
                                   ("c", "waiting", "2026-10-08T15:00"), ("d", "waiting", "2026-10-08T14:00")):
            audio = folder / (name + ".wav")
            audio.write_bytes(b"x")
            store.save({"id": name, "source": name, "status": status, "date": date, "audio": str(audio)})
        job = jobs.Jobs(store)
        order = []

        def fake(note_id, settings):
            order.append(note_id)
            if note_id == "a":
                job.restore("b")  # put back while the job is running
            note = store.get(note_id)
            note["status"] = "done"
            store.save(note)

        settings = dict(jobs.config.load_settings(), autoprocess=autoprocess)
        with mock.patch.object(job, "_process", side_effect=fake), mock.patch.object(job, "_ready", return_value=True), \
                mock.patch.object(jobs.config, "load_settings", return_value=settings):
            job._one("c")
        return order

    def test_process_now_continues_with_the_queue_when_automatic_processing_is_on(self):
        # chosen first, then everything else that is waiting, including the one put back
        self.assertEqual(self._queue_with_one_put_back(True), ["c", "a", "b", "d"])

    def test_process_now_does_only_that_recording_when_automatic_processing_is_off(self):
        self.assertEqual(self._queue_with_one_put_back(False), ["c"])

    def test_update_check_sees_prereleases(self):
        import io
        from unittest import mock

        from cairn import config, server

        def fake(payload):
            return mock.patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

        app = server.App.__new__(server.App)
        with fake([{"tag_name": "v9.0.0", "prerelease": True, "draft": False}, {"tag_name": "v99.0.0", "draft": True}]):
            result = app.check_update()
        self.assertEqual((result["latest"], result["available"]), ("v9.0.0", True))
        with fake([{"tag_name": "v" + config.VERSION}]):
            self.assertFalse(app.check_update()["available"])
        with fake([]):
            self.assertIsNone(app.check_update()["latest"])

    def test_watcher_runs_daily_upkeep_only_when_idle(self):
        from types import SimpleNamespace
        from unittest import mock

        from cairn import jobs, watch

        calls = []
        idle = {"running": False}
        app = SimpleNamespace(
            jobs=SimpleNamespace(snapshot=lambda: idle, start_privacy=lambda: calls.append("privacy"), start_sync=lambda: calls.append("sync")),
            pocket_state=lambda: {"new": 0}, waiting_count=lambda: 0, purge_pocket=lambda: 0, check_update=lambda: calls.append("update") or {"available": False}, update_info=None)
        with mock.patch.object(watch.config, "load_settings", return_value={"autocheck": True}), mock.patch.object(watch.privacy, "last_report", return_value=None):
            watcher = watch.Watcher(app)
            idle["running"] = True
            watcher.tick(now=10**9)
            self.assertEqual(calls, [])  # never while the user's job runs
            idle["running"] = False
            watcher.tick(now=10**9)
            self.assertEqual(calls, ["update", "privacy"])
            watcher.tick(now=10**9 + 60)
            self.assertEqual(calls, ["update", "privacy"])  # once a day
        calls.clear()
        with mock.patch.object(watch.config, "load_settings", return_value={"autocheck": False}), mock.patch.object(watch.privacy, "last_report", return_value=None):
            watch.Watcher(app).tick(now=10**9)
        self.assertEqual(calls, ["privacy"])  # update check turned off

    def test_watcher_copies_new_recordings_when_the_pocket_is_connected(self):
        from types import SimpleNamespace
        from unittest import mock

        from cairn import watch

        calls = []
        state = {"new": 2}
        app = SimpleNamespace(
            jobs=SimpleNamespace(snapshot=lambda: {"running": False}, start_privacy=lambda: None, start_sync=lambda: calls.append("sync")),
            pocket_state=lambda: state, waiting_count=lambda: 0, purge_pocket=lambda: 0, check_update=lambda: {"available": False}, update_info=None)
        fresh = {"when": "2999-01-01T00:00:00"}
        with mock.patch.object(watch.privacy, "last_report", return_value=fresh):
            with mock.patch.object(watch.config, "load_settings", return_value={"autoimport": True, "autocheck": False}):
                watcher = watch.Watcher(app)
                watcher.tick(now=10**9)
                self.assertEqual(calls, ["sync"])
                watcher.tick(now=10**9 + 30)
                self.assertEqual(calls, ["sync"])  # a failing copy is not retried in a loop
                watcher.tick(now=10**9 + 200)
                self.assertEqual(calls, ["sync", "sync"])
            calls.clear()
            with mock.patch.object(watch.config, "load_settings", return_value={"autoimport": False, "autocheck": False}):
                watch.Watcher(app).tick(now=10**9)
            self.assertEqual(calls, [])  # turned off

    def test_note_writing_reports_its_progress_on_long_recordings(self):
        from unittest import mock

        from cairn import llm

        reply = '{"template": "other", "title": "T", "tldr": "x", "actions": []}'
        seen = []
        with mock.patch.object(llm, "chat", return_value=reply):
            llm.summarize("word " * 7000, "mid", "en", progress=seen.append)
            self.assertEqual(llm.parts_of("word " * 7000), 4)
            self.assertEqual(seen, [0, 1, 2, 3])  # three parts condensed, then the final note
            seen.clear()
            llm.summarize("word " * 300, "mid", "en", progress=seen.append)
            self.assertEqual((llm.parts_of("word " * 300), seen), (1, [0]))

    def test_note_progress_moves_while_the_model_works(self):
        from unittest import mock

        from cairn import jobs, llm

        store = SimpleNamespaceStore()
        j = jobs.Jobs(store)
        j._set(step="summarizing", call=(1, 4, 1000.0, 100.0))
        with mock.patch.object(jobs.time, "time", return_value=1000.0):
            self.assertEqual(j.snapshot()["pct"], 25)  # one call of four done, the next one just started
        with mock.patch.object(jobs.time, "time", return_value=1100.0):
            mid = j.snapshot()["pct"]
        with mock.patch.object(jobs.time, "time", return_value=9999.0):
            late = j.snapshot()["pct"]
        self.assertTrue(25 < mid < late < 50, (mid, late))  # never reaches the next call before it is done
        self.assertNotIn("call", j.snapshot())

    def test_network_guard_blocks_outside_connections(self):
        import subprocess

        code = (
            "import socket, sys; sys.path.insert(0, %r)\n"
            "from cairn import netguard\nnetguard.install()\n"
            "for host in ('1.1.1.1', 'example.com'):\n"
            "    try:\n        socket.create_connection((host, 80), timeout=1)\n    except netguard.NetworkBlocked:\n        print('blocked')\n"
            "with netguard.allow('test'):\n"
            "    try:\n        socket.create_connection(('192.0.2.1', 80), timeout=0.2)\n    except netguard.NetworkBlocked:\n        print('WRONG')\n    except OSError:\n        print('allowed')\n"
            "print(len(netguard.blocked()))\n"
        ) % str(Path(__file__).resolve().parent.parent)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False).stdout.split()
        self.assertEqual(out, ["blocked", "blocked", "allowed", "2"])

    def test_background_service_files(self):
        import plistlib
        import stat

        from cairn import __main__ as entry
        from cairn import config, service

        plist = service.agent_plist()
        self.assertTrue(plist["KeepAlive"] and plist["RunAtLoad"])
        self.assertEqual(plist["ProgramArguments"][-1], "--no-browser")
        info, script = service.app_files()
        self.assertEqual(plistlib.loads(info)["CFBundleExecutable"], "Cairn")
        self.assertIn("service open", script)

        class Stub:
            port, token = 8765, "abc"

        entry.write_url(Stub)
        path = config.home() / "url.txt"
        self.assertEqual(path.read_text().strip(), "http://127.0.0.1:8765/?k=abc")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)

    def test_mp3_duration(self):
        from cairn import pocket

        frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)  # MPEG1 layer III, 128 kbit/s, 44.1 kHz
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(frame * 100)
        seconds = pocket.estimate_duration(f.name)
        os.unlink(f.name)
        self.assertAlmostEqual(seconds, 41700 * 8 / 128000, delta=0.2)

    def test_render_escapes(self):
        from cairn import render

        note = {"id": "x", "title": "<script>alert(1)</script>", "lang": "en", "summary": {"tldr": "<b>x</b>"}}
        out = render.to_html(note)
        self.assertNotIn("<script>alert", out)
        self.assertIn("&lt;b&gt;", out)


    def test_note_fidelity_counts_numbers_and_names_found_in_the_transcript(self):
        from cairn import score

        transcript = "Bonjour, ici Marc Dupont. Le budget est de 12500 francs, livraison le 14 mars à Lausanne."
        good = {"tldr": "Réunion avec Marc Dupont.", "key_points": ["Budget de 12 500 francs", "Livraison le 14 mars à Lausanne"], "actions": []}
        self.assertEqual(score.fidelity(good, transcript), 100)
        invented = dict(good, key_points=["Budget de 99 000 francs", "Livraison le 3 avril à Genève"])
        low = score.fidelity(invented, transcript)
        self.assertTrue(low is not None and low < 60, low)
        spoken = {"tldr": "Point à 11 h.", "key_points": ["Prix de 20 euros", "Équipe de 5 personnes"], "actions": []}
        self.assertEqual(score.fidelity(spoken, "Rendez-vous à onze heures, prix vingt euros, équipe de cinq personnes."), 100)
        clock = {"tldr": "Appel.", "actions": [{"what": "Relancer après 00:11", "when": "vendredi 10:00"}], "key_points": ["Budget 450 euros", "Prix 20 euros"]}
        self.assertEqual(score.fidelity(clock, "Vendredi à 10 heures. Budget 450 euros, prix 20 euros."), 100)
        self.assertIsNone(score.fidelity({"tldr": "Une courte note.", "actions": []}, transcript))  # too few details to tell

    def test_fidelity_is_stored_with_the_note_and_listed_for_older_notes(self):
        from cairn import notes

        store = notes.Store(Path(tempfile.mkdtemp()))
        summary = {"tldr": "Appel avec Sophie Martin.", "key_points": ["Prix 450 euros", "Rendez-vous le 12 mai"], "actions": []}
        store.save({"id": "old", "status": "done", "summary": summary, "clean": "Sophie Martin au téléphone, prix 450 euros, rendez-vous le 12 mai."})
        row = store.light()[0]
        self.assertEqual(row["fidelity"], 100)

    def test_exports_name_both_indicators(self):
        from cairn import render

        note = {"id": "x", "title": "T", "lang": "fr", "clean": "texte", "quality": 61, "fidelity": 92, "summary": {"template": "meeting", "tldr": "Court."}}
        md = render.to_markdown(note)
        self.assertIn("Fidélité de la note au transcript 92 %", md)
        self.assertIn("Confiance de la transcription brute 61 %", md)
        self.assertNotIn("Fiabilité estimée", md)
        page = render.to_html(note, fragment=True)
        self.assertIn("Fidélité de la note au transcript 92 %", page)
        self.assertIn("Confiance de la transcription brute 61 %", page)
        self.assertNotIn("C0392B", page)  # no alarm red on a score

    def test_html_export_design(self):
        from cairn import render

        note = {"id": "x", "title": "T", "lang": "en", "clean": "word " * 30, "quality": 90, "elapsed": 12,
                "models": {"speech": "Whisper large-v3-turbo", "llm": "Qwen3 4B"}, "summary": {"template": "meeting", "tldr": "Short."}}
        page = render.to_html(note)
        self.assertIn("<details", page)
        self.assertIn("Sovereign Pocket AI", page)
        self.assertIn("Qwen3 4B", page)
        mail = render.to_html(note, transcript=False, fragment=True)
        self.assertNotIn("<details", mail)
        self.assertNotIn("<svg", mail)
        self.assertIn("Sovereign Pocket AI", mail)



class PreflightAndWatchdogTest(unittest.TestCase):
    def test_the_model_is_checked_before_any_long_work(self):
        from unittest import mock

        from cairn import llm

        llm._READY.update(model=None, at=0.0)
        llm._CAPABLE.clear()
        with mock.patch.object(llm.config, "install_config", return_value={"llm": "m:8b"}), mock.patch.object(llm, "version", return_value="0.40.11"):
            with mock.patch.object(llm, "available", return_value=False):
                with self.assertRaisesRegex(llm.LLMError, "not running"):
                    llm.preflight()
            with mock.patch.object(llm, "available", return_value=True), mock.patch.object(llm, "models", return_value=[{"name": "other:1b"}]):
                with self.assertRaisesRegex(llm.LLMError, "not installed"):
                    llm.preflight()
            with mock.patch.object(llm, "available", return_value=True), mock.patch.object(llm, "models", return_value=[{"name": "m:8b"}]), \
                    mock.patch.object(llm, "chat", side_effect=llm.LLMError("structured output unavailable")):
                with self.assertRaisesRegex(llm.LLMError, "structured output"):
                    llm.preflight()
            with mock.patch.object(llm, "available", return_value=True), mock.patch.object(llm, "models", return_value=[{"name": "m:8b"}]), \
                    mock.patch.object(llm, "chat", return_value='{"ok": true}') as probe, mock.patch.object(llm, "unload") as unload, \
                    mock.patch.object(llm.machine, "ram_gb", return_value=16.0), mock.patch.object(llm, "version", return_value="0.40.11"):
                llm.preflight()
                llm.preflight()  # answered recently: not asked again
                self.assertEqual(probe.call_count, 1)
                self.assertEqual(probe.call_args.kwargs["num_ctx"], llm._ctx("one two three"))  # same context as a short note: no reload
                unload.assert_called_once()  # 16 GB: the model does not stay loaded beside the speech and speaker models
                llm._READY.update(model=None, at=0.0)
                llm.preflight()  # long after: the server and the model are looked at again, the probe is not repeated
                self.assertEqual(probe.call_count, 1)
                with mock.patch.object(llm, "version", return_value="0.41.0"):
                    llm._READY.update(model=None, at=0.0)
                    llm.preflight()  # a new server version: tried again
                    self.assertEqual(probe.call_count, 2)
        llm._READY.update(model=None, at=0.0)

    def test_a_failed_check_stops_the_queue_before_anything_is_started(self):
        import time
        from unittest import mock

        from cairn import jobs, llm, notes as notes_module

        folder = Path(tempfile.mkdtemp())
        store = notes_module.Store(folder / "Texts")
        audio = folder / "a.wav"
        audio.write_bytes(b"x")
        store.save({"id": "a", "source": "a", "status": "waiting", "date": "2026-10-08T17:00", "audio": str(audio)})
        job = jobs.Jobs(store)
        with mock.patch.object(jobs.llm, "preflight", side_effect=llm.LLMError("Ollama is not running")), \
                mock.patch.object(job, "_process") as process:
            job._drain({}, automatic=True)
        process.assert_not_called()
        self.assertEqual(store.get("a")["status"], "waiting")  # untouched: not marked as failed
        self.assertIn("Ollama is not running", job.snapshot()["errors"][0])
        self.assertGreater(job.llm_blocked_until, time.time() + 100)

    def test_automatic_processing_waits_while_the_model_server_is_down(self):
        from types import SimpleNamespace
        from unittest import mock

        from cairn import watch

        calls = []
        jobs_ns = SimpleNamespace(snapshot=lambda: {"running": False}, start_privacy=lambda: None, start_sync=lambda: None,
                                  start_queue=lambda: calls.append("queue"), paused=False, llm_blocked_until=10**9 + 100)
        app = SimpleNamespace(jobs=jobs_ns, pocket_state=lambda: {"new": 0}, waiting_count=lambda: 3, purge_pocket=lambda: 0,
                              check_update=lambda: {"available": False}, update_info=None)
        with mock.patch.object(watch.privacy, "last_report", return_value={"when": "2999-01-01T00:00:00"}), \
                mock.patch.object(watch.config, "load_settings", return_value={"autoimport": True, "autocheck": False, "autoprocess": True}):
            watcher = watch.Watcher(app)
            watcher.tick(now=10**9)
            self.assertEqual(calls, [])
            watcher.tick(now=10**9 + 200)
            self.assertEqual(calls, ["queue"])

    def test_a_call_to_the_model_that_never_answers_is_named(self):
        from unittest import mock

        from cairn import llm

        with mock.patch.object(llm, "_post", side_effect=TimeoutError("timed out")), \
                mock.patch.object(llm.config, "install_config", return_value={"llm": "m"}):
            with self.assertRaisesRegex(llm.LLMError, "did not answer"):
                llm.chat("s", "u", timeout=60)

    def _stuck_engine(self, **limits):
        import subprocess
        import sys
        from unittest import mock

        from cairn import speech

        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        speech._WORKER["proc"] = proc
        folder = Path(tempfile.mkdtemp())
        try:
            with mock.patch.object(speech, "_worker", return_value=proc), mock.patch.multiple(speech, **limits):
                if "STALL_SECONDS" in limits:
                    (folder / "progress").write_text("0.2000")  # it moved once, then nothing
                return speech._run("mlx", "m", "a.wav", str(folder / "out.json"), str(folder / "progress"), None)
        finally:
            proc.kill()
            speech._WORKER["proc"] = None

    def test_a_speech_engine_that_stops_moving_is_cut_off(self):
        from cairn import speech

        with self.assertRaisesRegex(RuntimeError, "did not answer"):
            self._stuck_engine(STALL_SECONDS=1)

    def test_a_speech_engine_that_never_reports_is_cut_off_at_the_cap(self):
        with self.assertRaisesRegex(RuntimeError, "did not answer"):
            self._stuck_engine(NO_PROGRESS_CAP=1)

    def test_the_computer_is_kept_awake_only_while_jobs_run(self):
        from unittest import mock

        from cairn import awake

        with mock.patch.object(awake.sys, "platform", "darwin"), mock.patch.object(awake.shutil, "which", return_value="/usr/bin/caffeinate"), \
                mock.patch.object(awake.subprocess, "Popen") as popen:
            awake.hold()
            awake.hold()
            self.assertEqual(popen.call_count, 1)
            awake.release()
            popen.return_value.terminate.assert_not_called()
            awake.release()
            popen.return_value.terminate.assert_called_once()
        with mock.patch.object(awake.sys, "platform", "linux"), mock.patch.object(awake.subprocess, "Popen") as popen:
            awake.hold()
            awake.release()
            popen.assert_not_called()


class RetryAndResumeTest(unittest.TestCase):
    def _jobs(self, **notes):
        from cairn import jobs, notes as notes_module

        folder = Path(tempfile.mkdtemp())
        store = notes_module.Store(folder / "Texts")
        for name, fields in notes.items():
            audio = folder / (name + ".wav")
            audio.write_bytes(b"x")
            store.save(dict({"id": name, "source": name, "status": "waiting", "date": "2026-10-08T17:00", "audio": str(audio)}, **fields))
        return jobs.Jobs(store), store

    def test_automatic_retries_are_limited_and_spaced_but_asking_by_hand_always_works(self):
        import time
        from unittest import mock

        from cairn import jobs

        job, store = self._jobs(
            fresh={"status": "waiting"},
            soon={"status": "error", "attempts": 1, "retry_after": time.time() + 600},
            due={"status": "error", "attempts": 1, "retry_after": time.time() - 5},
            given_up={"status": "error", "attempts": jobs.AUTO_ATTEMPTS, "retry_after": 0},
        )
        seen = []

        def fake(note_id, settings):
            seen.append(note_id)
            note = store.get(note_id)
            note["status"] = "done"
            store.save(note)

        with mock.patch.object(job, "_process", side_effect=fake), mock.patch.object(job, "_ready", return_value=True):
            job._drain({}, automatic=True)
        self.assertEqual(sorted(seen), ["due", "fresh"])
        job2, store = self._jobs(given_up={"status": "error", "attempts": 9, "retry_after": time.time() + 9999})
        seen.clear()
        with mock.patch.object(job2, "_process", side_effect=fake), mock.patch.object(job2, "_ready", return_value=True):
            job2._drain({})  # the person pressed the button
        self.assertEqual(seen, ["given_up"])

    def test_a_failure_counts_and_delays_the_next_automatic_try(self):
        import time
        from unittest import mock

        from cairn import jobs

        job, store = self._jobs(a={"status": "waiting"})
        with mock.patch.object(jobs.speech, "model_key", return_value="k"), \
                mock.patch.object(jobs.speech, "transcribe", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                job._process("a", {"ui": "en"})
        note = store.get("a")
        self.assertEqual((note["status"], note["attempts"], note["error"]), ("error", 1, "boom"))
        self.assertGreater(note["retry_after"], time.time() + jobs.RETRY_DELAY - 5)

    def _resume(self, saved, spoken=None):
        from unittest import mock

        from cairn import jobs

        segments = [{"start": 0.0, "end": 2.0, "text": "Hello there everyone today.", "logprob": -0.2}]
        job, store = self._jobs(a=dict({"status": "error", "error": "boom", "attempts": 1, "segments": segments, "duration": 2.0,
                                        "lang": "en", "speech_lang": spoken}, **saved))
        calls = []

        def transcribe(*args, **kwargs):
            calls.append(1)
            return {"language": "en", "segments": segments, "duration": 2.0}

        with mock.patch.object(jobs.speech, "model_key", return_value="mlx:large"), \
                mock.patch.object(jobs.speech, "model_name", return_value="Whisper"), \
                mock.patch.object(jobs.speech, "transcribe", side_effect=transcribe), \
                mock.patch.object(jobs.config, "install_config", return_value={"llm": "m"}), \
                mock.patch.object(job, "_summarize"):
            job._process("a", {"ui": "en", "diarize": False})
        return calls, store.get("a")

    def test_the_speech_engine_is_freed_after_a_transcription_only_on_a_small_computer(self):
        from unittest import mock

        from cairn import jobs

        for gb, expected in ((16.0, 1), (32.0, 0)):
            job, store = self._jobs(a={"status": "waiting"})
            segments = [{"start": 0.0, "end": 2.0, "text": "Hello there everyone today.", "logprob": -0.2}]
            with mock.patch.object(jobs.speech, "model_key", return_value="k"), mock.patch.object(jobs.speech, "model_name", return_value="W"), \
                    mock.patch.object(jobs.speech, "transcribe", return_value={"language": "en", "segments": segments, "duration": 2.0}), \
                    mock.patch.object(jobs.speech, "shutdown") as shutdown, mock.patch.object(jobs.system, "ram_gb", return_value=gb), \
                    mock.patch.object(jobs.config, "install_config", return_value={"llm": "m"}), mock.patch.object(job, "_summarize"):
                job._process("a", {"ui": "en", "diarize": False})
            self.assertEqual(shutdown.call_count, expected)

    def test_a_transcript_already_made_with_this_model_is_not_made_again(self):
        calls, note = self._resume({"transcribed_key": "mlx:large", "transcribed_lang": ""})
        self.assertEqual(calls, [])
        self.assertEqual(note["status"], "done")
        self.assertEqual(note["timings"]["reused"], ["transcribing"])
        self.assertNotIn("attempts", note)

    def test_a_transcript_is_made_again_when_the_model_or_the_language_changed(self):
        self.assertEqual(len(self._resume({"transcribed_key": "mlx:turbo", "transcribed_lang": ""})[0]), 1)
        self.assertEqual(len(self._resume({"transcribed_key": "mlx:large", "transcribed_lang": "fr"})[0]), 1)
        self.assertEqual(len(self._resume({})[0]), 1)  # a note made before this was recorded: not trusted


class DiarizeDeviceTest(unittest.TestCase):
    def test_graphics_chip_only_when_allowed_and_available(self):
        from cairn import diarize_worker

        self.assertEqual(diarize_worker.choose_device("auto", True), "mps")
        self.assertEqual(diarize_worker.choose_device("auto", False), "cpu")
        self.assertEqual(diarize_worker.choose_device("cpu", True), "cpu")
        self.assertEqual(diarize_worker.choose_device("whatever", True), "mps")

    def test_setting_defaults_to_auto_and_is_validated(self):
        from unittest import mock

        from cairn import config

        with mock.patch.object(config, "home", return_value=Path(tempfile.mkdtemp())):
            self.assertEqual(config.load_settings()["diarize_device"], "auto")
            self.assertEqual(config.save_settings({"diarize_device": "cpu"})["diarize_device"], "cpu")
            with self.assertRaises(ValueError):
                config.save_settings({"diarize_device": "tpu"})
            self.assertEqual(config.load_settings()["diarize_device"], "cpu")

    def test_the_choice_reaches_the_speaker_program(self):
        from unittest import mock

        from cairn import diarize

        seen = {}

        class FakeProc:
            returncode = 0

            def __init__(self, *args, **kwargs):
                seen.update(kwargs["env"])

            def communicate(self, timeout=None):
                return "[]", ""

        for saved, expected in (({"diarize_device": "cpu"}, "cpu"), ({}, "auto"), ({"diarize_device": "x"}, "auto")):
            with mock.patch.object(diarize.models, "diar_installed", return_value=True), \
                    mock.patch.object(diarize.config, "load_settings", return_value=saved), \
                    mock.patch.object(diarize.subprocess, "Popen", FakeProc):
                self.assertEqual(diarize.run("a.mp3")[0], "ok")
            self.assertEqual(seen["CAIRN_DIARIZE_DEVICE"], expected)


class VocabularyTest(unittest.TestCase):
    def test_entries_are_parsed_and_bounded(self):
        from cairn import vocab

        self.assertEqual(vocab.parse("Acme\nSpringfield; Acme, Yverdon\n\n  Gros-de-Vaud "), ["Acme", "Springfield", "Yverdon", "Gros-de-Vaud"])
        self.assertEqual(vocab.parse(["A name", "a name"]), ["A name"])
        self.assertEqual(vocab.parse(""), [])
        with self.assertRaises(ValueError):
            vocab.parse("x" * 61)
        with self.assertRaises(ValueError):
            vocab.parse([str(i) + "abcd" for i in range(vocab.MAX_TERMS + 1)])
        with self.assertRaises(ValueError):
            vocab.parse(12)

    def test_close_variants_are_corrected_and_other_words_are_not(self):
        from cairn import vocab

        fixed = lambda terms, text: vocab.fix_text(text, terms)[0]
        self.assertEqual(fixed(["Acme"], "The Sion awards"), "The Acme awards")
        self.assertEqual(fixed(["Springfield"], "à Eschalens et Échalens"), "à Springfield et Springfield")
        self.assertEqual(fixed(["Globex"], "chez Kudelsky et Koudelski"), "chez Globex et Globex")
        self.assertEqual(fixed(["Yverdon"], "à Iverdon"), "à Yverdon")
        # a different name, a common word, a word that already is the entry: left alone
        self.assertEqual(fixed(["Laurent"], "Laurence et Laurent"), "Laurence et Laurent")
        self.assertEqual(fixed(["Lise"], "les enfants"), "les enfants")
        self.assertEqual(fixed(["Marc"], "mars et Marc"), "mars et Marc")
        self.assertEqual(fixed(["Acme"], "Acme et acme"), "Acme et acme")

    def test_exact_rules_always_apply(self):
        from cairn import vocab

        text, found = vocab.fix_text("à Sion puis sion encore", ["Sion => Acme"])
        self.assertEqual(text, "à Acme puis Acme encore")
        self.assertEqual(len(found), 2)
        self.assertEqual(vocab.spellings(["Sion => Acme", "Springfield", "Acme"]), ["Acme", "Springfield"])

    def test_the_original_is_kept_and_comes_back_when_an_entry_is_removed(self):
        from cairn import vocab

        segments = [{"start": 0, "end": 2, "text": "The Sion awards"}, {"start": 2, "end": 4, "text": "nothing here"}]
        fixes = vocab.apply(segments, ["Acme"])
        self.assertEqual(fixes, [{"from": "Sion", "to": "Acme", "count": 1}])
        self.assertEqual((segments[0]["text"], segments[0]["orig"]), ("The Acme awards", "The Sion awards"))
        self.assertNotIn("orig", segments[1])
        self.assertEqual(vocab.apply(segments, ["Acme"]), fixes)  # running it again changes nothing
        self.assertEqual(vocab.apply(segments, []), [])
        self.assertEqual(segments[0]["text"], "The Sion awards")
        self.assertNotIn("orig", segments[0])

    def test_the_setting_is_validated_and_the_summary_is_given_the_spellings(self):
        from unittest import mock

        from cairn import config, llm

        with mock.patch.object(config, "home", return_value=Path(tempfile.mkdtemp())):
            self.assertEqual(config.load_settings()["vocabulary"], [])
            self.assertEqual(config.save_settings({"vocabulary": "Acme\nSion => Acme"})["vocabulary"], ["Acme", "Sion => Acme"])
            with self.assertRaises(ValueError):
                config.save_settings({"vocabulary": "x" * 99})
        seen = []
        with mock.patch.object(llm, "chat", side_effect=lambda system, *a, **k: seen.append(system) or '{"title": "T", "tldr": "x", "actions": []}'):
            llm.summarize("one two three four five six", "mid", "en", vocabulary=["Acme", "Springfield"])
            llm.summarize("one two three four five six", "mid", "en")
        self.assertIn("Acme; Springfield", seen[0])
        self.assertNotIn("Spell these names", seen[1])

    def test_corrections_are_kept_with_the_note_and_speaker_names_survive(self):
        from unittest import mock

        from cairn import jobs

        segments = [{"start": 0.0, "end": 2.0, "text": "The Sion awards today.", "logprob": -0.2, "speaker": "Speaker 1"}]
        job, store = RetryAndResumeTest()._jobs(a={"status": "done", "segments": segments, "duration": 2.0, "lang": "en",
                                                   "transcribed_key": "k", "transcribed_lang": "", "speaker_names": {"Speaker 1": "Marc"}})
        with mock.patch.object(jobs.speech, "model_key", return_value="k"), mock.patch.object(jobs.speech, "model_name", return_value="W"), \
                mock.patch.object(jobs.config, "install_config", return_value={"llm": "m"}), mock.patch.object(job, "_summarize"):
            job._process("a", {"ui": "en", "diarize": False, "vocabulary": ["Acme"]})
        note = store.get("a")
        self.assertEqual(note["vocab_fixes"], [{"from": "Sion", "to": "Acme", "count": 1}])
        self.assertIn("Marc: The Acme awards today.", note["clean"])
        self.assertEqual(note["segments"][0]["orig"], "The Sion awards today.")
        self.assertEqual(note["timings"]["reused"], ["transcribing"])

    def test_a_changed_vocabulary_redoes_the_words_without_transcribing_again(self):
        from unittest import mock

        from cairn import jobs, vocab

        job, store = RetryAndResumeTest()._jobs(a={"status": "done", "segments": [{"start": 0, "end": 1, "text": "x"}], "vocab_key": vocab.key([]),
                                                   "models": {"speech": "W"}, "speech_lang_used": None, "level": "mid", "lang": "en"})
        started = []
        for terms, expected in ((["Acme"], "_one"), ([], "_rerun")):
            started.clear()
            with mock.patch.object(jobs.speech, "model_name", return_value="W"), mock.patch.object(jobs.config, "load_settings", return_value={"vocabulary": terms}), \
                    mock.patch.object(job, "_start", side_effect=lambda kind, target, *a: started.append(target.__name__)):
                self.assertFalse(job.start_rerun("a", "mid"))  # False: the audio is not transcribed again
            self.assertEqual(started, [expected])


class SpeedTest(unittest.TestCase):
    def test_a_speaker_pass_can_be_stopped_at_once(self):
        import subprocess
        import sys
        import threading
        import time
        from unittest import mock

        from cairn import diarize

        real = subprocess.Popen
        result = []
        with mock.patch.object(diarize.models, "diar_installed", return_value=True), \
                mock.patch.object(diarize.config, "load_settings", return_value={}), \
                mock.patch.object(diarize.subprocess, "Popen", lambda *a, **k: real([sys.executable, "-c", "import time; time.sleep(60)"], **{x: y for x, y in k.items() if x in ("stdout", "stderr", "text")})):
            began = time.time()
            worker = threading.Thread(target=lambda: result.append(diarize.run("a.mp3", 900)))
            worker.start()
            time.sleep(0.5)
            diarize.abort()
            worker.join(10)
        self.assertEqual(result, [("none", None)])
        self.assertLess(time.time() - began, 10)

    def test_automatic_processing_starts_as_soon_as_the_copy_is_done(self):
        from unittest import mock

        from cairn import jobs

        for auto, expected in ((True, 1), (False, 0)):
            job, store = RetryAndResumeTest()._jobs()
            with mock.patch.object(jobs.pocket, "find_pocket", return_value=None), \
                    mock.patch.object(jobs.config, "load_settings", return_value={"autoprocess": auto}), mock.patch.object(job, "_drain") as drain:
                job._import(False)
            self.assertEqual(drain.call_count, expected)

    def test_the_model_stays_loaded_between_notes_only_with_enough_memory(self):
        from unittest import mock

        from cairn import llm

        sent = []
        for gb, expected in ((32.0, "30m"), (16.0, None)):
            with mock.patch.object(llm.machine, "ram_gb", return_value=gb), mock.patch.object(llm, "_post", side_effect=lambda path, body, timeout=0: sent.append(body) or {"message": {"content": "{}"}}), \
                    mock.patch.object(llm.config, "install_config", return_value={"llm": "m"}):
                llm.chat("s", "u")
            self.assertEqual(sent[-1].get("keep_alive"), expected)


class ListingCacheTest(unittest.TestCase):
    def test_a_rewrite_with_the_same_size_and_timestamp_is_still_seen(self):
        import os

        from cairn import notes

        folder = Path(tempfile.mkdtemp())
        store = notes.Store(folder / "Texts")
        store.save({"id": "a", "source": "a", "status": "skipped", "date": "2026-10-08T17:00", "audio": ""})
        self.assertEqual([n["status"] for n in store.slim()], ["skipped"])
        path = next((folder / "Texts").glob("*.json"))
        before = path.stat().st_mtime_ns
        store.save({"id": "a", "source": "a", "status": "waiting", "date": "2026-10-08T17:00", "audio": ""})  # same length: "skipped" and "waiting"
        os.utime(path, ns=(before, before))  # a file system with a coarse clock: the timestamp did not move
        self.assertEqual(path.stat().st_size, len(path.read_bytes()))
        self.assertEqual([n["status"] for n in store.slim()], ["waiting"])


class FailureMessagesTest(unittest.TestCase):
    def test_a_recording_interrupted_while_identifying_speakers_goes_back_to_waiting(self):
        from cairn import notes

        with tempfile.TemporaryDirectory() as tmp:
            store = notes.Store(Path(tmp) / "Texts")
            for name, status in (("a", "diarizing"), ("b", "summarizing"), ("c", "done"), ("d", "error")):
                store.save({"id": name, "source": name, "status": status, "step": status, "date": "2026-10-27T10:00", "audio": ""})
            store.reset_interrupted()
            self.assertEqual({n: store.get(n)["status"] for n in "abcd"}, {"a": "waiting", "b": "waiting", "c": "done", "d": "error"})
            self.assertEqual(store.get("a")["step"], "")

    def test_a_model_without_structured_output_is_named_as_such(self):
        import io
        import urllib.error
        from unittest import mock

        from cairn import llm

        refusal = urllib.error.HTTPError("http://127.0.0.1:11434/api/chat", 501, "Not Implemented", {},
                                         io.BytesIO(b'{"error":"structured output is unavailable"}'))
        with mock.patch.object(llm, "_post", side_effect=refusal), \
                mock.patch.object(llm.config, "install_config", return_value={"llm": "some:9b"}):
            with self.assertRaises(llm.LLMError) as caught:
                llm.chat("system", "user", schema={"type": "object"})
        self.assertIn("structured output", str(caught.exception))
        self.assertNotIn("not reachable", str(caught.exception))

    def test_speaker_turns_from_both_pyannote_result_shapes(self):
        from types import SimpleNamespace

        from cairn import diarize_worker

        class Annotation:
            def itertracks(self, yield_label=False):
                return iter([(SimpleNamespace(start=0.0, end=1.234), None, "SPEAKER_00"),
                             (SimpleNamespace(start=1.5, end=3.0), None, "SPEAKER_01")])

        expected = [{"start": 0.0, "end": 1.23, "speaker": "SPEAKER_00"}, {"start": 1.5, "end": 3.0, "speaker": "SPEAKER_01"}]
        self.assertEqual(diarize_worker.speaker_turns(Annotation()), expected)  # pyannote 3
        self.assertEqual(diarize_worker.speaker_turns(SimpleNamespace(speaker_diarization=Annotation())), expected)  # pyannote 4


class AboutHelpersTest(unittest.TestCase):
    def test_ollama_version_installed_and_running(self):
        from cairn import llm
        self.assertEqual(llm.parse_ollama_version("ollama version is 0.40.11\n"), ("0.40.11", ""))
        # a server started before an upgrade: the installed program is newer than the one running
        self.assertEqual(llm.parse_ollama_version("ollama version is 0.40.10\nWarning: client version is 0.40.11\n"), ("0.40.11", "0.40.10"))
        self.assertEqual(llm.parse_ollama_version("nothing useful"), ("-", ""))

    def test_summary_model_is_named_by_family(self):
        from cairn import catalog, server
        entry = lambda i: next(m for m in catalog.LLM if m["id"] == i)
        self.assertEqual(server._llm_component("qwen3:8b", entry("qwen3:8b"), 5)["name"], "Qwen3")
        self.assertEqual(server._llm_component("qwen3:8b", entry("qwen3:8b"), 5)["ver"], "8B")
        qwen35 = server._llm_component("qwen3.5:9b", {"label": "Qwen3.5 9B"}, 7)
        self.assertEqual((qwen35["name"], qwen35["ver"]), ("Qwen3.5", "9B"))
        self.assertEqual(server._llm_component("mine:1b", None, 0)["ok"], False)

    def test_size_counts_real_files_once(self):
        from cairn import models
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "blobs"
            blob.mkdir()
            (blob / "w").write_bytes(b"x" * 1000)
            snap = Path(tmp) / "snapshots"
            snap.mkdir()
            os.symlink(blob / "w", snap / "link")
            self.assertEqual(models.dir_size(tmp), 1000)


class LibraryTest(unittest.TestCase):
    """Search across notes, listening to a recording, the list of all actions, the follow-up email."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        os.environ.update(CAIRN_HOME=str(root / "Cairn"), CAIRN_POCKET_DIR=str(root / "none"), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=str(root))
        from cairn import server

        cls.server = server
        cls.app, cls.httpd = server.make_server(18790)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app, cls.httpd)
        audio = root / "Cairn" / "Audio"
        audio.mkdir(parents=True)
        cls.wav = audio / "a.wav"
        tone(cls.wav, seconds=2)
        cls.app.store.save({
            "id": "a", "status": "done", "title": "Appel Acme", "date": "2026-10-01T10:00:00", "lang": "fr", "audio": str(cls.wav),
            "summary": {"template": "call", "title": "Appel Acme", "tldr": "Budget de 300 000 francs approuv\u00e9",
                        "actions": [{"what": "Envoyer le plan", "who": "Sophie", "when": "vendredi"}, {"what": "Appeler le fournisseur", "who": "Marc"}],
                        "key_points": ["Certification en retard"], "decisions": ["Lancement en mars"]},
            "segments": [{"start": 12.0, "end": 15.0, "text": "On a vu l'association Acme \u00e0 \u00c9vian", "speaker": "Speaker 1"}],
            "speaker_names": {"Speaker 1": "Marc"}})
        cls.app.store.save({
            "id": "b", "status": "done", "title": "Point projet", "date": "2026-10-05T10:00:00", "lang": "en", "audio": str(root / "gone.wav"),
            "summary": {"template": "meeting", "title": "Point projet", "tldr": "Nothing special", "actions": [{"what": "Envoyer le plan", "who": "Sophie"}]},
            "segments": [{"start": 1.0, "end": 2.0, "text": "Hello everyone"}]})
        cls.app.store.save({"id": "w", "status": "waiting", "title": "", "date": "2026-10-06T10:00:00", "audio": str(cls.wav)})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def raw(self, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.c.port, timeout=30)
        conn.request("GET", path, None, dict({"Host": "127.0.0.1:%d" % self.c.port, "Cookie": self.c.cookie}, **(headers or {})))
        resp = conn.getresponse()
        data = resp.read()
        out = (resp.status, dict(resp.getheaders()), data)
        conn.close()
        return out

    def test_search_ignores_accents_and_needs_every_word(self):
        status, body = self.c.call("GET", "/api/search?q=evian+acme")
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in body["results"]], ["a"])
        hit = body["results"][0]["hits"][0]
        self.assertEqual(hit["where"], "transcript")
        self.assertEqual(hit["start"], 12.0)
        self.assertIn("Marc", "".join(p["t"] for p in hit["parts"]))  # the speaker's chosen name is searched, not the raw label
        self.assertEqual({p["t"].lower() for p in hit["parts"] if p["m"]}, {"acme", "\u00e9vian"})
        self.assertEqual(self.c.call("GET", "/api/search?q=evian+nothingelse")[1]["results"], [])
        self.assertEqual(self.c.call("GET", "/api/search?q=")[1]["results"], [])

    def test_search_ranks_titles_first_and_skips_unfinished_notes(self):
        ids = [r["id"] for r in self.c.call("GET", "/api/search?q=sophie")[1]["results"]]
        self.assertEqual(sorted(ids), ["a", "b"])
        self.assertNotIn("w", [r["id"] for r in self.c.call("GET", "/api/search?q=acme")[1]["results"]])
        self.assertEqual(self.c.call("GET", "/api/search?q=acme")[1]["results"][0]["id"], "a")

    def test_search_needs_the_session(self):
        self.assertEqual(self.c.call("GET", "/api/search?q=acme", cookie=False)[0], 403)

    def test_audio_is_served_whole_and_by_range(self):
        size = self.wav.stat().st_size
        whole = self.wav.read_bytes()
        status, head, data = self.raw("/api/note/a/audio")
        self.assertEqual((status, data), (200, whole))
        self.assertEqual(head["Accept-Ranges"], "bytes")
        self.assertEqual(head["Content-Type"], "audio/wav")
        status, head, data = self.raw("/api/note/a/audio", {"Range": "bytes=100-199"})
        self.assertEqual((status, data), (206, whole[100:200]))
        self.assertEqual(head["Content-Range"], "bytes 100-199/%d" % size)
        status, _, data = self.raw("/api/note/a/audio", {"Range": "bytes=-50"})
        self.assertEqual((status, data), (206, whole[-50:]))
        status, _, data = self.raw("/api/note/a/audio", {"Range": "bytes=%d-" % (size - 10)})
        self.assertEqual((status, data), (206, whole[-10:]))
        self.assertEqual(self.raw("/api/note/a/audio", {"Range": "bytes=%d-" % (size + 5)})[0], 416)

    def test_audio_missing_or_not_audio_is_not_served(self):
        self.assertEqual(self.raw("/api/note/b/audio")[0], 404)
        note = self.app.get_note("a")
        secret = Path(self.tmp.name) / "secret.txt"
        secret.write_text("private")
        self.app.store.save(dict(note, id="c", audio=str(secret)))
        self.assertEqual(self.raw("/api/note/c/audio")[0], 404)
        self.app.store.delete("c")
        self.assertEqual(self.c.call("GET", "/api/note/a/audio", cookie=False)[0], 403)

    def test_note_says_whether_its_audio_is_there(self):
        self.assertTrue(self.c.call("GET", "/api/note/a")[1]["has_audio"])
        self.assertFalse(self.c.call("GET", "/api/note/b")[1]["has_audio"])
        self.assertNotIn("has_audio", self.app.store.get("a"))  # a view of the note, never saved with it

    def test_all_actions_newest_note_first_and_ticked_ones_are_kept(self):
        actions = self.c.call("GET", "/api/actions")[1]["actions"]
        self.assertEqual([(a["note"], a["what"]) for a in actions], [("b", "Envoyer le plan"), ("a", "Envoyer le plan"), ("a", "Appeler le fournisseur")])
        self.assertEqual(actions[1]["who"], "Sophie")
        self.assertEqual(self.c.call("POST", "/api/note/a/action", {"what": "Envoyer le plan", "done": True})[0], 200)
        actions = self.c.call("GET", "/api/actions")[1]["actions"]
        self.assertEqual([a["done"] for a in actions], [False, True, False])  # only that note's action is ticked
        self.c.call("POST", "/api/note/a/action", {"what": "Envoyer le plan", "done": False})
        self.assertFalse(any(a["done"] for a in self.c.call("GET", "/api/actions")[1]["actions"]))
        self.assertEqual(self.c.call("POST", "/api/note/a/action", {"what": ""})[0], 400)

    def test_follow_up_email_is_written_once_and_redone_on_request(self):
        from cairn import llm
        calls = []

        def fake_chat(system, user, schema=None, **kw):
            calls.append((system, user))
            return json.dumps({"subject": "Suite %d" % len(calls), "body": "Bonjour,\n\nMerci."})

        keep = (llm.chat, llm.preflight)
        llm.chat, llm.preflight = fake_chat, lambda *a, **k: None
        try:
            status, mail = self.c.call("POST", "/api/note/a/followup")
            self.assertEqual((status, mail["subject"]), (200, "Suite 1"))
            self.assertIn("French", calls[0][0])  # written in the language of the note
            self.assertIn("Sophie", calls[0][1])
            self.assertEqual(self.c.call("POST", "/api/note/a/followup")[1]["subject"], "Suite 1")  # kept with the note
            self.assertEqual(len(calls), 1)
            self.assertEqual(self.c.call("POST", "/api/note/a/followup", {"redo": True})[1]["subject"], "Suite 2")
            self.assertEqual(self.c.call("POST", "/api/note/w/followup")[0], 400)  # nothing to write about yet

            def broken(*a, **k):
                raise llm.LLMError("model down")

            llm.preflight = broken
            self.assertEqual(self.c.call("POST", "/api/note/b/followup")[0], 503)
        finally:
            llm.chat, llm.preflight = keep


if __name__ == "__main__":
    unittest.main()
