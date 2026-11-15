"""Model profiles: the table in install.sh and the one in the catalog must say the same thing,
and the installer must choose the way it promises (asked only in a terminal, never in a script)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from cairn import catalog, setup

ROOT = Path(__file__).resolve().parent.parent
INSTALL = (ROOT / "install.sh").read_text()
GB = catalog.GB


def shell(code, **env):
    """Run shell code with the profile functions of install.sh loaded (and nothing else from it)."""
    start = INSTALL.index("# --- profiles begin")
    end = INSTALL.index("# --- profiles end")
    script = INSTALL[start:end] + "\n" + code
    done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=dict(os.environ, **env), check=False)
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return done.stdout.strip()


class CatalogMatchesInstallerTest(unittest.TestCase):
    def test_profiles_have_the_same_models_and_memory(self):
        for entry in catalog.PROFILES:
            with self.subTest(profile=entry["id"]):
                self.assertEqual(shell('profile_llm "%s"' % entry["id"]), entry["llm"])
                self.assertEqual(shell('profile_speech "%s"' % entry["id"]), entry["speech"])
                self.assertEqual(int(shell('profile_ram "%s"' % entry["id"])), entry["ram"])

    def test_sizes_are_the_catalog_sizes(self):
        for model in catalog.LLM:
            self.assertEqual(int(shell('llm_tenths "%s"' % model["id"])), round(model["bytes"] / (GB / 10)), model["id"])
        for engine, models in catalog.SPEECH.items():
            for model in models:
                if model["id"] in ("turbo", "large"):
                    self.assertEqual(int(shell('speech_tenths "%s"' % model["id"])), round(model["bytes"] / (GB / 10)), model["id"])

    def test_speech_repositories_and_revisions_are_the_catalog_ones(self):
        for engine, models in catalog.SPEECH.items():
            for model in models:
                if model["id"] not in ("turbo", "large"):
                    continue
                with self.subTest(engine=engine, model=model["id"]):
                    self.assertEqual(shell('ENGINE=%s; speech_repo "%s"' % (engine, model["id"])), model["repo"])
                    self.assertEqual(shell('known_rev "%s"' % model["repo"]), model["revision"])

    def test_every_profile_model_is_in_the_catalog(self):
        llm_ids = {m["id"] for m in catalog.LLM}
        for entry in catalog.PROFILES:
            self.assertIn(entry["llm"], llm_ids)
            for engine in ("mlx", "faster"):
                self.assertIn(entry["speech"], {m["id"] for m in catalog.SPEECH[engine]})

    def test_the_default_install_is_the_light_profile(self):
        self.assertIn('LLM="${CAIRN_LLM:-qwen3:4b}"', INSTALL)
        self.assertEqual(catalog.PROFILES[0]["llm"], "qwen3:4b")
        self.assertEqual(catalog.PROFILES[0]["speech"], "turbo")


class AdvisedProfileTest(unittest.TestCase):
    def test_by_memory(self):
        self.assertEqual(catalog.advised_profile(8)["id"], "light")
        self.assertEqual(catalog.advised_profile(16)["id"], "standard")
        self.assertEqual(catalog.advised_profile(15.9)["id"], "standard")
        self.assertEqual(catalog.advised_profile(32)["id"], "high")
        self.assertEqual(catalog.advised_profile(4)["id"], "light")

    def test_disk_steps_down(self):
        self.assertEqual(catalog.advised_profile(64, free_gb=10)["id"], "light")
        self.assertEqual(catalog.advised_profile(64, free_gb=13)["id"], "standard")
        self.assertEqual(catalog.advised_profile(64, free_gb=40)["id"], "high")

    def test_current_profile(self):
        self.assertEqual(catalog.current_profile("qwen3:8b", "turbo"), "standard")
        self.assertIsNone(catalog.current_profile("qwen3:4b", "large"))


class FirstStepsTest(unittest.TestCase):
    def check(self, ram):
        with mock.patch.object(setup.llm, "available", return_value=False), mock.patch.object(setup.system, "ram_gb", return_value=ram), \
                mock.patch.object(setup, "_free_gb", return_value=50), mock.patch.object(setup.pocket, "find_pocket", return_value=None), \
                mock.patch.object(setup.pocket, "volumes_without_record", return_value=False):
            return {c["id"]: c for c in setup.check()["checks"]}

    def test_the_advised_profile_is_shown_and_never_blocks(self):
        checks = self.check(16)
        self.assertEqual(checks["profile"]["advised"], "standard")
        self.assertEqual(checks["profile"]["status"], "ok")
        self.assertTrue(checks["profile"]["advisory"])


HEAD = INSTALL[:INSTALL.index('mkdir -p "$CAIRN_HOME"')]


def run_installer_head(arch="arm64", mem_gb=16, free_kb=90_000_000, answers=None, previous=None, **env):
    """Run the detection and the choice of install.sh on a pretend Mac and report what it picked."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "Cairn"
        if previous:
            home.mkdir()
            (home / "config.json").write_text(previous)
        keys = Path(tmp) / "keys"
        keys.write_text("".join(a + "\n" for a in (answers or [])))
        fake = (
            'uname() { if [ "$1" = "-s" ]; then echo Darwin; else echo %s; fi; }\n'
            "sysctl() { echo $((%d * 1073741824)); }\n"
            "df() { printf 'Filesystem 1024-blocks Used Available Capacity\\n/dev/x 1 1 %d 1%%\\n'; }\n" % (arch, mem_gb, free_kb)
        )
        code = fake + 'export CAIRN_HOME="%s"\n' % home + HEAD + '\necho "RESULT $PROFILE $LLM $WHISPER_REPO $LLM_LOCKED"\n'
        base = {k: v for k, v in os.environ.items() if k not in ("CI", "CAIRN_YES", "CAIRN_LLM", "CAIRN_WHISPER_REPO", "CAIRN_PROFILE")}
        base["CAIRN_TTY"] = str(keys)
        base.update(env)
        done = subprocess.run(["bash", "-c", code], capture_output=True, text=True, env=base, check=False)
        lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
        if not lines:
            raise AssertionError(done.stdout + done.stderr)
        return lines[-1].split()[1:], done.stderr


class InstallerChoiceTest(unittest.TestCase):
    def test_a_script_gets_the_light_models_as_before(self):
        (profile, llm, repo, locked), _ = run_installer_head(CI="1")
        self.assertEqual((profile, llm, locked), ("light", "qwen3:4b", "0"))
        self.assertEqual(repo, "mlx-community/whisper-large-v3-turbo")

    def test_models_named_in_the_environment_are_used_without_a_question(self):
        (profile, llm, repo, _), _ = run_installer_head(answers=["3"], CAIRN_LLM="qwen3:0.6b", CAIRN_WHISPER_REPO="mlx-community/whisper-tiny", CAIRN_ALLOW_TEST_MODELS="1")
        self.assertEqual((profile, llm, repo), ("custom", "qwen3:0.6b", "mlx-community/whisper-tiny"))

    def test_profile_from_the_environment(self):
        (profile, llm, repo, locked), _ = run_installer_head(CI="1", CAIRN_PROFILE="high", mem_gb=32)
        self.assertEqual((profile, llm, repo, locked), ("high", "qwen3:14b", "mlx-community/whisper-large-v3-mlx", "1"))

    def test_enter_takes_the_advised_profile(self):
        (profile, llm, _repo, _), shown = run_installer_head(mem_gb=16, answers=[""])
        self.assertEqual((profile, llm), ("standard", "qwen3:8b"))
        self.assertIn("advised for this computer", shown)

    def test_a_choice_by_number(self):
        (profile, llm, _repo, _), _ = run_installer_head(mem_gb=16, answers=["3"])
        self.assertEqual((profile, llm), ("high", "qwen3:14b"))

    def test_a_profile_that_does_not_fit_the_disk_is_refused(self):
        (profile, llm, _repo, _), shown = run_installer_head(mem_gb=64, free_kb=11_000_000, answers=["3", "2", "1"])
        self.assertEqual((profile, llm), ("light", "qwen3:4b"))
        self.assertIn("not enough free disk space", shown)

    def test_intel_gets_the_faster_whisper_models(self):
        (_profile, _llm, repo, _), _ = run_installer_head(arch="x86_64", mem_gb=8, answers=[""])
        self.assertEqual(repo, "deepdml/faster-whisper-large-v3-turbo-ct2")

    def test_an_update_keeps_what_is_installed(self):
        previous = '{\n  "llm": "qwen3:8b",\n  "whisper_repo": "mlx-community/whisper-large-v3-mlx"\n}'
        (profile, llm, repo, locked), _ = run_installer_head(mem_gb=16, previous=previous, answers=[""])
        self.assertEqual((profile, llm, repo, locked), ("keep", "qwen3:8b", "mlx-community/whisper-large-v3-mlx", "1"))
        (profile, llm, _repo, _), _ = run_installer_head(CI="1", mem_gb=16, previous=previous)
        self.assertEqual((profile, llm), ("keep", "qwen3:8b"))

    def test_an_update_can_still_change(self):
        previous = '{"llm": "qwen3:4b", "whisper_repo": "mlx-community/whisper-large-v3-turbo"}'
        (profile, llm, _repo, _), _ = run_installer_head(mem_gb=16, previous=previous, answers=["2"])
        self.assertEqual((profile, llm), ("standard", "qwen3:8b"))

    def test_a_wrong_answer_asks_again(self):
        (profile, _llm, _repo, _), shown = run_installer_head(mem_gb=16, answers=["x", "1"])
        self.assertEqual(profile, "light")
        self.assertIn("try again", shown)


if __name__ == "__main__":
    unittest.main()
