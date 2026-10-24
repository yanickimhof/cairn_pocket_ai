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
            if path.is_file() and path.suffix.lower() in AUDIO_EXT and not path.name.startswith("."):
                found.append(path)
        except OSError:
            continue
    return sorted(found, key=lambda p: (p.stat().st_mtime, p.name))


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
