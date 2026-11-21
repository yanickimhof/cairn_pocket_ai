"""Privacy mode: the audio is erased from this computer once the note is finished; the Pocket is left alone."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cairn import config, jobs


class PrivacyModeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio_dir = self.root / "Audio"
        day = self.audio_dir / "2026-11-17"
        day.mkdir(parents=True)
        self.audio = day / "rec.opus"
        self.audio.write_bytes(b"x" * 3000)
        self.store = mock.Mock()
        self.runner = jobs.Jobs.__new__(jobs.Jobs)
        self.runner.store = self.store
        patcher = mock.patch.object(jobs.config, "load_settings", return_value={"audio_dir": str(self.audio_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_keeps_the_audio_setting_on(self):
        self.assertTrue(config.DEFAULT_SETTINGS["audio_keep"])

    def test_setting_accepts_only_a_boolean(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(config, "home", return_value=Path(tmp)):
            self.assertFalse(config.save_settings({"audio_keep": False})["audio_keep"])
            with self.assertRaises(ValueError):
                config.save_settings({"audio_keep": "no"})

    def test_audio_is_shredded_removed_and_flagged(self):
        note = {"id": "n1", "audio": str(self.audio)}
        with mock.patch.object(jobs.pocket, "shred") as shred:
            self.runner._drop_audio(note)
        shred.assert_called_once_with(self.audio, 3000)
        self.assertFalse(self.audio.exists())
        self.assertFalse(self.audio.parent.exists())  # the empty dated folder goes too
        self.assertTrue(note["audio_removed"])
        self.store.save.assert_called_once_with(note)

    def test_a_folder_that_still_holds_something_stays(self):
        (self.audio.parent / "other.opus").write_bytes(b"y")
        self.runner._drop_audio({"id": "n1", "audio": str(self.audio)})
        self.assertTrue((self.audio.parent / "other.opus").exists())

    def test_missing_audio_is_not_an_error(self):
        note = {"id": "n2", "audio": str(self.audio.with_name("gone.opus"))}
        self.runner._drop_audio(note)
        self.assertTrue(note["audio_removed"])


if __name__ == "__main__":
    unittest.main()
