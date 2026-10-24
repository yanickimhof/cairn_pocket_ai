# Install

One command, in a terminal. See the [README](../README.md) for the command. It detects your system, installs everything in the Cairn folder in your home folder, then runs a self test. No administrator rights.

## Set up your Pocket

You do not need the Pocket desktop app or a Pocket account on the computer. Menu names can differ between app versions, see [heypocket.com](https://heypocket.com) for the latest instructions.

1. In the Pocket mobile app, open the device settings and turn on **USB Mode** (Pocket Web Sync). It is off by default: without it, the USB-C port only charges.
2. Plug the Pocket into the computer with a USB-C **data** cable.
3. Check that a drive named `Pocket` appears, with a `RECORD` folder. In Cairn, the dot next to the name turns green.
4. Close the Pocket desktop app if you use it, so that only one program reads the device.

Good to know

- Recordings already transferred by the Pocket phone app are no longer on the drive.
- To keep recordings out of Pocket's online service, turn off automatic sync in the Pocket mobile app before you record.
- The USB mode can drop under load. Cairn copies file by file, verifies each copy and resumes.

## Options

Set before the command: `CAIRN_HOME` (install folder), `CAIRN_LLM` (language model, default `qwen3:4b`), `CAIRN_WHISPER_REPO` (speech model), `CAIRN_REF` (branch or tag). Models too small to be useful (Whisper tiny or base, language models under 3B) are refused. If Ollama is already installed, Cairn reuses it and the models it holds. Larger models can be added later from **Settings, Models** in the app.

## Troubleshooting

| Symptom | Answer |
|---|---|
| The Pocket drive does not appear | Enable USB storage on the computer, replug, switch USB mode off and on, try another cable |
| Ollama is blocked at launch | Allow it in the security settings of your system |
| Downloads fail | Check that the network allows the sources listed in [SECURITY.md](../SECURITY.md) |
| Not enough memory | Keep the default model (`qwen3:4b`) and close other large applications |

## Uninstall

Delete the `Cairn` folder in your home folder. If Cairn installed Ollama for you outside that folder, remove it like any other app.
