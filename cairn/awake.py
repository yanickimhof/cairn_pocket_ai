"""Keep the computer awake while a job runs, so a long batch is not cut short by the idle sleep.

macOS only (caffeinate -i: the display may still sleep). Closing the lid of a laptop that has no
external display still puts it to sleep, whatever a program asks. Nothing happens elsewhere."""

import os
import shutil
import subprocess  # nosec B404
import sys
import threading

_LOCK = threading.Lock()
_STATE = {"proc": None, "count": 0}


def hold():
    with _LOCK:
        _STATE["count"] += 1
        if _STATE["proc"] is None and sys.platform == "darwin":
            path = shutil.which("caffeinate")
            if path:
                try:
                    _STATE["proc"] = subprocess.Popen(  # nosec B603
                        [path, "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                except OSError:
                    pass


def release():
    with _LOCK:
        _STATE["count"] = max(0, _STATE["count"] - 1)
        if _STATE["count"] == 0 and _STATE["proc"] is not None:
            proc, _STATE["proc"] = _STATE["proc"], None
            try:
                proc.terminate()
            except OSError:
                pass
