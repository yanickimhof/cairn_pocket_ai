"""Reads optional Pocket status (firmware, device state, storage) over Bluetooth. Run by Cairn as a small
separate program, only when the person has entered their own session key in the settings.

Read only: sends the session key once (as documented by the pocket-libre project, not reverse-engineered here)
followed by exactly three read commands (firmware, state, storage). No clock is set, no WiFi command is sent,
and nothing else is written to the Pocket. The key is read from stdin, never from a command-line argument, so
it never appears in a process list; it is not stored or logged by this script.

Exit codes: 0 success (JSON on stdout, possibly empty if nothing was read), 2 the key was not accepted,
3 the optional Bluetooth component (bleak) is not installed, 4 no usable key was given.
"""

import asyncio
import json
import sys

CMD = "e49a3002-f69a-11e8-8eb2-f2801f1b9fd1"
RSP = "e49a3003-f69a-11e8-8eb2-f2801f1b9fd1"
NAME_PREFIX = "PKT01"
QUERIES = ("APP&FW", "APP&STE", "APP&SPACE")


def _parse(line, result):
    parts = line.strip().split("&")
    if len(parts) >= 3 and parts[0] == "MCU":
        if parts[1] == "FW":
            result["firmware"] = parts[2]
        elif parts[1] == "STE" and parts[2].lstrip("-").isdigit():
            result["state"] = int(parts[2])
        elif parts[1] == "SPA" and len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
            result["used_kb"], result["total_kb"] = int(parts[2]), int(parts[3])


async def _read(key):
    from bleak import BleakClient, BleakScanner

    device = await BleakScanner.find_device_by_filter(lambda d, a: (d.name or "").startswith(NAME_PREFIX), timeout=10)
    if device is None:
        return None

    lines = []

    def on_response(_, data):
        lines.append(bytes(data).decode(errors="replace"))

    async with BleakClient(device, timeout=15) as client:
        await client.start_notify(RSP, on_response)
        await client.write_gatt_char(CMD, ("APP&SK&" + key).encode(), response=True)
        await asyncio.sleep(1.2)
        if not any(line.strip() == "MCU&SK&OK" for line in lines):
            await client.stop_notify(RSP)
            return {}  # key not accepted: nothing more to ask, and nothing more is sent
        result = {}
        for query in QUERIES:
            before = len(lines)
            await client.write_gatt_char(CMD, query.encode(), response=True)
            await asyncio.sleep(1.5)
            for line in lines[before:]:
                _parse(line, result)
        await client.stop_notify(RSP)
    return result


def main():
    try:
        import bleak  # noqa: F401
    except ImportError:
        return 3
    key = sys.stdin.readline().strip()
    if len(key) != 16:
        return 4
    try:
        result = asyncio.run(_read(key))
    except Exception as error:  # Bluetooth off, not allowed, Pocket busy or out of range
        print("%s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return 1
    if result is None:
        print("Pocket not found", file=sys.stderr)
        return 1
    if not result:
        print("Session key not accepted", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
