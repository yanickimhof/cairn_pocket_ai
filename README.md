# Cairn

**Sovereign Pocket AI.** Turn your voice recordings into clean, structured notes, entirely on your own computer.

No cloud. No account. No telemetry. Nothing leaves your machine.

| Secure by default | Your recordings | Your notes |
|---|---|---|
| ![Secure mode](docs/screenshots/secure-mode.png) | ![Recordings](docs/screenshots/recordings.png) | ![Note](docs/screenshots/note.png) |

> **Status: early stage.** The installer sets up and tests all the engines with one command. The app interface shown above is the target design and is under construction, see the [roadmap](docs/ROADMAP.md).

## Install

Open a terminal and paste one command. It detects your system, then downloads and sets up everything in your own folder: no administrator rights, no system change.

Not sure which command? Open **[the install page](https://yanickimhof.github.io/cairn_pocket_ai/)**. It shows the right command, the minimum version and the download sizes for your system.

bash or zsh:

```
curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.sh | bash
```

PowerShell:

```
irm https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.ps1 | iex
```

**Requirements**

| | |
|---|---|
| Computer | 64-bit, 16 GB of memory recommended (8 GB with a smaller model) |
| Operating system | A current version, the install page shows the minimum for yours |
| Disk space | 15 GB free, about 9 GB used once installed |
| Internet | During installation only, about 9 GB to download |
| USB | A USB-C port with data access (USB storage allowed) |
| Pocket | USB mode enabled in the Pocket app |

Details and Pocket setup: [docs/INSTALL.md](docs/INSTALL.md). The full list of downloads, with versions and sizes: [SECURITY.md](SECURITY.md).

## How to use it

Cairn is being built in two steps.

1. **Today:** the installer sets up the speech engine, the local language model and the model server, then runs a self test (a short audio file and one question, all local). If it ends with "Cairn is ready", your computer is set.
2. **Next:** the app, with the flow shown above. Plug in your Pocket, click **Import**, then read, rename, copy or export each note. Follow progress in the [roadmap](docs/ROADMAP.md).

## What it does

1. Imports your recordings over USB-C and verifies every copy.
2. Transcribes them locally with Whisper.
3. Cleans, titles and summarizes them with a local language model (Qwen3 through Ollama). Short, standard or detailed.
4. Lets you rename, copy or export a note (Markdown, HTML).
5. Optionally empties the Pocket, only after every copy is verified.

## Why sovereign

- Audio, transcripts and summaries stay on your computer.
- No outgoing connection once installed.
- Open models you can swap.
- The model server answers only on your own computer. Its address, `127.0.0.1`, is the computer talking to itself ("localhost"): no other device on your network can reach it.
- Each note shows a reliability score and flags passages worth checking.

See [docs/PRIVACY.md](docs/PRIVACY.md) for how to verify it yourself.

## Disclaimer

Cairn is an independent, unofficial project. It is **not affiliated with, endorsed by or sponsored by Pocket** ([heypocket.com](https://heypocket.com)), a product of Open Vision Engineering Inc. "Pocket" and "Pocket AI" are trademarks or product names of their respective owners. Cairn uses these names only to say which device it works with, includes none of their logos or assets, and reads the files the device exposes in its USB mode.

Use Cairn responsibly: make sure you have the right, and the consent where required, to record and process conversations.

## License

MIT, see [LICENSE](LICENSE). Third-party components keep their own licenses, see [NOTICE](NOTICE).

Copyright (c) 2026 Yanick Imhof.
