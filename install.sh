#!/usr/bin/env bash
# Cairn installer for bash and zsh.
# Detects the system, then installs everything in your own folder: no sudo, no system change.
#
#   curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.sh | bash
#
# Optional variables: CAIRN_HOME (default ~/Cairn), CAIRN_LLM (default qwen3:8b),
# CAIRN_WHISPER_REPO (speech model), CAIRN_REF (branch or tag to install).
set -euo pipefail
umask 077

REPO="yanickimhof/cairn_pocket_ai"
REF="${CAIRN_REF:-main}"
CAIRN_HOME="${CAIRN_HOME:-$HOME/Cairn}"
LLM="${CAIRN_LLM:-qwen3:8b}"
OLLAMA_ADDR="127.0.0.1:11434"
SERVER_PID=""

say() { printf '\n==> %s\n' "$1"; }
die() { printf '\nError: %s\n' "$1" >&2; exit 1; }
cleanup() { if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; fi; }
trap cleanup EXIT

# 1. Detect the system and pick the speech engine
OS="$(uname -s)"
ARCH="$(uname -m)"
[ "$OS" = "Darwin" ] || die "This installer is for macOS. On Windows, use the PowerShell command from docs/INSTALL.md."
if [ "$ARCH" = "arm64" ]; then
  ENGINE="mlx"
  REQ="mlx-macos-arm64.txt"
  DEFAULT_WHISPER="mlx-community/whisper-large-v3-turbo"
else
  ENGINE="faster"
  REQ="faster-macos-x86_64.txt"
  DEFAULT_WHISPER="deepdml/faster-whisper-large-v3-turbo-ct2"
fi
WHISPER_REPO="${CAIRN_WHISPER_REPO:-$DEFAULT_WHISPER}"
say "System detected: $OS $ARCH, speech engine: $ENGINE"

mkdir -p "$CAIRN_HOME"/{Audio,Texts,Exports,models,bin}
chmod 700 "$CAIRN_HOME"

# 2. Get the project files (already present if you cloned the repository)
HERE=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -z "$HERE" ] || [ ! -d "$HERE/requirements" ]; then
  say "Downloading Cairn ($REF)"
  HERE="$CAIRN_HOME/src"
  rm -rf "$HERE"
  mkdir -p "$HERE"
  curl --proto '=https' --tlsv1.2 -fsSL "https://codeload.github.com/$REPO/tar.gz/$REF" | tar -xz -C "$HERE" --strip-components=1
fi
[ -f "$HERE/requirements/$REQ" ] || die "Missing requirements/$REQ in the downloaded files."
[ -d "$HERE/cairn" ] || die "Missing the cairn application folder in the downloaded files."

# 3. Python tooling, kept inside the Cairn folder
export UV_PYTHON_INSTALL_DIR="$CAIRN_HOME/python"
export UV_CACHE_DIR="$CAIRN_HOME/.cache/uv"
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  say "Installing uv (Python manager) in $CAIRN_HOME/bin"
  curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$CAIRN_HOME/bin" sh
  UV="$CAIRN_HOME/bin/uv"
fi
[ -x "$UV" ] || die "uv could not be installed."

say "Creating the isolated Python environment"
"$UV" venv --python 3.11 "$CAIRN_HOME/.venv"
PY="$CAIRN_HOME/.venv/bin/python"
say "Installing the speech engine (versions and hashes pinned)"
"$UV" pip install --python "$PY" --require-hashes -r "$HERE/requirements/$REQ"
if [ "$ENGINE" = "mlx" ]; then
  # The speech engine reads audio through ffmpeg: use the build shipped in a pinned package.
  FFMPEG="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
  ln -sf "$FFMPEG" "$CAIRN_HOME/bin/ffmpeg"
  export PATH="$CAIRN_HOME/bin:$PATH"
fi

# 4. Local model server (Ollama)
find_ollama() {
  if command -v ollama >/dev/null 2>&1; then command -v ollama; return; fi
  for p in "$CAIRN_HOME/bin/Ollama.app/Contents/Resources/ollama" "/Applications/Ollama.app/Contents/Resources/ollama"; do
    if [ -x "$p" ]; then echo "$p"; return; fi
  done
}
OLLAMA="$(find_ollama || true)"
if [ -z "$OLLAMA" ]; then
  say "Downloading Ollama (official build)"
  TMP="$(mktemp -d)"
  curl --proto '=https' --tlsv1.2 -fsSL -o "$TMP/ollama.zip" "https://ollama.com/download/Ollama-darwin.zip"
  unzip -q "$TMP/ollama.zip" -d "$CAIRN_HOME/bin"
  rm -rf "$TMP"
  codesign --verify --deep --strict "$CAIRN_HOME/bin/Ollama.app" || die "The Ollama signature is invalid, installation stopped."
  OLLAMA="$CAIRN_HOME/bin/Ollama.app/Contents/Resources/ollama"
fi
[ -x "$OLLAMA" ] || die "Ollama could not be set up."

export OLLAMA_HOST="$OLLAMA_ADDR"
if ! curl -fs "http://$OLLAMA_ADDR/api/version" >/dev/null 2>&1; then
  say "Starting the local model server (127.0.0.1 only)"
  "$OLLAMA" serve >"$CAIRN_HOME/ollama.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 60); do
    curl -fs "http://$OLLAMA_ADDR/api/version" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -fs "http://$OLLAMA_ADDR/api/version" >/dev/null 2>&1 || die "The model server did not start. See $CAIRN_HOME/ollama.log"
fi
say "Downloading the language model: $LLM"
"$OLLAMA" pull "$LLM"

# 5. Speech model
say "Downloading the speech model: $WHISPER_REPO"
"$PY" -c "import sys; from huggingface_hub import snapshot_download as d; d(sys.argv[1], local_dir=sys.argv[2])" "$WHISPER_REPO" "$CAIRN_HOME/models/whisper"

# 6. Settings: everything stays local
{
  printf 'export CAIRN_HOME=%q\n' "$CAIRN_HOME"
  printf 'export CAIRN_ENGINE=%q\n' "$ENGINE"
  printf 'export CAIRN_WHISPER_MODEL=%q\n' "$CAIRN_HOME/models/whisper"
  printf 'export CAIRN_LLM=%q\n' "$LLM"
  printf 'export OLLAMA_HOST=%q\n' "$OLLAMA_ADDR"
  # shellcheck disable=SC2016
  printf 'export PATH=%q:"$PATH"\n' "$CAIRN_HOME/bin"
  printf 'export HF_HUB_OFFLINE=1\n'
  printf 'export DO_NOT_TRACK=1\n'
} >"$CAIRN_HOME/env.sh"

# 7. The application: configuration and launchers
"$PY" -c '
import json, sys
home, engine, model, repo, llm, host, ollama, app = sys.argv[1:9]
config = {"engine": engine, "whisper_model": model, "whisper_repo": repo, "llm": llm, "ollama_host": host, "ollama_bin": ollama, "app_dir": app}
with open(home + "/config.json", "w") as handle:
    json.dump(config, handle, indent=2)
' "$CAIRN_HOME" "$ENGINE" "$CAIRN_HOME/models/whisper" "$WHISPER_REPO" "$LLM" "$OLLAMA_ADDR" "$OLLAMA" "$HERE"
{
  echo '#!/bin/bash'
  printf 'export CAIRN_HOME=%q\n' "$CAIRN_HOME"
  printf 'export PYTHONPATH=%q\n' "$HERE"
  # shellcheck disable=SC2016
  printf 'export PATH=%q:"$PATH"\n' "$CAIRN_HOME/bin"
  # shellcheck disable=SC2016
  printf 'exec %q -m cairn "$@"\n' "$PY"
} >"$CAIRN_HOME/bin/cairn"
cp "$CAIRN_HOME/bin/cairn" "$CAIRN_HOME/Cairn.command"
chmod 700 "$CAIRN_HOME/bin/cairn" "$CAIRN_HOME/Cairn.command"

# 8. Self test: one short audio file and one question, all local
say "Running the self test"
# shellcheck disable=SC1091
source "$CAIRN_HOME/env.sh"
"$PY" "$HERE/scripts/selftest.py"
PYTHONPATH="$HERE" "$PY" -c "import cairn.server"

say "Done. Cairn is ready."
printf '\nStart Cairn: double-click Cairn.command in %s\nor run: %s/bin/cairn\n' "$CAIRN_HOME" "$CAIRN_HOME"
