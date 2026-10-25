"""Reads the battery level of the Pocket over Bluetooth and prints it. Run by Cairn as a small separate program.

Read only: it looks for a device named PKT01 and reads the standard Bluetooth "Battery Level" value (service 180F,
characteristic 2A19), which the Pocket publishes to any nearby reader. It sends no command, pairs with nothing and
changes nothing on the Pocket. Exit code 3 means the optional Bluetooth component (bleak) is not installed.
"""

import asyncio
import sys

BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
NAME_PREFIX = "PKT01"


async def level():
    from bleak import BleakClient, BleakScanner

    device = await BleakScanner.find_device_by_filter(lambda d, a: (d.name or "").startswith(NAME_PREFIX), timeout=10)
    if device is None:
        return None
    async with BleakClient(device, timeout=15) as client:
        value = await client.read_gatt_char(BATTERY_LEVEL)
    return value[0] if value and 0 <= value[0] <= 100 else None


def main():
    try:
        import bleak  # noqa: F401
    except ImportError:
        return 3
    try:
        found = asyncio.run(level())
    except Exception as error:  # Bluetooth off, not allowed, Pocket busy or out of range: nothing to show
        print("%s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return 1
    if found is None:
        print("Pocket not found", file=sys.stderr)
    else:
        print(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
