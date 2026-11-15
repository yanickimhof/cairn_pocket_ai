"""An update touches only what changes: the Python environment is kept when the pinned lists are the same, and a model that
is already there is not downloaded again."""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = (ROOT / "install.sh").read_text()
ENV_BLOCK = INSTALL[INSTALL.index("# --- environment begin"):INSTALL.index("# --- environment end")]
LLM_BLOCK = INSTALL[INSTALL.index("# --- llm begin"):INSTALL.index("# --- llm end")]


class Sandbox:
    def __init__(self, case):
        self.tmp = tempfile.TemporaryDirectory()
        case.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home = base / "Cairn"
        self.here = base / "src"
        (self.here / "requirements").mkdir(parents=True)
        (self.home / "bin").mkdir(parents=True)
        self.set_requirements("a==1 --hash=sha256:00\n")
        self.log = base / "calls.log"
        self.uv = base / "uv"
        # a stand-in for uv: `venv` makes an environment whose python runs, `pip` is recorded (or fails when told to)
        self.uv.write_text('#!/bin/bash\necho "uv $*" >> "%s"\n'
                           'if [ "$1" = venv ]; then mkdir -p "${@: -1}/bin"; printf "#!/bin/sh\\nexit 0\\n" > "${@: -1}/bin/python"; chmod +x "${@: -1}/bin/python"; fi\n'
                           'if [ "$1" = pip ] && [[ "$*" == *diar* ]] && [ -n "$FAIL_DIAR" ]; then exit 1; fi\n'
                           'exit 0\n' % self.log)
        self.uv.chmod(0o755)
        self.ollama = base / "ollama"
        self.ollama.write_text('#!/bin/bash\necho "ollama $*" >> "%s"\nif [ "$1" = list ]; then printf "NAME ID SIZE\\n%%s abc 2.5GB\\n" "$HAVE"; fi\nexit 0\n' % self.log)
        self.ollama.chmod(0o755)

    def set_requirements(self, text):
        (self.here / "requirements" / "mlx.txt").write_text(text)
        (self.here / "requirements" / "diar-macos-arm64.txt").write_text("d==1\n")

    def run(self, block, extra="", **env):
        header = 'set -e\nsay() { printf "==> %s\\n" "$1"; }\nsha256_of() { sha256sum "$1" | awk \'{print $1}\'; }\n'
        names = 'CAIRN_HOME="%s"; HERE="%s"; REQ=mlx.txt; ENGINE=mlx; ARCH=arm64; UV="%s"; OLLAMA="%s"; LLM="qwen3:4b"\n' % (self.home, self.here, self.uv, self.ollama)
        script = header + names + block + "\n" + extra
        done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=dict(os.environ, **env), check=False)
        return done

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""


class EnvironmentTest(unittest.TestCase):
    def test_a_first_install_builds_the_environment_and_marks_it_complete(self):
        box = Sandbox(self)
        done = box.run(ENV_BLOCK, 'echo "NOTE=$ENV_NOTE"')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("uv venv", box.calls())
        self.assertIn("uv pip install", box.calls())
        self.assertIn("NOTE=rebuilt", done.stdout)
        self.assertTrue((box.home / ".venv" / ".cairn-env").is_file())

    def test_the_same_lists_keep_the_environment(self):
        box = Sandbox(self)
        box.run(ENV_BLOCK)
        box.log.write_text("")
        done = box.run(ENV_BLOCK, 'echo "NOTE=$ENV_NOTE"')
        self.assertEqual(box.calls(), "")  # uv is not called at all
        self.assertIn("kept", done.stdout)

    def test_a_changed_list_rebuilds(self):
        box = Sandbox(self)
        box.run(ENV_BLOCK)
        box.log.write_text("")
        box.set_requirements("a==2 --hash=sha256:11\n")
        done = box.run(ENV_BLOCK, 'echo "NOTE=$ENV_NOTE"')
        self.assertIn("uv venv", box.calls())
        self.assertIn("NOTE=rebuilt", done.stdout)

    def test_a_broken_environment_rebuilds(self):
        box = Sandbox(self)
        box.run(ENV_BLOCK)
        (box.home / ".venv" / "bin" / "python").write_text("#!/bin/sh\nexit 1\n")
        box.log.write_text("")
        box.run(ENV_BLOCK)
        self.assertIn("uv venv", box.calls())

    def test_fresh_forces_a_rebuild(self):
        box = Sandbox(self)
        box.run(ENV_BLOCK)
        box.log.write_text("")
        box.run(ENV_BLOCK, CAIRN_FRESH="1")
        self.assertIn("uv venv", box.calls())

    def test_an_environment_with_speaker_identification_missing_is_not_marked_complete(self):
        box = Sandbox(self)
        diar = box.home / "models" / "diar"
        diar.mkdir(parents=True)
        (diar / ".cairn-complete").write_text("")
        done = box.run(ENV_BLOCK, FAIL_DIAR="1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((box.home / ".venv" / ".cairn-env").exists())  # the next update tries again


class ModelTest(unittest.TestCase):
    def test_a_model_already_there_is_not_downloaded(self):
        box = Sandbox(self)
        done = box.run(LLM_BLOCK, 'echo "NOTE=$LLM_NOTE"', HAVE="qwen3:4b")
        self.assertNotIn("ollama pull", box.calls())
        self.assertIn("already installed", done.stdout)

    def test_a_missing_model_is_downloaded(self):
        box = Sandbox(self)
        box.run(LLM_BLOCK, HAVE="qwen3:8b")
        self.assertIn("ollama pull qwen3:4b", box.calls())

    def test_a_similar_name_is_not_taken_for_the_model(self):
        box = Sandbox(self)
        box.run(LLM_BLOCK, HAVE="qwen3:4b-instruct")
        self.assertIn("ollama pull qwen3:4b", box.calls())


class FakeModelServer:
    """A model server on this computer: reports a larger model in memory, records the unload, answers slowly or at once."""

    def __init__(self, delay):
        self.unloaded = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, payload):
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.reply({"models": [{"name": "qwen3:8b"}, {"name": "qwen3:4b"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                if body.get("keep_alive") == 0:
                    outer.unloaded.append(body.get("model"))
                    return self.reply({"response": ""})
                time.sleep(delay)
                try:
                    self.reply({"response": "OK"})
                except OSError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class SelfTestTest(unittest.TestCase):
    def run_llm_test(self, delay, timeout, ci=False):
        server = FakeModelServer(delay)
        self.addCleanup(server.close)
        env = {k: v for k, v in os.environ.items() if k != "CI"}
        env.update(OLLAMA_HOST="127.0.0.1:%d" % server.port, CAIRN_LLM="qwen3:4b", CAIRN_SELFTEST_TIMEOUT=str(timeout))
        if ci:
            env["CI"] = "1"
        code = "import sys; sys.path.insert(0, %r); import selftest; print('RESULT', selftest.test_llm())" % str(ROOT / "scripts")
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False)
        return done, server

    def test_another_model_in_memory_is_unloaded_before_the_question(self):
        done, server = self.run_llm_test(0, 20)
        self.assertIn("RESULT True", done.stdout)
        self.assertEqual(server.unloaded, ["qwen3:8b"])  # the model being tested is left alone

    def test_a_slow_answer_is_a_warning_on_a_computer(self):
        done, _ = self.run_llm_test(3, 1)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("RESULT False", done.stdout)
        self.assertIn("ollama ps", done.stdout)

    def test_a_slow_answer_fails_in_the_automatic_tests(self):
        done, _ = self.run_llm_test(3, 1, ci=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("did not answer", done.stdout)


if __name__ == "__main__":
    unittest.main()
