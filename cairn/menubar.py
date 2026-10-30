"""The menu bar item (macOS): a small, quiet way to see Cairn at work without opening the page.

It runs as a separate process started and stopped by Cairn (AppKit needs the main thread of its own process) and talks to the
local server with the same session key as the page, on 127.0.0.1 only. The wording and the choice of lines are plain functions
(model, below), so they can be tested without a screen; the AppKit part only draws what the model says.

What it shows: one monochrome icon in the system's own style (three stacked stones), a short menu, and one notification per batch.
What it never shows: the title or the text of a note."""
import http.client
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import config

TEXT = {
    "fr": {
        "open": "Ouvrir Cairn", "unlock": "Déverrouiller Cairn", "locked": "Verrouillé", "lock": "Verrouiller", "quit": "Quitter",
        "pocket": "Pocket connectée", "import": "Importer {n} enregistrement", "imports": "Importer {n} enregistrements", "cancel": "Annuler",
        "waiting": "{n} en attente", "private": "Rien n’a quitté ce Mac", "check": "Vérification de confidentialité à refaire", "away": "Cairn ne répond pas",
        "of": "{a} sur {b}", "ready": "{n} note prête", "readys": "{n} notes prêtes",
        "steps": {"copying": "Copie", "transcribing": "Transcription", "diarizing": "Interlocuteurs", "summarizing": "Rédaction", "sealing": "Chiffrement",
                  "opening": "Déchiffrement", "indexing": "Indexation", "securing": "Pocket", "privacy": "Vérification"},
    },
    "en": {
        "open": "Open Cairn", "unlock": "Unlock Cairn", "locked": "Locked", "lock": "Lock", "quit": "Quit",
        "pocket": "Pocket connected", "import": "Import {n} recording", "imports": "Import {n} recordings", "cancel": "Cancel",
        "waiting": "{n} waiting", "private": "Nothing left this Mac", "check": "Privacy check due", "away": "Cairn is not answering",
        "of": "{a} of {b}", "ready": "{n} note ready", "readys": "{n} notes ready",
        "steps": {"copying": "Copying", "transcribing": "Transcribing", "diarizing": "Speakers", "summarizing": "Writing", "sealing": "Encrypting",
                  "opening": "Decrypting", "indexing": "Indexing", "securing": "Pocket", "privacy": "Checking"},
    },
}


def _t(lang):
    return TEXT.get(lang) or TEXT["en"]


def _clock(when):
    """HH:MM of an ISO time, or ''."""
    try:
        return str(when)[11:16] if len(str(when)) >= 16 else ""
    except (TypeError, ValueError):
        return ""


def model(state, lang="en", locked=False, away=False):
    """What the menu holds for this state of Cairn: the icon (idle, work, attention, locked, away), the lines and the actions.

    Each line is (kind, text, action): kind is "title", "text", "action" or "separator"; action is the code the click sends back."""
    t = _t(lang)
    if away or state is None and not locked:
        return {"icon": "away", "lines": [("title", "Cairn", None), ("text", t["away"], None), ("separator", "", None), ("action", t["quit"], "quit")]}
    if locked:
        return {"icon": "locked", "lines": [("title", "Cairn · " + t["locked"], None), ("action", t["unlock"], "open"), ("separator", "", None), ("action", t["quit"], "quit")]}
    job = state.get("job") or {}
    pocket = state.get("pocket") or {}
    totals = state.get("totals") or {}
    lock = state.get("lock") or {}
    lines = [("title", "Cairn", None), ("action", t["open"], "open")]
    if pocket.get("connected"):
        level = (state.get("battery") or {}).get("level")
        lines.append(("text", t["pocket"] + (" · %d %%" % level if isinstance(level, (int, float)) else ""), None))
        fresh = int(pocket.get("new") or 0)
        if fresh and not job.get("running"):
            lines.append(("action", (t["imports"] if fresh > 1 else t["import"]).format(n=fresh), "import"))
    if job.get("running"):
        step = t["steps"].get(job.get("step") or "", "")
        total, done = int(job.get("total") or 0), int(job.get("done") or 0)
        count = " · " + t["of"].format(a=min(done + 1, total), b=total) if total > 1 else ""
        if step:
            lines.append(("text", step + count, None))
        lines.append(("action", t["cancel"], "cancel"))
    elif int(totals.get("waiting") or 0):
        lines.append(("text", t["waiting"].format(n=int(totals["waiting"])), None))
    lines.append(("separator", "", None))
    if lock.get("enabled") and not lock.get("locked"):
        lines.append(("action", t["lock"], "lock"))
    privacy = state.get("privacy") or {}
    if privacy.get("ok"):
        when = _clock(privacy.get("when"))
        lines.append(("text", t["private"] + (" · " + when if when else ""), None))
    else:
        lines.append(("text", t["check"], None))
    lines.append(("separator", "", None))
    lines.append(("action", t["quit"], "quit"))
    attention = bool(job.get("errors")) or (privacy and not privacy.get("ok") and bool(privacy.get("when")))
    return {"icon": "work" if job.get("running") else "attention" if attention else "idle", "lines": lines}


def finished(before, after, lang="en"):
    """The text of a notification when a batch ended (one notification per batch, never one per step), or None."""
    was, now = (before or {}).get("job") or {}, (after or {}).get("job") or {}
    if not was.get("running") or now.get("running") or now.get("errors"):
        return None
    if was.get("kind") not in ("import", "queue", "process", "sync"):
        return None
    done = int(((after or {}).get("totals") or {}).get("done") or 0) - int(((before or {}).get("totals") or {}).get("done") or 0)
    if done <= 0:
        return None
    t = _t(lang)
    return (t["readys"] if done > 1 else t["ready"]).format(n=done)


# Talking to Cairn

class Client:
    """The page address and key Cairn wrote for itself (url.txt), and plain calls on the loopback."""

    def __init__(self, home=None):
        self.home = Path(home or config.home())

    def target(self):
        try:
            text = (self.home / "url.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        found = text.split("//", 1)[-1]
        host_port, _, rest = found.partition("/")
        port = host_port.rpartition(":")[2]
        key = rest.partition("k=")[2]
        return (int(port), key) if port.isdigit() and key else None

    def url(self):
        target = self.target()
        return "http://127.0.0.1:%d/?k=%s" % target if target else None

    def call(self, method, path, body=None, timeout=3):
        target = self.target()
        if not target:
            return None, None
        port, key = target
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
            headers = {"Host": "127.0.0.1:%d" % port, "X-Cairn-Key": key}
            if method == "POST":
                headers.update({"Content-Type": "application/json", "X-Cairn": "1"})
            conn.request(method, path, json.dumps(body or {}) if method == "POST" else None, headers)
            resp = conn.getresponse()
            raw = resp.read()
            conn.close()
            try:
                return resp.status, json.loads(raw or b"{}")
            except ValueError:
                return resp.status, None
        except (OSError, http.client.HTTPException):
            return None, None


# The process that Cairn starts

_proc = {"p": None}


def available():
    if sys.platform != "darwin":
        return False
    try:
        import AppKit  # noqa: F401
    except ImportError:
        return False
    return True


def ensure(wanted):
    """Start the menu bar process when it is wanted and not running; stop it when it is not wanted. Called by the upkeep."""
    proc = _proc["p"]
    alive = proc is not None and proc.poll() is None
    if wanted and not alive and available():
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _proc["p"] = subprocess.Popen([sys.executable, "-m", "cairn.menubar", str(os.getpid())], env=dict(os.environ, DO_NOT_TRACK="1"),  # nosec B603
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    elif not wanted and alive:
        proc.terminate()
        _proc["p"] = None


def stop():
    ensure(False)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# The part that draws (AppKit); everything it decides comes from the functions above

def run(parent):
    import AppKit
    import Foundation
    import objc

    client = Client()
    shown = {"icon": None, "lines": None}
    last = {"state": None, "lang": "en", "away_since": None}

    def image(kind):
        """Three stacked stones, drawn in the system's own style so it follows light and dark."""
        w, h = 20.0, 18.0

        def draw(rect):
            alpha = 0.45 if kind in ("locked", "away") else 1.0
            AppKit.NSColor.blackColor().colorWithAlphaComponent_(alpha).set()
            for index, (x, width) in enumerate(((3.0, 14.0), (5.0, 10.0), (7.0, 6.0))):
                y = 2.0 + index * 5.0
                path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(Foundation.NSMakeRect(x, y, width, 4.0), 2.0, 2.0)
                if kind == "work":
                    path.fill()
                else:
                    path.setLineWidth_(1.3)
                    path.stroke()
            if kind == "attention":
                AppKit.NSBezierPath.bezierPathWithOvalInRect_(Foundation.NSMakeRect(15.0, 12.0, 5.0, 5.0)).fill()
            return True

        picture = AppKit.NSImage.imageWithSize_flipped_drawingHandler_((w, h), False, draw)
        picture.setTemplate_(True)
        return picture

    class Controller(Foundation.NSObject):
        def init(self):
            self = objc.super(Controller, self).init()
            if self is None:
                return None
            self.item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(AppKit.NSVariableStatusItemLength)
            self.item.button().setImage_(image("idle"))
            return self

        def tick_(self, _timer):
            if not _alive(parent):
                AppKit.NSApp.terminate_(None)
                return
            status, state = client.call("GET", "/api/state?list=0")
            locked = False
            if status == 423:
                status, info = client.call("GET", "/api/lock")
                locked, state = True, None
            away = status is None
            if away:
                last["away_since"] = last["away_since"] or time.time()
                if time.time() - last["away_since"] > 180:
                    AppKit.NSApp.terminate_(None)  # Cairn has been gone for three minutes
                    return
            else:
                last["away_since"] = None
            if state and (state.get("settings") or {}).get("menubar") is False:
                AppKit.NSApp.terminate_(None)  # switched off in Settings
                return
            lang = ((state or {}).get("settings") or {}).get("ui") or last["lang"]
            last["lang"] = lang
            note = finished(last["state"], state, lang)
            if note:
                self.notify(note)
            last["state"] = None if locked else (state or last["state"])
            self.show(model(state, lang, locked=locked, away=away))

        def notify(self, text):
            safe = "".join(c for c in text if c.isalnum() or c in " ’'.,:-éèêàçùôîÉ")  # our own short text, nothing to escape
            try:
                subprocess.run(["osascript", "-e", 'display notification "%s" with title "Cairn"' % safe], timeout=10, check=False)  # nosec B603
            except (OSError, subprocess.SubprocessError):
                pass  # a notification is a courtesy

        def show(self, built):
            if built["icon"] != shown["icon"]:
                self.item.button().setImage_(image(built["icon"]))
                shown["icon"] = built["icon"]
            if built["lines"] == shown["lines"]:
                return
            shown["lines"] = built["lines"]
            menu = AppKit.NSMenu.alloc().init()
            menu.setAutoenablesItems_(False)
            for kind, text, action in built["lines"]:
                if kind == "separator":
                    menu.addItem_(AppKit.NSMenuItem.separatorItem())
                    continue
                entry = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(text, "act:" if action else None, "")
                if action:
                    entry.setTarget_(self)
                    entry.setRepresentedObject_(action)
                else:
                    entry.setEnabled_(False)
                menu.addItem_(entry)
            self.item.setMenu_(menu)

        def act_(self, sender):
            action = sender.representedObject()
            if action == "open":
                AppKit.NSWorkspace.sharedWorkspace().openURL_(Foundation.NSURL.URLWithString_(client.url() or "http://127.0.0.1"))
            elif action == "import":
                client.call("POST", "/api/import")
            elif action == "cancel":
                client.call("POST", "/api/cancel")
            elif action == "lock":
                client.call("POST", "/api/lock/now", timeout=20)
            elif action == "quit":
                quit_cairn(parent)
                AppKit.NSApp.terminate_(None)
            self.tick_(None)

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)  # no Dock icon, no window
    controller = Controller.alloc().init()
    Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(2.0, controller, "tick:", None, True)
    controller.tick_(None)
    app.run()


def quit_cairn(parent):
    """Quit means Cairn itself: through the background service when there is one (it would start again otherwise), else the process."""
    try:
        from . import service

        if service.agent_path().exists():
            subprocess.run([sys.executable, "-m", "cairn", "service", "stop"], timeout=30, check=False)  # nosec B603
            return
    except Exception:  # noqa: BLE001
        pass
    with_signal = getattr(signal, "SIGTERM", None)
    if with_signal and _alive(parent):
        os.kill(parent, with_signal)


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else os.getppid())
