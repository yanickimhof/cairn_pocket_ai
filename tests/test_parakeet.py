"""Parakeet as an optional speech model, and the test bench."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from cairn import bench, catalog, config, models, speech, speech_worker

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIBE = speech.transcribe  # other tests replace it while they run: keep the real one


class FakeSentence:
    def __init__(self, text, start, end, confidence):
        self.text, self.start, self.end, self.confidence = text, start, end, confidence


class CatalogTest(unittest.TestCase):
    def test_parakeet_is_offered_on_apple_silicon_only_and_is_never_the_default(self):
        mlx = {m["id"]: m for m in catalog.SPEECH["mlx"]}
        self.assertIn("parakeet", mlx)
        self.assertNotIn("parakeet", {m["id"] for m in catalog.SPEECH["faster"]})
        self.assertRegex(mlx["parakeet"]["revision"], r"^[0-9a-f]{40}$")  # fixed to a commit, like the others
        self.assertIn("parakeet", catalog.SPEECH_IDS)
        self.assertEqual(catalog.SPEECH["mlx"][0]["id"], "turbo")  # the first entry stays the default

    def test_its_packages_are_pinned_with_hashes_and_change_nothing_installed(self):
        text = (ROOT / "requirements" / "parakeet-macos-arm64.txt").read_text()
        base = (ROOT / "requirements" / "mlx-macos-arm64.txt").read_text()
        import re

        pins = lambda t: dict(re.findall(r"(?m)^([A-Za-z0-9_.-]+)==(\S+)", t))  # noqa: E731
        new, old = pins(text), pins(base)
        self.assertEqual(new["parakeet-mlx"], "0.5.1")
        for name, version in old.items():
            if name in new:
                self.assertEqual(new[name], version, name)  # no package already installed is moved to another version
        self.assertEqual(len(re.findall(r"(?m)^[A-Za-z0-9_.-]+==\S+ \\$", text)), len(new))


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        patch = mock.patch.dict(os.environ, {"CAIRN_HOME": str(self.home), "CAIRN_ENGINE": "mlx"})
        patch.start()
        for name in ("CAIRN_WHISPER_MODEL", "CAIRN_LLM"):  # left behind by other tests
            os.environ.pop(name, None)
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def choose(self, speech_id, complete=True):
        folder = self.home / "models" / speech_id
        folder.mkdir(parents=True)
        if complete:
            (folder / models.MARK).write_text("ok")
        config.write_json(self.home / "settings.json", {"speech": speech_id})
        return folder

    def test_the_chosen_model_decides_the_engine(self):
        self.assertEqual(config.install_config()["speech_engine"], "mlx")
        self.choose("parakeet")
        cfg = config.install_config()
        self.assertEqual(cfg["speech_engine"], "parakeet")
        self.assertTrue(cfg["whisper_model"].endswith("parakeet"))
        self.assertTrue(speech.model_key().startswith("parakeet:"))

    def test_a_model_not_fully_downloaded_changes_nothing(self):
        self.choose("parakeet", complete=False)
        self.assertEqual(config.install_config()["speech_engine"], "mlx")

    def test_the_worker_turns_sentences_into_segments(self):
        fake = types.SimpleNamespace()
        calls = {}

        class Model:
            def transcribe(self, audio, decoding_config=None, chunk_duration=None, overlap_duration=None, chunk_callback=None):
                calls.update(audio=audio, chunk=chunk_duration)
                chunk_callback(60, 120)
                return types.SimpleNamespace(sentences=[FakeSentence(" Bonjour à tous. ", 0.0, 2.0, 0.9), FakeSentence("   ", 2.0, 2.5, 0.9), FakeSentence("We start now.", 2.5, 4.0, 0.5)])

        mod = types.ModuleType("parakeet_mlx")
        mod.from_pretrained = lambda path: Model()
        mod.DecodingConfig = lambda sentence=None: ("config", sentence)
        mod.SentenceConfig = lambda **kw: kw
        seen = []
        with mock.patch.dict(sys.modules, {"parakeet_mlx": mod}):
            speech_worker._MODELS.clear()
            result = speech_worker._parakeet("/models/parakeet", "a.wav", seen.append)
        self.assertEqual([s["text"] for s in result["segments"]], ["Bonjour à tous.", "We start now."])  # the empty sentence is dropped
        self.assertIsNone(result["language"])
        self.assertAlmostEqual(result["segments"][1]["logprob"], -0.693, places=2)
        self.assertEqual(calls["chunk"], 120.0)
        self.assertEqual(seen[0], 0.5)
        self.assertEqual(seen[-1], 1.0)

    def test_the_language_is_read_from_the_words_when_the_engine_does_not_say(self):
        out = {"language": None, "segments": [{"start": 0, "end": 40, "text": "Nous avons une réunion pour la semaine et le budget est dans le plan", "logprob": -0.1}]}
        with mock.patch.object(speech, "_run", return_value=out), mock.patch.object(speech, "_worker"), mock.patch.dict(os.environ, {}):
            (self.home / "models" / "x").mkdir(parents=True)
            data = TRANSCRIBE("a.wav", engine="parakeet", model_dir=str(self.home / "models" / "x"))
        self.assertEqual(data["language"], "fr")


class BenchTest(unittest.TestCase):
    def test_difference_counts_the_words_that_disagree(self):
        self.assertEqual(bench.difference("a b c d", "a b c d"), 0)
        self.assertAlmostEqual(bench.difference("the cat sat down", "the dog sat down"), 0.25)
        self.assertAlmostEqual(bench.difference("a b c d", "a b"), 0.5)
        self.assertIsNone(bench.difference("", "anything"))
        self.assertEqual(bench.difference("Le chat, dort.", "le chat dort"), 0)  # case and punctuation do not count

    def test_the_report_holds_numbers_and_no_words_of_the_recording(self):
        rows = [
            {"file": "a.m4a", "label": "Whisper large-v3-turbo", "seconds": 60.0, "audio": 600.0, "speed": 10.0, "memory_mb": 2100, "quality": 88, "words": 1500,
             "languages": {"fr": 0.7, "en": 0.3}, "mixed": True, "text": "SECRET sentence about Brandt", "reference": 0.05},
            {"file": "a.m4a", "label": "Parakeet v3 (fast)", "seconds": 6.0, "audio": 600.0, "speed": 100.0, "memory_mb": 1500, "quality": 91, "words": 1400,
             "languages": {"fr": 0.4, "en": 0.6}, "mixed": True, "text": "SECRET sentence about Brandt maybe", "reference": None},
        ]
        text = bench.report(rows)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("Brandt", text)
        self.assertIn("| Parakeet v3 (fast) | 6.0 | 100.0 | 1500 | 91% | 1400 | 40% / 60% | - |", text)
        self.assertIn("Whisper large-v3-turbo and Parakeet v3 (fast):", text)

    def test_it_refuses_sealed_recordings_and_needs_a_model(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CAIRN_HOME": tmp}):
            (Path(tmp) / "lock.json").write_text("{}")
            with self.assertRaises(SystemExit):
                bench.recordings(3)
            (Path(tmp) / "lock.json").unlink()
            with self.assertRaises(SystemExit):
                bench.run([], 3)  # nothing to measure


if __name__ == "__main__":
    unittest.main()
