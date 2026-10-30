"""Find the Pocket, list its recordings and copy them with verification."""

import hashlib
import os
import shutil
import string
import struct
import sys
import time
import wave
from pathlib import Path

from . import vault
from .config import AUDIO_EXT


def _record_folder(volume):
    try:
        for child in volume.iterdir():
            if child.is_dir() and child.name.upper() == "RECORD":
                return child
    except OSError:
        pass
    return None


def _windows_label(root):
    import ctypes

    label = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), label, 261, None, None, None, None, 0
    )
    return label.value if ok else ""


def find_pocket():
    """The RECORD folder of the connected Pocket, or None.

    CAIRN_POCKET_DIR points to a folder instead (tests, backups of a Pocket).
    """
    override = os.environ.get("CAIRN_POCKET_DIR")
    if override:
        folder = Path(override).expanduser()
        return folder if folder.is_dir() else None
    volumes = []
    if sys.platform == "darwin":
        base = Path("/Volumes")
        if base.is_dir():
            volumes = [v for v in base.iterdir() if v.name.lower().startswith("pocket")]
    elif sys.platform.startswith("win"):
        import ctypes

        for letter in string.ascii_uppercase[2:]:
            root = letter + ":\\"
            if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) in (2, 3):
                if os.path.isdir(root + "RECORD") and _windows_label(root).lower().startswith("pocket"):
                    volumes.append(Path(root))
    else:
        user = os.environ.get("USER", "")
        for base in (Path("/media") / user, Path("/run/media") / user, Path("/mnt")):
            if base.is_dir():
                volumes += [v for v in base.iterdir() if v.name.lower().startswith("pocket")]
    for volume in volumes:
        folder = _record_folder(volume)
        if folder:
            return folder
    return None


def list_recordings(folder):
    """Audio files under the RECORD folder, oldest first."""
    found = []
    for path in Path(folder).rglob("*"):
        try:
            # a link is never followed: a drive must not be able to make Cairn copy a file of this computer
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in AUDIO_EXT and not path.name.startswith("."):
                found.append(path)
        except OSError:
            continue
    return sorted(found, key=lambda p: (p.stat().st_mtime, p.name))


class Entry:
    """One recording on the Pocket, readable or not: its name as Cairn knows it (rel), where the file is (path),
    whether it is encrypted, and its size and date as the recording had them."""

    __slots__ = ("rel", "size", "mtime", "path", "sealed", "fid")

    def __init__(self, rel, size, mtime, path, sealed=False, fid=None):
        self.rel, self.size, self.mtime, self.path, self.sealed, self.fid = rel, size, mtime, path, sealed, fid


class Listing:
    """What is on the Pocket: the plain recordings, the encrypted ones that can be read with the key, the encrypted
    ones that cannot (no key on this computer), and the vault header if the Pocket has one."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.header = vault.read_header(folder)
        self.key = vault.recall(self.header["id"]) if self.header else None
        if self.key is not None and not vault.key_matches(self.header, self.key):
            self.key = None  # a key that is not this vault's counts as no key
        self.plain, self.sealed, self.locked = [], [], 0

    @property
    def readable(self):
        return self.plain + self.sealed

    def state(self):
        """none (no vault), damaged (encrypted files but no readable header), partial (some recordings still plain), secured,
        or locked (no key here)."""
        if not self.header:
            return "damaged" if self.locked else "none"
        if self.key is None:
            return "locked"
        return "partial" if self.plain else "secured"


_RESERVED = frozenset("con prn aux nul com1 com2 com3 com4 com5 com6 com7 com8 com9 lpt1 lpt2 lpt3 lpt4 lpt5 lpt6 lpt7 lpt8 lpt9".split())


def _safe_rel(value):
    """A relative name coming from an encrypted file, kept only when it is an ordinary audio file name that stays inside the audio
    folder on every system (no drive, no stream, no device name, no trailing dot)."""
    if not isinstance(value, str) or not value or len(value) > 240 or any(c in value for c in '\\\0:*?"<>|'):
        return None
    if value.startswith("/") or Path(value).suffix.lower() not in AUDIO_EXT:
        return None
    for part in value.split("/"):
        if part in ("", ".", "..") or len(part) > 120 or part != part.strip() or part.endswith(".") or part.split(".")[0].lower() in _RESERVED:
            return None
        if any(ord(c) < 32 for c in part):
            return None
    return value


def scan(folder):
    """Look at the Pocket once: plain and encrypted recordings. Names of encrypted files are read once and then
    remembered on this computer."""
    found = Listing(folder)
    for path in list_recordings(folder):
        st = path.stat()
        found.plain.append(Entry(path.relative_to(folder).as_posix(), st.st_size, int(st.st_mtime), path))
    sealed = []
    try:
        for child in Path(folder).iterdir():
            if child.suffix == vault.EXT and not child.name.startswith(".") and child.is_file() and not child.is_symlink():
                sealed.append(child)
    except OSError:
        pass
    index = vault.load_index(found.header["id"]) if found.header and found.key else {}
    changed = False
    for child in sorted(sealed):
        if not found.key:
            found.locked += 1
            continue
        info = index.get(child.stem)
        size = child.stat().st_size
        if not info or info.get("file") != size:
            try:
                meta = vault.read_meta(child, found.key)
            except (vault.VaultError, OSError):
                found.locked += 1  # damaged, or made with another key: counted, never read
                continue
            rel = _safe_rel(meta.get("name"))
            if rel is None or not isinstance(meta.get("size"), int) or not isinstance(meta.get("mtime"), int):
                found.locked += 1
                continue
            info = {"rel": rel, "size": meta["size"], "mtime": meta["mtime"], "file": size}
            index[child.stem] = info
            changed = True
        found.sealed.append(Entry(info["rel"], info["size"], info["mtime"], child, True, child.stem))
    if changed:
        try:
            vault.save_index(found.header["id"], index)
        except OSError:
            pass
    found.plain.sort(key=lambda e: (e.mtime, e.rel))
    found.sealed.sort(key=lambda e: (e.mtime, e.rel))
    return found


def fetch(entry, dst, key=None):
    """Bring one recording to this computer with verification. Returns its SHA-256."""
    if not entry.sealed:
        return copy_verified(entry.path, dst)
    if key is None:
        raise OSError("the Pocket is locked")
    try:
        _, digest = vault.unseal(entry.path, dst, key)
    except vault.VaultError as error:
        raise OSError("cannot decrypt %s: %s" % (entry.rel, error)) from error
    try:
        os.utime(dst, (entry.mtime, entry.mtime))
    except OSError:
        pass
    return digest


def seal_entry(folder, entry, key, expect_sha):
    """Encrypt one plain recording of the Pocket and replace it, only once the encrypted file has been read back and
    proven identical, and only if the recording did not change meanwhile. Returns the (file id, info) to remember."""
    folder = Path(folder)
    before = entry.path.stat()
    fid = vault.new_fid()
    part = folder / (fid.hex() + vault.EXT + ".part")
    final = folder / (fid.hex() + vault.EXT)
    try:
        digest = vault.seal(entry.path, part, key, {"name": entry.rel, "size": before.st_size, "mtime": int(before.st_mtime)}, fid)
        if expect_sha and digest != expect_sha:
            raise OSError("the recording changed since it was copied: it stays as it is")
        if vault.content_hash(part, key) != digest:
            raise OSError("the encrypted copy could not be verified")
        after = entry.path.stat()
        if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            raise OSError("the recording changed while it was encrypted: it stays as it is")
        os.replace(part, final)
    except (OSError, vault.VaultError) as error:
        try:
            part.unlink()
        except OSError:
            pass
        raise OSError(str(error)) from error
    # the plain file first leaves its name (proving it can be removed), then is overwritten with noise, then deleted
    doomed = entry.path.with_name(".shred-" + fid.hex())
    try:
        os.replace(entry.path, doomed)
    except OSError as error:  # the plain file cannot be removed (read-only): keep one version only
        try:
            final.unlink()
        except OSError:
            pass
        raise OSError("cannot remove the plain recording: %s" % error) from error
    shred(doomed, before.st_size)
    try:
        doomed.unlink()
    except OSError:
        pass  # a hidden file of noise is left: nothing readable, and the listing never looks at hidden files
    try:  # the dated folders of the Pocket would tell when each recording was made: empty ones are removed
        parent = entry.path.parent
        while parent != folder and parent.is_relative_to(folder):
            parent.rmdir()
            parent = parent.parent
    except OSError:
        pass
    return fid.hex(), {"rel": entry.rel, "size": before.st_size, "mtime": int(before.st_mtime), "file": final.stat().st_size}


def shred(path, size):
    """Overwrite a recording with noise before it is deleted, so that an undelete tool finds nothing on a drive that keeps the old
    blocks. Best effort: a flash drive may still hold a copy in blocks it moved by itself."""
    try:
        with open(path, "r+b") as handle:
            left = size
            while left > 0:
                block = min(left, 1 << 20)
                handle.write(os.urandom(block))
                left -= block
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        pass


def clean_leftovers(folder):
    """Remove half-written encrypted files left by an unplugged Pocket."""
    try:
        for child in Path(folder).iterdir():
            if child.name.endswith(vault.EXT + ".part") or child.name == vault.HEADER_NAME + ".part" or child.name.startswith(".shred-"):
                child.unlink()
    except OSError:
        pass


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_verified(src, dst, retries=5):
    """Copy src to dst, read the copy back and compare. Returns the SHA-256 of the file.

    Resumable: a file that is already there with the same content is left alone.
    Raises OSError if no attempt produced an identical copy.
    """
    src, dst = Path(src), Path(dst)
    if not src.exists():  # unplugged or deleted: waiting and trying again would only make the person wait
        raise FileNotFoundError("the file is no longer there (Pocket disconnected?)")
    dst.parent.mkdir(parents=True, exist_ok=True)
    last = "unknown error"
    for attempt in range(retries):
        part = dst.with_name(dst.name + ".part")
        try:
            digest = hashlib.sha256()
            with open(src, "rb") as reader, open(part, "wb") as writer:
                for block in iter(lambda: reader.read(1 << 20), b""):
                    digest.update(block)
                    writer.write(block)
                writer.flush()
                os.fsync(writer.fileno())
            if sha256(part) != digest.hexdigest():
                raise OSError("the copy does not match the original")
            shutil.copystat(src, part, follow_symlinks=True)
            os.replace(part, dst)
            return digest.hexdigest()
        except OSError as error:
            last = str(error)
            try:
                part.unlink()
            except OSError:
                pass
            time.sleep(1 + attempt)
    raise OSError("copy failed after %d attempts: %s" % (retries, last))


_MP3_BITRATES = {
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_MP3_RATES = {1: (44100, 48000, 32000), 2: (22050, 24000, 16000), 3: (11025, 12000, 8000)}


def _mp3_duration(path):
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        head = handle.read(1 << 16)
    offset = 0
    if head[:3] == b"ID3" and len(head) >= 10:
        offset = 10 + ((head[6] & 0x7F) << 21 | (head[7] & 0x7F) << 14 | (head[8] & 0x7F) << 7 | (head[9] & 0x7F))
        with open(path, "rb") as handle:
            handle.seek(offset)
            head = handle.read(1 << 16)
    for i in range(len(head) - 4):
        if head[i] != 0xFF or (head[i + 1] & 0xE0) != 0xE0:
            continue
        version = {3: 1, 2: 2, 0: 3}.get((head[i + 1] >> 3) & 3)
        if version is None or ((head[i + 1] >> 1) & 3) != 1:  # layer III only
            continue
        bitrate_index, rate_index = head[i + 2] >> 4, (head[i + 2] >> 2) & 3
        if bitrate_index in (0, 15) or rate_index == 3:
            continue
        bitrate = _MP3_BITRATES[1 if version == 1 else 2][bitrate_index] * 1000
        rate = _MP3_RATES[version][rate_index]
        per_frame = 1152 if version == 1 else 576
        window = head[i : i + 200]
        for tag in (b"Xing", b"Info"):
            at = window.find(tag)
            if at != -1 and len(window) >= at + 12 and window[at + 7] & 1:
                frames = struct.unpack(">I", window[at + 8 : at + 12])[0]
                return frames * per_frame / rate
        return (size - offset) * 8 / bitrate
    return None


def estimate_duration(path):
    """Length in seconds (exact for WAV, estimated for MP3), or None."""
    try:
        suffix = Path(path).suffix.lower()
        if suffix == ".wav":
            with wave.open(str(path), "rb") as handle:
                return handle.getnframes() / float(handle.getframerate())
        if suffix == ".mp3":
            return _mp3_duration(path)
    except (OSError, EOFError, wave.Error, struct.error):
        pass
    return None
