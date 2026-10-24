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

from . import config, jobs, llm, notes, pocket, render

WEB = Path(__file__).parent / "web"
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/favicon.svg": "favicon.svg"}
COOKIE = "cairn_session"
MAX_BODY = 1 << 20
EXPORTS = {"md": ("text/markdown", ".md"), "html": ("text/html", ".html"), "text": ("text/plain", ".txt")}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
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


class App:
    """Everything the handlers share."""

    def __init__(self):
        self.store = notes.Store(config.home() / "Texts")
        self.jobs = jobs.Jobs(self.store)
        self.token = secrets.token_urlsafe(24)
        self.port = 0

    # Pocket

    def pocket_state(self):
        try:
            folder = pocket.find_pocket()
            return {"connected": bool(folder), "count": len(pocket.list_recordings(folder)) if folder else 0}
        except OSError:
            return {"connected": False, "count": 0}

    def verify_pocket(self):
        folder = pocket.find_pocket()
        if not folder:
            raise ApiError(409, "pocket_not_found")
        files = pocket.list_recordings(folder)
        good = []
        for path in files:
            note = self.store.find_source(path.relative_to(folder).as_posix())
            audio = (note or {}).get("audio")
            try:
                if audio and os.path.getsize(audio) == path.stat().st_size and pocket.sha256(audio) == pocket.sha256(path):
                    good.append(path)
            except OSError:
                continue
        return files, good

    def empty_pocket(self):
        files, good = self.verify_pocket()
        if len(good) != len(files):
            raise ApiError(409, "not_all_verified")
        for path in good:
            path.unlink()
        return len(good)

    # State

    def state(self, with_list):
        rows = self.store.light() if with_list else []
        everything = self.store.all()
        data = {
            "version": config.VERSION,
            "pocket": self.pocket_state(),
            "job": self.jobs.snapshot(),
            "ollama": llm.available(),
            "settings": config.load_settings(),
            "totals": {"notes": len(everything), "done": sum(1 for n in everything if n.get("status") == "done"),
                       "waiting": sum(1 for n in everything if n.get("status") in ("waiting", "error"))},
        }
        if with_list:
            data["notes"] = rows
        return data

    def about(self):
        cfg = config.install_config()
        found = {m.get("name", ""): m.get("size", 0) for m in llm.models()}
        llm_name = cfg["llm"]
        llm_size = found.get(llm_name) or found.get(llm_name + ":latest") or 0
        model_dir = Path(cfg["whisper_model"])
        comps = [
            {"name": "Whisper " + re.sub(r"^(faster-)?whisper-|-ct2$", "", (cfg.get("whisper_repo") or model_dir.name).split("/")[-1]),
             "ver": _gb(_size(model_dir)) if model_dir.is_dir() else "-", "ok": model_dir.is_dir()},
            {"name": "%s · Ollama" % llm_name, "ver": _gb(llm_size) if llm_size else "-", "ok": bool(llm_size)},
        ]
        ffmpeg = shutil.which("ffmpeg", path=str(config.home() / "bin") + os.pathsep + os.environ.get("PATH", ""))
        if cfg.get("engine") == "mlx":
            version = "-"
            if ffmpeg:
                try:
                    out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10, check=False).stdout
                    version = (re.search(r"version (\S+)", out) or [None, "-"])[1]
                except (OSError, subprocess.SubprocessError):
                    pass
            comps.append({"name": "ffmpeg", "ver": version, "ok": bool(ffmpeg)})
        comps.append({"name": "Python", "ver": platform.python_version(), "ok": True})
        return {"version": config.VERSION, "components": comps}

    def check_update(self):
        """The only outgoing request Cairn can make, and only when the user asks for it."""
        url = "https://api.github.com/repos/%s/releases/latest" % config.REPO
        request = urllib.request.Request(url, headers={"User-Agent": "Cairn", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 (fixed https URL)
                latest = json.load(response).get("tag_name", "")
        except urllib.error.HTTPError as error:
            if error.code == 404:  # no release published yet
                return {"current": config.VERSION, "latest": None, "available": False}
            raise ApiError(502, "update_check_failed")
        except (urllib.error.URLError, OSError, ValueError):
            raise ApiError(502, "update_check_failed")
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
            return self.store.get(note_id)
        except KeyError:
            raise ApiError(404, "not_found")

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

    def delete_note(self, note_id):
        note = self.get_note(note_id)
        audio = note.get("audio")
        if audio and Path(audio).is_file():
            try:
                Path(audio).unlink()
            except OSError:
                pass
        self.store.delete(note_id)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Cairn"

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
            length = int(self.headers.get("Content-Length") or 0)
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
                    cookie = "%s=%s; HttpOnly; SameSite=Strict; Path=/" % (COOKIE, app.token)
                    return self._send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
                if not self._authorized():
                    return self._send(403, "Open Cairn from its launcher.", "text/plain")
            elif not self._authorized():
                raise ApiError(403, "forbidden")
            name = STATIC[url.path]
            ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
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
            if method == "POST" and path == "/api/settings":
                try:
                    return self._json(200, config.save_settings(body))
                except (ValueError, OSError) as error:
                    raise ApiError(400, str(error))
            if method == "POST" and path == "/api/pick-folder":
                return self._json(200, app.pick_folder())
            if method == "POST" and path == "/api/update":
                return self._json(200, app.check_update())
            if method == "GET" and path == "/api/pocket/verify":
                files, good = app.verify_pocket()
                return self._json(200, {"total": len(files), "verified": len(good)})
            if method == "POST" and path == "/api/pocket/empty":
                if body.get("confirm") is not True:
                    raise ApiError(400, "confirm_required")
                return self._json(200, {"deleted": app.empty_pocket()})
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
            if method == "POST" and action == "rerun":
                level = body.get("level")
                if level not in config.LEVELS:
                    raise ApiError(400, "bad_level")
                app.get_note(note_id)
                try:
                    app.jobs.start_rerun(note_id, level)
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True})
            if method == "POST" and action == "delete":
                app.delete_note(note_id)
                return self._json(200, {"ok": True})
            raise ApiError(404, "not_found")

    return Handler


def make_server(port=8765):
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
