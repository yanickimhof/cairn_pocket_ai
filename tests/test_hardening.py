"""Hardening checks from the 0.7 security review: release consistency, installer integrity, network guard, server responses."""
import json
import os
import re
import socket
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ReleaseTest(unittest.TestCase):
    def version(self):
        return re.search(r'VERSION = "([^"]+)"', (ROOT / "cairn" / "config.py").read_text(encoding="utf-8")).group(1)

    def test_installers_and_readme_name_the_release(self):
        tag = "v" + self.version()
        sh = (ROOT / "install.sh").read_text(encoding="utf-8")
        ps = (ROOT / "install.ps1").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('REF="${CAIRN_REF:-%s}"' % tag, sh)
        self.assertIn("Opt 'CAIRN_REF' '%s'" % tag, ps)
        self.assertIn("cairn_pocket_ai/%s/install.sh" % tag, sh)
        self.assertIn("cairn_pocket_ai/%s/install.ps1" % tag, ps)
        self.assertIn("cairn_pocket_ai/%s/install.sh" % tag, readme)
        self.assertIn("cairn_pocket_ai/%s/install.ps1" % tag, readme)

    def test_installers_download_nothing_unverified(self):
        sh = (ROOT / "install.sh").read_text(encoding="utf-8")
        ps = (ROOT / "install.ps1").read_text(encoding="utf-8")
        for text in (sh, ps):
            self.assertNotIn("releases/latest", text)  # a fixed release only
            self.assertNotIn("astral.sh", text)  # no script piped into a shell
        self.assertNotIn("Invoke-Expression", ps)  # nothing downloaded is executed as a script
        self.assertNotIn("| sh", sh.replace("| bash", ""))
        self.assertEqual(len(re.findall(r"sha256_of", sh)), 3)  # defined once, used for uv and for Ollama
        self.assertIn("-ne 'acfde570451cfdb8689fa159a138ee805ba4e241c466432750302c86254b0984'", ps)
        self.assertNotRegex(sh + ps, r"pip install[^\n]*--quiet pyannote")  # speaker identification is installed from a hashed list

    def test_the_first_install_leaves_out_what_the_speech_engine_never_uses(self):
        import re

        base = (ROOT / "requirements" / "mlx-macos-arm64.txt").read_text(encoding="utf-8")
        names = set(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==", base))
        self.assertIn("mlx-whisper", names)
        self.assertIn("pyobjc-framework-localauthentication", names)  # Touch ID needs this macOS component in the environment
        for heavy in ("torch", "sympy", "networkx"):
            self.assertNotIn(heavy, names)  # about 700 MB that only speaker identification needs, installed with it
        diar = set(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==", (ROOT / "requirements" / "diar-macos-arm64.txt").read_text(encoding="utf-8")))
        self.assertIn("torch", diar)
        for path in ("install.sh", "install.ps1"):
            self.assertIn("--require-hashes --no-deps", (ROOT / path).read_text(encoding="utf-8"))  # nothing outside the hashed list is pulled in
        from cairn import models

        self.assertIn("--no-deps", models.Downloader._install_locked.__code__.co_consts)

    def test_speaker_identification_lists_are_hashed(self):
        for name in ("diar-macos-arm64.txt", "diar-windows.txt"):
            text = (ROOT / "requirements" / name).read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^pyannote-audio==4\.0\.7 \\$")
            pins = len(re.findall(r"(?m)^[A-Za-z0-9_.-]+==", text))
            self.assertEqual(pins, len(re.findall(r"(?m)^[A-Za-z0-9_.-]+==[^ ]+ \\$", text)))
            self.assertGreaterEqual(len(re.findall(r"--hash=sha256:", text)), pins)


class GuardTest(unittest.TestCase):
    def test_every_way_out_is_closed(self):
        from cairn import netguard

        netguard.install()
        def datagram(send):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                send(sock)

        for call in (
            lambda: socket.gethostbyname("example.com"),
            lambda: socket.gethostbyname_ex("example.com"),
            lambda: socket.getaddrinfo("example.com", 80),
            lambda: datagram(lambda s: s.sendmsg([b"x"], [], 0, ("93.184.216.34", 9))),
            lambda: datagram(lambda s: s.sendto(b"x", ("93.184.216.34", 9))),
            lambda: socket.create_connection(("93.184.216.34", 80), timeout=1),
        ):
            with self.assertRaises(netguard.NetworkBlocked):
                call()
        socket.gethostbyname("localhost")  # this computer stays reachable


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_app import Client, tone

        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.update(CAIRN_HOME=str(Path(cls.tmp.name) / "Cairn"), CAIRN_ENGINE="mlx")
        from cairn import server

        cls.server = server
        cls.app, cls.httpd = server.make_server(18797)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app, cls.httpd)
        cls.app.store.save({"id": "n", "status": "done", "title": "Point projet", "date": "2026-10-05T10:00:00", "lang": "en",
                            "summary": {"template": "meeting", "title": "Point projet", "tldr": "Nothing special", "actions": []},
                            "segments": [{"start": 1.0, "end": 2.0, "text": "Hello everyone"}]})

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def exports(self):
        return sorted((Path(os.environ["CAIRN_HOME"]) / "Exports").glob("*")) if (Path(os.environ["CAIRN_HOME"]) / "Exports").exists() else []

    def test_a_get_never_writes_to_disk(self):
        status, _ = self.c.call("GET", "/api/note/n/export?fmt=md&save=1")
        self.assertEqual(status, 200)
        self.assertEqual(self.exports(), [])

    def test_the_copy_in_exports_is_written_by_a_post(self):
        status, body = self.c.call("POST", "/api/note/n/export", {"fmt": "md"})
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual([p.name for p in self.exports()], ["Point_projet.md"])
        self.assertEqual(self.c.call("POST", "/api/note/n/export", {"fmt": "pdf"})[0], 400)
        self.assertEqual(self.c.call("POST", "/api/note/n/export", {"fmt": "md"}, headers={"X-Cairn": "0"})[0], 403)

    def test_an_error_page_names_no_exception(self):
        from unittest import mock

        with mock.patch.object(self.app, "state", side_effect=RuntimeError("/Users/someone/secret/path")):
            status, body = self.c.call("GET", "/api/state")
        self.assertEqual((status, body), (500, {"error": "server_error"}))

    def test_the_session_cookie_lasts_thirty_days(self):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=10)
        conn.request("GET", "/?k=" + self.app.token, headers={"Host": "127.0.0.1:%d" % self.app.port})
        resp = conn.getresponse()
        cookie = resp.getheader("Set-Cookie")
        conn.close()
        self.assertEqual(resp.status, 303)
        self.assertIn("Max-Age=%d" % (30 * 86400), cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)


class UploadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_app import Client

        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.update(CAIRN_HOME=str(Path(cls.tmp.name) / "Cairn"), CAIRN_ENGINE="mlx")
        from cairn import server

        cls.app, cls.httpd = server.make_server(18798)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app, cls.httpd)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def send(self, name, data, headers=None, cookie=True):
        import http.client
        from urllib.parse import quote

        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=30)
        hdr = {"Host": "127.0.0.1:%d" % self.app.port, "X-Cairn": "1", "Content-Type": "application/octet-stream",
               "X-Filename": quote(name), "X-Last-Modified": "1760000000000"}
        if cookie:
            hdr["Cookie"] = "cairn_session=" + self.app.token
        hdr.update(headers or {})
        conn.request("POST", "/api/import/file", data, hdr)
        resp = conn.getresponse()
        body = json.loads(resp.read() or b"{}")
        conn.close()
        return resp.status, body

    def wav(self, seconds=1):
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(os.urandom(2 * 8000 * seconds))
        return buf.getvalue()

    def test_a_dropped_file_becomes_a_waiting_note(self):
        status, body = self.send("Réunion 2026-10-12 09-30-00.wav", self.wav(2))
        self.assertEqual((status, body["ok"], body["duplicate"]), (200, True, False))
        note = self.app.store.get(body["id"])
        self.assertEqual((note["status"], note["origin"], note["date"][:10]), ("waiting", "file", "2026-10-12"))
        self.assertTrue(Path(note["audio"]).is_file())
        self.assertNotIn("source", note)  # not a Pocket recording: deleting it never touches a Pocket
        self.assertAlmostEqual(note["duration"], 2.0, places=1)

    def test_the_same_file_is_not_added_twice(self):
        data = self.wav(1)
        first = self.send("a.wav", data)[1]
        second = self.send("b.wav", data)[1]
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["id"], second["id"])

    def test_only_real_audio_is_taken(self):
        self.assertEqual(self.send("notes.txt", b"hello")[0], 415)
        self.assertEqual(self.send("fake.wav", b"MZ" + b"x" * 100)[0], 415)  # a program renamed .wav
        self.assertEqual(self.send("empty.wav", b"")[0], 400)
        left = list((Path(os.environ["CAIRN_HOME"]) / "Audio" / "Imported").glob(".upload-*"))
        self.assertEqual(left, [])  # nothing is left behind by a refused file

    def test_the_name_cannot_leave_the_audio_folder(self):
        from cairn import upload

        for hostile in ("../../etc/passwd.wav", "..\\..\\x.wav", "/abs/path/x.wav", "con.wav", "x.wav.exe"):
            name = upload.safe_name(hostile)
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertEqual(name, Path(name).name)  # one plain file name, nothing that points elsewhere
            self.assertFalse(name.startswith("."))
        self.assertEqual(upload.safe_name("x.wav.exe"), "")
        status, body = self.send("../../escape.wav", self.wav(1))
        note = self.app.store.get(body["id"])
        self.assertEqual(Path(note["audio"]).parent.name, "Imported")

    def test_it_needs_the_same_guards_as_any_change(self):
        data = self.wav(1)
        self.assertEqual(self.send("g.wav", data, cookie=False)[0], 403)
        self.assertEqual(self.send("g.wav", data, headers={"X-Cairn": "0"})[0], 403)
        self.assertEqual(self.send("g.wav", data, headers={"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(self.send("g.wav", data, headers={"Host": "evil.example:80"})[0], 403)

    def test_a_cut_upload_leaves_nothing(self):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=5)
        conn.putrequest("POST", "/api/import/file")
        for k, v in {"Host": "127.0.0.1:%d" % self.app.port, "X-Cairn": "1", "Content-Type": "application/octet-stream", "X-Filename": "cut.wav",
                     "Content-Length": "100000", "Cookie": "cairn_session=" + self.app.token}.items():
            conn.putheader(k, v)
        conn.endheaders()
        conn.send(self.wav(1)[:5000])
        conn.sock.shutdown(1)
        resp = conn.getresponse()
        self.assertEqual(resp.status, 400)
        conn.close()
        folder = Path(os.environ["CAIRN_HOME"]) / "Audio" / "Imported"
        self.assertEqual([p.name for p in folder.glob("*cut*")] + list(folder.glob(".upload-*")), [])


class SetupTest(unittest.TestCase):
    def run_check(self, **patches):
        from unittest import mock

        from cairn import setup

        with tempfile.TemporaryDirectory() as tmp:
            speech = Path(tmp) / "whisper"
            speech.mkdir()
            env = {"CAIRN_HOME": tmp, "CAIRN_ENGINE": "mlx", "CAIRN_WHISPER_MODEL": str(speech), "CAIRN_LLM": "qwen3:4b"}
            base = dict(available=True, models=[{"name": "qwen3:4b"}], find_ollama="/bin/ollama", ram=16.0, free=50.0, pocket=("ok", []))
            base.update(patches)
            with mock.patch.dict(os.environ, env), mock.patch.object(setup.llm, "available", return_value=base["available"]), \
                    mock.patch.object(setup.llm, "models", return_value=base["models"]), mock.patch.object(setup.llm, "find_ollama", return_value=base["find_ollama"]), \
                    mock.patch.object(setup.system, "ram_gb", return_value=base["ram"]), mock.patch.object(setup, "_free_gb", return_value=base["free"]), \
                    mock.patch.object(setup.shutil, "which", return_value="/bin/ffmpeg"), \
                    mock.patch.object(setup.pocket, "find_pocket", return_value=("x" if base["pocket"][0] == "ok" else None)), \
                    mock.patch.object(setup.pocket, "volumes_without_record", return_value=base["pocket"][1]):
                if patches.get("no_speech"):
                    speech.rmdir()
                return {c["id"]: c for c in setup.check()["checks"]}, setup.check()["ready"]

    def test_everything_in_place(self):
        checks, ready = self.run_check()
        self.assertTrue(ready)
        self.assertEqual({c["status"] for c in checks.values()}, {"ok"})

    def test_what_is_missing_is_named(self):
        checks, ready = self.run_check(available=False, models=[])
        self.assertFalse(ready)
        self.assertEqual((checks["ollama"]["status"], checks["llm"]["status"]), ("todo", "todo"))
        checks, ready = self.run_check(models=[{"name": "other:7b"}])
        self.assertEqual((checks["llm"]["status"], ready), ("todo", False))
        checks, ready = self.run_check(no_speech=True)
        self.assertEqual((checks["speech"]["status"], ready), ("todo", False))

    def test_the_pocket_never_blocks(self):
        checks, ready = self.run_check(pocket=("absent", []))
        self.assertEqual((checks["pocket"]["status"], ready), ("absent", True))  # audio files can be added by hand
        checks, _ = self.run_check(pocket=("absent", ["Pocket"]))
        self.assertEqual(checks["pocket"]["status"], "norecord")  # seen, but USB Mode is not on

    def test_small_machines_are_warned_not_stopped(self):
        checks, ready = self.run_check(ram=6.0, free=5.0)
        self.assertEqual((checks["memory"]["status"], checks["disk"]["status"], ready), ("warn", "warn", True))
        checks, ready = self.run_check(free=1.0)
        self.assertEqual((checks["disk"]["status"], ready), ("todo", False))


if __name__ == "__main__":
    unittest.main()
