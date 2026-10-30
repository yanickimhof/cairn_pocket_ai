"""Encryption at rest: formats, random access, tampering."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from cairn import seal


class BlobTest(unittest.TestCase):
    def test_round_trip_and_binding_to_the_name(self):
        key = seal.new_key()
        raw = seal.seal_blob(key, b'{"title": "Appel"}', "Texts/a.json")
        self.assertTrue(seal.is_blob(raw))
        self.assertNotIn(b"Appel", raw)
        self.assertEqual(seal.open_blob(key, raw, "Texts/a.json"), b'{"title": "Appel"}')
        with self.assertRaises(seal.SealError):
            seal.open_blob(key, raw, "Texts/b.json")  # a note moved under another name is refused
        with self.assertRaises(seal.SealError):
            seal.open_blob(seal.new_key(), raw, "Texts/a.json")
        with self.assertRaises(seal.SealError):
            seal.open_blob(key, raw[:-1] + bytes([raw[-1] ^ 1]), "Texts/a.json")

    def test_two_seals_of_the_same_data_differ(self):
        key = seal.new_key()
        self.assertNotEqual(seal.seal_blob(key, b"x", "c"), seal.seal_blob(key, b"x", "c"))


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.key = seal.new_key()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, size):
        data = os.urandom(size)
        src = self.dir / "a.wav"
        src.write_bytes(data)
        sealed = self.dir / "a.sealed"
        digest = seal.seal_file(src, sealed, self.key)
        self.assertEqual(digest, hashlib.sha256(data).hexdigest())
        return data, sealed

    def test_round_trip_for_every_size_around_the_block_edge(self):
        for size in (0, 1, seal.CHUNK - 1, seal.CHUNK, seal.CHUNK + 1, 3 * seal.CHUNK + 17):
            data, sealed = self.make(size)
            self.assertTrue(seal.is_sealed(sealed))
            self.assertEqual(seal.plain_size(sealed), size)
            self.assertEqual(b"".join(seal.iter_plain(sealed, self.key)), data, size)
            out = self.dir / "out.wav"
            self.assertEqual(seal.unseal_file(sealed, out, self.key), hashlib.sha256(data).hexdigest())
            self.assertEqual(out.read_bytes(), data)
            self.assertEqual(seal.content_sha256(sealed, self.key), hashlib.sha256(data).hexdigest())

    def test_any_moment_can_be_read_without_the_rest(self):
        size = 3 * seal.CHUNK + 5000
        data, sealed = self.make(size)
        for start, end in ((0, 0), (10, 99), (seal.CHUNK - 3, seal.CHUNK + 3), (2 * seal.CHUNK, 3 * seal.CHUNK + 4999), (size - 1, size + 50), (5, 5 + 2 * seal.CHUNK)):
            self.assertEqual(seal.read_range(sealed, self.key, start, end), data[start: min(end, size - 1) + 1], (start, end))
        self.assertEqual(seal.read_range(sealed, self.key, size, size + 10), b"")

    def test_the_content_is_not_in_the_file(self):
        marker = b"UNIQUE-MARKER-0123456789"
        src = self.dir / "m.wav"
        src.write_bytes(marker * 1000)
        seal.seal_file(src, self.dir / "m.sealed", self.key)
        self.assertNotIn(marker, (self.dir / "m.sealed").read_bytes())

    def test_a_cut_or_extended_or_altered_file_is_refused(self):
        data, sealed = self.make(2 * seal.CHUNK + 100)
        raw = sealed.read_bytes()
        cut = self.dir / "cut"
        cut.write_bytes(raw[:-50])
        with self.assertRaises(seal.SealError):
            b"".join(seal.iter_plain(cut, self.key))
        extended = self.dir / "ext"
        extended.write_bytes(raw + b"x" * 10)
        with self.assertRaises(seal.SealError):
            b"".join(seal.iter_plain(extended, self.key))
        flipped = self.dir / "flip"
        flipped.write_bytes(raw[:200] + bytes([raw[200] ^ 1]) + raw[201:])
        with self.assertRaises(seal.SealError):
            seal.read_range(flipped, self.key, 0, 10)
        bigger = bytearray(raw)  # a header that claims another size cannot be used to read past the data
        bigger[len(seal.FILE_MAGIC) + 16: seal.HEADER] = (len(data) + seal.CHUNK).to_bytes(8, "big")
        lie = self.dir / "lie"
        lie.write_bytes(bytes(bigger))
        with self.assertRaises(seal.SealError):
            b"".join(seal.iter_plain(lie, self.key))
        with self.assertRaises(seal.SealError):
            seal.read_range(sealed, seal.new_key(), 0, 10)

    def test_a_failed_seal_leaves_no_partial_file(self):
        from unittest import mock

        src = self.dir / "z.wav"
        src.write_bytes(os.urandom(3 * seal.CHUNK))
        with mock.patch.object(seal.os, "fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                seal.seal_file(src, self.dir / "z.sealed", self.key)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["z.wav"])


if __name__ == "__main__":
    unittest.main()
