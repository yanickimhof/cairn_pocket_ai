"""What the review of 0.5 found in the way jobs, handlers and caches work together."""

import copy
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def seg(start, text, **extra):
    return dict({"start": float(start), "end": float(start) + 3, "text": text, "logprob": -0.2}, **extra)


class AppBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.before = os.environ.get("CAIRN_HOME")
        os.environ.update(CAIRN_HOME=self.tmp.name, CAIRN_POCKET_DIR=self.tmp.name + "/none", CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b",
                          OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=self.tmp.name)
        from cairn import server

        self.server = server
        self.app = server.App()
        self.app.check_wait = 0.0
        self.note = {"id": "n", "status": "done", "title": "Old title", "date": "2026-10-01T10:00:00", "lang": "en", "level": "mid",
                     "audio": "", "segments": [seg(0, "Hello team."), seg(3, "We move the launch.")], "clean": "[00:00] Hello team.\n\n[00:03] We move the launch.",
                     "summary": {"title": "Old title", "tldr": "old"}}
        self.app.store.save(copy.deepcopy(self.note))

    def tearDown(self):
        if self.before is None:
            os.environ.pop("CAIRN_HOME", None)
        else:
            os.environ["CAIRN_HOME"] = self.before
        self.tmp.cleanup()


class LostUpdateTest(AppBase):
    """A job takes minutes; the person keeps working on the same note meanwhile."""

    def run_rewrite(self, during):
        from cairn import config, jobs, llm

        gate, started = threading.Event(), threading.Event()

        def slow(text, level, lang, progress=None, **kw):
            started.set()
            gate.wait(10)
            return {"title": "New title", "tldr": "new summary", "actions": [], "key_points": [], "decisions": []}

        errors = []

        def work():
            try:
                note = self.app.store.get("n")
                self.app.jobs._rewrite(note, "mid", "en", config.load_settings())
            except Exception as error:  # noqa: BLE001
                errors.append(error)

        with mock.patch.object(llm, "summarize", slow):
            thread = threading.Thread(target=work)
            thread.start()
            self.assertTrue(started.wait(10))
            during()
            gate.set()
            thread.join(10)
        return errors, jobs

    def test_a_correction_made_while_the_note_is_written_again_is_kept(self):
        errors, _ = self.run_rewrite(lambda: self.app.edit_segment("n", 0, "Hello everyone.", "here"))
        self.assertEqual(errors, [])
        note = self.app.store.get("n")
        self.assertEqual(note["summary"]["tldr"], "new summary")  # the job's work is there
        self.assertEqual(note["segments"][0]["text"], "Hello everyone.")  # and so is the person's
        self.assertTrue(note["segments"][0]["edit"])
        self.assertIn("Hello everyone.", note["clean"])

    def test_a_name_given_meanwhile_is_kept(self):
        self.app.store.save(dict(self.app.store.get("n"), segments=[seg(0, "Hello", speaker="Speaker 1")]))
        errors, _ = self.run_rewrite(lambda: self.app.rename_person("Nobody", "Nobody") or self._name())
        self.assertEqual(errors, [])
        self.assertEqual(self.app.store.get("n")["speaker_names"], {"Speaker 1": "Anna"})

    def _name(self):
        note = self.app.store.get("n")
        note["speaker_names"] = {"Speaker 1": "Anna"}
        self.app.store.save(note)

    def test_a_note_renamed_by_hand_keeps_its_title(self):
        self.app.store.save(dict(self.app.store.get("n"), renamed=True, title="Mine"))
        self.run_rewrite(lambda: None)
        self.assertEqual(self.app.store.get("n")["title"], "Mine")

    def test_a_note_deleted_meanwhile_stays_deleted(self):
        errors, jobs = self.run_rewrite(lambda: self.app.store.delete("n"))
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], jobs.Gone)
        self.assertFalse(self.app.store.exists("n"))

    def test_a_job_that_finds_its_note_gone_reports_nothing(self):
        from cairn import jobs

        def target():
            raise jobs.Gone("n")

        self.app.jobs._start("rerun", target)
        for _ in range(50):
            time.sleep(0.05)
            if not self.app.jobs.snapshot()["running"]:
                break
        self.assertEqual(self.app.jobs.snapshot()["errors"], [])


class JobsTest(AppBase):
    def test_the_index_gives_way_to_what_the_person_asks_for(self):
        seen = []

        def index():
            for _ in range(200):
                if self.app.jobs.cancelled:
                    seen.append("cancelled")
                    return
                time.sleep(0.02)

        self.app.jobs._start("index", index)
        self.app.jobs._start("import", lambda: seen.append("import"))  # does not raise Busy
        for _ in range(100):
            time.sleep(0.05)
            if not self.app.jobs.snapshot()["running"]:
                break
        self.assertEqual(seen, ["cancelled", "import"])

    def test_other_jobs_still_say_busy(self):
        from cairn import jobs

        release = threading.Event()
        self.app.jobs._start("import", lambda: release.wait(5))
        with self.assertRaises(jobs.Busy):
            self.app.jobs._start("privacy", lambda: None)
        release.set()

    def test_an_automatic_job_does_not_undo_stop(self):
        self.app.jobs.paused = True
        self.app.jobs._start("rerun", lambda: None)
        time.sleep(0.2)
        self.assertTrue(self.app.jobs.paused)
        self.app.jobs._start("import", lambda: None)
        self.assertFalse(self.app.jobs.paused)  # a manual import does


class WatcherTest(unittest.TestCase):
    def test_a_bad_pass_does_not_end_the_upkeep(self):
        from cairn import watch

        passes = []

        def tick(self_):
            passes.append(1)
            if len(passes) == 1:
                raise RuntimeError("boom")

        watcher = watch.Watcher(SimpleNamespace())
        with mock.patch.object(watch.Watcher, "tick", tick), mock.patch.object(watch.time, "sleep", side_effect=[None, None, None, SystemExit]):
            with self.assertRaises(SystemExit):
                watcher.loop()
        self.assertEqual(len(passes), 3)  # it went on after the failure

    def test_a_sync_that_fails_is_not_started_again_every_minute(self):
        from cairn import jobs, watch

        calls = []
        state = {"running": False, "errors": []}
        app = SimpleNamespace(
            jobs=SimpleNamespace(snapshot=lambda: state, start_sync=lambda: calls.append("sync"), paused=False, secure_wanted=False),
            pocket_state=lambda: {"new": 1}, waiting_count=lambda: 0, purge_pocket=lambda: 0, update_info=None, check_update=lambda: {})
        with mock.patch.object(watch.config, "load_settings", return_value={"autoimport": True, "autocheck": False}), \
                mock.patch.object(watch.privacy, "last_report", return_value={"when": "2999-01-01T00:00:00"}):
            watcher = watch.Watcher(app)
            watcher.tick(now=10 ** 9)
            self.assertEqual(calls, ["sync"])
            state["errors"] = ["a recording cannot be copied"]
            watcher.tick(now=10 ** 9 + 60)  # the failed run is noticed
            watcher.tick(now=10 ** 9 + 120)
            watcher.tick(now=10 ** 9 + 600)
            self.assertEqual(calls, ["sync"])  # nothing for a quarter of an hour
            state["errors"] = []
            watcher.tick(now=10 ** 9 + 1100)
            self.assertEqual(calls, ["sync", "sync"])


class HostileHeaderTest(unittest.TestCase):
    def test_whatever_a_drive_holds_it_is_not_a_crash(self):
        from cairn import vault

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / vault.HEADER_NAME
            good = {"v": 1, "id": "a" * 32, "kdf": "scrypt", "n": 1024, "r": 8, "p": 1, "salt": "AAAAAAAAAAAAAAAAAAAAAA==", "check": "AAAA"}
            for raw in ("[]", "null", '"x"', "5", "{}", json.dumps(dict(good, n=1e999)), json.dumps(dict(good, salt=5)), json.dumps(dict(good, id=None)), b"\xff\xfe".decode("latin-1")):
                path.write_text(raw, encoding="utf-8")
                self.assertIsNone(vault.read_header(folder), raw)

    def test_the_keychain_is_not_asked_again_at_every_poll(self):
        from cairn import vault

        asked = []

        class Fake:
            @staticmethod
            def get_password(*a):
                asked.append(1)
                return None

        with mock.patch.dict(sys.modules, {"keyring": Fake}):
            with vault._session_lock:
                vault._missed.pop("v-poll", None)
            for _ in range(10):
                self.assertIsNone(vault.recall("v-poll"))
        self.assertEqual(len(asked), 1)


class RuleGuardTest(unittest.TestCase):
    def test_a_correction_that_would_rewrite_other_lines_is_not_offered_as_a_rule(self):
        from cairn import vocab

        self.assertEqual(vocab.rule_from_edit("see you at ten", "see you at 10:00"), [])
        tied = vocab.rule_from_edit("je vais de la maison", "je vais Delà maison")  # common words: only with words of the same line
        self.assertEqual([(r["wrong"], bool(r["context"])) for r in tied], [("de la", True)])
        self.assertEqual(vocab.fix_text("la fin de la journée", [vocab.rule_line(tied[0])])[0], "la fin de la journée")
        self.assertEqual(vocab.rule_from_edit("it was ten then", "it was 10 then"), [])
        ok = vocab.rule_from_edit("the Harbour Studios contract is signed", "the Harbor Studios contract is signed")
        self.assertEqual([(r["wrong"], r["right"]) for r in ok], [("Harbour", "Harbor")])


class CachesTest(AppBase):
    def test_the_vector_cache_stays_bounded(self):
        from cairn import embed

        with embed._lock:
            embed._cache.clear()
        with mock.patch.object(embed, "CACHE_NOTES", 2), mock.patch.object(embed.config, "read_json", return_value={"chunks": [{"w": "t", "s": 0, "t": "x"}], "vec": embed._pack([[1.0, 0.0]]), "dim": 2}):
            for i in range(5):
                path = Path(self.tmp.name) / ("n%d.json" % i)
                path.write_text("{}")
                self.assertIsNotNone(embed._load(path))
        self.assertLessEqual(len(embed._cache), 2)
        with embed._lock:
            embed._cache.clear()

    def test_the_index_is_rebuilt_after_a_model_is_removed_or_switched(self):
        from cairn import embed

        embed.built["a-model"] = "sig"
        embed.forget("a-model")
        self.assertNotIn("a-model", embed.built)
        embed.built["a-model"] = "sig"
        self.assertNotEqual(embed.built.get("another"), "sig")  # a new model starts from nothing

    def test_the_badge_recovers_after_an_error(self):
        from cairn import vocabcheck

        real = vocabcheck.contribution
        with mock.patch.object(vocabcheck, "contribution", side_effect=ValueError("odd segment")):
            self.assertEqual(self.app.vocab_check(), [])
        self.assertFalse(self.app._check["busy"])
        self.assertEqual(vocabcheck.contribution, real)
        self.app.store.save(dict(self.app.store.get("n"), title="changed"))
        self.assertEqual(self.app.vocab_check(), [])  # computed again, no error

    def test_a_note_unchanged_is_not_read_again_for_the_names(self):
        from cairn import vocabcheck

        self.app.vocab_check()
        with mock.patch.object(vocabcheck, "contribution", side_effect=AssertionError("read again")):
            self.app._check["sig"] = None
            self.app.vocab_check()  # the contribution of the note is kept

    def test_the_settings_sent_to_the_page_never_hold_a_secret(self):
        from cairn import config

        config.save_settings({"hf_token": "hf_" + "x" * 20, "pocket_key": "A" * 16})
        shown = self.app.state(False)["settings"]
        self.assertIs(shown["hf_token"], True)
        self.assertIs(shown["pocket_key"], True)
        self.assertNotIn("xxxx", json.dumps(self.app.state(False)))
        self.assertEqual(config.load_settings()["pocket_key"], "A" * 16)  # the program itself still has them

    def test_a_name_with_two_spaces_is_found_and_new_names_are_stored_tidy(self):
        note = self.app.store.get("n")
        note["segments"][0]["speaker"] = "Speaker 1"
        note["speaker_names"] = {"Speaker 1": "Jean  Paul"}
        self.app.store.save(note)
        self.assertEqual(self.app.rename_person("Jean Paul", "Jean-Paul"), 1)
        self.assertEqual(self.app.store.get("n")["speaker_names"], {"Speaker 1": "Jean-Paul"})


if __name__ == "__main__":
    unittest.main()
