"""Local web server: the Cairn interface and its API, reachable from this computer only."""

import hmac
import json
import mimetypes
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import catalog, config, jobs, llm, models, netguard, notes, pocket, privacy, render, score, speech

WEB = Path(__file__).parent / "web"
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/favicon.svg": "favicon.svg",
          "/manifest.webmanifest": "manifest.webmanifest", "/icon-192.png": "icon-192.png", "/icon-512.png": "icon-512.png"}
PUBLIC = {"/favicon.svg", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"}  # nothing private: the browser fetches them without the session cookie
COOKIE = "cairn_session"
MAX_BODY = 1 << 20
EXPORTS = {"md": ("text/markdown", ".md"), "html": ("text/html", ".html"), "text": ("text/plain", ".txt")}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def _size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _gb(value):
    return "%.1f GB" % (value / 1e9)


def _version_tuple(text):
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


DEFAULT_PORT = 8731


def session_key():
    """The session key, kept in a private file so an installed web app and its cookie survive restarts."""
    path = config.home() / "session.key"
    try:
        value = path.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    except OSError:
        pass
    value = secrets.token_urlsafe(24)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
    except OSError:
        pass
    return value


def _privacy_summary():
    report = privacy.last_report()
    return {"ok": bool(report.get("ok")), "when": report.get("when")} if report else None


class App:
    """Everything the handlers share."""

    def __init__(self):
        self.store = notes.Store(config.home() / "Texts")
        self.jobs = jobs.Jobs(self.store)
        self.token = session_key()
        self.port = 0
        self.downloads = models.Downloader()
        self.update_info = None  # set by the background watcher

    # Pocket

    def pocket_state(self):
        try:
            folder = pocket.find_pocket()
            if not folder:
                return {"connected": False, "count": 0, "new": 0}
            files = pocket.list_recordings(folder)
            skip = self.store.ignored()
            known = {n.get("source") for n in self.store.slim()}
            fresh = [f for f in files if (rel := f.relative_to(folder).as_posix()) not in skip and rel not in known]
            return {"connected": True, "count": len(files), "new": len(fresh)}
        except OSError:
            return {"connected": False, "count": 0, "new": 0}

    def waiting_count(self):
        """Recordings copied and waiting to be processed (a failed one is not retried by itself)."""
        return sum(1 for n in self.store.slim() if n.get("status") == "waiting" and os.path.exists(n.get("audio", "")))

    # State

    def state(self, with_list):
        rows = self.store.light() if with_list else []
        everything = self.store.slim()
        data = {
            "version": config.VERSION,
            "pocket": self.pocket_state(),
            "job": self.jobs.snapshot(),
            "ollama": llm.available(),
            "download": self.downloads.state(),
            "settings": config.load_settings(),
            "update": self.update_info,
            "privacy": _privacy_summary(),
            "totals": {"notes": len(everything), "done": sum(1 for n in everything if n.get("status") == "done"),
                       "waiting": sum(1 for n in everything if n.get("status") in ("waiting", "error"))},
        }
        if with_list:
            data["notes"] = rows
        return data

    def about(self):
        """Installed components, alphabetical, each with its version and size."""
        cfg = config.install_config()
        found = {m.get("name", ""): m.get("size", 0) for m in llm.models()}
        llm_name = cfg["llm"]
        llm_size = found.get(llm_name) or found.get(llm_name + ":latest") or 0
        llm_entry = next((m for m in catalog.LLM if m["id"] == llm_name), None)
        model_dir = Path(cfg["whisper_model"])
        speech = next((m for m in models.speech_entries() if m["id"] == models.selected_speech()), None)
        comps = [
            {"name": "Qwen3", "ver": (llm_entry or {}).get("label", llm_name).replace("Qwen3 ", "") or llm_name,
             "size": llm_size, "ok": bool(llm_size), "fix": "llm"},
            {"name": "Whisper", "ver": (speech or {}).get("label", "").replace("Whisper ", "") or re.sub(
                r"^(faster-)?whisper-|-ct2$|-mlx$", "", (cfg.get("whisper_repo") or model_dir.name).split("/")[-1]),
             "size": _size(model_dir) if model_dir.is_dir() else 0, "ok": model_dir.is_dir(), "fix": "speech"},
        ]
        ffmpeg = shutil.which("ffmpeg", path=str(config.home() / "bin") + os.pathsep + os.environ.get("PATH", ""))
        if ffmpeg:
            version = "-"
            try:
                out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10, check=False).stdout
                version = (re.search(r"version (\S+)", out) or [None, "-"])[1]
            except (OSError, subprocess.SubprocessError):
                pass
            comps.append({"name": "ffmpeg", "ver": re.sub(r"[-_].*$", "", version), "size": os.path.getsize(os.path.realpath(ffmpeg)), "ok": True})
        elif cfg.get("engine") == "mlx":
            comps.append({"name": "ffmpeg", "ver": "", "size": 0, "ok": False})
        ollama = llm.find_ollama(cfg)
        if ollama:
            version = "-"
            try:
                out = subprocess.run([ollama, "--version"], capture_output=True, text=True, timeout=10, check=False)
                version = (re.search(r"(\d+\.\d+(?:\.\d+)?)", out.stdout + out.stderr) or [None, "-"])[1]
            except (OSError, subprocess.SubprocessError):
                pass
            real = Path(os.path.realpath(ollama))
            folder = next((p for p in real.parents if p.name in ("Ollama.app", "ollama")), None)
            comps.append({"name": "Ollama", "ver": version, "size": _size(folder) if folder else real.stat().st_size, "ok": True})
        else:
            comps.append({"name": "Ollama", "ver": "", "size": 0, "ok": False})
        base = Path(sys.base_prefix)
        owned = config.home() in base.parents or base == config.home()
        comps.append({"name": "Python", "ver": platform.python_version(), "size": _size(base) if owned or base.is_dir() else 0, "ok": True})
        comps.sort(key=lambda c: c["name"].lower())
        return {"version": config.VERSION, "components": comps, "referral": config.REFERRAL_URL}

    def check_update(self):
        """The only outgoing request Cairn can make, and only when the user asks for it."""
        # /releases/latest ignores pre-releases (404), so list releases and take the newest published one.
        url = "https://api.github.com/repos/%s/releases?per_page=5" % config.REPO
        request = urllib.request.Request(url, headers={"User-Agent": "Cairn", "Accept": "application/vnd.github+json"})
        try:
            with netguard.allow("update check"), urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 (fixed https URL)
                releases = json.load(response)
        except (urllib.error.URLError, OSError, ValueError):
            raise ApiError(502, "update_check_failed")
        tags = [r.get("tag_name", "") for r in releases if isinstance(r, dict) and not r.get("draft") and r.get("tag_name")]
        if not tags:
            return {"current": config.VERSION, "latest": None, "available": False}
        latest = max(tags, key=_version_tuple)
        return {"current": config.VERSION, "latest": latest, "available": _version_tuple(latest) > _version_tuple(config.VERSION)}

    def pick_folder(self):
        try:
            if sys.platform == "darwin":
                cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Cairn")']
            elif sys.platform.startswith("win"):
                script = (
                    "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
                )
                cmd = ["powershell", "-NoProfile", "-STA", "-Command", script]
            else:
                raise ApiError(501, "no_dialog")
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise ApiError(501, "no_dialog")
        if not out:
            raise ApiError(409, "cancelled")
        return {"path": out}

    # Notes

    def get_note(self, note_id):
        try:
            note = self.store.get(note_id)
        except KeyError:
            raise ApiError(404, "not_found")
        if note.get("fidelity") is None and note.get("status") == "done":
            note["fidelity"] = score.fidelity(note.get("summary"), note.get("clean"))
        return note

    def export(self, note_id, fmt, transcript, fragment):
        note = self.get_note(note_id)
        if fmt == "doubtful":
            return "text/plain", render.doubtful_text(note), ".txt"
        if fmt == "md":
            return EXPORTS["md"][0], render.to_markdown(note, transcript), ".md"
        if fmt == "html":
            return "text/html", render.to_html(note, transcript, fragment), ".html"
        if fmt == "text":
            return "text/plain", render.to_text(note), ".txt"
        raise ApiError(400, "bad_format")

    def purge_pocket(self):
        """Erase from the Pocket the recordings the person deleted. A file whose deletion was waiting for the
        Pocket to be connected goes now. Returns how many files were erased."""
        folder = pocket.find_pocket()
        if not folder:
            return 0
        erased, root = 0, folder.resolve()
        for rel in sorted(self.store.ignored()):
            target = (folder / rel).resolve()
            try:
                if root in target.parents and target.is_file():
                    target.unlink()
                    erased += 1
                self.store.ignore(rel, on=False)  # gone from the Pocket: nothing left to remember
            except OSError:
                continue  # read-only or busy: tried again at the next connection
        return erased

    def delete_note(self, note_id):
        """Delete a recording everywhere: audio, transcript and summary on this computer, and the file on the
        Pocket (at its next connection if it is not connected now). Returns whether the Pocket file is gone."""
        note = self.get_note(note_id)
        rel = note.get("source")
        if rel:
            self.store.ignore(rel)  # never imported again; also the memo of a Pocket file still to erase
        audio = note.get("audio")
        if audio and Path(audio).is_file():
            try:
                Path(audio).unlink()
            except OSError:
                pass
        self.store.delete(note_id)
        snapshot = self.jobs.snapshot()
        if snapshot.get("running") and snapshot.get("id") == note_id:
            speech.abort()  # it was being transcribed: stop at once, nothing of it is kept
        self.purge_pocket()
        return not rel or rel not in self.store.ignored()


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Cairn"
        timeout = 60  # a client that stops sending frees its thread

        def log_message(self, *args):  # no access log
            pass

        # Helpers

        def _send(self, status, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text/", "application/json")) else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload, ensure_ascii=False))

        def _authorized(self):
            host = self.headers.get("Host", "")
            if host not in ("127.0.0.1:%d" % app.port, "localhost:%d" % app.port):
                return False
            jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
            morsel = jar.get(COOKIE)
            return bool(morsel) and hmac.compare_digest(morsel.value, app.token)

        def _body(self):
            if self.headers.get("X-Cairn") != "1" or "application/json" not in self.headers.get("Content-Type", ""):
                raise ApiError(403, "forbidden")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "bad_length")
            if length < 0:
                raise ApiError(400, "bad_length")
            if length > MAX_BODY:
                raise ApiError(413, "too_large")
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                raise ApiError(400, "bad_json")
            return data if isinstance(data, dict) else {}

        # Routing

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def _route(self, method):
            url = urlparse(self.path)
            try:
                if method == "GET" and url.path in STATIC:
                    return self._static(url)
                if not self._authorized():
                    raise ApiError(403, "forbidden")
                if method == "POST":
                    body = self._body()
                else:
                    body = {}
                query = parse_qs(url.query)
                self._api(method, url.path, body, query)
            except ApiError as error:
                self._json(error.status, {"error": error.message})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:  # never leak a traceback to the page
                self._json(500, {"error": "server_error", "detail": str(error)[:200]})

        def _static(self, url):
            if url.path in ("/", "/index.html"):
                key = parse_qs(url.query).get("k", [""])[0]
                host = self.headers.get("Host", "")
                if host not in ("127.0.0.1:%d" % app.port, "localhost:%d" % app.port):
                    raise ApiError(403, "forbidden")
                if key and hmac.compare_digest(key, app.token):
                    cookie = "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=31536000" % (COOKIE, app.token)
                    return self._send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
                if not self._authorized():
                    return self._send(403, "Open Cairn from its launcher.", "text/plain")
            elif url.path not in PUBLIC and not self._authorized():
                raise ApiError(403, "forbidden")
            name = STATIC[url.path]
            ctype = "application/manifest+json" if name.endswith(".webmanifest") else mimetypes.guess_type(name)[0] or "application/octet-stream"
            return self._send(200, (WEB / name).read_bytes(), ctype)

        def _api(self, method, path, body, query):
            if method == "GET" and path == "/api/state":
                return self._json(200, app.state(query.get("list", ["1"])[0] != "0"))
            if method == "GET" and path == "/api/about":
                return self._json(200, app.about())
            if method == "POST" and path == "/api/import":
                try:
                    app.jobs.start_import()
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True})
            if method == "POST" and path == "/api/privacy/check":
                try:
                    app.jobs.start_privacy()
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True})
            if method == "GET" and path == "/api/privacy":
                return self._json(200, {"report": privacy.last_report(), "running": app.jobs.snapshot().get("kind") == "privacy" and app.jobs.snapshot().get("running"), "guard": netguard.blocked()})
            if method == "POST" and path == "/api/cancel":
                app.jobs.cancel()
                return self._json(200, {"ok": True})
            if method == "POST" and path == "/api/settings":
                try:
                    return self._json(200, config.save_settings(body))
                except (ValueError, OSError) as error:
                    raise ApiError(400, str(error))
            if method == "GET" and path == "/api/models":
                return self._json(200, models.listing(app.downloads.state()))
            if method == "POST" and path == "/api/models/install":
                if body.get("confirm") is not True:
                    raise ApiError(400, "confirm_required")
                if app.jobs.snapshot().get("running"):
                    raise ApiError(409, "busy")
                try:
                    app.downloads.start(body.get("kind"), body.get("id"))
                except RuntimeError:
                    raise ApiError(409, "busy")
                except ValueError as error:
                    raise ApiError(400, str(error))
                return self._json(202, {"ok": True})
            if method == "POST" and path == "/api/models/remove":
                if body.get("confirm") is not True:
                    raise ApiError(400, "confirm_required")
                if app.jobs.snapshot().get("running"):
                    raise ApiError(409, "busy")
                try:
                    return self._json(200, models.remove(body.get("kind"), body.get("id")))
                except ValueError as error:
                    raise ApiError(400, str(error))
            if method == "POST" and path == "/api/models/select":
                if app.jobs.snapshot().get("running"):
                    raise ApiError(409, "busy")
                try:
                    return self._json(200, models.select(body.get("kind"), body.get("id")))
                except ValueError as error:
                    raise ApiError(400, str(error))
            if method == "POST" and path == "/api/pick-folder":
                return self._json(200, app.pick_folder())
            match = re.fullmatch(r"/api/note/([A-Za-z0-9._-]+)(?:/(\w+))?", path)
            if match:
                return self._note(method, match.group(1), match.group(2), body, query)
            raise ApiError(404, "not_found")

        def _note(self, method, note_id, action, body, query):
            if method == "GET" and action is None:
                return self._json(200, app.get_note(note_id))
            if method == "GET" and action == "export":
                fmt = query.get("fmt", ["md"])[0]
                ctype, text, ext = app.export(note_id, fmt, query.get("transcript", ["1"])[0] == "1", query.get("fragment", ["0"])[0] == "1")
                name = re.sub(r"[^A-Za-z0-9._-]+", "_", app.get_note(note_id).get("title") or note_id).strip("_") or "note"
                disposition = "attachment; filename*=UTF-8''%s" % quote(name + ext)
                if query.get("save", ["0"])[0] == "1":
                    folder = config.home() / "Exports"
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / (name + ext)).write_text(text, encoding="utf-8")
                return self._send(200, text, ctype, {"Content-Disposition": disposition})
            if method == "POST" and action == "rename":
                title = str(body.get("title") or "").strip()[:200]
                if not title:
                    raise ApiError(400, "empty_title")
                note = app.get_note(note_id)
                note["title"], note["renamed"] = title, True
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "template":
                kind = body.get("template")
                if kind not in llm.TEMPLATES:
                    raise ApiError(400, "bad_template")
                note = app.get_note(note_id)
                note["template"] = kind  # the person's choice, kept when the note is redone
                note["summary"] = dict(note.get("summary") or {}, template=kind)
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "rerun":
                level, lang = body.get("level"), body.get("lang")
                if level not in config.LEVELS or (lang is not None and lang not in config.LANGS):
                    raise ApiError(400, "bad_level")
                app.get_note(note_id)
                try:
                    transcribe = app.jobs.start_rerun(note_id, level, lang)
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True, "transcribe": transcribe})
            if method == "POST" and action == "options":
                app.get_note(note_id)
                try:
                    app.jobs.set_options(note_id, body.get("level"), body.get("lang"))
                except ValueError as error:
                    raise ApiError(400, str(error))
                return self._json(200, {"ok": True})
            if method == "POST" and action == "process":
                app.get_note(note_id)
                try:
                    app.jobs.start_process(note_id)
                except jobs.Busy:
                    raise ApiError(409, "busy")
                except ValueError as error:
                    raise ApiError(400, str(error))
                return self._json(202, {"ok": True})
            if method == "POST" and action in ("skip", "restore"):
                app.get_note(note_id)
                getattr(app.jobs, action)(note_id)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "delete":
                return self._json(200, {"ok": True, "pocket": app.delete_note(note_id)})
            raise ApiError(404, "not_found")

    return Handler


def make_server(port=DEFAULT_PORT):
    """Bind to 127.0.0.1 only. Tries the next ports when the first one is taken."""
    app = App()
    last = None
    for candidate in range(port, port + 20):
        app.port = candidate
        try:
            server = ThreadingHTTPServer(("127.0.0.1", candidate), make_handler(app))
            server.daemon_threads = True
            return app, server
        except OSError as error:
            last = error
    raise last
