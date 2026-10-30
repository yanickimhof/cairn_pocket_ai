"""App lock and encryption at rest.

One random data key seals everything Cairn keeps (notes, settings, the search index, voices, and the recordings). That key is never
stored in the clear: it sits in lock.json wrapped twice, once under a key derived from the password (scrypt) and once under one
derived from a recovery phrase shown a single time. While Cairn is locked the data key is not in memory and the page refuses every
request except the ones that unlock it.

Touch ID (macOS) does not replace the password: it asks the system to confirm the person is there, and only then hands over a copy
of the data key kept in the keychain. A process running as the same user could read that keychain item without Touch ID, so Touch ID
protects against someone at the keyboard, the password and the sealed files protect against someone who has the disk."""
import base64
import contextlib
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from . import config, seal

SCRYPT = {"n": 1 << 17, "r": 8, "p": 1}
MIN_PASSWORD = 10
AUTO_CHOICES = (0, 5, 15, 60)  # minutes of inactivity before it locks again; 0 = only when asked
DEFAULT_AUTO = 15
KEYCHAIN = "Cairn data lock"
_WRAP_AAD = b"cairn-lock-v1"
_state = {"dek": None, "seen": time.time(), "fails": 0, "migrating": False, "opening": False, "checked": 0.0}
_guard = threading.RLock()
_attempts = threading.Lock()  # one guess at a time, so the delay after wrong tries cannot be beaten by sending them in parallel
RECHECK_SECONDS = 6 * 3600
_pass = threading.Lock()  # one pass of sealing or opening at a time


class LockError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class MigrationFailed(Exception):
    """Some files could not be sealed or opened; every other file was handled."""

    def __init__(self, failures):
        super().__init__("%d file(s) could not be handled: %s" % (len(failures), "; ".join("%s (%s)" % f for f in failures[:3])))
        self.failures = failures


def _path():
    return config.home() / "lock.json"


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(text):
    return base64.b64decode(str(text).encode("ascii"))


def _read():
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write(data):
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="lock.json.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _kek(secret, salt, n=SCRYPT["n"], r=SCRYPT["r"], p=SCRYPT["p"]):
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=128 * n * r * p * 2 + (1 << 20), dklen=32)


def _wrap(kek, dek):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = secrets.token_bytes(12)
    return _b64(nonce + AESGCM(kek).encrypt(nonce, dek, _WRAP_AAD))


def _unwrap(kek, wrapped):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = _unb64(wrapped)
    try:
        return AESGCM(kek).decrypt(raw[:12], raw[12:], _WRAP_AAD)
    except InvalidTag:
        return None


def phrase_new():
    """The recovery phrase: 128 random bits in groups, shown once."""
    text = base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")
    return "-".join(text[i: i + 5] for i in range(0, len(text), 5))


def _normal(phrase):
    return "".join(c for c in str(phrase or "").upper() if c.isalnum())


# State

def enabled():
    return _read() is not None


def locked():
    return enabled() and _state["dek"] is None


def touch():
    _state["seen"] = time.time()


def info():
    cfg = _read()
    if cfg is None:
        return {"enabled": False, "locked": False}
    from . import biometric

    return {"enabled": True, "locked": _state["dek"] is None, "auto_min": cfg.get("auto_min", DEFAULT_AUTO),
            "biometric": {"available": biometric.available(), "enabled": bool(cfg.get("biometric")), "reason": biometric.status()}, "migrating": _state["migrating"],
            "sealed": bool(cfg.get("migrated")), "opening": bool(cfg.get("opening"))}


class _Codec:
    """What config.read_json and write_json call to open and seal a file."""

    def __init__(self, dek):
        self.dek = dek

    def seal(self, raw, path):
        return seal.seal_blob(self.dek, raw, context(path))

    def open(self, raw, path):
        try:
            return seal.open_blob(self.dek, raw, context(path))
        except seal.SealError as error:
            raise config.Locked("the content could not be opened") from error


def context(path):
    path = Path(path)
    try:
        return path.relative_to(config.home()).as_posix()
    except ValueError:
        return path.name


_hooks = []


def on_unlock(callback):
    """Work that had to wait for the key (reading the notes at start-up), run each time Cairn is opened."""
    _hooks.append(callback)


_lock_hooks = []


def on_lock(callback):
    """What must forget what it read (listing caches) the moment Cairn locks."""
    _lock_hooks.append(callback)


def _install(dek):
    with _guard:
        _state["dek"] = dek
        _state["seen"] = time.time()
        _state["fails"] = 0
        config.set_codec(_Codec(dek))
        _apply_flags()
    for callback in list(_hooks):
        try:
            callback()
        except Exception:  # noqa: BLE001 (a hook must never keep the person out)
            pass


def lock_now():
    with _guard:
        _state["dek"] = None
        config.set_codec(None)
        purge_temp()
    for callback in list(_lock_hooks):
        try:
            callback()
        except Exception:  # noqa: BLE001 (forgetting must never fail the lock)
            pass


def _key():
    dek = _state["dek"]
    if dek is None:
        raise config.Locked("Cairn is locked")
    return dek


# Unlocking

def _open_with(secret, cfg, which):
    """The data key, from the password ("wrap") or the recovery phrase ("rwrap"), or None. Every check of a secret goes through here: one at a
    time, and each wrong try makes the next wait longer."""
    salt = cfg["salt"] if which == "wrap" else cfg["rsalt"]
    with _attempts:
        if _state["fails"] >= 3:
            time.sleep(min(_state["fails"] - 2, 5))
        dek = _unwrap(_kek(secret, _unb64(salt), cfg["n"], cfg["r"], cfg["p"]), cfg[which])
        if dek is None:
            _state["fails"] += 1
        return dek


def unlock(password):
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    dek = _open_with(str(password or ""), cfg, "wrap")
    if dek is None:
        raise LockError("wrong_password")
    _install(dek)
    return True


def unlock_biometric():
    from . import biometric

    cfg = _read()
    if cfg is None or not cfg.get("biometric") or not biometric.available():
        raise LockError("no_biometric")
    if not biometric.confirm("Unlock Cairn"):
        raise LockError("biometric_refused")
    dek = biometric.recall()
    if dek is None:
        raise LockError("no_biometric")
    _install(dek)
    return True


def recover(phrase, new_password):
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    _check_password(new_password)
    dek = _open_with(_normal(phrase), cfg, "rwrap")
    if dek is None:
        raise LockError("wrong_phrase")
    _rewrap(cfg, dek, new_password)
    _install(dek)


def _check_password(password):
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise LockError("password_short")


def _rewrap(cfg, dek, password):
    salt = secrets.token_bytes(16)
    cfg = dict(cfg, salt=_b64(salt), wrap=_wrap(_kek(password, salt, cfg["n"], cfg["r"], cfg["p"]), dek))
    _write(cfg)


def new_phrase(password):
    """A new recovery phrase, after the password was given again. The old phrase stops working. Shown once, like the first."""
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    dek = _open_with(str(password or ""), cfg, "wrap")
    if dek is None:
        raise LockError("wrong_password")
    rsalt, phrase = secrets.token_bytes(16), phrase_new()
    _write(dict(cfg, rsalt=_b64(rsalt), rwrap=_wrap(_kek(_normal(phrase), rsalt, cfg["n"], cfg["r"], cfg["p"]), dek)))
    return phrase


def change_password(old, new):
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    _check_password(new)
    dek = _open_with(str(old or ""), cfg, "wrap")
    if dek is None:
        raise LockError("wrong_password")
    _rewrap(cfg, dek, new)


# Switching on and off

def enable(password, biometric=False, auto_min=DEFAULT_AUTO):
    """Create the lock. Returns the recovery phrase. The data already on disk is sealed afterwards by migrate()."""
    if enabled():
        raise LockError("already_enabled")
    _check_password(password)
    from . import biometric as bio

    dek = seal.new_key()
    salt, rsalt, phrase = secrets.token_bytes(16), secrets.token_bytes(16), phrase_new()
    cfg = {"v": 1, "kdf": "scrypt", **SCRYPT, "salt": _b64(salt), "wrap": _wrap(_kek(password, salt), dek),
           "rsalt": _b64(rsalt), "rwrap": _wrap(_kek(_normal(phrase), rsalt), dek), "biometric": False,
           "auto_min": auto_min if auto_min in AUTO_CHOICES else DEFAULT_AUTO, "migrated": False}
    if biometric and bio.available() and bio.remember(dek):
        cfg["biometric"] = True
    _write(cfg)
    _install(dek)
    return phrase


def settings(auto_min=None, biometric=None):
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    from . import biometric as bio

    if auto_min is not None:
        if auto_min not in AUTO_CHOICES:
            raise LockError("bad_value")
        cfg["auto_min"] = auto_min
    if biometric is not None:
        if biometric:
            if not bio.available() or not bio.remember(_key()):
                raise LockError("no_biometric")
        else:
            bio.forget()
        cfg["biometric"] = bool(biometric)
    _write(cfg)


def disable(password):
    """Open every file again and remove the lock. The password is asked again: a session left open cannot switch it off."""
    cfg = _read()
    if cfg is None:
        raise LockError("not_enabled")
    if _open_with(str(password or ""), cfg, "wrap") is None:
        raise LockError("wrong_password")
    _key()
    # From here, what is written stays plain (nothing is sealed behind the pass) and the state says so on disk: a stop in the middle is taken up again.
    _write(dict(cfg, opening=True, migrated=False))
    _apply_flags()


def abort_disable():
    """Turning the lock off did not finish: go back to the locked state, and the upkeep seals what was opened."""
    cfg = _read()
    if cfg is not None:
        _write(dict(cfg, opening=False, migrated=False))
    _apply_flags()


def remaining():
    """How many files are still sealed (what turning the lock off has not opened yet)."""
    count = sum(1 for p in _data_files() if _is_blob(p))
    return count + sum(1 for p in audio_paths() if seal.is_sealed(p))


def _is_blob(path):
    try:
        with open(path, "rb") as handle:
            return seal.is_blob(handle.read(8))
    except OSError:
        return False


def finish_disable():
    """Remove the lock, but only once nothing is sealed any more: the key goes last."""
    from . import biometric

    left = remaining()
    if left:
        raise LockError("incomplete")
    biometric.forget()
    with _guard:
        with contextlib.suppress(OSError):
            _path().unlink()
        _state["dek"] = None
        config.set_codec(None)
        _apply_flags()


def _apply_flags(cfg=None):
    """What the rest of Cairn must know about the lock: write plain while it is being turned off, refuse plain files once all is sealed."""
    cfg = cfg if cfg is not None else _read()
    opening = bool(cfg and cfg.get("opening"))
    _state["opening"] = opening
    config.set_plain_writes(opening)
    config.set_strict(bool(cfg and cfg.get("migrated")) and not opening)


# Migration: seal (or open) what is already on disk. Each file is replaced only after the new copy was read back and matched.

def _data_files():
    home = config.home()
    for folder in (home / "Texts", home / "Index"):
        if folder.is_dir():
            yield from (p for p in sorted(folder.rglob("*.json")) if p.is_file())
    for name in ("settings.json", "voices.json"):
        if (home / name).is_file():
            yield home / name


def audio_files():
    folder = Path(config.load_settings().get("audio_dir") or config.home() / "Audio")
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in config.AUDIO_EXT and not path.is_symlink() and not path.name.startswith("."):
                yield path


def _replace_bytes(path, raw):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def audio_paths():
    """Every recording Cairn knows: the ones in the audio folder AND every file a note points to, wherever it is (the audio folder can be changed)."""
    seen, found = set(), []

    def add(path):
        try:
            key = path.resolve()
        except OSError:
            return
        if key not in seen and path.is_file() and not path.is_symlink() and path.suffix.lower() in config.AUDIO_EXT:
            seen.add(key)
            found.append(path)

    for path in audio_files():
        add(path)
    texts = config.home() / "Texts"
    if texts.is_dir():
        for note_path in sorted(texts.glob("*.json")):
            note = config.read_json_safe(note_path, default=None)
            if note and isinstance(note.get("audio"), str) and note["audio"]:
                add(Path(note["audio"]))
    return found


def migrate(to_sealed=True, progress=None, stop=None):
    """Seal (to_sealed) or open every protected file, then every recording. Safe to stop and start again: a file is in one state or the
    other, and both are read. A file that cannot be handled is reported at the end and does not keep the others from being handled.
    Returns how many files changed."""
    dek, changed, failures = _key(), 0, []
    _pass.acquire()  # a second request waits for the first and then finds nothing left to do
    _state["migrating"] = True
    try:
        files, audio = list(_data_files()), audio_paths()
        total, done = len(files) + len(audio), 0
        for path in files:
            if stop and stop():
                return changed  # stopped between two files: every file is whole, the next pass takes up the rest
            try:
                raw = path.read_bytes()
                if seal.is_blob(raw) != to_sealed:
                    if to_sealed:
                        new = seal.seal_blob(dek, raw, context(path))
                        if seal.open_blob(dek, new, context(path)) != raw:
                            raise config.Locked("the sealed copy did not match")
                    else:
                        new = seal.open_blob(dek, raw, context(path))
                    _replace_bytes(path, new)
                    changed += 1
            except (OSError, seal.SealError, config.Locked) as error:
                failures.append((path.name, str(error)[:60]))
            done += 1
            if progress:
                progress(done, total)
        for path in audio:
            if stop and stop():
                return changed
            try:
                if seal.is_sealed(path) != to_sealed:
                    new = path.with_name(path.name + ".new")
                    try:
                        if to_sealed:
                            digest = seal.seal_file(path, new, dek)
                            if seal.content_sha256(new, dek) != digest:
                                raise config.Locked("the sealed recording did not match")
                        else:
                            seal.unseal_file(path, new, dek)
                        os.replace(new, path)
                    finally:
                        with contextlib.suppress(OSError):
                            new.unlink()
                    changed += 1
            except (OSError, seal.SealError, config.Locked) as error:
                failures.append((path.name, str(error)[:60]))
            done += 1
            if progress:
                progress(done, total)
        _state["checked"] = time.time()
        cfg = _read()
        if cfg is not None and to_sealed and not failures:
            cfg["migrated"] = True
            _write(cfg)
            _apply_flags(cfg)
    finally:
        _state["migrating"] = False
        _pass.release()
    if failures:
        raise MigrationFailed(failures)
    return changed


def recheck_due():
    """Whether it is time to look again that every recording and file is sealed (a seal that failed once is not forgotten)."""
    if _state["dek"] is None or _state["opening"] or _state["migrating"] or not enabled():
        return False
    if time.time() - _state["checked"] < RECHECK_SECONDS:
        return False
    _state["checked"] = time.time()
    return True


def leftovers():
    """Temporary files a crash can leave behind (in the data folder, the audio folders and the private temporary folder): removed at start."""
    patterns = ("*.new", "*.sealing", "*.opening", ".upload-*.part")
    folders = [config.home() / ".tmp", Path(config.load_settings().get("audio_dir") or config.home() / "Audio")]
    for folder in folders:
        if not folder.is_dir():
            continue
        if folder.name == ".tmp":
            for path in folder.glob("*"):
                _shred(path)
            continue
        for pattern in patterns:
            for path in folder.rglob(pattern):
                if path.is_file():
                    _shred(path)


# Recordings

def tmpdir():
    folder = config.home() / ".tmp"
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    return folder


def purge_temp():
    folder = config.home() / ".tmp"
    if folder.is_dir():
        for path in folder.glob("*"):
            with contextlib.suppress(OSError):
                path.unlink()


@contextlib.contextmanager
def plain(path):
    """The recording as a plain file for a tool that needs one (the speech engine, the speaker model). A sealed recording is opened
    into a private temporary file that is overwritten and removed as soon as the tool is done."""
    if not seal.is_sealed(path):
        yield str(path)
        return
    temp = tmpdir() / ("%s%s" % (secrets.token_hex(8), Path(path).suffix))
    try:
        seal.unseal_file(path, temp, _key())
        yield str(temp)
    finally:
        _shred(temp)


def _shred(path):
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as handle:
            for _ in range(0, size, 1 << 20):
                handle.write(b"\0" * min(1 << 20, size))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        pass
    with contextlib.suppress(OSError):
        os.unlink(path)


def seal_audio(path):
    """Seal a recording that has just arrived, when the lock is on. A copy that cannot be read back is left plain, never lost."""
    if not enabled() or _state["dek"] is None or _state["opening"] or seal.is_sealed(path):
        return False
    dek = _state["dek"]
    new = Path(path).with_name(Path(path).name + ".new")
    try:
        digest = seal.seal_file(path, new, dek)
        if seal.content_sha256(new, dek) != digest:
            return False
        os.replace(new, path)
        return True
    except (OSError, seal.SealError):
        return False
    finally:
        with contextlib.suppress(OSError):
            new.unlink()


def audio_size(path):
    return seal.plain_size(path) if seal.is_sealed(path) else os.path.getsize(path)


def audio_read(path, start, end):
    if seal.is_sealed(path):
        return seal.read_range(path, _key(), start, end)
    with open(path, "rb") as handle:
        handle.seek(start)
        return handle.read(end - start + 1)


def audio_sha256(path):
    if seal.is_sealed(path):
        return seal.content_sha256(path, _key())
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def idle_for():
    return time.time() - _state["seen"]


def due():
    """Whether the idle time has passed and Cairn should lock itself."""
    from . import awake

    cfg = _read()
    minutes = (cfg or {}).get("auto_min", DEFAULT_AUTO)
    if awake.held():
        return False  # never while a job is running: a transcription is not cut by the lock
    return bool(cfg) and _state["dek"] is not None and minutes > 0 and idle_for() > minutes * 60
