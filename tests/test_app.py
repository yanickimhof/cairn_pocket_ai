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
        self._send({"version": "0"} if self.path == "/api/version" else {"models": [{"name": "stub:1b", "size": 1500000000}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
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

        def fake(path):
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


class UnitTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
