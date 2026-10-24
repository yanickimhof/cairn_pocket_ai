"""Run Cairn in the background (macOS): started at login, restarted if it stops.

    python -m cairn service install | open | start | stop | restart | status | uninstall

The service is a per-user launch agent: no administrator rights, nothing outside your
home folder. `open` starts it when needed, restarts it when it does not answer, and then
opens your browser on the right page.
"""

import os
import plistlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from . import config

LABEL = "io.github.cairn"


def agent_path():
    return Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")


def app_path():
    return config.home() / "Cairn.app"


def url_file():
    return config.home() / "url.txt"


def _launcher():
    return str(config.home() / "bin" / "cairn")


def agent_plist():
    """The launch agent definition: keep running, restart after a crash, log to ~/Cairn/cairn.log."""
    log = str(config.home() / "cairn.log")
    return {
        "Label": LABEL,
        "ProgramArguments": [_launcher(), "--no-browser"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }


def app_files():
    """A tiny application bundle: double-click it, no Terminal window."""
    info = {
        "CFBundleName": "Cairn", "CFBundleDisplayName": "Cairn", "CFBundleIdentifier": LABEL + ".app",
        "CFBundleExecutable": "Cairn", "CFBundlePackageType": "APPL", "CFBundleVersion": config.VERSION,
        "CFBundleShortVersionString": config.VERSION, "LSUIElement": True,
    }
    script = '#!/bin/bash\nexec "%s" service open\n' % _launcher()
    return plistlib.dumps(info), script


def _launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=False)  # nosec B603 B607


def _target():
    return "gui/%d/%s" % (os.getuid(), LABEL)


def loaded():
    return _launchctl("print", _target()).returncode == 0


def install():
    config.home().mkdir(parents=True, exist_ok=True)
    agent_path().parent.mkdir(parents=True, exist_ok=True)
    with open(agent_path(), "wb") as handle:
        plistlib.dump(agent_plist(), handle)
    info, script = app_files()
    contents = app_path() / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Info.plist").write_bytes(info)
    launcher = contents / "MacOS" / "Cairn"
    launcher.write_text(script, encoding="utf-8")
    launcher.chmod(0o755)
    if loaded():
        _launchctl("bootout", _target())
    result = _launchctl("bootstrap", "gui/%d" % os.getuid(), str(agent_path()))
    if result.returncode != 0:
        raise RuntimeError("launchctl: " + (result.stderr or result.stdout).strip())


def stop():
    if loaded():
        _launchctl("bootout", _target())


def restart():
    if not loaded():
        install()
    else:
        _launchctl("kickstart", "-k", _target())  # stops the process, then starts a fresh one


def uninstall():
    stop()
    agent_path().unlink(missing_ok=True)


def url():
    try:
        return url_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def healthy(address=None, timeout=4):
    address = address or url()
    if not address.startswith("http://127.0.0.1:"):
        return False
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(address, timeout=timeout):  # nosec B310 (loopback only)
            return True
    except urllib.error.HTTPError as error:  # the session page answers with a redirect once the key is accepted
        return error.code in (200, 303)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_healthy(seconds):
    end = time.time() + seconds
    while time.time() < end:
        if healthy():
            return True
        time.sleep(1)
    return False


def open_app():
    """Make sure Cairn answers (start or restart it if needed), then open the browser."""
    if not loaded():
        install()
    elif not healthy():
        restart()
    if not wait_healthy(45):
        restart()
        if not wait_healthy(45):
            print("Cairn did not start. See %s" % (config.home() / "cairn.log"))
            return 1
    webbrowser.open(url())
    return 0


def main(argv):
    command = argv[0] if argv else "status"
    if sys.platform != "darwin":
        print("Background mode is available on macOS. Run `cairn` to start Cairn in a window.")
        return 1
    if command == "install":
        install()
        print("Cairn runs in the background and starts at login. Open it with %s" % app_path())
    elif command in ("open", "start"):
        return open_app()
    elif command == "stop":
        stop()
        print("Cairn stopped.")
    elif command == "restart":
        restart()
        print("Cairn restarted." if wait_healthy(45) else "Cairn is starting. See %s" % (config.home() / "cairn.log"))
    elif command == "uninstall":
        uninstall()
        print("Background mode removed.")
    elif command == "status":
        print("running" if healthy() else ("loaded, not answering" if loaded() else "not running"))
    else:
        print(__doc__)
        return 2
    return 0
