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


if __name__ == "__main__":
    unittest.main()
