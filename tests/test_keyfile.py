"""The key file as a second factor: password + file open the data key, the password alone does not."""
import os
import threading
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cairn import lock
from tests.test_lock import PASSWORD, Base


class KeyfileTest(Base):
    def setUp(self):
        super().setUp()
        self.usb = Path(self.tmp.name) / "usb"
        self.usb.mkdir()
        self.key = self.usb / "cairn.key"
        self.phrase = lock.enable(PASSWORD)
        self.dek = lock._state["dek"]

    def relock(self):
        lock._state.update(dek=None, fails=0)

    def code(self, call, *args, **kw):
        with self.assertRaises(lock.LockError) as caught:
            call(*args, **kw)
        return caught.exception.code

    def test_enable_creates_a_private_32_byte_file(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.assertEqual(len(self.key.read_bytes()), 32)
        self.assertEqual(os.stat(self.key).st_mode & 0o777, 0o600)
        self.assertEqual(lock.info()["keyfile"], {"on": True, "path": str(self.key), "present": True})

    def test_password_and_file_unlock_but_the_password_alone_does_not(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        self.assertTrue(lock.unlock(PASSWORD))
        self.assertEqual(lock._state["dek"], self.dek)
        self.relock()
        saved = self.key.read_bytes()
        self.key.write_bytes(os.urandom(32))  # a different file of the right size
        self.assertEqual(self.code(lock.unlock, PASSWORD), "wrong_password")
        self.key.write_bytes(saved)
        self.assertTrue(lock.unlock(PASSWORD))

    def test_missing_file_is_told_apart_and_costs_no_attempt(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        moved = self.usb / "moved.key"
        self.key.rename(moved)
        self.assertEqual(self.code(lock.unlock, PASSWORD), "keyfile_missing")
        self.assertEqual(lock._state["fails"], 0)
        self.assertTrue(lock.unlock(PASSWORD, keyfile=moved))  # pointed at where it is now

    def test_wrong_size_file_is_invalid(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        self.key.write_bytes(b"short")
        self.assertEqual(self.code(lock.unlock, PASSWORD), "keyfile_invalid")

    def test_the_recovery_phrase_still_opens_and_switches_the_file_off(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        self.key.unlink()
        lock.recover(self.phrase, "another long password")
        self.assertEqual(lock._state["dek"], self.dek)
        self.assertFalse(lock.info()["keyfile"]["on"])
        self.relock()
        self.assertTrue(lock.unlock("another long password"))

    def test_change_password_keeps_the_file_requirement(self):
        lock.keyfile_enable(PASSWORD, self.key)
        lock.change_password(PASSWORD, "a brand new password")
        self.relock()
        self.assertEqual(self.code(lock.unlock, "a brand new password", keyfile=self.usb / "nope"), "keyfile_missing")
        self.assertTrue(lock.unlock("a brand new password"))

    def test_disable_goes_back_to_the_password_alone(self):
        lock.keyfile_enable(PASSWORD, self.key)
        lock.keyfile_disable(PASSWORD)
        self.key.unlink()
        self.relock()
        self.assertTrue(lock.unlock(PASSWORD))
        self.assertEqual(self.code(lock.keyfile_disable, PASSWORD), "keyfile_off")

    def test_enable_needs_the_right_password_and_leaves_no_file(self):
        self.assertEqual(self.code(lock.keyfile_enable, "wrong password!", self.key), "wrong_password")
        self.assertFalse(self.key.exists())

    def test_never_overwrites_nor_writes_inside_the_cairn_folder(self):
        self.key.write_bytes(b"mine")
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, self.key), "keyfile_exists")
        self.assertEqual(self.key.read_bytes(), b"mine")
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, self.home / "cairn.key"), "keyfile_inside")
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, "relative.key"), "keyfile_path")
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, self.usb / "missing" / "k"), "keyfile_path")

    def test_a_failed_write_of_lock_json_removes_the_new_file_and_changes_nothing(self):
        before = lock._read()
        with mock.patch.object(lock, "_write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                lock.keyfile_enable(PASSWORD, self.key)
        self.assertFalse(self.key.exists())
        self.assertEqual(lock._read(), before)

    def test_lock_json_never_holds_the_file_content(self):
        lock.keyfile_enable(PASSWORD, self.key)
        raw = self.key.read_bytes()
        text = (self.home / "lock.json").read_bytes()
        self.assertNotIn(raw.hex().encode(), text)
        self.assertNotIn(raw, text)

    def test_every_action_accepts_the_new_place_of_the_file(self):
        lock.keyfile_enable(PASSWORD, self.key)
        moved = self.usb / "moved.key"
        self.key.rename(moved)
        for call in (lambda: lock.new_phrase(PASSWORD), lambda: lock.change_password(PASSWORD, "x" * 12), lambda: lock.keyfile_disable(PASSWORD)):
            self.assertEqual(self.code(call), "keyfile_missing")
        self.assertTrue(lock.new_phrase(PASSWORD, keyfile=moved))
        lock.change_password(PASSWORD, "a brand new password", keyfile=moved)
        lock.keyfile_disable("a brand new password", keyfile=moved)
        self.assertFalse(lock.info()["keyfile"]["on"])

    def test_new_phrase_and_disable_need_the_file(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.key.rename(self.usb / "gone.key")
        self.assertEqual(self.code(lock.new_phrase, PASSWORD), "keyfile_missing")
        self.assertEqual(self.code(lock.disable, PASSWORD), "keyfile_missing")

    def test_odd_paths_are_refused_without_blocking(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        fifo = self.usb / "pipe"
        os.mkfifo(fifo)
        link = self.usb / "link.key"
        link.symlink_to(self.key)
        for odd in (fifo, self.usb, link, "bad\x00path", self.usb / "none"):
            self.assertEqual(self.code(lock.unlock, PASSWORD, keyfile=odd), "keyfile_missing")
        self.key.write_bytes(os.urandom(33))
        self.assertEqual(self.code(lock.unlock, PASSWORD), "keyfile_invalid")

    def test_a_path_given_by_the_client_does_not_tell_invalid_from_absent(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        other = self.usb / "other.bin"
        other.write_bytes(b"1234")
        self.assertEqual(self.code(lock.unlock, PASSWORD, keyfile=other), "keyfile_missing")
        self.assertEqual(self.code(lock.unlock, PASSWORD, keyfile=self.usb / "nope"), "keyfile_missing")

    def test_a_wrong_file_of_the_right_size_still_counts_as_an_attempt(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.relock()
        other = self.usb / "other.key"
        other.write_bytes(os.urandom(32))
        self.assertEqual(self.code(lock.unlock, PASSWORD, keyfile=other), "wrong_password")
        self.assertEqual(lock._state["fails"], 1)

    def test_the_cairn_folder_is_refused_under_another_spelling_or_a_link(self):
        link = Path(self.tmp.name) / "shortcut"
        link.symlink_to(self.home)
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, link / "k.key"), "keyfile_inside")
        sub = self.home / "Audio"
        sub.mkdir()
        self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, sub / "k.key"), "keyfile_inside")
        upper = Path(str(self.home).replace("Cairn", "CAIRN"))
        if upper.exists():  # a volume that ignores the case of names
            self.assertEqual(self.code(lock.keyfile_enable, PASSWORD, upper / "k.key"), "keyfile_inside")

    def test_touch_id_and_the_key_file_exclude_each_other(self):
        lock.keyfile_enable(PASSWORD, self.key)
        self.assertEqual(self.code(lock.settings, biometric=True), "keyfile_biometric")
        lock.keyfile_disable(PASSWORD)

    def test_enabling_the_file_switches_touch_id_off(self):
        cfg = lock._read()
        lock._write(dict(cfg, biometric=True))
        with mock.patch("cairn.biometric.forget") as forget:
            lock.keyfile_enable(PASSWORD, self.key)
        forget.assert_called_once()
        self.assertFalse(lock._read()["biometric"])

    def test_two_changes_at_once_do_not_overwrite_each_other(self):
        results = {}

        def new_phrase():
            results["phrase"] = lock.new_phrase(PASSWORD)

        def enable():
            lock.keyfile_enable(PASSWORD, self.key)

        threads = [threading.Thread(target=new_phrase), threading.Thread(target=enable)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.relock()
        self.assertTrue(lock.info()["keyfile"]["on"])
        lock.recover(results["phrase"], "fresh long password")  # the phrase that was shown still works
        self.assertEqual(lock._state["dek"], self.dek)


if __name__ == "__main__":
    unittest.main()
