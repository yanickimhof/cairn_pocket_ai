"""Privacy check: watch the network connections of Cairn and its engines while they work.

It runs a tiny transcription and a tiny question on the local engines, and lists every
connection that leaves this computer. Nothing is sent anywhere: the check only reads the
operating system's connection table.
"""

import ipaddress
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave

from . import config, llm, netguard, speech

SAMPLE_SECONDS = 0.3


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False).stdout  # nosec B603
    except (OSError, subprocess.SubprocessError):
        return ""


def process_table():
    """(pid, ppid, command) of every process."""
    rows = []
    if os.name == "nt":
        command = "Get-CimInstance Win32_Process | ForEach-Object { '{0},{1},{2}' -f $_.ProcessId, $_.ParentProcessId, $_.Name }"
        out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command])
        for line in out.splitlines():
            parts = line.strip().split(",", 2)
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                rows.append((int(parts[0]), int(parts[1]), parts[2]))
        return rows
    for line in _run(["ps", "-axo", "pid=,ppid=,command="]).splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)\s+(.*)", line)
        if match:
            rows.append((int(match.group(1)), int(match.group(2)), match.group(3)))
    return rows


def watched_pids():
    """Cairn itself, its children (the speech engine) and the local model server."""
    table = process_table()
    mine = {os.getpid()}
    grew = True
    while grew:
        grew = False
        for pid, ppid, _ in table:
            if ppid in mine and pid not in mine:
                mine.add(pid)
                grew = True
    models = {pid for pid, _, command in table if "ollama" in command.lower() and "cairn" not in command.lower().split()[0:1]}
    return mine, models


def _remote_is_outside(remote):
    host = remote.rsplit(":", 1)[0].strip("[]").split("%")[0]
    if host in ("*", ""):  # unconnected sockets
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_loopback or address.is_unspecified)


def connections(pids):
    """Established or connecting sockets of the given processes: [(pid, remote)]."""
    found = []
    if os.name == "nt":
        for line in _run(["netstat", "-ano"]).splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] in ("TCP", "UDP") and parts[-1].isdigit() and int(parts[-1]) in pids:
                state = parts[3] if parts[0] == "TCP" else ""
                if parts[0] == "TCP" and state not in ("ESTABLISHED", "SYN_SENT"):
                    continue  # closing connections are left over from earlier work (a model download, say)
                found.append((int(parts[-1]), parts[2]))
        return found
    if not pids:
        return found
    out = _run(["lsof", "-nP", "-i", "-a", "-p", ",".join(str(p) for p in sorted(pids))])
    for line in out.splitlines()[1:]:
        parts = line.split()
        match = re.search(r"->(\S+)", line)
        if len(parts) > 1 and parts[1].isdigit() and match and ("ESTABLISHED" in line or "SYN_SENT" in line):
            found.append((int(parts[1]), match.group(1)))
    return found


def _tone(path, seconds=2, rate=16000):
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", int(6000 * math.sin(n / 18))) for n in range(seconds * rate)))


def run_check():
    """Exercise the engines while sampling their connections. Returns the report."""
    started = time.time()
    seen, stop = {}, threading.Event()
    models_seen = set()
    errors = []

    def sample():
        while not stop.is_set():
            mine, models = watched_pids()
            models_seen.update(models)
            for pid, remote in connections(mine | models):
                if _remote_is_outside(remote):
                    seen[(pid, remote)] = seen.get((pid, remote), 0) + 1
            time.sleep(SAMPLE_SECONDS)

    # Connections already open before the test (a keep-alive left by an earlier model download,
    # for instance) are reported apart: the test itself must not open any.
    mine0, models0 = watched_pids()
    baseline = {(pid, remote) for pid, remote in connections(mine0 | models0) if _remote_is_outside(remote)}
    watcher = threading.Thread(target=sample, daemon=True)
    watcher.start()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            audio = os.path.join(tmp, "check.wav")
            _tone(audio)
            try:
                speech.transcribe(audio)
            except Exception as error:  # the check reports it, the observation still counts
                errors.append("speech: %s" % str(error)[:120])
        try:
            llm.chat("Answer with one word.", "Say ok.")
        except Exception as error:
            errors.append("language model: %s" % str(error)[:120])
        time.sleep(1.0)
    finally:
        stop.set()
        watcher.join(timeout=3)
    mine, models = watched_pids()
    names = {pid: os.path.basename(command.split(" ")[0]) for pid, _, command in process_table()}
    label = lambda key: "%s (%d) -> %s" % (names.get(key[0], "?"), key[0], key[1])  # noqa: E731
    external = sorted(label(key) for key in seen if key not in baseline)
    leftover = sorted(label(key) for key in baseline if key in seen)
    report = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - started, 1),
        "external": external, "leftover": leftover, "blocked": netguard.blocked(), "model_server_seen": bool(models_seen or models),
        "errors": errors, "ok": not external and not netguard.blocked() and not errors,
        "platform": sys.platform,
    }
    try:
        config.write_json(config.home() / "privacy-check.json", report)
    except OSError:
        pass
    return report


def last_report():
    return config.read_json(config.home() / "privacy-check.json", default=None)
