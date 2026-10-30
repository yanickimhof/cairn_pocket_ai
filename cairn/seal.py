"""Encryption at rest: small blobs (notes, settings, the search index) and large files (recordings), AES-256-GCM.

Two formats, both authenticated end to end:

- blob:  "CAIRNB1\\0" + 12-byte random nonce + ciphertext. The name of the file is part of what is authenticated, so an
  encrypted note cannot be copied over another one without being refused.
- file:  "CAIRNF1\\0" + 16-byte file id + 8-byte size, then the content in 1 MiB blocks. Every block is sealed under a key of its own
  file (HKDF from the data key and the file id) with its position and a "last block" flag authenticated. The blocks have a fixed
  size, so any moment of a recording can be read without opening what comes before it.

The data key itself is handled elsewhere (lock.py); nothing here stores or prints a key."""
import hashlib
import os
import secrets
import struct
from pathlib import Path

BLOB_MAGIC = b"CAIRNB1\0"
FILE_MAGIC = b"CAIRNF1\0"
HEADER = len(FILE_MAGIC) + 16 + 8
CHUNK = 1 << 20
TAG = 16
_INFO_FILE = b"cairn-at-rest-file-v1"
_INFO_BLOB = b"cairn-at-rest-blob-v1"


class SealError(Exception):
    """The data is not what was sealed: a wrong key, a damaged file, or a file moved under another name."""


def _crypto():
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return InvalidTag, hashes, AESGCM, HKDF


def _derive(key, salt, info):
    _, hashes, _, HKDF = _crypto()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(key)


def new_key():
    return secrets.token_bytes(32)


# Blobs

def is_blob(raw):
    return raw[: len(BLOB_MAGIC)] == BLOB_MAGIC


def seal_blob(key, plain, context):
    _, _, AESGCM, _ = _crypto()
    nonce = secrets.token_bytes(12)
    return BLOB_MAGIC + nonce + AESGCM(_derive(key, b"", _INFO_BLOB)).encrypt(nonce, plain, context.encode("utf-8"))


def open_blob(key, raw, context):
    InvalidTag, _, AESGCM, _ = _crypto()
    if not is_blob(raw) or len(raw) < len(BLOB_MAGIC) + 12 + TAG:
        raise SealError("not a sealed blob")
    nonce, body = raw[len(BLOB_MAGIC): len(BLOB_MAGIC) + 12], raw[len(BLOB_MAGIC) + 12:]
    try:
        return AESGCM(_derive(key, b"", _INFO_BLOB)).decrypt(nonce, body, context.encode("utf-8"))
    except InvalidTag as error:
        raise SealError("the content does not match (wrong key, damaged, or moved)") from error


# Files

def _nonce(counter):
    return b"\0\0\0\0" + struct.pack(">Q", counter)


def _aad(head, counter, final):
    return head + struct.pack(">QB", counter, 1 if final else 0)


def _blocks(size):
    return max(1, -(-size // CHUNK))


def is_sealed(path):
    try:
        with open(path, "rb") as handle:
            return handle.read(len(FILE_MAGIC)) == FILE_MAGIC
    except OSError:
        return False


def _header(handle):
    head = handle.read(HEADER)
    if len(head) != HEADER or head[: len(FILE_MAGIC)] != FILE_MAGIC:
        raise SealError("not a sealed file")
    (size,) = struct.unpack(">Q", head[len(FILE_MAGIC) + 16:])
    return head, size


def plain_size(path):
    """The size of the recording inside, from the header alone (checked as soon as a block is read)."""
    with open(path, "rb") as handle:
        return _header(handle)[1]


def seal_file(src, dst, key):
    """Seal src into dst (written whole or not at all). Returns the SHA-256 of the plain content, computed on the way."""
    _, _, AESGCM, _ = _crypto()
    src, dst = Path(src), Path(dst)
    size = src.stat().st_size
    fid = secrets.token_bytes(16)
    head = FILE_MAGIC + fid + struct.pack(">Q", size)
    aead = AESGCM(_derive(key, fid, _INFO_FILE))
    digest, part = hashlib.sha256(), dst.with_name(dst.name + ".sealing")
    last = _blocks(size) - 1
    try:
        with open(src, "rb") as reader, open(part, "wb") as writer:
            os.chmod(part, 0o600)
            writer.write(head)
            for counter in range(last + 1):
                block = reader.read(CHUNK)
                digest.update(block)
                writer.write(aead.encrypt(_nonce(counter), block, _aad(head, counter, counter == last)))
            if reader.read(1):
                raise SealError("the file grew while it was sealed")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(part, dst)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise
    return digest.hexdigest()


def read_range(path, key, start, end):
    """The bytes start..end (inclusive) of the recording inside a sealed file, opening only the blocks they sit in."""
    InvalidTag, _, AESGCM, _ = _crypto()
    with open(path, "rb") as handle:
        head, size = _header(handle)
        if size == 0 or start < 0 or start > end or start >= size:
            return b""
        end = min(end, size - 1)
        last = _blocks(size) - 1
        aead = AESGCM(_derive(key, head[len(FILE_MAGIC): len(FILE_MAGIC) + 16], _INFO_FILE))
        out = bytearray()
        for counter in range(start // CHUNK, end // CHUNK + 1):
            handle.seek(HEADER + counter * (CHUNK + TAG))
            want = (CHUNK if counter < last else size - last * CHUNK) + TAG
            blob = handle.read(want)
            if len(blob) != want:
                raise SealError("the file is cut")
            try:
                plain = aead.decrypt(_nonce(counter), blob, _aad(head, counter, counter == last))
            except InvalidTag as error:
                raise SealError("the content does not match (wrong key or damaged file)") from error
            lo = start - counter * CHUNK if counter == start // CHUNK else 0
            hi = end - counter * CHUNK + 1 if counter == end // CHUNK else len(plain)
            out += plain[lo:hi]
        return bytes(out)


def iter_plain(path, key):
    """Every block of the recording inside, in order. The whole file is checked: a cut or extended file is refused."""
    with open(path, "rb") as handle:
        _, size = _header(handle)
    position = 0
    while position < size or position == 0:
        block = read_range(path, key, position, min(position + CHUNK, size) - 1) if size else b""
        yield block
        position += CHUNK
        if not size:
            break
    if os.path.getsize(path) != HEADER + size + _blocks(size) * TAG:
        raise SealError("the file does not have the size it announces")


def unseal_file(src, dst, key):
    """Write the plain recording to dst (whole or not at all). Returns its SHA-256."""
    dst = Path(dst)
    part = dst.with_name(dst.name + ".opening")
    digest = hashlib.sha256()
    try:
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as writer:
            for block in iter_plain(src, key):
                digest.update(block)
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(part, dst)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise
    return digest.hexdigest()


def content_sha256(path, key):
    digest = hashlib.sha256()
    for block in iter_plain(path, key):
        digest.update(block)
    return digest.hexdigest()
