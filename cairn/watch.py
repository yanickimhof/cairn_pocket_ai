"""Quiet background upkeep: new recordings are copied from the Pocket as soon as it is connected (unless turned off),
recordings are processed by themselves only if the person turned that on, plus a daily privacy check and, unless turned off, a daily look for a new version."""

import threading
import time
from datetime import datetime

from . import battery, config, jobs, privacy

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
        self.sync_at = 0.0
        self.queue_at = 0.0

    def tick(self, now=None):
        """One pass. Does nothing while a job is running, so it never competes with the user's work."""
        now = time.time() if now is None else now
        app = self.app
        settings = config.load_settings()
        gauge = getattr(app, "gauge", None)
        if gauge is not None and battery.available():
            gauge.poll(now)  # a Bluetooth reading in the background: it never waits for, nor delays, a job
        status = getattr(app, "status", None)
        if status is not None and battery.available() and settings.get("pocket_key"):
            status.poll(settings["pocket_key"], now)
        if app.jobs.snapshot()["running"]:
            return
        try:
            app.purge_pocket()
        except OSError:
            pass
        if settings.get("autoimport", True) and now - self.sync_at >= 120:
            if app.pocket_state().get("new"):
                self.sync_at = now  # at most one attempt every two minutes, so a failing copy never loops
                app.jobs.paused = False  # new recordings are new work
                try:
                    app.jobs.start_sync()
                except jobs.Busy:
                    pass
                return
        if settings.get("autoprocess", False) and not app.jobs.paused and now - self.queue_at >= 60 and app.waiting_count():
            self.queue_at = now
            try:
                app.jobs.start_queue()
            except jobs.Busy:
                pass
            return
        if settings.get("autocheck", True) and now - self.update_at >= DAY:
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
        time.sleep(10)
        while True:
            self.tick()
            time.sleep(20)


def start(app):
    threading.Thread(target=Watcher(app).loop, daemon=True).start()
