"""End-to-end tests of the Cairn app with a stub speech engine and a stub model server.

No network, no model: run with `python -m unittest discover -s tests`.
"""

import http.client
import json
import math
import os
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


class SimpleNamespaceStore:
    def reset_interrupted(self):
        pass


class UnitTest(unittest.TestCase):
    def test_process_now_then_continues_with_the_queue(self):
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

        with mock.patch.object(job, "_process", side_effect=fake):
            job._one("c")  # chosen first, then everything else that is waiting, including the one put back
        self.assertEqual(order, ["c", "a", "b", "d"])

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



if __name__ == "__main__":
    unittest.main()
