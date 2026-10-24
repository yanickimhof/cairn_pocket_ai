"""Start Cairn: the local model server, the web server and the browser.

    python -m cairn [--port 8765] [--no-browser]
"""

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import config, llm, server, speech


find_ollama = llm.find_ollama


def start_model_server():
    """Make sure the local model server answers on 127.0.0.1. Returns the process we started, if any."""
    if llm.available():
        return None
    cfg = config.install_config()
    binary = find_ollama(cfg)
    if not binary:
        print("The local model server (Ollama) was not found. Run the installer again.")
        return None
    log = open(config.home() / "ollama.log", "ab")
    env = dict(os.environ, OLLAMA_HOST=cfg["ollama_host"], DO_NOT_TRACK="1")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen([binary, "serve"], stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    for _ in range(60):
        if llm.available():
            return process
        time.sleep(1)
    print("The model server did not start. See %s" % (config.home() / "ollama.log"))
    return process


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cairn", description="Cairn: sovereign Pocket AI, on your own computer.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CAIRN_PORT", "8765")))
    parser.add_argument("--no-browser", action="store_true", default=bool(os.environ.get("CAIRN_NO_BROWSER")))
    args = parser.parse_args(argv)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    config.home().mkdir(parents=True, exist_ok=True)
    started = start_model_server() if not os.environ.get("CAIRN_NO_MODEL_SERVER") else None
    app, httpd = server.make_server(args.port)
    url = "http://127.0.0.1:%d/?k=%s" % (app.port, app.token)
    print("Cairn is running. Everything stays on this computer.")
    print("Open: %s" % url, flush=True)
    print("Close this window to quit.")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        speech.shutdown()
        if started:
            started.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
