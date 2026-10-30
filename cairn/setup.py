"""First steps: what Cairn needs, what is there, and what to do about what is missing.

Every check is a code and a status (ok, todo or warn), never a sentence: the page words them in the person's language.
The Pocket is advisory: audio files can be added by hand, so a missing Pocket never blocks the rest."""
import os
import shutil
import sys
from pathlib import Path

from . import config, llm, models, pocket, system

MIN_RAM_GB = 7.5      # the light models are meant for 8 GB
MIN_FREE_GB = 3.0     # a note needs little; a model download needs room
LOW_FREE_GB = 8.0


def _free_gb(folder):
    try:
        probe = Path(folder)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return shutil.disk_usage(probe).free / 1e9
    except OSError:
        return None


def _pocket():
    if pocket.find_pocket():
        return "ok"
    return "norecord" if pocket.volumes_without_record() else "absent"


def check():
    cfg = config.install_config()
    checks = []

    def add(code, status, **extra):
        checks.append(dict(extra, id=code, status=status))

    model_dir = Path(cfg["whisper_model"])
    add("speech", "ok" if model_dir.is_dir() else "todo")
    server = llm.available()
    add("ollama", "ok" if server and llm.find_ollama(cfg) else "todo")
    if server:
        names = {m.get("name", "") for m in llm.models()}
        wanted = cfg["llm"]
        add("llm", "ok" if wanted in names or wanted + ":latest" in names else "todo")
    else:
        add("llm", "todo")
    if cfg.get("engine") == "mlx":
        ffmpeg = shutil.which("ffmpeg", path=str(config.home() / "bin") + os.pathsep + os.environ.get("PATH", ""))
        add("ffmpeg", "ok" if ffmpeg else "todo")
    ram = system.ram_gb()
    if ram:
        add("memory", "ok" if ram >= MIN_RAM_GB else "warn", gb=round(ram))
    free = _free_gb(config.load_settings().get("audio_dir") or config.home())
    if free is not None:
        add("disk", "todo" if free < MIN_FREE_GB else ("warn" if free < LOW_FREE_GB else "ok"), gb=int(free))
    add("pocket", _pocket(), advisory=True)
    ready = all(c["status"] != "todo" for c in checks if not c.get("advisory"))
    return {"ready": ready, "checks": checks, "platform": sys.platform}
