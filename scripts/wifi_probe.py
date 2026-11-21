#!/usr/bin/env python3
"""Cairn Wi-Fi probe (phase 0, read-only): does a Pocket on your Wi-Fi network announce itself, and where?

Run it on your Mac, on the same private Wi-Fi network as the Pocket, with the Pocket awake and Wi-Fi sync switched on:

    python3 scripts/wifi_probe.py                 # lists what announces itself on the network (Bonjour) and the ARP table
    python3 scripts/wifi_probe.py --ip 192.168.1.42   # also checks a short list of ports on that one address

What it does: listens to Bonjour announcements for a few seconds, reads the ARP table, and, only if you give --ip, tries a plain
TCP connection to about 20 common ports of that one address, reading nothing but what the device volunteers (no request is sent).
With --range 1024-12000 it also tries every port of that range on that one address (connect only, nothing is sent, at most
20000 ports, off by default). What it never does: send data to the device, log in, touch any address outside your private
network, or read recordings. Nothing is installed and nothing outside this script is changed. The report is written to ~/cairn-wifi-probe.txt:
it holds local addresses (and MAC addresses), so look at it before sharing it.
"""
import argparse
import ipaddress
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PORTS = (8475, 22, 53, 80, 443, 554, 1883, 3000, 5000, 5353, 7000, 8000, 8080, 8081, 8443, 8883, 9000, 9090, 49152)
REPORT = Path.home() / "cairn-wifi-probe.txt"


def say(lines, text=""):
    print(text)
    lines.append(text)


def browse(args, seconds):
    """Run one `dns-sd` browse for a few seconds and return what it printed (the command never ends by itself)."""
    with tempfile.TemporaryFile() as out:
        process = subprocess.Popen(["dns-sd"] + args, stdout=out, stderr=subprocess.DEVNULL)
        time.sleep(seconds)
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()
        out.seek(0)
        return out.read().decode("utf-8", "replace")


ROW = re.compile(r"\s(Add|Rmv)\s+\d+\s+\d+\s+(\S+)\s+(\S+)\s+(.*)$")


def parse_rows(text):
    """(domain, service type column, instance name) of every 'Add' row printed by dns-sd -B."""
    found = []
    for row in text.splitlines():
        match = ROW.search(row)
        if match and match.group(1) == "Add":
            found.append((match.group(2), match.group(3), match.group(4).strip()))
    return found


def bonjour(lines, seconds=6):
    say(lines, "== Bonjour (names that devices announce on your network) ==")
    if platform.system() != "Darwin":
        say(lines, "This step needs macOS (dns-sd). Skipped.")
        return
    kinds = sorted({name + "." + column.split(".")[0] for _, column, name in parse_rows(browse(["-B", "_services._dns-sd._udp", "local."], seconds))})
    say(lines, "service types seen: %d" % len(kinds))
    found = 0
    for kind in kinds[:30]:
        for _, _, instance in parse_rows(browse(["-B", kind, "local."], 2)):
            found += 1
            flag = "   <-- looks like a Pocket" if "pocket" in instance.lower() else ""
            say(lines, "  %s : %s%s" % (kind, instance, flag))
    if not found:
        say(lines, "no named device found on these %d service types." % len(kinds))


def arp(lines):
    say(lines, "")
    say(lines, "== ARP table (devices your Mac has talked to recently) ==")
    try:
        text = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        say(lines, "arp is not available.")
        return
    for row in text.splitlines():
        if "incomplete" not in row and "ff:ff:ff" not in row:
            say(lines, "  " + row.strip())
    say(lines, "Tip: note the address of the Pocket from your router's list of connected devices, then rerun with --ip.")


def parse_range(text):
    try:
        low, high = (int(part) for part in text.split("-", 1))
    except ValueError:
        raise SystemExit("--range must look like 1024-12000")
    if not (1 <= low <= high <= 65535) or high - low >= 20000:
        raise SystemExit("--range: ports 1 to 65535, at most 20000 ports")
    return low, high


def sweep(lines, address, low, high):
    def attempt(port):
        try:
            with socket.create_connection((address, port), timeout=0.4):
                return port
        except OSError:
            return None

    say(lines, "")
    say(lines, "== TCP range %d-%d on %s (connect only) ==" % (low, high, address))
    with ThreadPoolExecutor(max_workers=200) as pool:
        opened = [port for port in pool.map(attempt, range(low, high + 1)) if port]
    say(lines, "  open: %s" % (", ".join(map(str, opened)) if opened else "none"))


def check_ports(lines, address):
    ip = ipaddress.ip_address(address)
    if not (ip.is_private and not ip.is_loopback and not ip.is_multicast):
        raise SystemExit("Refused: %s is not a private network address." % address)
    say(lines, "")
    say(lines, "== Is %s reachable at all? ==" % address)
    try:
        ping = subprocess.run(["ping", "-c", "3", "-t", "5", address], capture_output=True, text=True, timeout=20)
        tail = [row for row in ping.stdout.splitlines() if "packets" in row or "round-trip" in row]
        say(lines, "  " + (" | ".join(tail) if tail else "no answer to ping (some devices ignore ping)"))
        neighbour = subprocess.run(["arp", "-n", address], capture_output=True, text=True, timeout=10).stdout.strip()
        say(lines, "  arp: " + (neighbour or "no entry"))
    except (OSError, subprocess.TimeoutExpired):
        say(lines, "  ping is not available.")
    say(lines, "")
    say(lines, "== TCP ports on %s (connect only, nothing is sent) ==" % address)
    open_ports = 0
    for port in PORTS:
        try:
            with socket.create_connection((address, port), timeout=0.8) as link:
                link.settimeout(0.6)
                try:
                    hello = link.recv(64)
                except OSError:
                    hello = b""
                open_ports += 1
                say(lines, "  %5d open%s" % (port, ("   first bytes: %r" % hello) if hello else ""))
        except OSError as error:
            if port == PORTS[0]:
                say(lines, "  first attempt: %s" % error)
    if not open_ports:
        say(lines, "  none of these %d ports answers. The device may use another port, UDP, or only talk to its own app." % len(PORTS))


def main():
    parser = argparse.ArgumentParser(description="Read-only look at how a Pocket shows itself on your Wi-Fi network.")
    parser.add_argument("--ip", help="the Pocket's address on your network (private addresses only)")
    parser.add_argument("--quick", action="store_true", help="only test the device given with --ip (ping and ports), about 20 seconds: for a Pocket that stays reachable only briefly")
    parser.add_argument("--range", help="also try every TCP port of this range on --ip, for example 1024-12000")
    parser.add_argument("--seconds", type=int, default=6, help="how long to listen for Bonjour announcements")
    args = parser.parse_args()
    lines = []
    say(lines, "Cairn Wi-Fi probe, %s, %s" % (time.strftime("%Y-%m-%d %H:%M"), platform.platform()))
    if args.quick and not args.ip:
        raise SystemExit("--quick needs --ip")
    if not args.quick:
        bonjour(lines, max(3, min(args.seconds, 20)))
        arp(lines)
    if args.ip:
        check_ports(lines, args.ip)
        if args.range:
            sweep(lines, args.ip, *parse_range(args.range))
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nReport written to %s" % REPORT)


if __name__ == "__main__":
    sys.exit(main())
