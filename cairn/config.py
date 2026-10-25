"""Paths, settings and installer configuration."""

import json
import os
import re
import tempfile
import threading
from pathlib import Path

from . import catalog

VERSION = "0.1.0"
REPO = "yanickimhof/cairn_pocket_ai"
REFERRAL_URL = "https://referral.heypocketai.com/refer/39179caf?source=desktop_qr"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".opus", ".ogg", ".flac")
LOOPBACK = re.compile(r"127\.0\.0\.1:\d{2,5}")
DEFAULT_LLM = "qwen3:4b"
LEVELS = ("short", "mid", "full")
LANGS = ("fr", "en")
DEFAULT_SETTINGS = {"ui": None, "tr": None, "audio_dir": None, "llm": None, "speech": None, "polish": False, "autocheck": True}

_lock = threading.RLock()


def home():
    """The Cairn folder (default ~/Cairn)."""
    return Path(os.environ.get("CAIRN_HOME") or Path.home() / "Cairn").expanduser()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {} if default is None else default


def write_json(path, data):
    """Atomic write, readable by the owner only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
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
    if os.environ.get("CAIRN_WHISPER_MODEL"):
        cfg["whisper_dir"] = cfg["whisper_model"] = os.environ["CAIRN_WHISPER_MODEL"]
    else:
        cfg["whisper_dir"] = cfg.get("whisper_model") or cfg["whisper_dir"]
        speech_id = chosen.get("speech")
        marked = home() / "models" / str(speech_id) / ".cairn-complete"
        cfg["whisper_model"] = str(marked.parent) if speech_id and marked.exists() else cfg["whisper_dir"]
    return cfg


def load_settings():
    with _lock:
        saved = read_json(home() / "settings.json")
    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    if not settings["audio_dir"]:
        settings["audio_dir"] = str(home() / "Audio")
    return settings


def save_settings(patch):
    """Validate and store a partial settings update. Returns the new settings."""
    with _lock:
        current = load_settings()
        for key, value in patch.items():
            if key == "ui" and value in LANGS:
                current["ui"] = value
            elif key == "tr" and value in LANGS:
                current["tr"] = value
            elif key in ("polish", "autocheck") and isinstance(value, bool):
                current[key] = value
            elif key == "llm" and value in catalog.LLM_IDS:
                current["llm"] = value
            elif key == "speech" and value in catalog.SPEECH_IDS:
                current["speech"] = value
            elif key == "audio_dir" and isinstance(value, str) and value.strip():
                folder = Path(value.strip()).expanduser()
                if not folder.is_absolute():
                    raise ValueError("The audio folder must be an absolute path.")
                folder.mkdir(parents=True, exist_ok=True)
                current["audio_dir"] = str(folder)
            else:
                raise ValueError("Invalid setting: %s" % key)
        write_json(home() / "settings.json", current)
        return current
