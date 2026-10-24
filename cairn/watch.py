"""Quiet background upkeep: a daily privacy check and, unless turned off, a daily look for a new version."""

import threading
import time
from datetime import datetime

from . import config, jobs, privacy

DAY = 24 * 3600


def _age(report):
    """Seconds since the last privacy check (a very large number when there is none)."""
    try:
        return time.time() - datetime.fromisoformat(report["when"]).timestamp()
    except (TypeError, KeyError, ValueError):
        return 10 * DAY


class Watcher:
    def __init__(self, app):
        self.app = app
        self.update_at = 0.0
        self.privacy_at = 0.0

    def tick(self, now=None):
        """One pass. Does nothing while a job is running, so it never competes with the user's work."""
        now = time.time() if now is None else now
        app = self.app
        if app.jobs.snapshot()["running"]:
            return
        if config.load_settings().get("autocheck", True) and now - self.update_at >= DAY:
            self.update_at = now
            try:
                app.update_info = app.check_update()
            except Exception:  # offline or GitHub unreachable: stay quiet, try again tomorrow
                pass
        if _age(privacy.last_report()) >= DAY and now - self.privacy_at >= 600:
            self.privacy_at = now
            try:
                app.jobs.start_privacy()
            except jobs.Busy:
                pass

    def loop(self):
        time.sleep(90)
        while True:
            self.tick()
            time.sleep(60)


def start(app):
    threading.Thread(target=Watcher(app).loop, daemon=True).start()
