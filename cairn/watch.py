"""Quiet background upkeep: new recordings are copied from the Pocket as soon as it is connected (unless turned off),
recordings are processed by themselves only if the person turned that on, plus a daily privacy check and, unless turned off, a daily look for a new version."""

import threading
import time
import traceback
from datetime import datetime

from . import battery, config, embed, jobs, lock, menubar, privacy

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
        self.index_at = 0.0
        self.sync_hold = 0.0   # after a sync that ended in errors, the next one waits
        self.synced = False

    def tick(self, now=None):
        """One pass. Does nothing while a job is running, so it never competes with the user's work."""
        now = time.time() if now is None else now
        app = self.app
        menubar.ensure(bool(config.load_settings().get("menubar", True)))  # the menu bar item follows the setting, also while locked
        if lock.locked():
            return  # nothing can be read while Cairn is locked: the upkeep waits
        if lock.due() and not app.jobs.snapshot()["running"]:
            lock.lock_now()
            return
        settings = config.load_settings()
        gauge = getattr(app, "gauge", None)
        if gauge is not None and battery.available():
            gauge.poll(now)  # a Bluetooth reading in the background: it never waits for, nor delays, a job
        status = getattr(app, "status", None)
        if status is not None and battery.available() and settings.get("pocket_key"):
            status.poll(settings["pocket_key"], now)
        if app.jobs.snapshot()["running"]:
            return
        info = lock.info()
        if info.get("enabled") and not info.get("sealed") and not info.get("locked") and not info.get("migrating"):
            try:
                app.jobs.start_seal()  # an interrupted pass is taken up again
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            app.purge_pocket()
        except OSError:
            pass
        if self.synced:
            self.synced = False
            if app.jobs.snapshot().get("errors"):
                self.sync_hold = now + 900  # a recording that cannot be copied or sealed is not tried every minute
        if now - self.sync_at >= 45 and now >= self.sync_hold:
            pocket = app.pocket_state()
            vault_state = (pocket.get("vault") or {}).get("state")
            pending = getattr(app.jobs, "secure_wanted", False) and vault_state == "partial"
            tidy = settings.get("pocket_secure_auto", False) and vault_state == "partial"  # recordings left plain by an earlier interruption
            if (settings.get("autoimport", True) and pocket.get("new")) or pending or tidy:
                self.sync_at = now  # at most one attempt every two minutes, so a failing copy never loops
                app.jobs.paused = False  # new recordings are new work
                try:
                    app.jobs.start_sync()
                    self.synced = True
                except jobs.Busy:
                    pass
                return
        if settings.get("autoprocess", False) and not app.jobs.paused and now - self.queue_at >= 15 and now >= getattr(app.jobs, 'llm_blocked_until', 0.0) and app.waiting_count():
            self.queue_at = now
            try:
                app.jobs.start_queue()
            except jobs.Busy:
                pass
            return
        if now - self.index_at >= 60 and settings.get("embed") and not app.jobs.paused:
            self.index_at = now  # a failing index (model server stopped) is tried again a minute later, never in a loop
            try:
                model = embed.chosen()
                if model and embed.built.get(model) != app.store.signature():
                    app.jobs.start_index(model)
                    return
            except (jobs.Busy, AttributeError):
                pass
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
            try:
                self.tick()
            except Exception:  # one bad pass must not end the upkeep for good
                traceback.print_exc()
            time.sleep(10)


def start(app):
    threading.Thread(target=Watcher(app).loop, daemon=True).start()
