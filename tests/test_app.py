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

    def test_07_settings(self):
        self.assertEqual(self.c.call("POST", "/api/settings", {"ui": "fr", "tr": "en", "level": "full"})[0], 200)
        _, st = self.c.call("GET", "/api/state")
        self.assertEqual((st["settings"]["ui"], st["settings"]["tr"], st["settings"]["level"]), ("fr", "en", "full"))
        self.assertEqual(self.c.call("POST", "/api/settings", {"ui": "xx"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/settings", {"audio_dir": "relative/path"})[0], 400)

    def test_08_empty_pocket_needs_verified_copies(self):
        _, v = self.c.call("GET", "/api/pocket/verify")
        self.assertEqual((v["total"], v["verified"]), (2, 2))
        self.assertEqual(self.c.call("POST", "/api/pocket/empty", {})[0], 400)
        extra = self.pocket / "unverified.wav"
        tone(extra)
        self.assertEqual(self.c.call("POST", "/api/pocket/empty", {"confirm": True})[0], 409)
        self.assertTrue(extra.exists())
        extra.unlink()
        status, out = self.c.call("POST", "/api/pocket/empty", {"confirm": True})
        self.assertEqual((status, out["deleted"]), (200, 2))
        self.assertEqual(list(self.pocket.rglob("*.wav")), [])

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

    def test_13_web_app_files(self):
        status, _ = self.c.call("GET", "/manifest.webmanifest", cookie=False)
        self.assertEqual(status, 200)
        self.assertEqual(self.c.call("GET", "/icon-192.png", cookie=False)[0], 200)
        self.assertEqual(self.c.call("GET", "/app.js", cookie=False)[0], 403)  # the app itself still needs the session
        from cairn import server

        self.assertEqual(server.session_key(), server.session_key())

    def test_11_about_components(self):
        status, data = self.c.call("GET", "/api/about")
        self.assertEqual(status, 200)
        names = [c["name"] for c in data["components"]]
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertTrue(all({"name", "ver", "size", "ok"} <= set(c) for c in data["components"]))
        self.assertTrue(data["referral"].startswith("https://referral.heypocketai.com/"))
        status, svg = self.c.call("GET", "/referral-qr.svg")
        self.assertEqual(status, 200)


class UnitTest(unittest.TestCase):
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
