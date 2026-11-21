#!/usr/bin/env python3
"""Read-only Bluetooth inspection of a Pocket (PKT01): lists its GATT services and characteristics.

Sends nothing: no session key, no command. It only connects, reads the service table, and disconnects.
Needed once, to confirm which characteristics carry commands, replies and audio on this firmware before
Cairn gets a Bluetooth import. Writes a report to ~/cairn-ble-explore.txt (no secret in it).

Run with the Python that runs Cairn, from the Cairn folder:  python3 scripts/ble_explore.py
Close the vendor app first: the Pocket accepts one Bluetooth session at a time.
"""
import asyncio
import sys
import time
from pathlib import Path

NAME_PREFIX = "PKT01"
REPORT = Path.home() / "cairn-ble-explore.txt"


async def run(out):
    from bleak import BleakClient, BleakScanner

    out("Scanning 15 s for a device named %s*" % NAME_PREFIX)
    seen = await BleakScanner.discover(timeout=15, return_adv=True)
    names = sorted({(d.name or "(no name)") for d, _ in seen.values()})
    out("%d Bluetooth device(s) in range; names: %s" % (len(names), ", ".join(names[:30]) or "none"))
    for dev, adv in seen.values():  # unnamed devices: the Pocket may announce its name only on request
        if not dev.name:
            out("unnamed device: rssi=%s local_name=%s services=%s manufacturer_ids=%s" % (
                adv.rssi, adv.local_name, ",".join(adv.service_uuids) or "-", ",".join(str(k) for k in adv.manufacturer_data) or "-"))
    device = next((d for d, a in seen.values() if (d.name or a.local_name or "").startswith(NAME_PREFIX)), None)
    if device is None:
        out("Pocket not found. Turn Bluetooth off on the iPhone, press the Pocket side button once, and run again.")
        out("If the list above is empty, macOS may have refused Bluetooth to Terminal (System Settings > Privacy & Security > Bluetooth).")
        return 1
    out("Found %s" % (device.name or "?"))
    async with BleakClient(device, timeout=20) as client:
        await asyncio.sleep(0.5)
        for service in client.services:
            out("service %s" % service.uuid)
            for char in service.characteristics:
                out("  char %s  handle=%s  props=%s" % (char.uuid, char.handle, ",".join(char.properties)))
    out("Done. Nothing was written to the Pocket.")
    return 0


def main():
    try:
        import bleak  # noqa: F401
    except ImportError:
        print("The Bluetooth component (bleak) is not installed in this Python. Use the Python that runs Cairn.")
        return 3
    lines = []

    def out(text):
        print(text)
        lines.append(text)

    try:
        code = asyncio.run(run(out))
    except Exception as error:  # Bluetooth off, permission refused, Pocket busy
        out("%s: %s" % (type(error).__name__, str(error)[:200]))
        code = 1
    REPORT.write_text("cairn ble explore %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), "\n".join(lines)), encoding="utf-8")
    print("Report: %s" % REPORT)
    return code


if __name__ == "__main__":
    sys.exit(main())
