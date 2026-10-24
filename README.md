# Cairn

**Sovereign Pocket AI.** Turn your Pocket recordings into clean, structured notes, entirely on your computer.

No cloud, no account, no telemetry. Nothing leaves your machine.

*A cairn is a stack of stones that marks a trail. This one marks the way from your voice to your notes.*

| Secure by default | Your recordings | Your notes |
|---|---|---|
| ![Secure mode](docs/screenshots/secure-mode.png) | ![Recordings, with live progress](docs/screenshots/recordings.png) | ![Note](docs/screenshots/note.png) |

| Settings | Models on demand | About |
|---|---|---|
| ![Settings](docs/screenshots/settings.png) | ![Models](docs/screenshots/models.png) | ![About](docs/screenshots/about.png) |

| Export to HTML (transcript folded) | Copy for an email |
|---|---|
| ![HTML export](docs/screenshots/html-export.png) | ![Email](docs/screenshots/email.png) |

> **Status: v0.1, preview.** Runs in your browser, offline. Tested end to end on macOS; Windows is checked in CI. See the [roadmap](docs/ROADMAP.md).

## Install

Paste one command in a terminal. It detects your system and installs everything in your own folder: no administrator rights, no system change. Not sure which one? The [install page](https://yanickimhof.github.io/cairn_pocket_ai/) shows the right command, the minimum version and the download sizes.

bash or zsh:

```
curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.sh | bash
```

PowerShell:

```
irm https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.ps1 | iex
```

| | Minimum | Recommended |
|---|---|---|
| Processor | 64-bit, 4 cores (Intel Mac or Windows PC: slower) | Apple silicon (M1 or later), or a recent 8-core PC |
| Memory | 8 GB | 16 GB or more (larger models) |
| Disk space | 12 GB free | 20 GB free |
| System | macOS 14, Windows 10 22H2 | Latest version |
| Graphics card | Not required | Not required |
| Internet | Installation only: about 5.5 GB (Mac) or 7 GB (Windows), about 2.5 GB if Ollama and a Qwen3 model are already installed | |
| Pocket | USB-C data port, USB mode enabled in the Pocket app | |

A faster machine means faster notes. Everything works offline once installed. Pocket setup and troubleshooting: [docs/INSTALL.md](docs/INSTALL.md). Every download, with versions and sizes: [SECURITY.md](SECURITY.md).

## How it works

1. Start Cairn: open `~/Cairn/Cairn.app` (macOS), the Start menu shortcut or `Cairn.cmd` (Windows), or run `~/Cairn/bin/cairn`. A page opens, served only by your computer (`127.0.0.1`) and protected by a session key.
2. Plug in your Pocket (USB mode) and click **Import**. Cairn copies and verifies every recording.
3. It transcribes each one with Whisper, then cleans, titles and summarizes it with a local model (Qwen3 through Ollama), at a short, standard or detailed level. Each note carries a reliability score and flags the passages worth checking.
4. Rename, copy or export a note (Markdown, HTML). Exports go to `~/Cairn/Exports`.
5. Optionally empty the Pocket, only after every copy is verified.

Secure mode hides the list of notes until you reveal it. Tap a waiting recording to process it now, or skip it (it can be restored). Newest recordings come first, and Stop interrupts the current job.

## Good to know

**Models.** The default install is the smallest that gives good results: Whisper large-v3-turbo (1.6 GB) and Qwen3 4B (2.5 GB). On a French recording, smaller speech models misheard names and produced wrong actions, so Cairn does not offer them. If Qwen3 8B is already in your Ollama, Cairn uses it. It never modifies your existing Ollama or models. For sharper notes, open **Settings, Models**, pick a larger model (Qwen3 8B or 14B, Whisper large-v3), confirm the download, then press **Use**. Nothing downloads without your click, and a model can be removed from the same screen to free disk space.

**Speed.** The speech model stays loaded between recordings and is released after five idle minutes. **Polish the transcript** (Settings) rewrites the raw transcript for readability. It is off by default because it is the slowest step, and summaries do not depend on it.

**Background mode and web app (macOS).** Cairn runs as a small background service that starts at login and restarts if it stops. If the page does not answer, open `Cairn.app` again, or run `~/Cairn/bin/cairn service restart` (`service uninstall` removes the background mode). It is also an installable web app: Chrome, Install Cairn; Safari, File, Add to Dock. It then opens in its own window, still served from your computer.

**"Not secure" in the address bar?** Cairn is served over plain `http` on `127.0.0.1`, an address that exists only inside your computer. Nothing travels over a network, so there is nothing to intercept, and browsers treat it as trustworthy. Chrome still labels any `http` page "not secure". Switching to `https` would mean installing a certificate authority on your computer, which weakens your security far more than this label does, so Cairn does not do it. The installed web app has no address bar.

## Why sovereign

- Audio, transcripts and summaries stay on your computer.
- No outgoing connection once installed. A network guard refuses any outside connection in the app and the speech engine, and the shield icon in About runs a privacy check that proves it. The automated tests run the same check on macOS and Windows.
- The model server answers only on `127.0.0.1` (your computer talking to itself), so no other device on your network can reach it.
- Open models you can swap.

How to verify it yourself: [docs/PRIVACY.md](docs/PRIVACY.md).

## Buying a Pocket

Cairn is free and works with any Pocket you already own. To buy one, use the official site, [heypocket.com](https://heypocket.com). The maintainer's [referral link](https://referral.heypocketai.com/refer/39179caf?source=desktop_copy) is optional: it is Pocket's own programme, so the offer (10% off at the time of writing) is set by Pocket alone and can change or end at any time. If you use it, the maintainer receives a reward from Pocket at no cost to you. Cairn works the same either way.

## Disclaimer

Cairn is an independent, unofficial project, **not affiliated with, endorsed by or sponsored by Pocket** ([heypocket.com](https://heypocket.com)), a product of Open Vision Engineering Inc. "Pocket" and "Pocket AI" belong to their owners. Cairn uses these names only to say which device it works with, includes none of their logos or assets, and reads the files the device exposes in USB mode.

Make sure you have the right, and the consent where required, to record and process conversations.

## License

MIT, see [LICENSE](LICENSE). Third-party components keep their own licenses, see [NOTICE](NOTICE). Copyright (c) 2026 Yanick Imhof.
