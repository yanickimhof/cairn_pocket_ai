"""Models on demand: list, download (only when the user asks) and select."""

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import catalog, config, llm

MARK = ".cairn-complete"
_PULL_STATUS_KEYS = ("status", "total", "completed")


def speech_entries():
    cfg = config.install_config()
    return catalog.SPEECH.get(cfg.get("engine"), [])


def diar_dir():
    """Where the diarization model's weights are cached (kept inside Cairn's own folder, not the user's global
    Hugging Face cache), and the marker file that says the one-time download finished."""
    return config.home() / "models" / "diar"


def diar_installed():
    """The model is there and so is the package that runs it (an update that rebuilds the environment removes the package)."""
    if not (diar_dir() / MARK).exists():
        return False
    try:
        return importlib.util.find_spec("pyannote.audio") is not None
    except (ImportError, ValueError):
        return False


def dir_size(path):
    """Bytes really used on disk by the files under `path`: links are not followed, so a cache that points to
    its own files is not counted twice."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            try:
                if not os.path.islink(full):
                    total += os.path.getsize(full)
            except OSError:
                pass
    return total


def diar_entries():
    installed = diar_installed()
    return [dict(m, installed=installed, **({"bytes": dir_size(diar_dir())} if installed else {})) for m in catalog.DIAR]


def speech_dir(model_id):
    return config.home() / "models" / model_id


def speech_installed(entry):
    cfg = config.install_config()
    if (speech_dir(entry["id"]) / MARK).exists():
        return True
    # the model the installer downloaded (folder "whisper")
    return cfg.get("whisper_repo") == entry["repo"] and os.path.isdir(cfg.get("whisper_dir") or "")


def speech_path(entry):
    cfg = config.install_config()
    if (speech_dir(entry["id"]) / MARK).exists():
        return str(speech_dir(entry["id"]))
    return cfg.get("whisper_dir") or ""


def selected_speech():
    wanted = config.load_settings().get("speech")
    entries = speech_entries()
    for entry in entries:
        if entry["id"] == wanted and speech_installed(entry):
            return wanted
    cfg = config.install_config()
    for entry in entries:
        if entry["repo"] == cfg.get("whisper_repo"):
            return entry["id"]
    return None


def listing(job):
    sizes = {m.get("name"): m.get("size", 0) for m in llm.models()}
    chosen_llm = config.install_config()["llm"]
    chosen_speech = selected_speech()
    # an installed model shows the size it really has on this computer; the catalog size is only an estimate
    out_llm = [
        dict(m, installed=m["id"] in sizes, selected=m["id"] == chosen_llm, **({"bytes": sizes[m["id"]]} if sizes.get(m["id"]) else {}))
        for m in catalog.LLM
    ]
    out_speech = []
    for m in speech_entries():
        have = speech_installed(m)
        entry = {k: v for k, v in m.items() if k not in ("repo", "revision")}
        if have and os.path.isdir(speech_path(m) or ""):
            entry["bytes"] = dir_size(speech_path(m))
        out_speech.append(dict(entry, installed=have, selected=m["id"] == chosen_speech))
    from . import embed

    chosen_embed = config.load_settings().get("embed")
    out_embed = [
        dict(m, installed=embed.installed(m["id"]), selected=m["id"] == chosen_embed, **({"bytes": sizes[m["id"]]} if sizes.get(m["id"]) else {}))
        for m in catalog.EMBED
    ]
    return {"llm": out_llm, "speech": out_speech, "diar": diar_entries(), "embed": out_embed, "job": job, "server_up": llm.available()}


class Downloader:
    """One model download at a time, started only by an explicit request."""

    def __init__(self):
        self._lock = threading.Lock()
        self.job = None

    def state(self):
        with self._lock:
            return dict(self.job) if self.job else None

    def _set(self, **fields):
        with self._lock:
            if self.job is not None:
                self.job.update(fields)

    def start(self, kind, model_id):
        with self._lock:
            if self.job and self.job["state"] == "running":
                raise RuntimeError("busy")
            if kind == "llm":
                entry = next((m for m in catalog.LLM if m["id"] == model_id), None)
            elif kind == "embed":
                entry = next((m for m in catalog.EMBED if m["id"] == model_id), None)
            elif kind == "diar":
                entry = next((m for m in catalog.DIAR if m["id"] == model_id), None)
                if entry is not None and not config.load_settings().get("hf_token"):
                    raise ValueError("token_required")
            else:
                entry = next((m for m in speech_entries() if m["id"] == model_id), None)
            if entry is None:
                raise ValueError("unknown_model")
            self.job = {"kind": kind, "id": model_id, "state": "running", "pct": 0, "error": ""}
        target = self._pull_llm if kind in ("llm", "embed") else self._fetch_diar if kind == "diar" else self._fetch_speech
        threading.Thread(target=target, args=(entry,), daemon=True).start()

    def _pull_llm(self, entry):
        try:
            minimum = entry.get("min_ollama")
            if minimum:
                found = llm.version()
                if not llm.at_least(found, minimum):
                    raise RuntimeError("%s needs Ollama %s or newer (found %s). Update Ollama, then try again." % (entry["label"], minimum, found))
            body = json.dumps({"model": entry["id"], "stream": True}).encode()
            request = urllib.request.Request(
                "http://%s/api/pull" % llm._host(), data=body, headers={"Content-Type": "application/json"}
            )
            # Loopback only, plain http: the local model server fetches the model itself.
            with urllib.request.urlopen(request, timeout=3600) as response:  # nosec B310
                for raw in response:
                    try:
                        line = json.loads(raw)
                    except ValueError:
                        continue
                    if line.get("error"):
                        raise RuntimeError(str(line["error"])[:160])
                    if line.get("total"):
                        self._set(pct=int(100 * line.get("completed", 0) / line["total"]))
            if entry in catalog.EMBED and not config.load_settings().get("embed"):
                config.save_settings({"embed": entry["id"]})  # the first search model installed is the one used
            self._set(state="done", pct=100)
        except Exception as error:  # reported to the page, never raised
            self._set(state="error", error=str(error)[:400])

    @staticmethod
    def parakeet_requirements():
        path = Path(__file__).resolve().parent.parent / "requirements" / "parakeet-macos-arm64.txt"
        return path if path.is_file() and sys.platform == "darwin" and platform.machine() == "arm64" else None

    def _install_locked(self, lock):
        """Install a pinned, hashed list of packages inside Cairn's own environment (uv when there is one, else pip)."""
        uv = shutil.which("uv") or str(config.home() / "bin" / "uv")
        if Path(uv).exists() or shutil.which(uv):
            command = [uv, "pip", "install", "--python", sys.executable, "--quiet", "--require-hashes", "--no-deps", "-r", str(lock)]
        else:
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True, timeout=120, check=False)  # nosec B603
            command = [sys.executable, "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps", "-r", str(lock)]
        done = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)  # nosec B603
        if done.returncode != 0:
            tail = (done.stderr or "").strip().splitlines()[-1:]
            raise RuntimeError("Could not install the package. " + " ".join(tail))

    def _fetch_speech(self, entry):
        target = speech_dir(entry["id"])
        part = target.with_name(target.name + ".part")
        try:
            shutil.rmtree(part, ignore_errors=True)
            part.mkdir(parents=True, exist_ok=True)
            if entry.get("engine") == "parakeet" and importlib.util.find_spec("parakeet_mlx") is None:
                lock = self.parakeet_requirements()
                if lock is None:
                    raise RuntimeError("Parakeet needs a Mac with Apple silicon.")
                self._set(pct=1)
                self._install_locked(lock)
            env = dict(os.environ, HF_HUB_OFFLINE="0", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
            code = "import sys; from huggingface_hub import snapshot_download as d; d(sys.argv[1], revision=sys.argv[3] or None, local_dir=sys.argv[2])"
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(  # nosec B603
                [sys.executable, "-c", code, entry["repo"], str(part), entry.get("revision", "")],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, creationflags=flags,
            )
            while proc.poll() is None:
                size = sum(f.stat().st_size for f in part.rglob("*") if f.is_file())
                self._set(pct=min(99, int(100 * size / max(entry["bytes"], 1))))
                time.sleep(1)
            if proc.returncode != 0:
                tail = (proc.stderr.read() or "").strip().splitlines()[-1:]
                raise RuntimeError("Download failed. " + " ".join(tail))
            (part / MARK).write_text("ok", encoding="utf-8")
            shutil.rmtree(target, ignore_errors=True)
            os.replace(part, target)
            self._set(state="done", pct=100)
        except Exception as error:  # reported to the page, never raised
            shutil.rmtree(part, ignore_errors=True)
            self._set(state="error", error=str(error)[:400])

    @staticmethod
    def diar_requirements():
        """The pinned, hashed list of packages for speaker identification on this system, or None where none exists
        (Intel Macs: the speech package it needs has no build for them)."""
        name = {"darwin": "diar-macos-arm64.txt" if platform.machine() == "arm64" else None, "win32": "diar-windows.txt"}.get(sys.platform)
        path = Path(__file__).resolve().parent.parent / "requirements" / name if name else None
        return path if path and path.is_file() else None

    def _fetch_diar(self, entry):
        """Installs the diarization package (pyannote.audio) if needed, then downloads its gated model
        weights with the person's own Hugging Face token, cached inside Cairn's own folder. The token is
        passed as an environment variable to a subprocess, never written to a file, never logged."""
        target = diar_dir()
        part = target.with_name(target.name + ".part")
        token = config.load_settings().get("hf_token") or ""
        try:
            shutil.rmtree(part, ignore_errors=True)
            part.mkdir(parents=True, exist_ok=True)
            self._set(pct=2)
            try:
                import pyannote.audio  # noqa: F401
            except ImportError:
                lock = self.diar_requirements()
                if lock is None:
                    raise RuntimeError("Speaker identification is not available on this computer.")
                uv = shutil.which("uv") or str(config.home() / "bin" / "uv")
                if Path(uv).exists() or shutil.which(uv):
                    pip = subprocess.run(  # nosec B603
                        [uv, "pip", "install", "--python", sys.executable, "--quiet", "--require-hashes", "--no-deps", "-r", str(lock)],
                        capture_output=True, text=True, timeout=1800, check=False,
                    )
                else:
                    # No pip inside this venv (installed with uv) and no uv on hand: bootstrap pip itself first.
                    subprocess.run(  # nosec B603
                        [sys.executable, "-m", "ensurepip", "--upgrade"],
                        capture_output=True, text=True, timeout=120, check=False,
                    )
                    pip = subprocess.run(  # nosec B603
                        [sys.executable, "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps", "-r", str(lock)],
                        capture_output=True, text=True, timeout=1800, check=False,
                    )
                if pip.returncode != 0:
                    tail = (pip.stderr or "").strip().splitlines()[-1:]
                    raise RuntimeError("Could not install pyannote.audio. " + " ".join(tail))
            self._set(pct=40)
            env = dict(os.environ, HF_HUB_OFFLINE="0", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", HF_HOME=str(part / "hf_cache"), HF_TOKEN=token)
            code = (
                "import os, sys\n"
                "from pyannote.audio import Pipeline\n"
                "tok = os.environ.get('HF_TOKEN') or None\n"
                "try:\n"
                "    Pipeline.from_pretrained(sys.argv[1], token=tok)\n"
                "except TypeError:\n"
                "    Pipeline.from_pretrained(sys.argv[1], use_auth_token=tok)\n"
            )
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.run(  # nosec B603
                [sys.executable, "-c", code, entry["repo"]], env=env, capture_output=True, text=True,
                timeout=1800, check=False, creationflags=flags,
            )
            if proc.returncode != 0:
                tail = (proc.stderr or "").strip().splitlines()[-1:]
                raise RuntimeError("Download failed. " + " ".join(tail))
            (part / MARK).write_text("ok", encoding="utf-8")
            shutil.rmtree(target, ignore_errors=True)
            os.replace(part, target)
            self._set(state="done", pct=100)
        except Exception as error:  # reported to the page, never raised; the token itself is never included
            shutil.rmtree(part, ignore_errors=True)
            self._set(state="error", error=str(error)[:400])


def select(kind, model_id):
    """Use an installed model from now on."""
    if kind == "llm":
        if model_id not in catalog.LLM_IDS or model_id not in {m.get("name") for m in llm.models()}:
            raise ValueError("not_installed")
        return config.save_settings({"llm": model_id})
    if kind == "embed":
        from . import embed

        if model_id not in catalog.EMBED_IDS or not embed.installed(model_id):
            raise ValueError("not_installed")
        return config.save_settings({"embed": model_id})
    entry = next((m for m in speech_entries() if m["id"] == model_id), None)
    if entry is None or not speech_installed(entry):
        raise ValueError("not_installed")
    return config.save_settings({"speech": model_id})


def remove(kind, model_id):
    """Uninstall a model that is installed and not in use, to free disk space."""
    if kind == "llm":
        if model_id not in catalog.LLM_IDS or model_id not in {m.get("name") for m in llm.models()}:
            raise ValueError("not_installed")
        if model_id == config.install_config()["llm"]:
            raise ValueError("in_use")
        try:
            llm.delete_model(model_id)
        except (OSError, ValueError, llm.LLMError):
            raise ValueError("remove_failed")
        return {"ok": True}
    if kind == "embed":
        from . import embed

        if model_id not in catalog.EMBED_IDS or not embed.installed(model_id):
            raise ValueError("not_installed")
        try:
            llm.delete_model(model_id)
        except (OSError, ValueError, llm.LLMError):
            raise ValueError("remove_failed")
        embed.forget(model_id)
        if config.load_settings().get("embed") == model_id:
            config.save_settings({"embed": None})
        return {"ok": True}
    if kind == "diar":
        if model_id not in catalog.DIAR_IDS or not diar_installed():
            raise ValueError("not_installed")
        if config.load_settings().get("diarize"):
            raise ValueError("in_use")
        shutil.rmtree(diar_dir(), ignore_errors=True)
        return {"ok": True}
    entry = next((m for m in speech_entries() if m["id"] == model_id), None)
    if entry is None or not speech_installed(entry):
        raise ValueError("not_installed")
    if model_id == selected_speech():
        raise ValueError("in_use")
    path = Path(speech_path(entry)).resolve()
    root = (config.home() / "models").resolve()
    if root not in path.parents:  # only ever delete inside Cairn's own models folder
        raise ValueError("remove_failed")
    shutil.rmtree(path, ignore_errors=True)
    return {"ok": True}
