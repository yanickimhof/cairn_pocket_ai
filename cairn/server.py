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
import threading
import time
import traceback
import urllib.error
import urllib.request
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import ask, battery, catalog, config, diarize, embed, jobs, llm, lock, menubar, models, netguard, notes, pocket, pocket_status, privacy, render, score, search, setup, speech, tags, templates, upload, vault, vocab, vocabcheck, voices

WEB = Path(__file__).parent / "web"
STATIC = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/favicon.svg": "favicon.svg",
          "/manifest.webmanifest": "manifest.webmanifest", "/icon-192.png": "icon-192.png", "/icon-512.png": "icon-512.png"}
PUBLIC = {"/favicon.svg", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"}  # nothing private: the browser fetches them without the session cookie
COOKIE = "cairn_session"
COOKIE_DAYS = 30  # renewed each time Cairn is opened from its launcher
MAX_BODY = 1 << 20
EXPORTS = {"md": ("text/markdown", ".md"), "html": ("text/html", ".html"), "text": ("text/plain", ".txt")}
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; "
    "connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


_size = models.dir_size


def _llm_component(llm_name, entry, size):
    """Family and size label of the summary model, e.g. ("Qwen3", "8B") or ("Qwen3.5", "9B")."""
    label = (entry or {}).get("label") or llm_name
    family, _, rest = label.partition(" ")
    return {"name": family, "ver": rest or llm_name, "size": size, "ok": bool(size), "fix": "llm"}


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
        self.gauge = battery.Gauge()  # battery of the Pocket, shown when it can be read
        self.status = pocket_status.StatusGauge()  # firmware/state/storage, shown only once a session key is set
        self._check = {"sig": None, "items": [], "busy": False, "at": 0.0}
        self.check_wait = 20.0  # seconds between two looks at the names, however often the notes change
        self._check_notes = {}  # note id -> (file signature, what the note says about names)
        self._check_lock = threading.Lock()

    # Pocket

    def pocket_state(self):
        idle = {"connected": False, "count": 0, "new": 0, "vault": {"available": vault.available(), "state": "none", "plain": 0, "sealed": 0, "locked": 0, "trusted": False}}
        try:
            folder = pocket.find_pocket()
            if not folder:
                return idle
            listing = pocket.scan(folder)
            known = {(n.get("source"), n.get("size"), n.get("mtime")) for n in self.store.slim()}
            fresh = [e for e in listing.readable if not self.store.is_ignored(e.rel, e.size, e.mtime) and (e.rel, e.size, e.mtime) not in known]
            return {"connected": True, "count": len(listing.readable), "new": len(fresh), "vault": {
                "available": vault.available(), "state": listing.state(), "plain": len(listing.plain), "sealed": len(listing.sealed),
                "locked": listing.locked, "trusted": bool(listing.header) and vault.trusted(listing.header["id"])}}
        except (OSError, vault.VaultError):
            return idle

    def search_state(self):
        """The search by meaning: which model is used (None when there is none) and how much of the notes it has read."""
        model = config.load_settings().get("embed")
        if not model:
            return {"model": None, "indexed": 0, "total": 0}
        return embed.status(self.store, model)

    # Pocket vault

    def _vault_target(self):
        if not vault.available():
            raise ApiError(501, "vault_unavailable")
        folder = pocket.find_pocket()
        if not folder:
            raise ApiError(409, "no_pocket")
        return folder

    def vault_create(self, password, trust, auto):
        folder = self._vault_target()
        if not isinstance(password, str):
            raise ApiError(400, "bad_password")
        try:
            header, key = vault.create(folder, password)
        except vault.VaultError as error:
            raise ApiError(400, str(error))
        except OSError as error:
            raise ApiError(500, "The Pocket cannot be written to: %s" % error)
        trusted = vault.remember(header["id"], key, bool(trust))
        if auto:
            config.save_settings({"pocket_secure_auto": True})
        self.secure_now()
        return trusted

    def vault_unlock(self, password, trust):
        folder = self._vault_target()
        if not isinstance(password, str):
            raise ApiError(400, "bad_password")
        try:
            key = vault.unlock(folder, password)
        except vault.WrongPassword:
            time.sleep(0.5)  # slows down guessing; scrypt already makes each try costly
            raise ApiError(403, "wrong_password")
        except vault.VaultError as error:
            raise ApiError(400, str(error))
        trusted = vault.remember(vault.read_header(folder)["id"], key, bool(trust))
        try:
            self.jobs.start_sync()  # the recordings of this Pocket come in now
        except jobs.Busy:
            pass
        return trusted

    def vault_forget(self):
        """Take the key of this Pocket out of this computer. Without the Pocket at hand, every vault this computer has seen is forgotten."""
        folder = pocket.find_pocket()
        header = vault.read_header(folder) if folder else None
        for vault_id in [header["id"]] if header else vault.known_ids():
            vault.forget(vault_id)

    def secure_now(self):
        """Copy what is new and encrypt everything on the Pocket; if another job is running, as soon as it is done."""
        try:
            self.jobs.start_secure()
        except jobs.Busy:
            self.jobs.secure_wanted = True

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
            "settings": config.public_settings(config.load_settings()),
            "battery": self.gauge.snapshot(),
            "pocket_status": self.status.snapshot(),
            "update": self.update_info,
            "lock": lock.info(),
            "menubar": {"available": menubar.available()},
            "privacy": _privacy_summary(),
            "diar_installed": models.diar_installed(),
            "search": self.search_state(),
            "gpu": sys.platform == "darwin" and platform.machine() == "arm64",
            "totals": {"notes": len(everything), "done": sum(1 for n in everything if n.get("status") == "done"),
                       "waiting": sum(1 for n in everything if n.get("status") in ("waiting", "error")),
                       "vocab_todo": len(self.vocab_outdated(everything)), "vocab_check": self.vocab_check_count()},
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
            _llm_component(llm_name, llm_entry, llm_size),
            {"name": "Whisper", "ver": (speech or {}).get("label", "").replace("Whisper ", "") or re.sub(
                r"^(faster-)?whisper-|-ct2$|-mlx$", "", (cfg.get("whisper_repo") or model_dir.name).split("/")[-1]),
             "size": _size(model_dir) if model_dir.is_dir() else 0, "ok": model_dir.is_dir(), "fix": "speech"},
        ]
        if models.diar_installed():
            diar_entry = catalog.DIAR[0]
            comps.append({"name": "Diarization", "ver": diar_entry["label"].split("(")[-1].rstrip(")"),
             "size": _size(models.diar_dir()), "ok": True, "fix": "diar"})
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
                installed, running = llm.parse_ollama_version(out.stdout + out.stderr)
                version = installed + (" \u00b7 running " + running if running else "")
            except (OSError, subprocess.SubprocessError):
                pass
            real = Path(os.path.realpath(ollama))
            folder = next((p for p in real.parents if p.name in ("Ollama.app", "ollama")), None)
            comps.append({"name": "Ollama", "ver": version, "size": _size(folder) if folder else real.stat().st_size, "ok": True})
        else:
            comps.append({"name": "Ollama", "ver": "", "size": 0, "ok": False})
        wanted = config.load_settings().get("embed")
        if wanted and embed.installed(wanted):
            found_embed = next((m for m in catalog.EMBED if m["id"] == wanted), None)
            comps.append({"name": "Search model", "ver": (found_embed or {}).get("label", wanted), "size": found.get(wanted) or found.get(wanted + ":latest") or 0, "ok": True})
        libs = vault.libraries()
        comps.append({"name": "Pocket vault", "ver": "AES-256-GCM", "size": sum(_size(d) for _, _, d in libs if d), "ok": vault.available()})
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
            heard = note.get("heard")
            note["fidelity"], note["fidelity_basis"] = score.fidelity_detail(note.get("summary"), note.get("clean"), words_ok=heard in (None, note.get("lang")))
        return note

    def vocab_outdated(self, rows=None):
        """The finished notes written with another vocabulary than the current one (none when there is no vocabulary to apply)."""
        terms = config.load_settings().get("vocabulary") or []
        key = vocab.key(terms)
        rows = self.store.slim() if rows is None else rows
        return [n for n in rows if n.get("status") == "done" and n.get("vocab_key", "") != key and (terms or n.get("vocab_fixes"))]

    def vocab_targets(self, body):
        """(notes, force): chosen ones or a range of dates are written again even when up to date (force); all the out of date ones only
        when the vocabulary changes their words."""
        rows = {n["id"]: n for n in self.store.slim() if n.get("status") == "done"}
        if isinstance(body.get("ids"), list):
            return [i for i in dict.fromkeys(str(i) for i in body["ids"]) if i in rows], True
        if body.get("from") or body.get("to"):
            low, high = str(body.get("from") or "0000-00-00")[:10], str(body.get("to") or "9999-99-99")[:10]
            return [i for i, n in sorted(rows.items(), key=lambda kv: kv[1].get("date") or "") if low <= (n.get("date") or "")[:10] <= high], True
        return [n["id"] for n in sorted(self.vocab_outdated(list(rows.values())), key=lambda n: n.get("date") or "")], False

    def edit_segment(self, note_id, index, text, scope):
        """Correct one line of a transcript by hand. scope "here": this line only. "always": the change also becomes entries of the
        vocabulary, applied to every note. Returns {"ok", "rules": [entries added], "updating": notes being written}."""
        with self.store.lock:
            return self._edit_segment(note_id, index, text, scope)

    def _edit_segment(self, note_id, index, text, scope):
        note = self.get_note(note_id)
        segments = note.get("segments") or []
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(segments) or scope not in ("here", "always"):
            raise ApiError(400, "bad_segment")
        text = " ".join(str(text or "").split())
        if not text or len(text) > 2000:
            raise ApiError(400, "bad_text")
        seg = segments[index]
        engine = seg.get("orig", seg.get("text", ""))
        rules = []
        if scope == "always":
            rules = vocab.rule_from_edit(engine, text)
            if not rules:
                raise ApiError(400, "no_rule")
        if text == engine:
            seg.pop("orig", None)
            seg.pop("edit", None)
        else:
            seg["orig"], seg["edit"] = engine, True
        seg["text"] = text
        names = note.get("speaker_names") or {}
        note["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(segments, names) if names else segments))
        self.store.save(note)
        lines = [vocab.rule_line(r) for r in rules]
        updating = 0
        if lines:
            try:
                config.save_settings({"vocabulary": vocab.add_entries(config.load_settings().get("vocabulary"), lines)})
            except ValueError as error:
                raise ApiError(400, str(error))
            updating = self.refresh_vocab()
        return {"ok": True, "rules": lines, "updating": updating}

    # People: the speakers named in the notes

    def people(self):
        """Every named speaker across the notes, and the notes that still have speakers without a name."""
        found, unnamed = {}, []
        for note in self.store.all():
            segments = note.get("segments") or []
            if note.get("status") != "done" or not segments:
                continue
            names, seconds, order = note.get("speaker_names") or {}, {}, []
            for seg in segments:
                label = seg.get("speaker")
                if not label:
                    continue
                if label not in order:
                    order.append(label)
                seconds[label] = seconds.get(label, 0.0) + max(0.0, float(seg.get("end", 0)) - float(seg.get("start", 0)))
            row = {"id": note["id"], "title": note.get("title") or "", "date": note.get("date") or ""}
            for label in order:
                name = names.get(label)
                if name:
                    entry = found.setdefault(name, {"name": name, "seconds": 0.0, "notes": []})
                    entry["seconds"] += seconds[label]
                    if not any(n["id"] == row["id"] for n in entry["notes"]):
                        entry["notes"].append(dict(row))
            open_labels = [label for label in order if not names.get(label)]
            if open_labels:
                unnamed.append(dict(row, labels=open_labels))
        stored = voices.counts()
        people = sorted(found.values(), key=lambda p: (-len(p["notes"]), p["name"].lower()))
        for entry in people:
            entry["seconds"] = round(entry["seconds"])
            entry["notes"].sort(key=lambda n: n["date"], reverse=True)
            entry["voice"] = stored.get(entry["name"], 0)
        unnamed.sort(key=lambda n: n["date"], reverse=True)
        return {"people": people, "unnamed": unnamed, "enabled": bool(config.load_settings().get("voices")),
                "voiceprints": sum(1 for _ in stored), "orphans": sorted(n for n in stored if n not in found)}

    def rename_person(self, old, new):
        """Write a name differently in every note (or merge two people when the new name already exists). Returns how many notes changed."""
        old, new = " ".join(str(old or "").split())[:60], " ".join(str(new or "").split())[:60]
        if not old or not new:
            raise ApiError(400, "bad_name")
        changed = 0
        if old != new:
            for listed in self.store.all():
                with self.store.lock:  # read, change and write the note as one step: a job saving at the same time cannot undo it
                    note = self.store.get(listed["id"])
                    names = note.get("speaker_names") or {}
                    labels = [label for label, name in names.items() if " ".join(str(name).split()) == old]
                    if not labels:
                        continue
                    for label in labels:
                        names[label] = new
                    note["speaker_names"] = names
                    if note.get("segments"):
                        note["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(note["segments"], names)))
                    self.store.save(note)
                    changed += 1
            voices.rename(old, new)
        return changed

    def forget_voices(self, name=None):
        """Erase the voiceprints of one person, or of everybody (those kept with the notes as well)."""
        erased = voices.forget(name)
        for note in self.store.all():
            changed = False
            if name is None:
                changed = note.pop("voices", None) is not None
                changed = note.pop("speaker_auto", None) is not None or changed
            else:  # the voiceprints kept with the notes would teach the voice again at the next naming
                labels = [label for label, who in (note.get("speaker_names") or {}).items() if who == name]
                for label in labels:
                    changed = (note.get("voices") or {}).pop(label, None) is not None or changed
                    changed = (note.get("speaker_auto") or {}).pop(label, None) is not None or changed
            if changed:
                self.store.save(note)
        return erased

    # Names to check

    def _check_key(self):
        settings = config.load_settings()
        return (self.store.signature(), vocab.key(settings.get("vocabulary")), tuple(settings.get("vocab_ignored") or []))

    def _check_compute(self, sig):
        """The names to check. What each note says is kept for as long as the note does not change, so a note written again costs
        its own reading only, and the lock of the store is never held for the whole library."""
        try:
            settings = config.load_settings()
            contributions, live = [], set()
            for file_sig, note in self.store.iter_notes():
                live.add(note["id"])
                cached = self._check_notes.get(note["id"])
                if not cached or cached[0] != file_sig:
                    cached = self._check_notes[note["id"]] = (file_sig, vocabcheck.contribution(note))
                contributions.append(cached[1])
            for gone in set(self._check_notes) - live:
                self._check_notes.pop(gone, None)
            items = vocabcheck.assemble(contributions, settings.get("vocabulary") or [], settings.get("vocab_ignored") or [])
        except Exception:  # never leaves the badge stuck: the next change tries again
            traceback.print_exc()
            items = []
        with self._check_lock:
            self._check.update(sig=sig, items=items, busy=False, at=time.time())
        return items

    def vocab_check(self):
        """The names worth checking, computed when the notes or the vocabulary changed."""
        sig = self._check_key()
        with self._check_lock:
            if self._check["sig"] == sig:
                return list(self._check["items"])
        return self._check_compute(sig)

    def vocab_check_count(self):
        """How many names are worth checking, for the badge. Never slows the state down: a change is looked at in the background."""
        sig = self._check_key()
        with self._check_lock:
            stale = self._check["sig"] != sig
            idle = not self.jobs.snapshot().get("running") and time.time() - self._check["at"] >= self.check_wait  # not while a batch rewrites notes, not in a rush
            if stale and idle and not self._check["busy"]:
                self._check["busy"] = True
                threading.Thread(target=self._check_compute, args=(sig,), daemon=True).start()
            return len(self._check["items"])

    def vocab_check_apply(self, key, right, context):
        right = " ".join(str(right or "").split())
        if not right or len(right) > vocab.MAX_LEN or any(c in right for c in "|,;=>\n"):
            raise ApiError(400, "bad_spelling")
        item = next((i for i in self.vocab_check() if i["key"] == key), None)
        if item is None:
            raise ApiError(404, "not_found")
        near = [c.strip() for c in str(context or "").split(",") if c.strip() and not any(x in c for x in "|;=>\n")][:5]
        wrong = [f["text"] for f in item["forms"] if f["text"] != right]
        if wrong:
            line = vocab.rule_line({"wrong": ", ".join(wrong), "right": right, "context": near})
        else:
            line = right  # the spelling is right: the name goes in the vocabulary so that it stays that way
        try:
            terms = vocab.add_entries(config.load_settings().get("vocabulary"), [line])
            config.save_settings({"vocabulary": terms})
        except ValueError as error:
            raise ApiError(400, str(error))
        return self.refresh_vocab()

    def vocab_check_ignore(self, key):
        key = vocabcheck.normalise_key(key)
        if not key:
            raise ApiError(400, "bad_key")
        ignored = list(config.load_settings().get("vocab_ignored") or [])
        config.save_settings({"vocab_ignored": (ignored + [key])[-500:]})

    def refresh_vocab(self):
        """Write again, with the new vocabulary, the notes it changes. Returns how many are being written (0 when a job is running: the badge shows them)."""
        ids, force = self.vocab_targets({})
        if not ids:
            return 0
        try:
            self.jobs.start_vocab(ids, force)
        except jobs.Busy:
            return 0
        return len(ids)

    def actions(self):
        """Every action of every finished note, newest note first, with its done flag."""
        out = []
        for note in self.store.all():
            if note.get("status") != "done":
                continue
            finished = set(note.get("actions_done") or [])
            for index, action in enumerate((note.get("summary") or {}).get("actions") or []):
                what = str(action.get("what") or "").strip()
                if what:
                    out.append({"note": note["id"], "index": index, "title": note.get("title") or "", "date": note.get("date") or "", "what": what,
                                "who": str(action.get("who") or "").strip(), "when": str(action.get("when") or "").strip(), "done": what in finished})
        out.sort(key=lambda a: a["date"], reverse=True)
        return out

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
        wanted = self.store.ignored_files()
        if not wanted:
            return 0
        listing = pocket.scan(folder)
        by_name = {}
        for entry in listing.readable:
            by_name.setdefault(entry.rel, []).append(entry)
        erased, root = 0, folder.resolve()
        for rel, meta in sorted(wanted.items()):
            entries = by_name.get(rel, [])
            try:
                if not entries and listing.locked:
                    continue  # an encrypted file may be the one: its name cannot be read without the key
                mine = [e for e in entries if meta is None or (e.size, e.mtime) == meta]  # a name used again by another recording is not erased
                for entry in mine:  # every copy: a crash can leave the same recording twice
                    target = entry.path.resolve()
                    if root in target.parents and target.is_file():
                        pocket.shred(target, entry.size)
                        target.unlink()
                        erased += 1
                        if entry.sealed and listing.header:
                            vault.drop_index(listing.header["id"], entry.fid)
                self.store.ignore(rel, on=False)  # gone from the Pocket: nothing left to remember
            except OSError:
                continue  # read-only or busy: tried again at the next connection
        return erased

    @staticmethod
    def _drop_empty_day(folder):
        """Remove the dated folder that held a deleted recording once it is empty (rmdir never removes content)."""
        try:
            if folder.parent == Path(config.load_settings()["audio_dir"]):
                folder.rmdir()
        except (OSError, KeyError):
            pass

    def delete_note(self, note_id):
        """Delete a recording everywhere: audio, transcript and summary on this computer, and the file on the
        Pocket (at its next connection if it is not connected now). Returns whether the Pocket file is gone."""
        note = self.get_note(note_id)
        rel = note.get("source")
        if rel:
            self.store.ignore(rel, size=note.get("size"), mtime=note.get("mtime"))  # never imported again; also the memo of the Pocket file still to erase
        audio = note.get("audio")
        if audio and Path(audio).is_file():
            try:
                Path(audio).unlink()
            except OSError:
                pass
            self._drop_empty_day(Path(audio).parent)
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
                if url.path == "/api/lock" or url.path.startswith("/api/lock/"):
                    body = self._body() if method == "POST" else {}
                    return self._lock_api(method, url.path, body)
                if lock.locked():
                    raise ApiError(423, "locked")  # sealed data: nothing but the way to open it is answered
                if method == "POST":
                    lock.touch()  # a change comes from the person: the idle time starts again (a poll of the list does not count)
                if method == "POST" and url.path == "/api/import/file":
                    return self._upload()
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
            except config.Locked:
                self._json(423, {"error": "locked"})
            except Exception:  # never leak a traceback or a path to the page
                self._json(500, {"error": "server_error"})

        def _upload(self):
            """One audio file, sent as it is (not as JSON). The same guards as any change: session cookie, Host, and a header a
            web page of another origin cannot add without Cairn's consent."""
            if self.headers.get("X-Cairn") != "1" or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/octet-stream":
                raise ApiError(403, "forbidden")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "bad_length")
            try:
                note, duplicate = upload.receive(app.store, self.rfile, length, unquote(self.headers.get("X-Filename", ""))[:255],
                                                 self.headers.get("X-Last-Modified"), config.load_settings()["audio_dir"])
            except upload.Rejected as error:
                raise ApiError(error.status, error.code)
            if not duplicate and config.load_settings().get("autoprocess", False):
                try:
                    app.jobs.start_queue()
                except jobs.Busy:
                    pass  # the running job picks the new recording up when it reads the queue again
            return self._json(200, {"ok": True, "id": note["id"], "duplicate": duplicate})

        LOCK_STATUS = {"wrong_password": 401, "wrong_phrase": 401, "biometric_refused": 401, "no_biometric": 400, "password_short": 400,
                       "not_enabled": 400, "already_enabled": 409, "bad_value": 400}

        def _lock_api(self, method, path, body):
            """Opening and closing. The only part of the API that answers while Cairn is locked."""
            if method == "GET" and path == "/api/lock":
                return self._json(200, lock.info())
            if method != "POST":
                raise ApiError(404, "not_found")
            action = path[len("/api/lock/"):]
            try:
                if action == "unlock":
                    lock.unlock(body.get("password"))
                elif action == "biometric":
                    lock.unlock_biometric()
                elif action == "recover":
                    lock.recover(body.get("phrase"), body.get("password"))
                elif action == "ping":
                    if not lock.locked():
                        lock.touch()
                    return self._json(200, {"ok": True})
                else:
                    if lock.locked():
                        raise ApiError(423, "locked")
                    lock.touch()
                    if action == "now":
                        if app.jobs.snapshot().get("running"):
                            app.jobs.cancel()
                            for _ in range(80):  # the job ends cleanly before the key goes
                                if not app.jobs.snapshot().get("running"):
                                    break
                                time.sleep(0.1)
                        lock.lock_now()
                    elif action == "enable":
                        phrase = lock.enable(body.get("password"), bool(body.get("biometric")), body.get("auto_min", lock.DEFAULT_AUTO))
                        try:
                            app.jobs.start_seal()
                        except Exception:  # noqa: BLE001 (the phrase exists now: nothing after this may keep it from the person; the upkeep seals the rest)
                            pass
                        return self._json(200, {"ok": True, "recovery": phrase})
                    elif action == "phrase":
                        return self._json(200, {"ok": True, "recovery": lock.new_phrase(body.get("password"))})
                    elif action == "disable":
                        lock.disable(body.get("password"))
                        app.jobs.start_unseal()
                    elif action == "password":
                        lock.change_password(body.get("old"), body.get("new"))
                    elif action == "settings":
                        lock.settings(body.get("auto_min"), body.get("biometric"))
                    else:
                        raise ApiError(404, "not_found")
            except lock.LockError as error:
                raise ApiError(self.LOCK_STATUS.get(error.code, 400), error.code)
            except jobs.Busy:
                raise ApiError(409, "busy")
            return self._json(200, {"ok": True, **lock.info()})

        def _ask(self, body):
            question = " ".join(str(body.get("q") or "").split())[: ask.MAX_QUESTION]
            if not question:
                raise ApiError(400, "empty")
            events = ask.stream(app.store, question, note=str(body.get("note") or "")[:80],
                                since=str(body.get("since") or "")[:10], tag=str(body.get("tag") or "")[:40], history=body.get("history"))
            self.send_response(200)  # no length: the answer is sent as it is written, and the connection closes at its end
            for key, value in (("Content-Type", "application/x-ndjson; charset=utf-8"), ("Cache-Control", "no-store"),
                               ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                               ("Content-Security-Policy", CSP), ("Connection", "close")):
                self.send_header(key, value)
            self.end_headers()
            self.close_connection = True
            try:
                for event in events:
                    self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()
            except OSError:  # the page was closed or the question left: the model is stopped
                pass
            finally:
                events.close()

        def _static(self, url):
            if url.path in ("/", "/index.html"):
                key = parse_qs(url.query).get("k", [""])[0]
                host = self.headers.get("Host", "")
                if host not in ("127.0.0.1:%d" % app.port, "localhost:%d" % app.port):
                    raise ApiError(403, "forbidden")
                if key and hmac.compare_digest(key, app.token):
                    cookie = "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d" % (COOKIE, app.token, COOKIE_DAYS * 86400)
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
            if method == "GET" and path == "/api/setup":
                return self._json(200, setup.check())
            if method == "GET" and path == "/api/about":
                return self._json(200, app.about())
            if method == "POST" and path == "/api/import":
                try:
                    app.jobs.start_import()
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True})
            if method == "POST" and path == "/api/vault/create":
                trusted = app.vault_create(body.get("password"), body.get("trust", True), body.get("auto", False))
                return self._json(202, {"ok": True, "trusted": trusted})
            if method == "POST" and path == "/api/vault/unlock":
                trusted = app.vault_unlock(body.get("password"), body.get("trust", False))
                return self._json(202, {"ok": True, "trusted": trusted})
            if method == "POST" and path == "/api/vault/secure":
                app._vault_target()
                app.secure_now()
                return self._json(202, {"ok": True})
            if method == "POST" and path == "/api/vault/forget":
                app.vault_forget()
                return self._json(200, {"ok": True})
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
                    return self._json(200, config.public_settings(config.save_settings(body)))
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
            if method == "POST" and path == "/api/vocabulary/apply":
                ids, force = app.vocab_targets(body)
                if ids:
                    try:
                        app.jobs.start_vocab(ids, force)
                    except jobs.Busy:
                        raise ApiError(409, "busy")
                return self._json(202 if ids else 200, {"ok": True, "count": len(ids)})
            if method == "GET" and path == "/api/vocabulary/check":
                return self._json(200, {"items": app.vocab_check()})
            if method == "POST" and path == "/api/vocabulary/check/apply":
                return self._json(200, {"ok": True, "updating": app.vocab_check_apply(str(body.get("key") or ""), body.get("right"), body.get("context"))})
            if method == "POST" and path == "/api/vocabulary/check/ignore":
                app.vocab_check_ignore(body.get("key"))
                return self._json(200, {"ok": True})
            if method == "GET" and path == "/api/people":
                return self._json(200, app.people())
            if method == "POST" and path == "/api/people/rename":
                return self._json(200, {"ok": True, "notes": app.rename_person(body.get("from"), body.get("to"))})
            if method == "POST" and path == "/api/people/forget":
                name = body.get("name")
                if name is None and body.get("all") is not True:
                    raise ApiError(400, "bad_request")
                return self._json(200, {"ok": True, "erased": app.forget_voices(None if name is None else str(name))})
            if method == "GET" and path == "/api/tags":
                return self._json(200, {"tags": app.store.tag_counts()})
            if method == "POST" and path == "/api/tags/add":
                try:
                    tag = tags.clean([body.get("tag")])
                except ValueError as error:
                    raise ApiError(400, str(error))
                if not tag or not isinstance(body.get("ids"), list):
                    raise ApiError(400, "bad_tag")
                changed = 0
                for note_id in dict.fromkeys(str(i) for i in body["ids"]):
                    if not app.store.exists(note_id):
                        continue
                    note = app.store.get(note_id)
                    mine = [t for t in note.get("tags") or [] if t.casefold() != tag[0].casefold()]
                    if not body.get("remove"):
                        mine.append(tag[0])
                    try:
                        note["tags"] = tags.clean(mine)
                    except ValueError:
                        continue  # a note that already has the most tags
                    note["tag_suggestions"] = [s for s in note.get("tag_suggestions") or [] if s.casefold() != tag[0].casefold()]
                    app.store.save(note)
                    changed += 1
                return self._json(200, {"ok": True, "count": changed})
            if method == "GET" and path == "/api/search":
                return self._json(200, {"results": search.find(app.store.folder, (query.get("q") or [""])[0][:200])})
            if method == "GET" and path == "/api/search/meaning":
                try:
                    return self._json(200, {"results": embed.search(app.store, (query.get("q") or [""])[0][:300])})
                except (llm.LLMError, OSError, ValueError) as error:
                    raise ApiError(503, str(error)[:200])
            if method == "POST" and path == "/api/ask":
                return self._ask(body)
            if method == "POST" and path == "/api/ask/warm":
                return self._json(200, {"ok": True, "started": ask.warm()})
            if method == "GET" and path == "/api/actions":
                return self._json(200, {"actions": app.actions()})
            if method == "POST" and path == "/api/pick-folder":
                return self._json(200, app.pick_folder())
            match = re.fullmatch(r"/api/note/([A-Za-z0-9._-]+)(?:/(\w+))?", path)
            if match:
                return self._note(method, match.group(1), match.group(2), body, query)
            raise ApiError(404, "not_found")

        AUDIO_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".opus": "audio/ogg", ".ogg": "audio/ogg", ".flac": "audio/flac"}
        AUDIO_CHUNK = 16 * 1024 * 1024

        def _audio(self, note_id):
            """The recording of a note, with byte ranges so the page can jump to any moment."""
            note = app.get_note(note_id)
            try:
                path = Path(note.get("audio") or "").resolve(strict=True)
            except (OSError, RuntimeError):
                raise ApiError(404, "no_audio")
            ctype = self.AUDIO_TYPES.get(path.suffix.lower())
            if not ctype or not path.is_file():
                raise ApiError(404, "no_audio")
            size = lock.audio_size(path)
            start, end, status = 0, size - 1, 200
            found = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
            if found and (found.group(1) or found.group(2)):
                if found.group(1):
                    start = int(found.group(1))
                    end = int(found.group(2)) if found.group(2) else size - 1
                else:
                    start = max(0, size - int(found.group(2)))
                if start >= size or start > end:
                    return self._send(416, b"", "text/plain", {"Content-Range": "bytes */%d" % size})
                end = min(end, size - 1, start + self.AUDIO_CHUNK - 1)
                status = 206
            data = lock.audio_read(path, start, end)
            extra = {"Accept-Ranges": "bytes"}
            if status == 206:
                extra["Content-Range"] = "bytes %d-%d/%d" % (start, end, size)
            return self._send(status, data, ctype, extra)

        def _note(self, method, note_id, action, body, query):
            if method == "GET" and action is None:
                note = app.get_note(note_id)
                note["has_audio"] = os.path.isfile(note.get("audio") or "")
                return self._json(200, note)
            if method == "GET" and action == "audio":
                return self._audio(note_id)
            if method == "POST" and action == "action":
                what = str(body.get("what") or "").strip()[:500]
                if not what:
                    raise ApiError(400, "bad_action")
                note = app.get_note(note_id)
                finished = [w for w in note.get("actions_done") or [] if w != what]
                if body.get("done"):
                    finished.append(what)
                note["actions_done"] = finished[-300:]
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "tags":
                note = app.get_note(note_id)
                if body.get("dismiss"):
                    note.pop("tag_suggestions", None)
                else:
                    try:
                        note["tags"] = tags.clean(body.get("tags"))
                    except ValueError as error:
                        raise ApiError(400, str(error))
                    have = {t.casefold() for t in note["tags"]}
                    note["tag_suggestions"] = [s for s in note.get("tag_suggestions") or [] if s.casefold() not in have]
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "actionedit":
                note = app.get_note(note_id)
                actions = (note.get("summary") or {}).get("actions")
                try:
                    index = int(body.get("index"))
                except (TypeError, ValueError):
                    raise ApiError(400, "bad_action")
                was = str(body.get("was") or "").strip()
                if not isinstance(actions, list) or not 0 <= index < len(actions) or str(actions[index].get("what") or "").strip() != was:
                    raise ApiError(409, "changed")  # the note was written again meanwhile: the list shown is out of date
                ticked = was in (note.get("actions_done") or [])
                finished = [w for w in note.get("actions_done") or [] if w != was]
                if body.get("delete"):
                    del actions[index]
                else:
                    what = str(body.get("what") or "").strip()[:500]
                    if not what:
                        raise ApiError(400, "empty_action")
                    item = {"what": what}
                    for key in ("who", "when"):
                        value = str(body.get(key) or "").strip()[:80]
                        if value:
                            item[key] = value
                    actions[index] = item
                    if ticked:
                        finished.append(what)
                note["actions_done"] = finished[-300:]
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "followup":
                note = app.get_note(note_id)
                if note.get("status") != "done" or not note.get("summary") or note["summary"].get("empty"):
                    raise ApiError(400, "no_summary")
                if note.get("followup") and not body.get("redo"):
                    return self._json(200, note["followup"])
                try:
                    llm.preflight()
                    draft = llm.followup(note, note.get("lang") if note.get("lang") in config.LANGS else "en")
                except llm.LLMError as error:
                    raise ApiError(503, str(error)[:300])
                note = app.get_note(note_id)
                note["followup"] = draft
                app.store.save(note)
                return self._json(200, draft)
            if method == "GET" and action == "export":
                fmt = query.get("fmt", ["md"])[0]
                ctype, text, ext = app.export(note_id, fmt, query.get("transcript", ["1"])[0] == "1", query.get("fragment", ["0"])[0] == "1")
                name = re.sub(r"[^A-Za-z0-9._-]+", "_", app.get_note(note_id).get("title") or note_id).strip("_") or "note"
                disposition = "attachment; filename*=UTF-8''%s" % quote(name + ext)
                return self._send(200, text, ctype, {"Content-Disposition": disposition})
            if method == "POST" and action == "export":  # writing to disk is a POST, never a GET
                fmt = str(body.get("fmt") or "md")
                ctype, text, ext = app.export(note_id, fmt, body.get("transcript", True) is not False, bool(body.get("fragment")))
                name = re.sub(r"[^A-Za-z0-9._-]+", "_", app.get_note(note_id).get("title") or note_id).strip("_") or "note"
                folder = config.home() / "Exports"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (name + ext)).write_text(text, encoding="utf-8")
                return self._json(200, {"ok": True, "name": name + ext})
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
                custom = templates.find(config.load_settings().get("templates"), kind)
                if kind not in llm.TEMPLATES and not custom:
                    raise ApiError(400, "bad_template")
                note = app.get_note(note_id)
                note["template"] = kind  # the person's choice, kept when the note is redone
                summary = {k: v for k, v in (note.get("summary") or {}).items() if k not in ("custom", "template_name")}
                if custom:  # the note is written again with its instruction (the page asks for it)
                    summary.update(custom=custom["id"], template_name=custom["name"])
                else:
                    summary["template"] = kind
                note["summary"] = summary
                app.store.save(note)
                return self._json(200, {"ok": True})
            if method == "POST" and action == "rerun":
                level, lang = body.get("level"), body.get("lang")
                spoken = body.get("speech_lang")
                if level not in config.LEVELS or (lang is not None and lang not in config.LANGS) or (spoken is not None and spoken not in ("auto",) + config.LANGS):
                    raise ApiError(400, "bad_level")
                app.get_note(note_id)
                try:
                    transcribe = app.jobs.start_rerun(note_id, level, lang, body.get("speech_lang"))
                except jobs.Busy:
                    raise ApiError(409, "busy")
                return self._json(202, {"ok": True, "transcribe": transcribe})
            if method == "POST" and action == "options":
                app.get_note(note_id)
                try:
                    app.jobs.set_options(note_id, body.get("level"), body.get("lang"), body.get("speech_lang"))
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
            if method == "POST" and action == "rediarize":
                app.get_note(note_id)
                try:
                    app.jobs.start_rediarize(note_id)
                except jobs.Busy:
                    raise ApiError(409, "busy")
                except ValueError as error:
                    raise ApiError(400, str(error))
                return self._json(202, {"ok": True})
            if method == "POST" and action == "segment":
                return self._json(200, app.edit_segment(note_id, body.get("index"), body.get("text"), body.get("scope")))
            if method == "POST" and action == "speaker":
                with app.store.lock:  # read, change and write as one step
                    raw = str(body.get("from") or "").strip()[:60]
                    name = " ".join(str(body.get("name") or "").split())[:60]
                    if not raw:
                        raise ApiError(400, "bad_speaker")
                    note = app.get_note(note_id)
                    names = dict(note.get("speaker_names") or {})
                    if name:
                        names[raw] = name
                    else:
                        names.pop(raw, None)
                    note["speaker_names"] = names
                    auto = dict(note.get("speaker_auto") or {})
                    auto.pop(raw, None)  # named by hand from now on
                    note["speaker_auto"] = auto
                    if not auto:
                        note.pop("speaker_auto")
                    if name and config.load_settings().get("voices") and (note.get("voices") or {}).get(raw):
                        voices.learn(name, note["voices"][raw])  # a voice is only learned from a name the person typed
                    if note.get("segments"):
                        note["clean"] = "\n\n".join(speech.raw_lines(diarize.renamed(note["segments"], names)))
                    app.store.save(note)
                    return self._json(200, {"ok": True})
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
