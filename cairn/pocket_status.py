"""Optional, read-only Pocket status (firmware, device state, storage), shown only once the person has entered
their own BLE session key in the settings (macOS). Without a key, nothing here is used and nothing changes in
Cairn's behaviour: the unauthenticated battery reading in battery.py keeps working on its own.

Exactly three read commands are sent, after the session key: firmware, state, storage. No clock is set, no
WiFi command is ever sent, nothing is written to the Pocket beyond that session-key handshake. The key is
passed to the worker over stdin, kept only in memory for the length of one reading, and never logged.
"""

import json
import subprocess  # nosec B404
import sys
import threading
import time
from pathlib import Path

REFRESH = 120  # seconds between two readings once one succeeded
RETRY = 300    # seconds before retrying after a reading that found nothing (Pocket away, Bluetooth off)
STALE = 600    # a reading older than this is no longer shown


def available():
    return sys.platform == "darwin"


def read(key, timeout=30):
    """One reading for this key: ("ok", {...}), ("rejected", None), ("missing", None), or ("none", None)."""
    try:
        done = subprocess.run(  # nosec B603
            [sys.executable, "-m", "cairn.pocket_status_worker"], input=key + "\n", capture_output=True,
            text=True, timeout=timeout, cwd=str(Path(__file__).resolve().parent.parent), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "none", None
    if done.returncode == 3:
        return "missing", None
    if done.returncode == 2:
        return "rejected", None
    if done.returncode == 0 and done.stdout.strip():
        try:
            return "ok", json.loads(done.stdout.strip())
        except ValueError:
            return "none", None
    detail = (done.stderr or "").strip().splitlines()[-1:] or ["exit %d" % done.returncode]
    print("pocket_status: no reading (%s)" % detail[0][:160], file=sys.stderr, flush=True)
    return "none", None


class StatusGauge:
    def __init__(self, reader=read):
        self.reader = reader
        self.data = None
        self.state = "none"
        self.when = 0.0
        self.tried = 0.0
        self.busy = False
        self.lock = threading.Lock()

    def poll(self, key, now=None):
        """Start a reading in the background when one is due and a key is set. Never blocks."""
        now = time.time() if now is None else now
        if not key or len(key) != 16:
            return False
        with self.lock:
            if self.state == "missing":
                return False  # the optional component is not installed: nothing to try
            wait = REFRESH if self.state == "ok" else RETRY
            if self.busy or now - self.tried < wait:
                return False
            self.busy, self.tried = True, now
        threading.Thread(target=self._run, args=(key,), daemon=True).start()
        return True

    def _run(self, key):
        try:
            state, data = self.reader(key)
        except Exception:
            state, data = "none", None
        with self.lock:
            self.state, self.data = state, data
            if data is not None:
                self.when = time.time()
            self.busy = False

    def snapshot(self):
        """What the interface needs: the data when there is a recent reading."""
        with self.lock:
            fresh = self.data is not None and time.time() - self.when <= STALE
            return {"state": self.state, "data": self.data if fresh else None}
