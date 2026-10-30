"""App lock and encryption at rest: keys, migration, the locked API, recordings."""
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest import mock

from cairn import config, lock, seal

PASSWORD = "correct horse battery"


def wav_bytes(seconds=1):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(os.urandom(2 * 8000 * seconds))
    return buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "Cairn"
        self.home.mkdir()
        patcher = mock.patch.dict(os.environ, {"CAIRN_HOME": str(self.home), "CAIRN_ENGINE": "mlx"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.reset)
        self.reset()

    def reset(self):
        lock._state.update(dek=None, fails=0, migrating=False, seen=0)
        config.set_codec(None)

    def tearDown(self):
        self.tmp.cleanup()

    def populate(self):
        texts = self.home / "Texts"
        texts.mkdir()
        config.write_json(texts / "n1.json", {"id": "n1", "title": "Appel Brandt", "status": "done", "segments": [{"text": "budget de 300 000"}]})
        config.write_json(self.home / "settings.json", {"vocabulary": ["Brandt"], "hf_token": "hf_secret_token_value"})
        (self.home / "Index" / "m").mkdir(parents=True)
        config.write_json(self.home / "Index" / "m" / "n1.json", {"sig": 1, "chunks": [{"t": "budget de 300 000"}]})
        audio = self.home / "Audio" / "2026-10"
        audio.mkdir(parents=True)
        self.audio = audio / "a.wav"
        self.audio.write_bytes(wav_bytes(2))
        self.audio_plain = self.audio.read_bytes()


class KeysTest(Base):
    def test_enable_unlock_and_lock(self):
        self.assertFalse(lock.enabled())
        phrase = lock.enable(PASSWORD)
        self.assertRegex(phrase, r"^([A-Z2-7]{5}-){4}[A-Z2-7]{5}-[A-Z2-7]{1,5}$")
        self.assertEqual((lock.enabled(), lock.locked()), (True, False))
        lock.lock_now()
        self.assertTrue(lock.locked())
        with self.assertRaises(lock.LockError) as ctx:
            lock.unlock("wrong password here")
        self.assertEqual(ctx.exception.code, "wrong_password")
        self.assertTrue(lock.unlock(PASSWORD))
        self.assertFalse(lock.locked())

    def test_the_data_key_is_not_in_the_lock_file(self):
        lock.enable(PASSWORD)
        dek = lock._state["dek"]
        text = (self.home / "lock.json").read_text()
        self.assertNotIn(dek.hex(), text)
        self.assertNotIn(__import__("base64").b64encode(dek).decode(), text)
        self.assertNotIn(PASSWORD, text)

    def test_a_short_password_is_refused(self):
        with self.assertRaises(lock.LockError) as ctx:
            lock.enable("short")
        self.assertEqual(ctx.exception.code, "password_short")
        self.assertFalse(lock.enabled())

    def test_password_change_and_recovery_phrase(self):
        phrase = lock.enable(PASSWORD)
        lock.change_password(PASSWORD, "another long password")
        lock.lock_now()
        with self.assertRaises(lock.LockError):
            lock.unlock(PASSWORD)
        lock.unlock("another long password")
        lock.lock_now()
        with self.assertRaises(lock.LockError) as ctx:
            lock.recover("AAAAA-AAAAA-AAAAA-AAAAA-AAAAA-A", "brand new password")
        self.assertEqual(ctx.exception.code, "wrong_phrase")
        lock.recover(phrase.lower().replace("-", " "), "brand new password")  # case and separators do not matter
        self.assertFalse(lock.locked())
        lock.lock_now()
        lock.unlock("brand new password")

    def test_idle_time_locks(self):
        lock.enable(PASSWORD, auto_min=5)
        self.assertFalse(lock.due())
        lock._state["seen"] -= 6 * 60
        self.assertTrue(lock.due())
        lock.touch()
        self.assertFalse(lock.due())
        lock.settings(auto_min=0)
        lock._state["seen"] -= 10 ** 6
        self.assertFalse(lock.due())  # 0 = only when asked

    def test_touch_id_is_only_a_confirmation_before_the_key_is_handed_over(self):
        from cairn import biometric

        with mock.patch.object(biometric, "available", return_value=True), mock.patch.object(biometric, "remember", return_value=True) as remember:
            lock.enable(PASSWORD, biometric=True)
            dek = lock._state["dek"]
            remember.assert_called_once_with(dek)
            lock.lock_now()
            with mock.patch.object(biometric, "confirm", return_value=False), mock.patch.object(biometric, "recall", return_value=dek):
                with self.assertRaises(lock.LockError):
                    lock.unlock_biometric()
                self.assertTrue(lock.locked())  # a refused fingerprint never hands the key over
            with mock.patch.object(biometric, "confirm", return_value=True), mock.patch.object(biometric, "recall", return_value=dek):
                lock.unlock_biometric()
            self.assertFalse(lock.locked())


class SealedFilesTest(Base):
    def test_json_is_sealed_and_unreadable_while_locked(self):
        lock.enable(PASSWORD)
        config.write_json(self.home / "Texts" / "x.json", {"title": "SECRET-TITLE"})
        raw = (self.home / "Texts" / "x.json").read_bytes()
        self.assertNotIn(b"SECRET-TITLE", raw)
        self.assertEqual(config.read_json(self.home / "Texts" / "x.json"), {"title": "SECRET-TITLE"})
        lock.lock_now()
        with self.assertRaises(config.Locked):
            config.read_json(self.home / "Texts" / "x.json")
        with self.assertRaises(config.Locked):
            config.write_json(self.home / "Texts" / "y.json", {"a": 1})  # nothing is written in the clear while locked
        self.assertEqual(config.read_json(self.home / "settings.json"), {})  # start-up code reads the settings before anyone unlocked
        self.assertFalse((self.home / "Texts" / "y.json").exists())

    def test_a_sealed_note_cannot_be_moved_under_another_name(self):
        lock.enable(PASSWORD)
        config.write_json(self.home / "Texts" / "a.json", {"title": "A"})
        (self.home / "Texts" / "b.json").write_bytes((self.home / "Texts" / "a.json").read_bytes())
        with self.assertRaises(config.Locked):
            config.read_json(self.home / "Texts" / "b.json")

    def test_existing_data_is_sealed_and_comes_back(self):
        self.populate()
        lock.enable(PASSWORD)
        changed = lock.migrate(True)
        self.assertEqual(changed, 4)  # note, settings, index, recording
        for path in (self.home / "Texts" / "n1.json", self.home / "settings.json", self.home / "Index" / "m" / "n1.json"):
            self.assertTrue(seal.is_blob(path.read_bytes()), path)
            self.assertNotIn(b"Brandt", path.read_bytes())
            self.assertNotIn(b"hf_secret", path.read_bytes())
        self.assertTrue(seal.is_sealed(self.audio))
        self.assertEqual(config.read_json(self.home / "Texts" / "n1.json")["title"], "Appel Brandt")
        self.assertEqual(lock.audio_sha256(self.audio), __import__("hashlib").sha256(self.audio_plain).hexdigest())
        self.assertEqual(lock.migrate(True), 0)  # again: nothing left to do, nothing harmed
        self.assertTrue(lock.info()["sealed"])
        self.assertEqual(lock.migrate(False), 4)
        lock.finish_disable()
        self.assertFalse(lock.enabled())
        self.assertEqual(self.audio.read_bytes(), self.audio_plain)
        self.assertEqual(config.read_json(self.home / "Texts" / "n1.json")["title"], "Appel Brandt")

    def test_a_pass_that_stopped_halfway_is_taken_up_again(self):
        self.populate()
        lock.enable(PASSWORD)
        calls = {"n": 0}
        real = lock._replace_bytes

        def flaky(path, raw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("power cut")
            return real(path, raw)

        with mock.patch.object(lock, "_replace_bytes", flaky):
            with self.assertRaises(OSError):
                lock.migrate(True)
        self.assertEqual(lock.info()["sealed"], False)
        self.assertEqual(lock._state["migrating"], False)
        self.assertEqual(config.read_json(self.home / "Texts" / "n1.json")["title"], "Appel Brandt")  # sealed and plain files both read
        lock.migrate(True)
        self.assertTrue(lock.info()["sealed"])
        self.assertTrue(seal.is_sealed(self.audio))

    def test_a_recording_is_opened_for_a_tool_and_nothing_stays(self):
        self.populate()
        lock.enable(PASSWORD)
        lock.migrate(True)
        with lock.plain(self.audio) as path:
            self.assertEqual(Path(path).read_bytes(), self.audio_plain)
            self.assertTrue(str(path).startswith(str(self.home / ".tmp")))
            kept = path
        self.assertFalse(os.path.exists(kept))
        self.assertEqual(list((self.home / ".tmp").glob("*")), [])
        self.assertEqual(lock.audio_read(self.audio, 10, 99), self.audio_plain[10:100])
        self.assertEqual(lock.audio_size(self.audio), len(self.audio_plain))
        lock.lock_now()
        with self.assertRaises(config.Locked):
            with lock.plain(self.audio):
                pass

    def test_a_new_recording_is_sealed_on_arrival_only_when_the_lock_is_on(self):
        self.populate()
        fresh = self.home / "Audio" / "new.wav"
        fresh.write_bytes(wav_bytes(1))
        self.assertFalse(lock.seal_audio(fresh))
        self.assertFalse(seal.is_sealed(fresh))
        lock.enable(PASSWORD)
        self.assertTrue(lock.seal_audio(fresh))
        self.assertTrue(seal.is_sealed(fresh))
        self.assertEqual([p.name for p in (self.home / "Audio").glob("*.new")], [])


class LockedServerTest(Base):
    def setUp(self):
        super().setUp()
        from cairn import server

        self.populate()
        self.app, self.httpd = server.make_server(18799)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=30)
        hdr = {"Host": "127.0.0.1:%d" % self.app.port, "Cookie": "cairn_session=" + self.app.token}
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
            return resp.status, raw

    def test_nothing_but_the_way_in_answers_while_locked(self):
        status, body = self.call("POST", "/api/lock/enable", {"password": PASSWORD})
        self.assertEqual(status, 200)
        self.assertIn("recovery", body)
        self.assertEqual(self.call("POST", "/api/lock/now")[0], 200)
        self.assertEqual(self.call("GET", "/api/state")[0], 423)
        self.assertEqual(self.call("GET", "/api/note/n1")[0], 423)
        self.assertEqual(self.call("GET", "/api/note/n1/audio")[0], 423)
        self.assertEqual(self.call("POST", "/api/import")[0], 423)
        self.assertEqual(self.call("POST", "/api/lock/disable", {"password": PASSWORD})[0], 423)
        status, info = self.call("GET", "/api/lock")
        self.assertEqual((status, info["enabled"], info["locked"]), (200, True, True))
        self.assertEqual(self.call("POST", "/api/lock/unlock", {"password": "not the password"})[0], 401)
        self.assertEqual(self.call("GET", "/api/state")[0], 423)
        self.assertEqual(self.call("POST", "/api/lock/unlock", {"password": PASSWORD})[0], 200)
        self.assertEqual(self.call("GET", "/api/state")[0], 200)

    def test_the_unlock_needs_the_same_guards(self):
        self.call("POST", "/api/lock/enable", {"password": PASSWORD})
        self.call("POST", "/api/lock/now")
        self.assertEqual(self.call("POST", "/api/lock/unlock", {"password": PASSWORD}, headers={"X-Cairn": "0"})[0], 403)
        self.assertEqual(self.call("POST", "/api/lock/unlock", {"password": PASSWORD}, headers={"Host": "evil.example"})[0], 403)

    def test_a_sealed_recording_is_played_with_ranges(self):
        self.call("POST", "/api/lock/enable", {"password": PASSWORD})
        lock.migrate(True)
        config.write_json(self.home / "Texts" / "n1.json", {"id": "n1", "status": "done", "title": "Appel", "audio": str(self.audio), "segments": []})
        status, data = self.call("GET", "/api/note/n1/audio", headers={"Range": "bytes=10-99"})
        self.assertEqual((status, data), (206, self.audio_plain[10:100]))
        status, data = self.call("GET", "/api/note/n1/audio")
        self.assertEqual((status, data), (200, self.audio_plain))

    def test_a_dropped_file_is_sealed_on_arrival(self):
        from urllib.parse import quote

        self.call("POST", "/api/lock/enable", {"password": PASSWORD})
        conn = http.client.HTTPConnection("127.0.0.1", self.app.port, timeout=30)
        data = wav_bytes(1)
        conn.request("POST", "/api/import/file", data, {"Host": "127.0.0.1:%d" % self.app.port, "Cookie": "cairn_session=" + self.app.token, "X-Cairn": "1",
                                                          "Content-Type": "application/octet-stream", "X-Filename": quote("drop.wav")})
        body = json.loads(conn.getresponse().read())
        conn.close()
        note = self.app.store.get(body["id"])
        self.assertTrue(seal.is_sealed(note["audio"]))
        self.assertNotIn(data[100:200], Path(note["audio"]).read_bytes())

    def test_a_note_written_while_sealing_is_sealed(self):
        self.call("POST", "/api/lock/enable", {"password": PASSWORD})
        self.app.store.save({"id": "z", "status": "waiting", "title": "TITRE-SECRET"})
        self.assertNotIn(b"TITRE-SECRET", (self.home / "Texts" / "z.json").read_bytes())
        self.assertEqual(self.app.store.get("z")["title"], "TITRE-SECRET")


if __name__ == "__main__":
    unittest.main()
