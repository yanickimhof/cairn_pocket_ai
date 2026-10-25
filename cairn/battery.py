"""Battery level of the Pocket, shown when it can be read (macOS). Nothing is shown otherwise.

The level is read over Bluetooth by a small separate program (battery_worker), read only, about every two minutes.
Nothing goes over the network, nothing is stored, and the Pocket is neither paired nor changed.
"""

import subprocess  # nosec B404
import sys
import threading
import time
from pathlib import Path

REFRESH = 120  # seconds between two readings
RETRY = 300    # seconds before trying again when nothing could be read (Pocket away, Bluetooth off or refused)
STALE = 600    # a reading older than this is no longer shown


def available():
    return sys.platform == "darwin"


def read(timeout=40):
    """One reading: ("ok", level), ("missing", None) when the Bluetooth component is not installed, else ("none", None)."""
    try:
        done = subprocess.run(  # nosec B603
            [sys.executable, "-m", "cairn.battery_worker"], capture_output=True, text=True, timeout=timeout,
            cwd=str(Path(__file__).resolve().parent.parent), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "none", None
    if done.returncode == 3:
        return "missing", None
    text = done.stdout.strip()
    if text.isdigit() and 0 <= int(text) <= 100:
        return "ok", int(text)
    detail = (done.stderr or "").strip().splitlines()[-1:] or ["exit %d" % done.returncode]
    print("battery: no reading (%s)" % detail[0][:160], file=sys.stderr, flush=True)  # in the log, to understand a missing level
    return "none", None


class Gauge:
    def __init__(self, reader=read):
        self.reader = reader
        self.level = None
        self.state = "none"
        self.when = 0.0
        self.tried = 0.0
        self.busy = False
        self.lock = threading.Lock()

    def poll(self, now=None):
        """Start a reading in the background when one is due. Never blocks."""
        now = time.time() if now is None else now
        with self.lock:
            if self.state == "missing":
                return False  # the optional component is not installed: nothing to try
            wait = REFRESH if self.state == "ok" else RETRY
            if self.busy or now - self.tried < wait:
                return False
            self.busy, self.tried = True, now
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        try:
            state, level = self.reader()
        except Exception:
            state, level = "none", None
        with self.lock:
            self.state, self.level = state, level
            if level is not None:
                self.when = time.time()
            self.busy = False

    def snapshot(self):
        """What the interface needs: the level when there is a recent one."""
        data = {"available": available()}
        if available():
            with self.lock:
                fresh = self.level is not None and time.time() - self.when <= STALE
                data.update(level=self.level if fresh else None, state=self.state)
        return data
