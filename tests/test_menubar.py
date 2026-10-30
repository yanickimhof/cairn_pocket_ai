"""The menu bar item: what it says, when it speaks, how it finds Cairn and when it is started."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cairn import menubar


def texts(built):
    return [line[1] for line in built["lines"] if line[0] != "separator"]


def actions(built):
    return [line[2] for line in built["lines"] if line[2]]


BASE = {"job": {"running": False, "errors": []}, "pocket": {"connected": False, "new": 0}, "totals": {"waiting": 0, "done": 5},
        "lock": {"enabled": False}, "privacy": {"ok": True, "when": "2026-10-30T06:00:12"}, "battery": {}, "settings": {"ui": "fr"}}


def state(**changes):
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE.items()}
    for key, value in changes.items():
        out[key] = dict(out[key], **value) if isinstance(out.get(key), dict) else value
    return out


class ModelTest(unittest.TestCase):
    def test_a_quiet_cairn_says_little(self):
        built = menubar.model(state(), "fr")
        self.assertEqual(built["icon"], "idle")
        self.assertEqual(texts(built), ["Cairn", "Ouvrir Cairn", "Rien n’a quitté ce Mac · 06:00", "Quitter"])
        self.assertEqual(actions(built), ["open", "quit"])

    def test_the_pocket_and_what_can_be_imported(self):
        built = menubar.model(state(pocket={"connected": True, "new": 3}, battery={"level": 78}), "fr")
        self.assertIn("Pocket connectée · 78 %", texts(built))
        self.assertIn("Importer 3 enregistrements", texts(built))
        self.assertIn("import", actions(built))
        one = menubar.model(state(pocket={"connected": True, "new": 1}), "en")
        self.assertIn("Import 1 recording", texts(one))

    def test_a_job_shows_its_step_and_can_be_cancelled(self):
        built = menubar.model(state(job={"running": True, "step": "transcribing", "done": 1, "total": 3}, pocket={"connected": True, "new": 2}), "fr")
        self.assertEqual(built["icon"], "work")
        self.assertIn("Transcription · 2 sur 3", texts(built))
        self.assertIn("cancel", actions(built))
        self.assertNotIn("import", actions(built))  # no second import over the first

    def test_waiting_recordings_and_the_lock(self):
        built = menubar.model(state(totals={"waiting": 4}, lock={"enabled": True, "locked": False}), "en")
        self.assertIn("4 waiting", texts(built))
        self.assertIn("lock", actions(built))
        locked = menubar.model(None, "fr", locked=True)
        self.assertEqual((locked["icon"], texts(locked)), ("locked", ["Cairn · Verrouillé", "Déverrouiller Cairn", "Quitter"]))

    def test_attention_only_for_a_real_problem(self):
        self.assertEqual(menubar.model(state(job={"errors": ["x"]}), "en")["icon"], "attention")
        self.assertEqual(menubar.model(state(privacy={"ok": False, "when": "2026-10-30T06:00:12"}), "en")["icon"], "attention")
        self.assertEqual(menubar.model(None, "en", away=True)["icon"], "away")

    def test_no_note_text_ever_reaches_the_menu(self):
        built = menubar.model(state(job={"running": True, "step": "summarizing", "id": "SECRET-ID", "done": 0, "total": 1}), "en")
        self.assertNotIn("SECRET", " ".join(texts(built)))

    def test_one_notification_per_batch(self):
        before = state(job={"running": True, "kind": "import"}, totals={"done": 5})
        after = state(job={"running": False, "kind": "import"}, totals={"done": 7})
        self.assertEqual(menubar.finished(before, after, "fr"), "2 notes prêtes")
        self.assertEqual(menubar.finished(before, state(totals={"done": 6}), "en"), "1 note ready")
        self.assertIsNone(menubar.finished(before, state(job={"errors": ["x"]}, totals={"done": 7})))  # an error is not good news
        self.assertIsNone(menubar.finished(state(), after))  # nothing was running before
        self.assertIsNone(menubar.finished(state(job={"running": True, "kind": "index"}), after))  # indexing is not a batch of notes
        self.assertIsNone(menubar.finished(before, state(totals={"done": 5})))


class ClientTest(unittest.TestCase):
    def test_it_reads_the_address_cairn_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "url.txt").write_text("http://127.0.0.1:8731/?k=abc123\n")
            client = menubar.Client(tmp)
            self.assertEqual(client.target(), (8731, "abc123"))
            self.assertEqual(client.url(), "http://127.0.0.1:8731/?k=abc123")
            (Path(tmp) / "url.txt").write_text("garbage")
            self.assertIsNone(client.target())
            self.assertEqual(menubar.Client(Path(tmp) / "nothing").call("GET", "/api/state"), (None, None))

    def test_it_talks_to_the_real_server_as_the_page_does(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CAIRN_HOME": tmp, "CAIRN_ENGINE": "mlx"}):
            from cairn import lock, server

            lock._state.update(dek=None)
            app, httpd = server.make_server(18862)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                (Path(tmp) / "url.txt").write_text("http://127.0.0.1:%d/?k=%s\n" % (app.port, app.token))
                client = menubar.Client(tmp)
                status, data = client.call("GET", "/api/state?list=0")
                self.assertEqual(status, 200)
                self.assertEqual(menubar.model(data, "en")["icon"], "idle")
                self.assertIn("menubar", data)
                self.assertEqual(client.call("POST", "/api/cancel")[0], 200)
                (Path(tmp) / "url.txt").write_text("http://127.0.0.1:%d/?k=wrong\n" % app.port)
                self.assertEqual(menubar.Client(tmp).call("GET", "/api/state")[0], 403)  # without the key it gets nothing
            finally:
                httpd.shutdown()
                httpd.server_close()


class StartTest(unittest.TestCase):
    def test_it_is_started_when_wanted_and_stopped_when_not(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        with mock.patch.object(menubar, "available", return_value=True), mock.patch.object(menubar.subprocess, "Popen", return_value=proc) as popen:
            menubar._proc["p"] = None
            menubar.ensure(True)
            menubar.ensure(True)  # already running: not started twice
            self.assertEqual(popen.call_count, 1)
            self.assertEqual(popen.call_args[0][0][1:3], ["-m", "cairn.menubar"])
            menubar.ensure(False)
            proc.terminate.assert_called_once()
            self.assertIsNone(menubar._proc["p"])

    def test_it_is_never_started_where_it_cannot_run(self):
        with mock.patch.object(menubar, "available", return_value=False), mock.patch.object(menubar.subprocess, "Popen") as popen:
            menubar._proc["p"] = None
            menubar.ensure(True)
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
