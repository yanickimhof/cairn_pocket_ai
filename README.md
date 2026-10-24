# Cairn

**Sovereign Pocket AI.** Turn your voice recordings into clean, structured notes, entirely on your own computer.

No cloud. No account. No email. No telemetry. Nothing leaves your machine.

| Secure by default | Your recordings | Your notes |
|---|---|---|
| ![Secure mode](docs/screenshots/secure-mode.png) | ![Recordings](docs/screenshots/recordings.png) | ![Note](docs/screenshots/note.png) |

> **Status: early stage.** The engines install with one command. The app itself is under construction, see the [roadmap](docs/ROADMAP.md).

## Install

Open a terminal and paste one command. It detects your system, then downloads and sets up everything in your own folder: no administrator rights, no system change.

Not sure which command? Open **[the install page](https://yanickimhof.github.io/cairn_pocket_ai/)**, it shows the right one for your system.

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
| Computer | 64-bit, 16 GB of memory recommended |
| Disk space | 15 GB free |
| Internet | During installation only |
| USB | A USB-C port with data access (USB storage allowed) |
| Pocket | USB mode enabled in the Pocket app |

Details and Pocket setup: [docs/INSTALL.md](docs/INSTALL.md). Prefer to read before you run? See [SECURITY.md](SECURITY.md).

## What it does

1. Imports your recordings over USB-C and verifies every copy.
2. Transcribes them locally with Whisper.
3. Cleans, titles and summarizes them with a local language model (Qwen3 through Ollama). Short, standard or detailed.
4. Lets you rename, copy or export a note (Markdown, HTML).
5. Optionally empties the Pocket, only after every copy is verified.

## Why sovereign

- Audio, transcripts and summaries stay on your computer.
- No outgoing connection once installed, and no email feature.
- Open models you can swap, running on `127.0.0.1` only.
- Each note shows a reliability score and flags passages worth checking.

See [docs/PRIVACY.md](docs/PRIVACY.md) for how to verify it yourself.

## Disclaimer

Cairn is an independent, unofficial project. It is **not affiliated with, endorsed by or sponsored by Pocket** ([heypocket.com](https://heypocket.com)). "Pocket", "Pocket AI" and heypocket.com belong to their respective owners. Cairn uses these names only to say which device it works with, includes none of their logos or assets, and reads the files the device exposes in its USB mode.

Use Cairn responsibly: make sure you have the right, and the consent where required, to record and process conversations.

## License

MIT, see [LICENSE](LICENSE). Third-party components keep their own licenses, see [NOTICE](NOTICE).

Copyright (c) 2026 Yanick Imhof.
