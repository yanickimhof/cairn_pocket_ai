# Install

The command is in the [README](../README.md). It detects your system, installs everything in the Cairn folder of your home folder, then runs a self test. No administrator rights.

## Options

Set before the command: `CAIRN_HOME` (install folder), `CAIRN_LLM` (language model, default `qwen3:4b`), `CAIRN_WHISPER_REPO` (speech model), `CAIRN_REF` (branch or tag). Models too small to be useful (Whisper tiny or base, language models under 3B) are refused. An existing Ollama and its models are reused.

## Update

Cairn looks for a new version once a day (switch in **Settings, Check for updates**) and puts a dot on the info icon when one exists. To update, run the install command again: it replaces the engine and keeps your notes, settings and models.

## Troubleshooting

| Symptom | Answer |
|---|---|
| The Pocket drive does not appear | Check that USB Mode is on in the Pocket app. Allow USB storage on the computer, replug, switch USB mode off and on, try another cable |
| Recordings are missing | Recordings already synced by the phone app are no longer on the drive: turn off automatic sync before you record |
| The Pocket disconnects during import | USB mode can drop under load. Replug: Cairn copies file by file, verifies each copy and resumes |
| Ollama is blocked at launch | Allow it in your system security settings |
| Downloads fail | Check that the network allows the sources listed in [SECURITY.md](../SECURITY.md) |
| Not enough memory | Keep the default model (`qwen3:4b`) and close other large applications |
| The page does not open | See the background mode section of the [guide](GUIDE.md) |

## Uninstall

On macOS, run `~/Cairn/bin/cairn service uninstall`, then delete the `Cairn` folder in your home folder. If Cairn installed Ollama for you outside that folder, remove it like any other app.
