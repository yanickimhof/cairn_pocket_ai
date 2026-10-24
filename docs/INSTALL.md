# Install

One command in a terminal (see the [README](../README.md)). It detects your system, installs everything in the Cairn folder of your home folder, then runs a self test. No administrator rights.

## Set up your Pocket

You need neither the Pocket desktop app nor a Pocket account on the computer. Menu names can vary between app versions: see [heypocket.com](https://heypocket.com).

1. In the Pocket mobile app, open the device settings and turn **on** USB Mode (Pocket Web Sync). It is off by default, and the USB-C port then only charges.
2. In the same settings, turn **off** every automatic or cloud sync option (auto-sync, Wi-Fi or online sync, cloud backup, and any similar option). Otherwise the Pocket sends recordings to Pocket's online service on its own, and the phone app then removes them from the drive, so Cairn never sees them.
3. Connect the Pocket with a USB-C **data** cable.
4. Check that a drive named `Pocket` appears, with a `RECORD` folder. In Cairn, the dot next to the name turns green.
5. Close the Pocket desktop app if you use it, so that only one program reads the device.

Good to know:

- Option names vary between app versions: look for anything that syncs or backs up online.
- Recordings already synced by the phone app are no longer on the drive.
- USB mode can drop under load. Cairn copies file by file, verifies each copy and resumes.

## Options

Set before the command: `CAIRN_HOME` (install folder), `CAIRN_LLM` (language model, default `qwen3:4b`), `CAIRN_WHISPER_REPO` (speech model), `CAIRN_REF` (branch or tag). Models too small to be useful (Whisper tiny or base, language models under 3B) are refused. An existing Ollama and its models are reused. Larger models can be added later in **Settings, Models**.

## Update

Cairn looks for a new version once a day (switch in **Settings, Check for updates**) and puts a dot on the info icon when one exists. To update, run the install command again: it replaces the engine and keeps your notes, settings and models.

## Troubleshooting

| Symptom | Answer |
|---|---|
| The Pocket drive does not appear | Allow USB storage on the computer, replug, switch USB mode off and on, try another cable |
| Ollama is blocked at launch | Allow it in your system security settings |
| Downloads fail | Check that the network allows the sources listed in [SECURITY.md](../SECURITY.md) |
| Not enough memory | Keep the default model (`qwen3:4b`) and close other large applications |

## Uninstall

Delete the `Cairn` folder in your home folder (on macOS, run `~/Cairn/bin/cairn service uninstall` first). If Cairn installed Ollama for you outside that folder, remove it like any other app.
