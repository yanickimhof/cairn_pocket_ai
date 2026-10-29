"""What this computer has, to decide what is worth doing at the same time."""

import os


def ram_gb():
    """Physical memory in GB, or 0 when it cannot be read."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    except (ValueError, OSError, AttributeError):
        return 0.0
