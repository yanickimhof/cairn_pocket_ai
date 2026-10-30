"""Paths, settings and installer configuration."""

import json
import os
import re
import tempfile
import threading
from pathlib import Path

from . import catalog, templates, vocab

VERSION = "0.7.0"
REPO = "yanickimhof/cairn_pocket_ai"
REFERRAL_URL = "https://referral.heypocketai.com/refer/39179caf?source=desktop_qr"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".opus", ".ogg", ".flac")
LOOPBACK = re.compile(r"127\.0\.0\.1:\d{2,5}")
DEFAULT_LLM = "qwen3:4b"
LEVELS = ("short", "mid", "full")
LANGS = ("fr", "en")
DEFAULT_SETTINGS = {"ui": None, "audio_dir": None, "llm": None, "speech": None, "autocheck": True, "autoimport": True, "autoprocess": False, "pocket_key": None, "diarize": False, "diarize_device": "auto", "vocabulary": [], "templates": [], "template_default": "", "tags_suggest": False, "pocket_secure_auto": False, "vocab_ignored": [], "embed": None, "voices": False, "hf_token": None, "setup_done": False, "menubar": True}

_lock = threading.RLock()


def home():
    """The Cairn folder (default ~/Cairn)."""
    return Path(os.environ.get("CAIRN_HOME") or Path.home() / "Cairn").expanduser()


class Locked(Exception):
    """Cairn is locked: what is kept sealed cannot be read or written until it is opened."""


_codec = None  # set by lock.py while Cairn is unlocked: it seals and opens what read_json and write_json handle
NEVER_SEALED = ("config.json", "lock.json", "privacy-check.json", "vault-index.json")


def set_codec(codec):
    global _codec
    _codec = codec


def _sealing():
    return (home() / "lock.json").is_file()


def read_json(path, default=None):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        if raw[:7] == b"CAIRNB1":
            if _codec is None:
                if Path(path).name == "settings.json":
                    return {} if default is None else default  # the start-up code reads the settings before anyone has unlocked
                raise Locked("Cairn is locked")
            raw = _codec.open(raw, path)
        return json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, data):
    """Atomic write, readable by the owner only. Sealed when the lock is on, and refused while Cairn is locked."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seal_it = path.name not in NEVER_SEALED and _sealing()
    if seal_it and _codec is None:
        raise Locked("Cairn is locked")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            handle.write(_codec.seal(raw, path) if seal_it else raw)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def install_config():
    """Values written by the installer (config.json), overridable by environment variables."""
    cfg = read_json(home() / "config.json")
    names = {
        "engine": "CAIRN_ENGINE",
        "whisper_model": "CAIRN_WHISPER_MODEL",
        "llm": "CAIRN_LLM",
        "ollama_host": "OLLAMA_HOST",
        "ollama_bin": "CAIRN_OLLAMA",
    }
    for key, var in names.items():
        if os.environ.get(var):
            cfg[key] = os.environ[var]
    cfg.setdefault("llm", DEFAULT_LLM)
    cfg.setdefault("ollama_host", "127.0.0.1:11434")
    cfg.setdefault("whisper_dir", str(home() / "models" / "whisper"))
    # the model chosen in the app, unless the environment forces one
    chosen = read_json(home() / "settings.json")
    if chosen.get("llm") and not os.environ.get("CAIRN_LLM"):
        cfg["llm"] = chosen["llm"]
    cfg["speech_engine"] = cfg.get("engine")  # the engine that runs the speech model: "parakeet" when that model is the chosen one
    if os.environ.get("CAIRN_WHISPER_MODEL"):
        cfg["whisper_dir"] = cfg["whisper_model"] = os.environ["CAIRN_WHISPER_MODEL"]
    else:
        cfg["whisper_dir"] = cfg.get("whisper_model") or cfg["whisper_dir"]
        speech_id = chosen.get("speech")
        marked = home() / "models" / str(speech_id) / ".cairn-complete"
        cfg["whisper_model"] = str(marked.parent) if speech_id and marked.exists() else cfg["whisper_dir"]
        if speech_id == "parakeet" and marked.exists() and cfg.get("engine") == "mlx":
            cfg["speech_engine"] = "parakeet"
    return cfg


def load_settings():
    with _lock:
        saved = read_json(home() / "settings.json")
    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    if not settings["audio_dir"]:
        settings["audio_dir"] = str(home() / "Audio")
    return settings


def public_settings(settings):
    """The settings as the page needs them: a secret is shown as set or not, never in full."""
    shown = dict(settings)
    for key in ("hf_token", "pocket_key"):
        shown[key] = True if shown.get(key) else None
    return shown


def save_settings(patch):
    """Validate and store a partial settings update. Returns the new settings."""
    with _lock:
        current = load_settings()
        for key, value in patch.items():
            if key == "ui" and value in LANGS:
                current["ui"] = value
            elif key in ("autocheck", "autoimport", "autoprocess", "tags_suggest", "pocket_secure_auto", "voices", "setup_done", "menubar") and isinstance(value, bool):
                current[key] = value
            elif key == "llm" and value in catalog.LLM_IDS:
                current["llm"] = value
            elif key == "embed" and (value in catalog.EMBED_IDS or value in (None, "")):
                current["embed"] = value or None
            elif key == "speech" and value in catalog.SPEECH_IDS:
                current["speech"] = value
            elif key == "audio_dir" and isinstance(value, str) and value.strip():
                folder = Path(value.strip()).expanduser()
                if not folder.is_absolute():
                    raise ValueError("The audio folder must be an absolute path.")
                folder.mkdir(parents=True, exist_ok=True)
                current["audio_dir"] = str(folder)
            elif key == "diarize" and isinstance(value, bool):
                current["diarize"] = value
            elif key == "diarize_device" and value in ("auto", "cpu"):
                current["diarize_device"] = value
            elif key == "vocabulary":
                current["vocabulary"] = vocab.parse(value)
            elif key == "vocab_ignored":
                if not isinstance(value, list) or len(value) > 500 or not all(isinstance(v, str) and 0 < len(v) <= 60 for v in value):
                    raise ValueError("Invalid list of ignored words.")
                current["vocab_ignored"] = list(dict.fromkeys(value))
            elif key == "templates":
                current["templates"] = templates.parse(value)
                if current.get("template_default") and not templates.find(current["templates"], current["template_default"]):
                    current["template_default"] = ""  # the template that was the default is gone
            elif key == "template_default":
                if value and not templates.find(current.get("templates"), value):
                    raise ValueError("Unknown template.")
                current["template_default"] = value or ""
            elif key == "hf_token":
                # a Hugging Face access token, used only to download the gated diarization model once.
                # Not sent anywhere by Cairn beyond that one download; never logged. Empty clears it.
                if value in (None, ""):
                    current["hf_token"] = None
                elif isinstance(value, str) and 8 <= len(value.strip()) <= 200 and not any(c.isspace() for c in value.strip()):
                    current["hf_token"] = value.strip()
                else:
                    raise ValueError("Invalid Hugging Face token.")
            elif key == "pocket_key":
                # the person's own Pocket BLE session key (captured by them, with their own tools), used only to
                # read firmware/state/storage over an authenticated connection. Empty clears it. Never logged.
                if value in (None, ""):
                    current["pocket_key"] = None
                elif isinstance(value, str) and len(value.strip()) == 16 and value.strip().isprintable() and not any(c.isspace() for c in value.strip()):
                    current["pocket_key"] = value.strip()
                else:
                    raise ValueError("The Pocket session key must be exactly 16 characters.")
            else:
                raise ValueError("Invalid setting: %s" % key)
        write_json(home() / "settings.json", current)
        return current
