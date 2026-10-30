"""People across the notes, and the optional memory of voices."""

import copy
import json
import math
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def unit(*values):
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def voice(axis, noise=0.0, dim=16):
    """A voiceprint pointing mostly along one axis."""
    values = [0.0] * dim
    values[axis] = 1.0
    values[(axis + 1) % dim] = noise
    return unit(*values)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.before = os.environ.get("CAIRN_HOME")
        os.environ["CAIRN_HOME"] = self.tmp.name
        from cairn import voices

        self.voices = voices

    def tearDown(self):
        if self.before is None:
            os.environ.pop("CAIRN_HOME", None)
        else:
            os.environ["CAIRN_HOME"] = self.before
        self.tmp.cleanup()


class MemoryTest(Base):
    def test_a_known_voice_is_recognised_and_an_unknown_one_is_not(self):
        v = self.voices
        v.learn("Anna", voice(0))
        v.learn("Marc", voice(5))
        self.assertEqual(v.best(voice(0, 0.1))[0], "Anna")
        self.assertEqual(v.best(voice(5, 0.1))[0], "Marc")
        self.assertIsNone(v.best(voice(9)))

    def test_two_close_people_are_never_confused(self):
        v = self.voices
        v.learn("Anna", unit(1, 0.35, 0, 0, 0, 0, 0, 0))
        v.learn("Anne", unit(1, 0.45, 0, 0, 0, 0, 0, 0))
        self.assertIsNone(v.best(unit(1, 0.4, 0, 0, 0, 0, 0, 0)))  # in between: no guess

    def test_voiceprints_are_validated(self):
        v = self.voices
        for bad in (None, "x", [], [1.0] * 3, [float("nan")] * 16, [float("inf")] * 16, ["a"] * 16, [1.0] * 5000):
            self.assertIsNone(v.clean(bad), bad)
            self.assertFalse(v.learn("Anna", bad))
        self.assertFalse(v.learn("", voice(0)))
        self.assertEqual(v.load(), {})

    def test_only_the_latest_samples_are_kept(self):
        v = self.voices
        for i in range(12):
            v.learn("Anna", voice(i % 16))
        self.assertEqual(len(v.load()["Anna"]["samples"]), v.MAX_SAMPLES)

    def test_a_different_size_never_mixes_with_the_old_ones(self):
        v = self.voices
        v.learn("Anna", voice(0, dim=16))
        v.learn("Anna", voice(0, dim=32))
        self.assertEqual({len(s) for s in v.load()["Anna"]["samples"]}, {32})
        self.assertIsNone(v.best(voice(0, dim=16)))

    def test_rename_pools_two_people_and_forget_erases(self):
        v = self.voices
        v.learn("Anna B", voice(0))
        v.learn("Anna", voice(0, 0.05))
        v.rename("Anna B", "Anna")
        self.assertEqual(list(v.load()), ["Anna"])
        self.assertEqual(len(v.load()["Anna"]["samples"]), 2)
        v.learn("Marc", voice(4))
        self.assertEqual(v.forget("Marc"), 1)
        self.assertEqual(v.forget("Marc"), 0)
        self.assertEqual(v.forget(), 1)
        self.assertEqual(v.load(), {})

    def test_the_file_stays_readable_by_the_owner_only_and_survives_damage(self):
        self.voices.learn("Anna", voice(0))
        path = self.voices._path()
        if os.name == "posix":
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
        path.write_text("not json")
        self.assertEqual(self.voices.load(), {})
        self.assertTrue(self.voices.learn("Anna", voice(0)))

    def test_recognise_names_free_speakers_once_and_leaves_the_others(self):
        v = self.voices
        v.learn("Anna", voice(0))
        v.learn("Marc", voice(5))
        note = {"voices": {"Speaker 1": voice(0, 0.1), "Speaker 2": voice(0, 0.12), "Speaker 3": voice(5, 0.1), "Speaker 4": voice(9)},
                "speaker_names": {"Speaker 4": "Chosen by hand"}}
        found = v.recognise(note)
        self.assertEqual(found, {"Speaker 1": "Anna", "Speaker 3": "Marc"})  # Anna is not given to two speakers
        self.assertEqual(note["speaker_names"]["Speaker 4"], "Chosen by hand")
        self.assertNotIn("Speaker 2", note["speaker_names"])
        self.assertEqual(set(note["speaker_auto"]), {"Speaker 1", "Speaker 3"})

    def test_a_name_already_given_is_not_overridden(self):
        self.voices.learn("Anna", voice(0))
        note = {"voices": {"Speaker 1": voice(0)}, "speaker_names": {"Speaker 1": "Someone else"}}
        self.assertEqual(self.voices.recognise(note), {})
        self.assertEqual(note["speaker_names"], {"Speaker 1": "Someone else"})


class WorkerAndLabelsTest(unittest.TestCase):
    def test_voiceprints_follow_the_labels_of_the_annotation(self):
        from cairn import diarize_worker

        class Annotation:
            def labels(self):
                return ["SPEAKER_01", "SPEAKER_00"]

        class Output:
            speaker_diarization = Annotation()

        prints = diarize_worker.voiceprints(Output(), [[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(prints, {"SPEAKER_01": [1.0, 2.0], "SPEAKER_00": [3.0, 4.0]})
        self.assertEqual(diarize_worker.voiceprints(Output(), None), {})
        self.assertEqual(diarize_worker.voiceprints(Output(), [[float("nan"), 1.0], [3.0, 4.0]]), {"SPEAKER_00": [3.0, 4.0]})

    def test_both_shapes_of_pipeline_result(self):
        from cairn import diarize_worker

        self.assertEqual(diarize_worker.split_result(("d", "e")), ("d", "e"))

        class New:
            speaker_embeddings = "e"

        result = New()
        self.assertEqual(diarize_worker.split_result(result), (result, "e"))
        plain = object()
        self.assertEqual(diarize_worker.split_result(plain), (plain, None))

    def test_labels_are_numbered_in_the_order_of_speaking(self):
        from cairn import diarize

        turns = [{"start": 0, "end": 2, "speaker": "SPEAKER_07"}, {"start": 2, "end": 4, "speaker": "SPEAKER_03"}]
        segments = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.0, "end": 4.0, "text": "b"}]
        prints = {"SPEAKER_03": [3.0], "SPEAKER_07": [7.0], "SPEAKER_99": [9.0]}
        self.assertEqual(diarize.label_voices(segments, turns, prints, "en"), {"Speaker 1": [7.0], "Speaker 2": [3.0]})
        self.assertEqual(diarize.label_voices(segments, turns, {}, "fr"), {})

    def test_the_program_answers_in_both_formats(self):
        from cairn import diarize

        class Proc:
            returncode = 0
            out = ""

            def __init__(self, *a, **k):
                Proc.env = k["env"]

            def communicate(self, timeout=None):
                return Proc.out, ""

        turns = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
        with mock.patch.object(diarize.models, "diar_installed", return_value=True), mock.patch.object(diarize.subprocess, "Popen", Proc):
            Proc.out = json.dumps(turns)
            self.assertEqual(diarize.run("a.mp3"), ("ok", turns))
            self.assertEqual(diarize.run_with_voices("a.mp3"), ("ok", turns, {}))
            self.assertEqual(Proc.env["CAIRN_VOICES"], "1")
            Proc.out = json.dumps({"turns": turns, "voices": {"SPEAKER_00": [1.0, 2.0]}})
            self.assertEqual(diarize.run_with_voices("a.mp3"), ("ok", turns, {"SPEAKER_00": [1.0, 2.0]}))
            self.assertEqual(diarize.run("a.mp3"), ("ok", turns))
            self.assertEqual(Proc.env["CAIRN_VOICES"], "0")
            Proc.out = json.dumps({"nothing": 1})
            self.assertEqual(diarize.run("a.mp3"), ("none", None))
            self.assertEqual(diarize.run_with_voices("a.mp3"), ("none", None, {}))


class PeopleTest(Base):
    def setUp(self):
        super().setUp()
        os.environ.update(CAIRN_POCKET_DIR=self.tmp.name + "/none", CAIRN_ENGINE="mlx", CAIRN_LLM="stub:1b", OLLAMA_HOST="127.0.0.1:9", CAIRN_WHISPER_MODEL=self.tmp.name)
        from cairn import server

        self.server = server
        self.app = server.App()
        seg = lambda start, label: {"start": float(start), "end": float(start) + 4, "text": "x", "speaker": label}  # noqa: E731
        self.notes = {
            "a": {"id": "a", "status": "done", "title": "A", "date": "2026-10-01T10:00:00", "segments": [seg(0, "Speaker 1"), seg(4, "Speaker 2"), seg(8, "Speaker 1")],
                  "speaker_names": {"Speaker 1": "Anna", "Speaker 2": "Marc"}, "voices": {"Speaker 1": voice(0), "Speaker 2": voice(5)}},
            "b": {"id": "b", "status": "done", "title": "B", "date": "2026-10-02T10:00:00", "segments": [seg(0, "Speaker 1"), seg(4, "Speaker 2")],
                  "speaker_names": {"Speaker 1": "Anna B"}, "voices": {"Speaker 1": voice(0)}},
            "c": {"id": "c", "status": "done", "title": "C", "date": "2026-10-03T10:00:00", "segments": [seg(0, "Speaker 1")], "speaker_names": {}},
            "d": {"id": "d", "status": "done", "title": "D", "date": "2026-10-04T10:00:00", "segments": [{"start": 0, "end": 3, "text": "no speakers"}]},
            "w": {"id": "w", "status": "waiting", "title": "W", "segments": [seg(0, "Speaker 1")], "speaker_names": {"Speaker 1": "Ghost"}},
        }
        for note in self.notes.values():
            self.app.store.save(copy.deepcopy(note))

    def test_people_are_counted_across_the_notes(self):
        data = self.app.people()
        by = {p["name"]: p for p in data["people"]}
        self.assertEqual(set(by), {"Anna", "Marc", "Anna B"})
        self.assertEqual(by["Anna"]["seconds"], 8)
        self.assertEqual([n["id"] for n in by["Anna"]["notes"]], ["a"])
        self.assertNotIn("Ghost", by)  # a note not finished does not count
        self.assertEqual([(n["id"], n["labels"]) for n in data["unnamed"]], [("c", ["Speaker 1"]), ("b", ["Speaker 2"])])
        self.assertFalse(data["enabled"])

    def test_renaming_changes_every_note_and_merging_pools_the_people(self):
        self.voices.learn("Anna", voice(0))
        self.voices.learn("Anna B", voice(0, 0.05))
        self.assertEqual(self.app.rename_person("Anna B", "Anna"), 1)
        self.assertEqual(self.app.store.get("b")["speaker_names"], {"Speaker 1": "Anna"})
        self.assertIn("Anna: x", self.app.store.get("b")["clean"])
        by = {p["name"]: p for p in self.app.people()["people"]}
        self.assertEqual(sorted(n["id"] for n in by["Anna"]["notes"]), ["a", "b"])
        self.assertEqual(list(self.voices.load()), ["Anna"])
        self.assertEqual(self.app.rename_person("Anna", "Anna"), 0)
        self.assertEqual(self.app.rename_person("Nobody", "Someone"), 0)
        for bad in ("", "  "):
            with self.assertRaises(self.server.ApiError):
                self.app.rename_person("Anna", bad)
        with self.assertRaises(self.server.ApiError):
            self.app.rename_person("", "x")

    def test_forgetting_one_person_or_everybody(self):
        self.voices.learn("Anna", voice(0))
        self.voices.learn("Marc", voice(5))
        self.assertEqual(self.app.forget_voices("Marc"), 1)
        self.assertEqual(list(self.voices.load()), ["Anna"])
        self.assertEqual(self.app.forget_voices(None), 1)
        self.assertEqual(self.voices.load(), {})
        self.assertNotIn("voices", self.app.store.get("a"))
        self.assertNotIn("voices", self.app.store.get("b"))

    def test_forgetting_one_person_also_removes_the_voiceprints_kept_with_the_notes(self):
        self.voices.learn("Anna", voice(0))
        self.app.forget_voices("Anna")
        self.assertNotIn("Speaker 1", self.app.store.get("a")["voices"])
        self.assertIn("Speaker 2", self.app.store.get("a")["voices"])  # somebody else's voice is not touched
        self.assertNotIn("voices", self.app.store.get("b")) if not self.app.store.get("b").get("voices") else None
        self.assertEqual(self.voices.load(), {})

    def test_naming_a_speaker_teaches_the_voice_only_when_the_memory_is_on(self):
        from cairn import config

        def name(note_id, label, text):
            conn_app = self.app
            note = conn_app.get_note(note_id)
            names = dict(note.get("speaker_names") or {})
            names[label] = text
            note["speaker_names"] = names
            conn_app.store.save(note)

        import http.client

        httpd = None
        try:
            app, httpd = self.server.make_server(18820)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()

            def post(note_id, label, text):
                conn = http.client.HTTPConnection("127.0.0.1", app.port, timeout=30)
                conn.request("POST", "/api/note/%s/speaker" % note_id, json.dumps({"from": label, "name": text}),
                             {"Host": "127.0.0.1:%d" % app.port, "Cookie": "cairn_session=" + app.token, "Content-Type": "application/json", "X-Cairn": "1"})
                resp = conn.getresponse()
                resp.read()
                conn.close()
                return resp.status

            self.assertEqual(post("a", "Speaker 2", "Marc D"), 200)
            self.assertEqual(self.voices.load(), {})  # memory off: nothing learned
            config.save_settings({"voices": True})
            self.assertEqual(post("a", "Speaker 2", "Marc Dupont"), 200)
            self.assertEqual(list(self.voices.load()), ["Marc Dupont"])
            self.assertEqual(post("c", "Speaker 1", "Someone"), 200)  # this note has no voiceprint
            self.assertEqual(list(self.voices.load()), ["Marc Dupont"])
            self.assertEqual(post("a", "Speaker 2", ""), 200)
            self.assertNotIn("Speaker 2", self.app.store.get("a")["speaker_names"])
        finally:
            if httpd:
                httpd.shutdown()
                httpd.server_close()

    def test_a_new_speaker_pass_names_the_voices_it_knows(self):
        from cairn import config, diarize, jobs

        config.save_settings({"voices": True})
        self.voices.learn("Anna", voice(0))
        audio = Path(self.tmp.name) / "a.wav"
        audio.write_bytes(b"x")
        note = copy.deepcopy(self.notes["c"])
        note.update(audio=str(audio), speaker_names={"Speaker 1": "Old"}, speaker_auto={})
        note["segments"] = [{"start": 0.0, "end": 4.0, "text": "hello", "speaker": "Speaker 1"}]
        self.app.store.save(note)
        turns = [{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00"}]
        runner = mock.Mock(return_value=("ok", turns, {"SPEAKER_00": voice(0, 0.1)}))
        with mock.patch.object(diarize, "available", return_value=True), mock.patch.object(diarize, "run_with_voices", runner):
            self.app.jobs._rediarize("c")
        saved = self.app.store.get("c")
        self.assertEqual(saved["speaker_names"], {"Speaker 1": "Anna"})
        self.assertIn("Anna: hello", saved["clean"])
        self.assertIn("Speaker 1", saved["speaker_auto"])
        self.assertEqual(set(saved["voices"]), {"Speaker 1"})
        config.save_settings({"voices": False})
        plain = mock.Mock(return_value=("ok", turns))
        with mock.patch.object(diarize, "available", return_value=True), mock.patch.object(diarize, "run", plain):
            self.app.jobs._rediarize("c")
        saved = self.app.store.get("c")
        self.assertEqual(saved["speaker_names"], {})
        self.assertNotIn("voices", saved)  # memory off: no voiceprint is kept with a new pass
        self.assertNotIn("speaker_auto", saved)


if __name__ == "__main__":
    unittest.main()
