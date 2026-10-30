"""The Pocket vault: encryption, tampering, passwords, keychain, and the whole path from a Pocket to another computer."""

import hashlib
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import keyring
    import keyring.backend
    import cryptography  # noqa: F401
    HAVE = True
except ImportError:  # pragma: no cover - the installer always provides both
    HAVE = False

SECRET = b"TOP-SECRET-MARKER-3f9a"


class MemoryKeyring(keyring.backend.KeyringBackend if HAVE else object):
    """A keychain in memory, so that the tests never touch the real one."""

    priority = 99

    def __init__(self):
        self.items = {}

    def set_password(self, service, username, password):
        self.items[(service, username)] = password

    def get_password(self, service, username):
        return self.items.get((service, username))

    def delete_password(self, service, username):
        self.items.pop((service, username), None)


def fake_recording(path, size=3000, marker=SECRET):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(marker + os.urandom(size))
    return path


@unittest.skipUnless(HAVE, "cryptography and keyring are part of the installation")
class VaultBase(unittest.TestCase):
    def setUp(self):
        from cairn import vault

        self.vault = vault
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.keys = MemoryKeyring()
        keyring.set_keyring(self.keys)
        with vault._session_lock:
            vault._session.clear()
            vault._trusted.clear()
        self.home_before = os.environ.get("CAIRN_HOME")
        os.environ["CAIRN_HOME"] = str(self.root / "Cairn")
        self.folder = self.root / "Pocket" / "RECORD"
        self.folder.mkdir(parents=True)

    def tearDown(self):
        if self.home_before is None:
            os.environ.pop("CAIRN_HOME", None)
        else:
            os.environ["CAIRN_HOME"] = self.home_before
        self.tmp.cleanup()


class CryptoTest(VaultBase):
    def roundtrip(self, size):
        src = self.root / "in.bin"
        src.write_bytes(os.urandom(size))
        key = os.urandom(32)
        fid = self.vault.new_fid()
        dst = self.root / "out.cairn"
        digest = self.vault.seal(src, dst, key, {"name": "a/b.mp3", "size": size, "mtime": 5}, fid)
        self.assertEqual(digest, hashlib.sha256(src.read_bytes()).hexdigest())
        self.assertEqual(self.vault.read_meta(dst, key)["name"], "a/b.mp3")
        self.assertEqual(self.vault.content_hash(dst, key), digest)
        back = self.root / "back.bin"
        meta, again = self.vault.unseal(dst, back, key)
        self.assertEqual(again, digest)
        self.assertEqual(back.read_bytes(), src.read_bytes())
        self.assertEqual(meta["size"], size)
        return dst, key

    def test_sizes_around_the_chunk(self):
        for size in (0, 1, 1000, self.vault.CHUNK - 1, self.vault.CHUNK, self.vault.CHUNK + 1, 2 * self.vault.CHUNK + 17):
            with self.subTest(size=size):
                self.roundtrip(size)

    def test_nothing_readable_in_the_encrypted_file(self):
        src = fake_recording(self.root / "x.mp3", 5000)
        dst = self.root / "x.cairn"
        self.vault.seal(src, dst, os.urandom(32), {"name": "secret-name.mp3", "size": 5000 + len(SECRET), "mtime": 1}, self.vault.new_fid())
        raw = dst.read_bytes()
        self.assertNotIn(SECRET, raw)
        self.assertNotIn(b"secret-name", raw)

    def test_wrong_key_is_refused(self):
        dst, _ = self.roundtrip(5000)
        with self.assertRaises(self.vault.Corrupt):
            self.vault.read_meta(dst, os.urandom(32))
        with self.assertRaises(self.vault.Corrupt):
            self.vault.unseal(dst, self.root / "never.bin", os.urandom(32))
        self.assertFalse((self.root / "never.bin").exists())
        self.assertFalse((self.root / "never.bin.part").exists())

    def test_every_kind_of_damage_is_refused(self):
        size = 2 * self.vault.CHUNK + 100
        dst, key = self.roundtrip(size)
        good = dst.read_bytes()
        cases = {
            "flipped byte": good[:100] + bytes([good[100] ^ 1]) + good[101:],
            "flipped in the last chunk": good[:-5] + bytes([good[-5] ^ 1]) + good[-4:],
            "cut at the end": good[:-1],
            "cut at a chunk boundary": good[: 24 + 4 + self.vault.CHUNK + 16 + 4 + 40 + 0] if False else None,
            "extra data": good + b"\0",
            "empty": b"",
            "other magic": b"NOTCAIRN" + good[8:],
        }
        # cut exactly after the first data chunk: a valid-looking prefix
        first = 24
        import struct

        meta_len = struct.unpack(">I", good[first:first + 4])[0]
        second = first + 4 + meta_len
        data_len = struct.unpack(">I", good[second:second + 4])[0]
        cases["cut at a chunk boundary"] = good[: second + 4 + data_len]
        for name, blob in cases.items():
            with self.subTest(name):
                bad = self.root / "bad.cairn"
                bad.write_bytes(blob)
                with self.assertRaises(self.vault.Corrupt):
                    self.vault.content_hash(bad, key)
                with self.assertRaises(self.vault.Corrupt):
                    self.vault.unseal(bad, self.root / "bad.out", key)
                self.assertFalse((self.root / "bad.out").exists())
                self.assertFalse((self.root / "bad.out.part").exists())

    def test_chunks_cannot_be_swapped(self):
        import struct

        dst, key = self.roundtrip(3 * self.vault.CHUNK)
        raw = dst.read_bytes()
        pos, parts = 24, []
        while pos < len(raw):
            (n,) = struct.unpack(">I", raw[pos:pos + 4])
            parts.append(raw[pos:pos + 4 + n])
            pos += 4 + n
        self.assertGreaterEqual(len(parts), 4)
        swapped = raw[:24] + parts[0] + parts[2] + parts[1] + b"".join(parts[3:])
        bad = self.root / "swap.cairn"
        bad.write_bytes(swapped)
        with self.assertRaises(self.vault.Corrupt):
            self.vault.content_hash(bad, key)

    def test_two_files_never_share_a_key(self):
        key = os.urandom(32)
        src = self.root / "s.bin"
        src.write_bytes(b"same")
        a, b = self.root / "a.cairn", self.root / "b.cairn"
        self.vault.seal(src, a, key, {"name": "x", "size": 4, "mtime": 1}, self.vault.new_fid())
        self.vault.seal(src, b, key, {"name": "x", "size": 4, "mtime": 1}, self.vault.new_fid())
        self.assertNotEqual(a.read_bytes(), b.read_bytes())
        swap = self.root / "swap.cairn"  # the head of one file on the content of the other
        swap.write_bytes(a.read_bytes()[:24] + b.read_bytes()[24:])
        with self.assertRaises(self.vault.Corrupt):
            self.vault.content_hash(swap, key)


class HeaderAndKeysTest(VaultBase):
    def test_create_and_unlock(self):
        header, key = self.vault.create(self.folder, "correct horse")
        self.assertEqual(self.vault.unlock(self.folder, "correct horse"), key)
        self.assertTrue(self.vault.key_matches(header, key))
        with self.assertRaises(self.vault.WrongPassword):
            self.vault.unlock(self.folder, "wrong horse!")
        with self.assertRaises(self.vault.WrongPassword):
            self.vault.unlock(self.folder, "")
        raw = (self.folder / self.vault.HEADER_NAME).read_text()
        self.assertNotIn("correct horse", raw)

    def test_password_rules_and_one_vault_per_pocket(self):
        with self.assertRaises(self.vault.VaultError):
            self.vault.create(self.folder, "short")
        self.assertIsNone(self.vault.read_header(self.folder))
        self.vault.create(self.folder, "long enough password")
        with self.assertRaises(self.vault.VaultError):
            self.vault.create(self.folder, "another password")

    def test_damaged_or_hostile_header_is_ignored(self):
        self.vault.create(self.folder, "long enough password")
        path = self.vault.header_path(self.folder)
        good = json.loads(path.read_text())
        for patch in ({"n": 1 << 30}, {"r": 1000}, {"p": 99}, {"v": 2}, {"kdf": "md5"}, {"salt": "AAAA"}, {"id": "short"}):
            with self.subTest(patch):
                path.write_text(json.dumps(dict(good, **patch)))
                self.assertIsNone(self.vault.read_header(self.folder))
        path.write_text("not json")
        self.assertIsNone(self.vault.read_header(self.folder))

    def test_keychain_roundtrip(self):
        key = os.urandom(32)
        self.assertFalse(self.vault.trusted("v1"))
        self.assertTrue(self.vault.remember("v1", key, trust=True))
        self.assertTrue(self.vault.trusted("v1"))
        with self.vault._session_lock:
            self.vault._session.clear()
            self.vault._trusted.clear()
        self.assertEqual(self.vault.recall("v1"), key)  # read back from the keychain
        self.assertTrue(self.vault.trusted("v1"))
        self.vault.forget("v1")
        self.assertIsNone(self.vault.recall("v1"))
        self.assertEqual(self.keys.items, {})

    def test_untrusted_key_stays_in_memory_only(self):
        key = os.urandom(32)
        self.assertFalse(self.vault.remember("v2", key, trust=False))
        self.assertEqual(self.keys.items, {})
        self.assertEqual(self.vault.recall("v2"), key)
        self.assertFalse(self.vault.trusted("v2"))

    def test_a_broken_keychain_does_not_break_anything(self):
        class Broken(MemoryKeyring):
            def get_password(self, *a):
                raise RuntimeError("keychain locked")

            def set_password(self, *a):
                raise RuntimeError("keychain locked")

        keyring.set_keyring(Broken())
        self.assertFalse(self.vault.remember("v3", os.urandom(32), trust=True))
        self.assertIsNotNone(self.vault.recall("v3"))  # kept in memory for the session
        with self.vault._session_lock:
            self.vault._session.clear()
        self.assertIsNone(self.vault.recall("v3"))
        self.assertFalse(self.vault.trusted("v3"))


class PocketLayerTest(VaultBase):
    def test_safe_names(self):
        from cairn import pocket

        for ok in ("a.mp3", "2026-10-08/a.wav", "a b/c d.mp3"):
            self.assertEqual(pocket._safe_rel(ok), ok)
        for bad in ("", "/etc/passwd", "../x.mp3", "a/../../x", "a//b", "C:/x.wav", "a\\b.wav", "a\0b", None, 5, "./a"):
            self.assertIsNone(pocket._safe_rel(bad), bad)

    def make_sealed(self, count=2):
        from cairn import pocket

        header, key = self.vault.create(self.folder, "long enough password")
        self.vault.remember(header["id"], key)
        names = []
        for i in range(count):
            rel = "2026-10-0%d/r%d.mp3" % (i + 1, i)
            names.append(rel)
            path = fake_recording(self.folder / rel)
            listing = pocket.scan(self.folder)
            entry = [e for e in listing.plain if e.rel == rel][0]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            fid, info = pocket.seal_entry(self.folder, entry, key, digest)
            idx = self.vault.load_index(header["id"])
            idx[fid] = info
            self.vault.save_index(header["id"], idx)
        return header, key, names

    def test_sealing_replaces_the_plain_file_and_removes_empty_day_folders(self):
        from cairn import pocket

        header, key, names = self.make_sealed()
        listing = pocket.scan(self.folder)
        self.assertEqual(listing.state(), "secured")
        self.assertEqual([e.rel for e in listing.sealed], names)
        self.assertEqual(listing.plain, [])
        self.assertEqual(listing.locked, 0)
        leftovers = sorted(p.name for p in self.folder.rglob("*"))
        self.assertTrue(all(n.endswith(".cairn") or n == ".cairn-vault" for n in leftovers), leftovers)
        blob = b"".join(p.read_bytes() for p in self.folder.rglob("*") if p.is_file())
        self.assertNotIn(SECRET, blob)

    def test_without_the_key_nothing_is_listed_but_everything_is_counted(self):
        from cairn import pocket

        header, key, names = self.make_sealed(3)
        self.vault.forget(header["id"])
        listing = pocket.scan(self.folder)
        self.assertEqual(listing.state(), "locked")
        self.assertEqual(listing.readable, [])
        self.assertEqual(listing.locked, 3)

    def test_another_vault_key_means_locked_files(self):
        from cairn import pocket

        header, key, _ = self.make_sealed(2)
        self.vault.remember(header["id"], os.urandom(32))  # a wrong key under the right id
        listing = pocket.scan(self.folder)
        self.assertEqual((listing.state(), listing.locked, listing.readable), ("locked", 2, []))

    def test_a_recording_that_changed_is_not_replaced(self):
        from cairn import pocket

        header, key = self.vault.create(self.folder, "long enough password")
        path = fake_recording(self.folder / "r.mp3")
        entry = pocket.scan(self.folder).plain[0]
        with self.assertRaises(OSError):
            pocket.seal_entry(self.folder, entry, key, "0" * 64)  # not what was copied
        self.assertTrue(path.exists())
        self.assertEqual([p.name for p in self.folder.iterdir() if p.name != ".cairn-vault" and p.name != "r.mp3"], [])

    def test_a_recording_that_cannot_be_removed_leaves_only_one_version(self):
        from cairn import pocket

        header, key = self.vault.create(self.folder, "long enough password")
        path = fake_recording(self.folder / "r.mp3")
        entry = pocket.scan(self.folder).plain[0]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        original = os.replace

        def refuse(src, dst, *a, **k):
            if Path(src).name == "r.mp3":
                raise PermissionError("read-only")
            return original(src, dst, *a, **k)

        os.replace = refuse
        try:
            with self.assertRaises(OSError):
                pocket.seal_entry(self.folder, entry, key, digest)
        finally:
            os.replace = original
        self.assertEqual(path.stat().st_size, len(SECRET) + 3000)  # the recording was not touched
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [".cairn-vault", "r.mp3"])

    def test_leftovers_of_an_unplugged_pocket_are_cleaned(self):
        from cairn import pocket

        (self.folder / ("a" * 32 + ".cairn.part")).write_bytes(b"half")
        (self.folder / ".cairn-vault.part").write_text("{}")
        pocket.clean_leftovers(self.folder)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_symlinks_on_the_pocket_are_never_followed(self):
        from cairn import pocket

        header, key = self.vault.create(self.folder, "long enough password")
        outside = self.root / "outside.cairn"
        outside.write_bytes(b"x")
        try:
            os.symlink(outside, self.folder / ("b" * 32 + ".cairn"))
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        listing = pocket.scan(self.folder)
        self.assertEqual((listing.sealed, listing.locked), ([], 0))


class HardeningTest(VaultBase):
    """What the review of 0.5 found: each case here was a way to lose recordings or to be tricked by a hostile Pocket."""

    def test_a_vault_is_never_replaced_whatever_the_state_of_its_header(self):
        self.vault.create(self.folder, "long enough password")
        header = self.vault.header_path(self.folder)
        good = header.read_text()
        for broken in ("", "not json", json.dumps(dict(json.loads(good), v=2))):
            header.write_text(broken)
            with self.assertRaises(self.vault.VaultError):
                self.vault.create(self.folder, "another long password")
            self.assertEqual(header.read_text(), broken)  # untouched
        header.unlink()
        (self.folder / ("a" * 32 + ".cairn")).write_bytes(b"x")
        with self.assertRaises(self.vault.VaultError):  # encrypted files without a header: their key is lost for good with a new one
            self.vault.create(self.folder, "another long password")
        self.assertFalse(header.exists())

    def test_two_requests_at_once_make_one_vault(self):
        results = []

        def go():
            try:
                self.vault.create(self.folder, "long enough password")
                results.append("ok")
            except self.vault.VaultError:
                results.append("refused")

        threads = [threading.Thread(target=go) for _ in range(4)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), ["ok", "refused", "refused", "refused"])
        self.assertIsNotNone(self.vault.read_header(self.folder))

    def test_the_cost_asked_by_a_header_is_bounded_and_a_bad_one_is_an_error_not_a_crash(self):
        self.vault.create(self.folder, "long enough password")
        header = self.vault.header_path(self.folder)
        good = json.loads(header.read_text())
        for patch in ({"n": 1 << 18}, {"n": 3 << 15}, {"r": 9}, {"p": 3}, {"n": 1 << 20, "r": 32}):
            header.write_text(json.dumps(dict(good, **patch)))
            self.assertIsNone(self.vault.read_header(self.folder), patch)
        header.write_text(json.dumps(good))
        self.assertIsNotNone(self.vault.read_header(self.folder))
        self.assertEqual(self.vault.SCRYPT["n"], 1 << 17)
        with mock.patch.object(self.vault.hashlib, "scrypt", side_effect=ValueError("memory limit")):
            with self.assertRaises(self.vault.VaultError):
                self.vault.unlock(self.folder, "long enough password")

    def test_the_password_is_the_same_whatever_the_keyboard_composes(self):
        composed, decomposed = "caf\u00e9 long password", "cafe\u0301 long password"
        header, key = self.vault.create(self.folder, composed)
        self.assertEqual(self.vault.unlock(self.folder, decomposed), key)

    def test_ten_characters_at_least(self):
        with self.assertRaises(self.vault.VaultError):
            self.vault.create(self.folder, "123456789")
        self.vault.create(self.folder, "1234567890")

    def test_names_that_cannot_be_files_everywhere_are_refused(self):
        from cairn import pocket

        for bad in ("a/b.wav:stream", "CON.wav", "dir/nul.mp3", "name.wav.", "name.wav ", "a.exe", "noextension", "x" * 300 + ".wav", "a\x01b.wav", "d:/x.wav"):
            self.assertIsNone(pocket._safe_rel(bad), bad)
        self.assertEqual(pocket._safe_rel("2026-10-08/rec 1.MP3"), "2026-10-08/rec 1.MP3")

    def seal_one(self, name="r.mp3", content=None):
        from cairn import pocket

        header, key = (self.vault.read_header(self.folder), None)
        if not header:
            header, key = self.vault.create(self.folder, "long enough password")
        else:
            key = self.vault.recall(header["id"])
        self.vault.remember(header["id"], key)
        path = fake_recording(self.folder / name)
        entry = [e for e in pocket.scan(self.folder).plain if e.rel == name][0]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return header, key, entry, digest

    def test_the_plain_recording_is_overwritten_before_it_is_removed_and_nothing_hidden_is_left(self):
        from cairn import pocket

        header, key, entry, digest = self.seal_one()
        seen = []
        real = pocket.shred

        def watch(path, size):
            seen.append((Path(path).name, Path(path).read_bytes()[:len(SECRET)] == SECRET))  # still readable at this moment
            real(path, size)
            seen.append((Path(path).name, Path(path).read_bytes()[:len(SECRET)] == SECRET))

        with mock.patch.object(pocket, "shred", watch):
            pocket.seal_entry(self.folder, entry, key, digest)
        self.assertEqual([flag for _n, flag in seen], [True, False])  # noise before the unlink
        self.assertTrue(seen[0][0].startswith(".shred-"))
        self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith(".shred-")], [])

    def test_a_crash_between_the_replacement_and_the_removal_leaves_no_duplicate(self):
        from cairn import jobs, notes, pocket

        header, key, entry, digest = self.seal_one()
        fid, info = pocket.seal_entry(self.folder, entry, key, digest)
        twin = fake_recording(self.folder / "r.mp3", marker=SECRET)  # the plain recording came back (the crash)
        os.utime(twin, (info["mtime"], info["mtime"]))
        twin.write_bytes(b"\0" * info["size"])  # same size, same date: the same recording as far as the Pocket can tell
        os.utime(twin, (info["mtime"], info["mtime"]))
        self.assertEqual(len(pocket.scan(self.folder).plain), 1)
        store = notes.Store(Path(self.tmp.name) / "Cairn" / "Texts")
        job = jobs.Jobs(store)
        store.save({"id": "n", "source": "r.mp3", "size": info["size"], "mtime": info["mtime"], "sha256": "x", "audio": str(twin), "status": "waiting"})
        job._seal_all(self.folder, pocket.scan(self.folder), Path(self.tmp.name))
        listing = pocket.scan(self.folder)
        self.assertEqual((len(listing.plain), len(listing.sealed)), (0, 1))

    def test_deleting_erases_every_copy_but_never_another_recording_with_the_same_name(self):
        from cairn import notes, pocket, server

        os.environ.update(CAIRN_POCKET_DIR=str(self.folder), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b", OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=self.tmp.name)
        app = server.App()
        old = fake_recording(self.folder / "same.mp3", 3000)
        stat = old.stat()
        app.store.save({"id": "old", "source": "same.mp3", "size": stat.st_size, "mtime": int(stat.st_mtime), "status": "done", "audio": "", "title": "old"})
        # the Pocket is formatted and the same name is used for another recording
        old.unlink()
        new = fake_recording(self.folder / "same.mp3", 5000)
        os.utime(new, (stat.st_mtime + 86400, stat.st_mtime + 86400))
        self.assertTrue(app.delete_note("old"))
        self.assertTrue(new.exists())  # the new recording is not the deleted one
        self.assertFalse(app.store.is_ignored("same.mp3", new.stat().st_size, int(new.stat().st_mtime)))
        self.assertEqual(app.store.ignored(), set())

    def test_a_reused_name_is_a_new_note_and_leaves_the_finished_one_alone(self):
        from cairn import jobs, notes, pocket

        os.environ["CAIRN_HOME"] = str(self.root / "Cairn")
        store = notes.Store(self.root / "Cairn" / "Texts")
        job = jobs.Jobs(store)
        audio = self.root / "Cairn" / "Audio"
        first = fake_recording(self.folder / "same.mp3", 3000)
        entry = pocket.scan(self.folder).plain[0]
        job._copy_one(entry, audio)
        original = Path(store.find_source("same.mp3")["audio"]).read_bytes()
        done = store.find_source("same.mp3")
        done["status"] = "done"
        store.save(done)
        first.write_bytes(b"other recording" * 100)
        os.utime(first, (1_700_000_000, 1_700_000_000))
        job._copy_one(pocket.scan(self.folder).plain[0], audio)
        rows = [n for n in store.slim() if n["source"] == "same.mp3"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(Path(store.get(done["id"])["audio"]).read_bytes(), original)  # the finished note keeps its audio
        job._copy_one(pocket.scan(self.folder).plain[0], audio)  # and a second pass does not make a third
        self.assertEqual(len([n for n in store.slim() if n["source"] == "same.mp3"]), 2)

    def test_a_damaged_local_copy_is_never_the_reason_to_replace_the_recording_on_the_pocket(self):
        from cairn import jobs, notes, pocket

        header, key, entry, digest = self.seal_one()
        local = self.root / "local.mp3"
        local.write_bytes(entry.path.read_bytes())
        store = notes.Store(self.root / "Cairn" / "Texts")
        store.save({"id": "n", "source": "r.mp3", "size": entry.size, "mtime": entry.mtime, "sha256": digest, "audio": str(local), "status": "waiting"})
        local.write_bytes(b"damaged")
        job = jobs.Jobs(store)
        job._seal_all(self.folder, pocket.scan(self.folder), self.root)
        self.assertTrue((self.folder / "r.mp3").exists())
        self.assertEqual(pocket.scan(self.folder).sealed, [])
        self.assertTrue(job.snapshot()["errors"])

    def test_encrypted_files_without_a_readable_header_are_called_damaged(self):
        from cairn import pocket

        header, key, entry, digest = self.seal_one()
        pocket.seal_entry(self.folder, entry, key, digest)
        self.assertEqual(pocket.scan(self.folder).state(), "secured")
        self.vault.header_path(self.folder).write_text("{broken")
        self.assertEqual(pocket.scan(self.folder).state(), "damaged")

    def test_forgetting_the_key_works_without_the_pocket(self):
        from cairn import server

        os.environ.update(CAIRN_POCKET_DIR=str(self.root / "unplugged"), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b", OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=self.tmp.name)
        app = server.App()
        self.vault.remember("v-known", os.urandom(32), trust=True)
        self.vault.save_index("v-known", {})
        app.vault_forget()
        self.assertIsNone(self.vault.recall("v-known"))
        self.assertEqual(self.keys.items, {})


class WholePathTest(VaultBase):
    """A Pocket goes through the application: secured on one computer, read on a trusted one, locked on a stranger's."""

    def computer(self, name):
        os.environ["CAIRN_HOME"] = str(self.root / name)
        os.environ.update(CAIRN_POCKET_DIR=str(self.folder), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=str(self.root))
        from cairn import server

        return server.App()

    def idle(self, app):
        for _ in range(300):
            time.sleep(0.05)
            if not app.jobs.snapshot()["running"]:
                return
        self.fail("job did not finish")

    def test_secure_import_delete_and_a_stranger_computer(self):
        from cairn import pocket, server

        files = {}
        for rel in ("2026-10-08/20261008_080600.mp3", "2026-10-09/20261009_090000.mp3"):
            files[rel] = fake_recording(self.folder / rel).read_bytes()
        mine = self.computer("mine")
        self.assertEqual(mine.pocket_state()["vault"]["state"], "none")

        with self.assertRaises(server.ApiError):
            mine.vault_create("short", True, False)
        mine.vault_create("a long passphrase", True, True)  # trust this computer, secure automatically
        self.idle(mine)
        self.assertEqual(mine.jobs.snapshot()["errors"], [])
        state = mine.pocket_state()
        self.assertEqual((state["vault"]["state"], state["vault"]["sealed"], state["vault"]["plain"]), ("secured", 2, 0))
        self.assertTrue(state["vault"]["trusted"])
        self.assertEqual(state["new"], 0)
        for rel, content in files.items():  # every recording is on this computer, identical
            note = mine.store.find_source(rel)
            self.assertEqual(Path(note["audio"]).read_bytes(), content)
        blob = b"".join(p.read_bytes() for p in self.folder.rglob("*") if p.is_file())
        self.assertNotIn(SECRET, blob)
        self.assertFalse(any(p.suffix == ".mp3" for p in self.folder.rglob("*")))

        # a new recording, and automatic securing at the next connection
        files["2026-10-10/20261010_100000.mp3"] = fake_recording(self.folder / "2026-10-10/20261010_100000.mp3").read_bytes()
        self.assertEqual(mine.pocket_state()["vault"]["state"], "partial")
        mine.jobs.start_sync()
        self.idle(mine)
        self.assertEqual(mine.pocket_state()["vault"]["state"], "secured")
        self.assertEqual(mine.pocket_state()["vault"]["sealed"], 3)
        self.assertEqual(len(mine.store.slim()), 3)

        # a second computer with Cairn but without the key
        vault_id = self.vault.read_header(self.folder)["id"]
        with self.vault._session_lock:
            self.vault._session.clear()
            self.vault._trusted.clear()
        saved = dict(self.keys.items)
        self.keys.items.clear()
        stranger = self.computer("stranger")
        state = stranger.pocket_state()
        self.assertEqual((state["vault"]["state"], state["vault"]["locked"], state["count"], state["new"]), ("locked", 3, 0, 0))
        stranger.jobs.start_sync()
        self.idle(stranger)
        self.assertEqual(stranger.store.slim(), [])
        with self.assertRaises(server.ApiError) as raised:
            stranger.vault_unlock("not the password", False)
        self.assertEqual(raised.exception.args[1] if len(raised.exception.args) > 1 else raised.exception.args[0], "wrong_password")
        stranger.vault_unlock("a long passphrase", False)  # the right password, without trusting this computer
        self.idle(stranger)
        self.assertEqual(stranger.jobs.snapshot()["errors"], [])
        self.assertFalse(self.vault.trusted(vault_id))
        self.assertEqual(len(stranger.store.slim()), 3)
        for rel, content in files.items():
            self.assertEqual(Path(stranger.store.find_source(rel)["audio"]).read_bytes(), content)
        again = stranger.pocket_state()
        self.assertEqual((again["vault"]["state"], again["new"]), ("secured", 0))

        # deleting a recording erases its encrypted file from the Pocket
        victim = stranger.store.find_source("2026-10-09/20261009_090000.mp3")
        self.assertTrue(stranger.delete_note(victim["id"]))
        remaining = pocket.scan(self.folder)
        self.assertEqual(sorted(e.rel for e in remaining.sealed), sorted(set(files) - {"2026-10-09/20261009_090000.mp3"}))
        self.assertEqual(len(list(self.folder.glob("*.cairn"))), 2)
        self.assertEqual(stranger.store.ignored(), set())
        self.keys.items.update(saved)

    def test_securing_waits_for_the_running_job(self):
        mine = self.computer("busy")
        fake_recording(self.folder / "a.mp3")
        mine.vault_create("a long passphrase", True, False)
        self.idle(mine)
        fake_recording(self.folder / "b.mp3")
        mine.jobs._start("privacy", lambda: time.sleep(0.4))
        mine.secure_now()  # busy: remembered
        self.assertTrue(mine.jobs.secure_wanted)
        self.idle(mine)
        from cairn import watch

        watch.Watcher(mine).tick(now=10 ** 9)
        self.idle(mine)
        self.assertFalse(mine.jobs.secure_wanted)
        self.assertEqual(mine.pocket_state()["vault"]["state"], "secured")

    def test_an_unplugged_pocket_never_loses_a_recording(self):
        from cairn import pocket

        mine = self.computer("unplug")
        for name in ("a.mp3", "b.mp3", "c.mp3"):
            fake_recording(self.folder / name)
        real = pocket.seal_entry
        calls = []

        def flaky(folder, entry, key, expect):
            calls.append(entry.rel)
            if len(calls) == 2:
                raise OSError("the Pocket was unplugged")
            return real(folder, entry, key, expect)

        pocket.seal_entry = flaky
        try:
            mine.vault_create("a long passphrase", True, False)
            self.idle(mine)
        finally:
            pocket.seal_entry = real
        listing = pocket.scan(self.folder)
        self.assertEqual(len(listing.plain) + len(listing.sealed), 3)  # nothing lost
        self.assertEqual(len(listing.plain), 1)
        self.assertEqual(len(mine.store.slim()), 3)  # all three are on this computer
        mine.secure_now()  # the next connection finishes the work
        self.idle(mine)
        self.assertEqual(pocket.scan(self.folder).state(), "secured")

    def test_wrong_state_requests_are_refused(self):
        from cairn import server

        mine = self.computer("refuse")
        with self.assertRaises(server.ApiError):
            mine.vault_unlock("whatever long", False)  # no vault yet
        mine.vault_create("a long passphrase", True, False)
        self.idle(mine)
        with self.assertRaises(server.ApiError):
            mine.vault_create("another long phrase", True, False)  # one vault per Pocket
        with self.assertRaises(server.ApiError):
            mine.vault_create(12345, True, False)
        os.environ["CAIRN_POCKET_DIR"] = str(self.root / "unplugged")
        with self.assertRaises(server.ApiError):
            mine.vault_unlock("a long passphrase", False)
        self.assertEqual(mine.pocket_state()["connected"], False)


class RoutesTest(VaultBase):
    def test_routes_need_the_session_and_the_header(self):
        os.environ.update(CAIRN_HOME=str(self.root / "web"), CAIRN_POCKET_DIR=str(self.folder), CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=str(self.root))
        import threading

        from cairn import server

        app, httpd = server.make_server(18802)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            def call(path, body, cookie=True, header=True):
                conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=30)
                hdr = {"Host": "127.0.0.1:%d" % app.port, "Content-Type": "application/json"}
                if cookie:
                    hdr["Cookie"] = "cairn_session=" + app.token
                if header:
                    hdr["X-Cairn"] = "1"
                conn.request("POST", path, json.dumps(body), hdr)
                resp = conn.getresponse()
                data = resp.read()
                conn.close()
                return resp.status, data

            for path in ("/api/vault/create", "/api/vault/unlock", "/api/vault/secure", "/api/vault/forget"):
                self.assertEqual(call(path, {"password": "a long passphrase"}, cookie=False)[0], 403, path)
                self.assertEqual(call(path, {"password": "a long passphrase"}, header=False)[0], 403, path)
            self.assertEqual(call("/api/vault/create", {"password": "short"})[0], 400)
            self.assertEqual(call("/api/vault/unlock", {"password": "a long passphrase"})[0], 400)  # no vault yet
            status, _ = call("/api/vault/create", {"password": "a long passphrase", "trust": True, "auto": True})
            self.assertEqual(status, 202)
            for _ in range(100):
                time.sleep(0.05)
                if not app.jobs.snapshot()["running"]:
                    break
            self.assertTrue(app.state(False)["settings"]["pocket_secure_auto"])
            self.assertEqual(call("/api/vault/unlock", {"password": "wrong password!"})[0], 403)
            self.assertNotIn(b"a long passphrase", (self.root / "web" / "settings.json").read_bytes())
            self.assertEqual(call("/api/vault/forget", {})[0], 200)
            self.assertEqual(app.pocket_state()["vault"]["state"], "locked")
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
