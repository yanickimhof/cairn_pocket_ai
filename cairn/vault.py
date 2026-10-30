"""Pocket vault: the recordings on the Pocket are encrypted with a password, so that someone who plugs the
Pocket into another computer finds nothing readable.

Design, in short
- AES-256-GCM, in chunks of 1 MiB, with a different key for every file (HKDF from the vault key and a random
  16-byte file id). A chunk carries its position and a "last chunk" flag in its authenticated data, so a file
  that was cut, reordered or extended is refused, never half read.
- The vault key comes from the password with scrypt. The password itself is never stored. The key is kept in
  the system keychain (macOS Keychain, Windows Credential Manager) only on a computer the person trusts.
- On the Pocket: ".cairn-vault" (salt, scrypt cost and a check value, nothing secret) and one opaque "<id>.cairn"
  file per recording. The original name, size and date travel inside the encrypted file.
- A recording is replaced only after the encrypted copy was written, read back and found identical.
"""

import base64
import hashlib
import json
import os
import secrets
import struct
import sys
import threading
import time
import unicodedata
from pathlib import Path

from . import config

MAGIC = b"CAIRNV1\0"
HEADER_NAME = ".cairn-vault"
EXT = ".cairn"
CHUNK = 1 << 20
SERVICE = "Cairn Pocket vault"
SCRYPT = {"n": 1 << 17, "r": 8, "p": 1}  # 128 MiB of memory and about half a second per try
MAX_COST = {"n": 1 << 17, "r": 8, "p": 2}  # what a header found on a Pocket may ask for
MIN_PASSWORD = 10
_CHECK = b"cairn-vault-ok"
_INFO = b"cairn-pocket-file-v1"
_MAX_META = 1 << 16


class VaultError(Exception):
    pass


class WrongPassword(VaultError):
    pass


class Corrupt(VaultError):
    pass


def _crypto():
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as error:
        raise VaultError("The encryption library is not installed (cryptography).") from error
    return InvalidTag, hashes, AESGCM, HKDF


def available():
    try:
        _crypto()
        return True
    except VaultError:
        return False


def libraries():
    """The libraries the vault relies on, as (label, version, folder) for those that are installed."""
    import importlib.metadata
    import importlib.util

    found = []
    for module, dist in (("cryptography", "cryptography"), ("keyring", "keyring")):
        try:
            spec = importlib.util.find_spec(module)
            where = list(getattr(spec, "submodule_search_locations", None) or [])[:1] if spec else []
            found.append((dist, importlib.metadata.version(dist), Path(where[0]) if where else None))
        except (ImportError, ValueError, importlib.metadata.PackageNotFoundError):
            continue
    return found


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _unb64(text):
    return base64.b64decode(text.encode("ascii"), validate=True)


def derive_key(password, salt, n=SCRYPT["n"], r=SCRYPT["r"], p=SCRYPT["p"]):
    if not isinstance(password, str) or not password:
        raise WrongPassword("empty password")
    password = unicodedata.normalize("NFKC", password)  # the same keys on a Mac and on Windows, whatever the keyboard composes
    try:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=128 * n * r * p * 2 + (1 << 20), dklen=32)
    except (ValueError, MemoryError) as error:
        raise VaultError("The vault of this Pocket asks for more memory than this computer allows.") from error


# The header on the Pocket

def header_path(folder):
    return Path(folder) / HEADER_NAME


def read_header(folder):
    """The vault header of this Pocket, or None when there is none (or when it is not valid)."""
    try:
        raw = json.loads(header_path(folder).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("v") != 1 or raw.get("kdf") != "scrypt":
            return None
        header = {
            "id": str(raw["id"]), "salt": _unb64(raw["salt"]), "check": _unb64(raw["check"]),
            "n": int(raw["n"]), "r": int(raw["r"]), "p": int(raw["p"]),
        }
        if not (len(header["id"]) == 32 and 1 << 10 <= header["n"] <= MAX_COST["n"] and header["n"] & (header["n"] - 1) == 0
                and 1 <= header["r"] <= MAX_COST["r"] and 1 <= header["p"] <= MAX_COST["p"] and len(header["salt"]) == 16):
            return None
        return header
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return None  # whatever a hostile or damaged drive holds, it is not a vault header


def _check_value(key, vault_id):
    _, _, AESGCM, _ = _crypto()
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, _CHECK, vault_id.encode("ascii"))


def key_matches(header, key):
    InvalidTag, _, AESGCM, _ = _crypto()
    try:
        blob = header["check"]
        return AESGCM(key).decrypt(blob[:12], blob[12:], header["id"].encode("ascii")) == _CHECK
    except (InvalidTag, ValueError):
        return False


_create_lock = threading.Lock()


def create(folder, password):
    """Start a vault on this Pocket. Returns (header, key).

    Never replaces anything: a header that exists, even one that cannot be read, or encrypted files already there mean that the
    Pocket has a vault whose recordings would be lost for good with a new key."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise VaultError("The password must have at least %d characters." % MIN_PASSWORD)
    with _create_lock:
        target = header_path(folder)
        if target.exists() or any(Path(folder).glob("*" + EXT)):
            raise VaultError("This Pocket already has a vault, or one that cannot be read right now. Replug the Pocket and try again.")
        salt, vault_id = secrets.token_bytes(16), secrets.token_hex(16)
        key = derive_key(password, salt)
        body = {"v": 1, "id": vault_id, "kdf": "scrypt", "n": SCRYPT["n"], "r": SCRYPT["r"], "p": SCRYPT["p"],
                "salt": _b64(salt), "check": _b64(_check_value(key, vault_id))}
        try:
            with open(target, "x", encoding="utf-8") as handle:  # exclusive: two requests cannot both write it
                handle.write(json.dumps(body))
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as error:
            raise VaultError("This Pocket already has a vault.") from error
        return read_header(folder), key


def unlock(folder, password):
    """The vault key for this password, or WrongPassword."""
    header = read_header(folder)
    if not header:
        raise VaultError("This Pocket has no vault.")
    key = derive_key(password, header["salt"], header["n"], header["r"], header["p"])
    if not key_matches(header, key):
        raise WrongPassword("wrong password")
    return key


# Keys: in memory for this session, in the system keychain on a trusted computer

_session = {}
_trusted = set()
_session_lock = threading.Lock()


def remember(vault_id, key, trust=True):
    """Keep the key for this session and, when trust is set, in the keychain. Returns whether the keychain has it."""
    with _session_lock:
        _session[vault_id] = key
        _missed.pop(vault_id, None)
    if not trust:
        return False
    try:
        import keyring

        keyring.set_password(SERVICE, vault_id, _b64(key))
        with _session_lock:
            _trusted.add(vault_id)
        return True
    except Exception as error:  # no usable keychain on this computer: the key stays in memory for this session only
        print("vault: the keychain did not take the key (%s)" % type(error).__name__, file=sys.stderr, flush=True)
        return False


_missed = {}  # vault id -> when the keychain last had nothing for it: it is not asked again at every poll


def recall(vault_id):
    with _session_lock:
        if vault_id in _session:
            return _session[vault_id]
        if time.time() - _missed.get(vault_id, 0.0) < 30:
            return None
    try:
        import keyring

        stored = keyring.get_password(SERVICE, vault_id)
        if stored:
            key = _unb64(stored)
            if len(key) == 32:
                with _session_lock:
                    _session[vault_id] = key
                    _trusted.add(vault_id)
                return key
    except Exception:  # nosec B110
        pass  # a keychain that cannot be read is the same as no key
    with _session_lock:
        _missed[vault_id] = time.time()
    return None


def forget(vault_id):
    with _session_lock:
        _session.pop(vault_id, None)
        _trusted.discard(vault_id)
    try:
        import keyring

        keyring.delete_password(SERVICE, vault_id)
    except Exception:  # nosec B110
        pass  # nothing stored, or no keychain: either way the key is gone


def known_ids():
    """The vaults this computer has seen (their keys may be in its keychain)."""
    return sorted(config.read_json(_index_path()))


def trusted(vault_id):
    """Whether the key came from, or was put in, the keychain of this computer."""
    with _session_lock:
        return vault_id in _trusted


# Encrypted files

def _file_key(key, fid):
    _, hashes, _, HKDF = _crypto()
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=fid, info=_INFO).derive(key)


def _aad(head, counter, final):
    return head + struct.pack(">QB", counter, 1 if final else 0)


def _nonce(counter):
    return b"\0\0\0\0" + struct.pack(">Q", counter)


def new_fid():
    return secrets.token_bytes(16)


def seal(src, dst, key, meta, fid):
    """Encrypt the file src into dst under the 16-byte file id fid. meta (original relative name, size, mtime)
    is stored inside. Returns the SHA-256 of the plain content, computed while reading."""
    _, _, AESGCM, _ = _crypto()
    head = MAGIC + fid
    aead = AESGCM(_file_key(key, fid))
    digest = hashlib.sha256()
    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    if len(meta_bytes) > _MAX_META:
        raise VaultError("The file description is too long.")
    with open(src, "rb") as reader, open(dst, "wb") as writer:
        writer.write(head)

        def put(counter, plain, final):
            blob = aead.encrypt(_nonce(counter), plain, _aad(head, counter, final))
            writer.write(struct.pack(">I", len(blob)))
            writer.write(blob)

        put(0, meta_bytes, False)
        counter = 1
        block = reader.read(CHUNK)
        while True:
            following = reader.read(CHUNK)  # one block ahead, to know which one is the last
            digest.update(block)
            put(counter, block, not following)
            counter += 1
            if not following:
                break
            block = following
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest()


def _chunks(path, key):
    """Yield (counter, plain) for every chunk of an encrypted file. Raises Corrupt on any irregularity."""
    InvalidTag, _, AESGCM, _ = _crypto()
    with open(path, "rb") as reader:
        head = reader.read(len(MAGIC) + 16)
        if len(head) != len(MAGIC) + 16 or head[: len(MAGIC)] != MAGIC:
            raise Corrupt("not a Cairn vault file")
        aead = AESGCM(_file_key(key, head[len(MAGIC):]))
        counter, seen_final = 0, False
        while True:
            prefix = reader.read(4)
            if not prefix:
                break
            if seen_final or len(prefix) != 4:
                raise Corrupt("unexpected data after the end")
            (length,) = struct.unpack(">I", prefix)
            if not 16 <= length <= CHUNK + _MAX_META + 16:
                raise Corrupt("invalid chunk")
            blob = reader.read(length)
            if len(blob) != length:
                raise Corrupt("the file is cut")
            plain, final = None, False
            for flag in (False, True):  # the last chunk is the one that authenticates with the "last" flag
                try:
                    plain = aead.decrypt(_nonce(counter), blob, _aad(head, counter, flag))
                    final = flag
                    break
                except InvalidTag:
                    continue
            if plain is None:
                raise Corrupt("the content does not match (wrong key or damaged file)")
            seen_final = final
            yield counter, plain
            counter += 1
        if not seen_final:
            raise Corrupt("the file is cut")


def _parse_meta(plain):
    try:
        meta = json.loads(plain.decode("utf-8"))
    except ValueError as error:
        raise Corrupt("unreadable description") from error
    if not isinstance(meta, dict):
        raise Corrupt("unreadable description")
    return meta


def read_meta(path, key):
    """The description stored inside an encrypted file (reads only its first chunk)."""
    chunks = _chunks(path, key)
    try:
        for counter, plain in chunks:
            if counter == 0:
                return _parse_meta(plain)
    finally:
        chunks.close()
    raise Corrupt("no description")


def unseal(src, dst, key):
    """Decrypt src into dst (written whole or not at all). Returns (meta, sha256 of the content)."""
    digest, meta, wrote = hashlib.sha256(), None, 0
    part = Path(str(dst) + ".part")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(part, "wb") as writer:
            for counter, plain in _chunks(src, key):
                if counter == 0:
                    meta = _parse_meta(plain)
                    continue
                digest.update(plain)
                writer.write(plain)
                wrote += len(plain)
            writer.flush()
            os.fsync(writer.fileno())
        if meta is None or (isinstance(meta.get("size"), int) and meta["size"] != wrote):
            raise Corrupt("the size does not match")
        os.replace(part, dst)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise
    return meta, digest.hexdigest()


def content_hash(path, key):
    """SHA-256 of the decrypted content, without writing anything."""
    digest = hashlib.sha256()
    for counter, plain in _chunks(path, key):
        if counter:
            digest.update(plain)
    return digest.hexdigest()


# Names already read on this computer (an encrypted file name tells nothing without the key)

def _index_path():
    return config.home() / "vault-index.json"


def load_index(vault_id):
    return dict(config.read_json(_index_path()).get(vault_id) or {})


def drop_index(vault_id, fid):
    entries = load_index(vault_id)
    if entries.pop(fid, None) is not None:
        save_index(vault_id, entries)


def save_index(vault_id, entries):
    everything = config.read_json(_index_path())
    everything[vault_id] = entries
    config.write_json(_index_path(), everything)
