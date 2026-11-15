"""Background mode: replacing a running service must wait for the old one to stop."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cairn import service


def result(code, err=""):
    return subprocess.CompletedProcess([], code, stdout="", stderr=err)


class InstallTest(unittest.TestCase):
    def run_install(self, launchctl, loaded_states):
        """Run install() in a temporary home, with a scripted launchctl and a scripted `loaded` answer."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            states = iter(loaded_states)
            with mock.patch.object(service.config, "home", return_value=home / "Cairn"), \
                    mock.patch.object(service.Path, "home", return_value=home), \
                    mock.patch.object(service, "loaded", side_effect=lambda: next(states, False)), \
                    mock.patch.object(service, "_launchctl", side_effect=launchctl) as calls, \
                    mock.patch.object(service.time, "sleep"):
                service.install()
            return [c.args[0] for c in calls.call_args_list]

    def test_a_first_install_just_starts(self):
        calls = self.run_install(lambda *a: result(0), [False])
        self.assertEqual(calls, ["bootstrap"])

    def test_waits_for_the_old_service_to_stop_then_starts(self):
        calls = self.run_install(lambda *a: result(0), [True, True, True, False])
        self.assertEqual(calls, ["bootout", "bootstrap"])

    def test_retries_while_the_system_is_still_stopping(self):
        answers = iter([result(0), result(5, "Input/output error"), result(5, "Input/output error"), result(0)])
        calls = self.run_install(lambda *a: next(answers), [True, False])
        self.assertEqual(calls, ["bootout", "bootstrap", "bootstrap", "bootstrap"])

    def test_gives_up_with_the_system_message(self):
        def launchctl(*args):
            return result(5, "Input/output error") if args[0] == "bootstrap" else result(0)
        with self.assertRaises(RuntimeError) as caught:
            self.run_install(launchctl, [False])
        self.assertIn("Input/output error", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
