# Install

The command is in the [README](../README.md). It detects your system, installs everything in the Cairn folder of your home folder, then runs a self test. No administrator rights.

## Options

Set before the command: `CAIRN_HOME` (install folder), `CAIRN_LLM` (language model, default `qwen3:4b`), `CAIRN_WHISPER_REPO` (speech model), `CAIRN_REF` (branch or tag), `CAIRN_NO_SERVICE=1` (see below). Models too small to be useful (Whisper tiny or base, language models under 3B) are refused. An existing Ollama and its models are reused. The encryption library for the Pocket vault (`cryptography`, `keyring`) is part of the default install.

### A second copy, next to the one you use

On macOS the installer sets up the background mode, a small login item named `io.github.cairn` that keeps Cairn running. There is one per Mac: a second install would replace it and take its place. To try an install in another folder without touching yours, set `CAIRN_NO_SERVICE=1` before the command, and give the folder a name of its own:

```
CAIRN_HOME=~/CairnTest CAIRN_NO_SERVICE=1 bash install.sh
CAIRN_PORT=8741 ~/CairnTest/bin/cairn
```

Nothing is registered, so nothing starts by itself. Cairn listens on port 8731, or the next free one; `CAIRN_PORT` picks the first port to try, so both copies can run side by side. Delete the folder to remove the copy.

## Update

Cairn looks for a new version once a day (switch in **Settings, Check for updates**) and puts a dot on the info icon when one exists. To update, run the install command again: it replaces the engine and keeps your notes, settings and models. If speaker identification was installed, it is put back. The version it replaces stays in `~/Cairn/src.previous`, in case you need to go back. If you secured a Pocket, macOS may ask once to let the new copy of Python use the keychain: allow it, or enter the Pocket password again.

## Troubleshooting

| Symptom | Answer |
|---|---|
| The Pocket drive does not appear | The Pocket must show up as an external drive (named `Pocket` in the Finder or File Explorer). That is done by the Pocket and your computer, before Cairn is involved: without the drive, Cairn cannot see the device. A blinking light without a drive means the computer has not detected it. In the Pocket mobile app, switch USB Mode (Web Sync) off, then on again, then unplug and replug the Pocket. This is also the fix when the Pocket is no longer recognized after you deleted or resynced recordings in the Pocket app. Also try a USB-C data cable, another port, without a hub |
| Recordings are missing | Recordings already synced by the phone app are no longer on the drive: turn off automatic sync before you record |
| The Pocket disconnects during import | USB mode can drop under load. Replug: Cairn copies file by file, verifies each copy and resumes |
| Ollama is blocked at launch | Allow it in your system security settings |
| Downloads fail | Check that the network allows the sources listed in [SECURITY.md](../SECURITY.md) |
| Not enough memory | Keep the default model (`qwen3:4b`) and close other large applications |
| The page does not open | See the background mode section of the [guide](GUIDE.md) |

## Uninstall

On macOS, run `~/Cairn/bin/cairn service uninstall`, then delete the `Cairn` folder in your home folder. If Cairn installed Ollama for you outside that folder, remove it like any other app.
