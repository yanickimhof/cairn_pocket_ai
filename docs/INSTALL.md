# Install

Two ways to install, the same installer: the command in the [README](../README.md), or `bash install.sh` (`.\install.ps1` on Windows) from a clone of the repository. It detects your system, installs everything in the Cairn folder of your home folder, then runs a self test. No administrator rights, nothing to install beforehand.

## Choosing your models (macOS)

In a terminal, the installer reads your Mac (chip, memory, free disk space), advises a profile and asks which one to install. Enter takes the advised one. It works with the piped command too: the question is read from the keyboard, not from the script.

| Profile | Made for | Speech | Notes | Models to download |
|---|---|---|---|---|
| Light | 8 GB of memory | Whisper large-v3-turbo | Qwen3 4B | about 4.1 GB |
| Standard | 16 GB | Whisper large-v3-turbo | Qwen3 8B | about 6.8 GB |
| High | 32 GB or more | Whisper large-v3 | Qwen3 14B | about 12.4 GB |

- A profile needs its models plus about 5 GB of room (packages, model server, working files). One that does not fit the free space is not offered.
- On an update, a copy that is already installed keeps its models: Enter keeps them, `k` says so, and a number changes them. Models you added in Settings, Models stay in place.
- Nothing is final. Settings, Models adds, switches and removes models at any time, and **About, Check the installation** shows which profile is advised for this computer and which one is in use.
- Optional models (a search model, Parakeet, speaker identification) are never part of the install: they come from Settings, Models, when you ask.

Windows keeps one set of choices for now (the Light models); change them afterwards in Settings, Models, or name them with `CAIRN_LLM` and `CAIRN_WHISPER_REPO`.

## Options

Set before the command.

| Variable | Effect |
|---|---|
| `CAIRN_HOME` | Install folder (default `~/Cairn`) |
| `CAIRN_PROFILE` | `light`, `standard` or `high`: that profile, no question asked |
| `CAIRN_YES=1` | Never ask: keep what is installed, or take the Light models |
| `CAIRN_LLM`, `CAIRN_WHISPER_REPO` | Name the models yourself; nothing is asked. Models too small to be useful (Whisper tiny or base, language models under 3B) are refused |
| `CAIRN_REF` | Branch or tag to install (default: the release the script belongs to) |
| `CAIRN_NO_SERVICE=1` | macOS: no background mode (see below) |
| `CAIRN_NO_OPEN=1` | macOS: do not open the app in the browser when the install is done |

In a script, in CI or without a keyboard, nothing is asked: an update keeps what is installed and a first install gets the Light models. An existing Ollama and its models are reused. The encryption library for the Pocket vault (`cryptography`, `keyring`) is part of the default install.

### A second copy, next to the one you use

On macOS the installer sets up the background mode, a small login item named `io.github.cairn` that keeps Cairn running. There is one per Mac: a second install would replace it and take its place. To try an install in another folder without touching yours, set `CAIRN_NO_SERVICE=1` before the command, and give the folder a name of its own:

```
CAIRN_HOME=~/CairnTest CAIRN_NO_SERVICE=1 bash install.sh
CAIRN_PORT=8741 ~/CairnTest/bin/cairn
```

Nothing is registered, so nothing starts by itself. Cairn listens on port 8731, or the next free one; `CAIRN_PORT` picks the first port to try, so both copies can run side by side. Delete the folder to remove the copy.

## Update

Cairn looks for a new version once a day (switch in **Settings, Check for updates**) and puts a dot on the info icon when one exists. To update, run the install command again (from a clone: `git pull`, then `bash install.sh`): it replaces the engine, keeps your notes, settings and models, and offers to keep the models you have. If speaker identification was installed, it is put back from its own hashed list. The version it replaces stays in `~/Cairn/src.previous`, in case you need to go back. If you secured a Pocket, macOS may ask once to let the new copy of Python use the keychain: allow it, or enter the Pocket password again.

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
