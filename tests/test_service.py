"""Background mode: replacing a running service must wait for the old one to stop."""
import plistlib
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


class LoginTest(unittest.TestCase):
    """Start at login can be turned off: the agent is then started only when Cairn is opened."""

    def in_home(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name)
        for patcher in (mock.patch.object(service.config, "home", return_value=home / "Cairn"),
                        mock.patch.object(service.Path, "home", return_value=home)):
            patcher.start()
            self.addCleanup(patcher.stop)
        return home

    def test_default_is_start_at_login_with_restart(self):
        plist = service.agent_plist()
        self.assertTrue(plist["RunAtLoad"])
        self.assertTrue(plist["KeepAlive"])

    def test_off_means_neither_start_nor_restart(self):
        plist = service.agent_plist(login=False)
        self.assertIs(plist["RunAtLoad"], False)
        self.assertIs(plist["KeepAlive"], False)

    def test_no_agent_yet_counts_as_on_but_is_not_available_to_change(self):
        self.in_home()
        self.assertTrue(service.login_enabled())
        self.assertFalse(service.login_state()["available"])
        self.assertFalse(service.apply_login(False))

    def test_apply_login_rewrites_only_the_two_keys_and_touches_no_service(self):
        self.in_home()
        service.agent_path().parent.mkdir(parents=True)
        with open(service.agent_path(), "wb") as handle:
            plistlib.dump(service.agent_plist(True), handle)
        with mock.patch.object(service, "_launchctl") as launchctl:
            self.assertTrue(service.apply_login(False))
        launchctl.assert_not_called()  # the running Cairn is the page that asked: it must not be stopped
        saved = plistlib.loads(service.agent_path().read_bytes())
        self.assertIs(saved["RunAtLoad"], False)
        self.assertIs(saved["KeepAlive"], False)
        self.assertEqual(saved["Label"], service.LABEL)
        self.assertEqual(saved["ProgramArguments"], service.agent_plist()["ProgramArguments"])
        self.assertFalse(service.login_enabled())
        self.assertTrue(service.apply_login(True))
        self.assertTrue(service.login_enabled())
        self.assertFalse(service.agent_path().with_name(service.agent_path().name + ".part").exists())

    def test_install_with_login_off_starts_it_now(self):
        self.in_home()
        with mock.patch.object(service, "loaded", return_value=False), \
                mock.patch.object(service, "_launchctl", return_value=result(0)) as launchctl, \
                mock.patch.object(service.time, "sleep"):
            service.install(login=False)
        self.assertEqual([c.args[0] for c in launchctl.call_args_list], ["bootstrap", "kickstart"])

    def test_a_reinstall_keeps_the_choice(self):
        self.in_home()
        with mock.patch.object(service, "loaded", return_value=False), \
                mock.patch.object(service, "_launchctl", return_value=result(0)), \
                mock.patch.object(service.time, "sleep"):
            service.install(login=False)
            service.install()
        self.assertFalse(service.login_enabled())


if __name__ == "__main__":
    unittest.main()
