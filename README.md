# Cairn

**Sovereign Pocket AI.** Turn your voice recordings into clean, structured notes, entirely on your own computer.

No cloud. No account. No telemetry. Nothing leaves your machine.

| Secure by default | Your recordings | Your notes |
|---|---|---|
| ![Secure mode](docs/screenshots/secure-mode.png) | ![Recordings](docs/screenshots/recordings.png) | ![Note](docs/screenshots/note.png) |

> **Status: v0.1, preview.** The app runs on your computer in your browser, entirely offline. Checked end to end on macOS by automated tests; Windows checks run in CI, see the [roadmap](docs/ROADMAP.md).

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

**Minimum and recommended machine**

| | Minimum | Recommended |
|---|---|---|
| Processor | 64-bit, 4 cores. Intel Mac or Windows PC: works, but slower | Apple silicon (M1 or later), or a recent 8-core PC |
| Memory | 8 GB, with the lighter language model (`CAIRN_LLM=qwen3:4b`) | 16 GB or more, with the default model |
| Disk space | 15 GB free | 20 GB free (notes and audio take extra space) |
| Operating system | macOS 14 or later, Windows 10 22H2 or later | The latest version of either |
| Graphics card | Not required | Not required |
| Internet | During installation only, about 9 to 10 GB to download (about 3.5 GB if Ollama and the language model are already installed) | |
| USB | A USB-C port with data access (USB storage allowed) | |
| Pocket | USB mode enabled in the Pocket app | |

Processing happens on your computer, so a faster machine means faster notes. Everything works offline once installed.

**Models.** Cairn installs models that do the job well: Whisper large-v3-turbo for transcription and Qwen3 8B for notes. If you already have Ollama, Cairn reuses it and any model it already holds (nothing is reinstalled or modified, so the download is smaller). Models too small to give reliable notes are refused by the installer. For a modest computer, use `CAIRN_LLM=qwen3:4b`.

Details and Pocket setup: [docs/INSTALL.md](docs/INSTALL.md). The full list of downloads, with versions and sizes: [SECURITY.md](SECURITY.md).

## How to use it

1. Run the install command once. It ends with "Done. Cairn is ready".
2. Start Cairn: double-click `Cairn.command` in your Cairn folder (Start menu shortcut or `Cairn.cmd` on Windows), or run `~/Cairn/bin/cairn`. Your browser opens a page served only by your own computer (127.0.0.1), protected by a one-time session key.
3. Plug in your Pocket (USB mode) and click **Import**. Cairn copies and verifies every recording, transcribes it, then cleans and summarizes it.
4. Read, rename, copy or export each note (Markdown, HTML). Exports are saved in `~/Cairn/Exports`.

Secure mode hides the list of notes until you reveal it.

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

## Buying a Pocket

Cairn is free and works with any Pocket you already own. If you are still thinking about getting one, you can buy it on the official site, [heypocket.com](https://heypocket.com). Using the maintainer's [referral link](https://referral.heypocketai.com/refer/39179caf?source=desktop_copy) is entirely optional. It is Pocket's own referral programme: the offer (currently 10% off at the time of writing) and its availability are set solely by Pocket, can change or end at any time, and the maintainer has no control over them. If you use the link, the maintainer receives a reward from Pocket's programme at no cost to you. Cairn works the same whether you use it or not.

## Disclaimer

Cairn is an independent, unofficial project. It is **not affiliated with, endorsed by or sponsored by Pocket** ([heypocket.com](https://heypocket.com)), a product of Open Vision Engineering Inc. "Pocket" and "Pocket AI" are trademarks or product names of their respective owners. Cairn uses these names only to say which device it works with, includes none of their logos or assets, and reads the files the device exposes in its USB mode.

Use Cairn responsibly: make sure you have the right, and the consent where required, to record and process conversations.

## License

MIT, see [LICENSE](LICENSE). Third-party components keep their own licenses, see [NOTICE](NOTICE).

Copyright (c) 2026 Yanick Imhof.
