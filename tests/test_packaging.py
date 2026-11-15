"""The macOS installer app that goes in the disk image: it must open Terminal on the installer of its own release."""
import os
import plistlib
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from cairn import config

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "packaging" / "macos" / "Install Cairn.app"
SCRIPT = APP / "Contents" / "MacOS" / "install-cairn"


class BundleTest(unittest.TestCase):
    def test_the_bundle_describes_an_app_that_runs_the_script(self):
        info = plistlib.loads((APP / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(info["CFBundleExecutable"], "install-cairn")
        self.assertEqual(info["CFBundleVersion"], "__VERSION__")  # filled in by the build script
        self.assertTrue(SCRIPT.is_file() and os.access(SCRIPT, os.X_OK))

    def test_the_scripts_are_valid_shell(self):
        for path in (SCRIPT, ROOT / "scripts" / "build-dmg.sh"):
            done = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_note_explains_how_to_open_it(self):
        note = (ROOT / "packaging" / "macos" / "Read me first.txt").read_text()
        self.assertIn("Open Anyway", note)
        self.assertIn("Control-click", note)

    def test_the_build_reads_the_version_the_app_reports(self):
        build = (ROOT / "scripts" / "build-dmg.sh").read_text()
        self.assertIn('cairn/config.py', build)
        self.assertRegex(config.VERSION, r"^\d+\.\d+\.\d+$")


class LaunchTest(unittest.TestCase):
    """Run the app's script with a stand-in for `open` and a fake installer, in a temporary home."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.app = base / "Install Cairn.app"          # a name with a space, like the real one
        shutil.copytree(APP, self.app)
        resources = self.app / "Contents" / "Resources"
        resources.mkdir()
        (resources / "install.sh").write_text('#!/bin/bash\necho "fake installer ran"\n')
        self.bin = base / "bin"
        self.bin.mkdir()
        self.log = base / "open.log"
        stub = self.bin / "open"
        stub.write_text('#!/bin/bash\necho "$@" >> "%s"\n' % self.log)
        stub.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin) + os.pathsep + os.environ["PATH"], TMPDIR=str(base))

    def tearDown(self):
        self.tmp.cleanup()

    def run_app(self):
        return subprocess.run([str(self.app / "Contents" / "MacOS" / "install-cairn")], capture_output=True, text=True, env=self.env, check=False)

    def test_a_first_launch_opens_terminal_on_a_command_that_runs_the_installer(self):
        done = self.run_app()
        self.assertEqual(done.returncode, 0, done.stderr)
        opened = self.log.read_text().strip()
        self.assertTrue(opened.startswith("-a Terminal "), opened)
        command = Path(opened[len("-a Terminal "):])
        self.assertTrue(command.is_file())
        self.assertTrue(command.stat().st_mode & stat.S_IXUSR)
        ran = subprocess.run(["bash", str(command)], capture_output=True, text=True, env=self.env, check=False)
        self.assertIn("fake installer ran", ran.stdout)
        self.assertIn("You can close this window", ran.stdout)

    def test_a_failing_installer_says_so(self):
        (self.app / "Contents" / "Resources" / "install.sh").write_text("#!/bin/bash\nexit 3\n")
        self.run_app()
        command = Path(self.log.read_text().strip()[len("-a Terminal "):])
        ran = subprocess.run(["bash", str(command)], capture_output=True, text=True, env=self.env, check=False)
        self.assertIn("The installation stopped", ran.stdout)


if __name__ == "__main__":
    unittest.main()
