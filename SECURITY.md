# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue.

## What the installer downloads

| Component | Version | Size | From | Protection |
|---|---|---|---|---|
| Cairn files | The release named in the install command (`v0.2.0`), or the tag in `CAIRN_REF` | Under 1 MB | GitHub | HTTPS only (TLS 1.2 or later), fixed release rather than a moving branch |
| Python manager (uv) | 0.11.32 | About 30 MB | astral.sh | Official installer at a fixed version, kept in the Cairn folder, your shell profile is untouched |
| Python | 3.11 | About 90 MB | uv | Kept in the Cairn folder |
| Python packages | Pinned in `requirements/` | About 1 GB | PyPI | Versions and SHA-256 hashes pinned, installed with `--require-hashes` |
| Model server (Ollama) | Latest | 0.2 to 1.7 GB, by system | ollama.com | Code signature checked before use (macOS: also accepted as notarized by the system; Windows: signed by Ollama), installed for your user only |
| Language model | Qwen3 4B (`qwen3:4b`, default). On demand: Qwen3 8B (5.2 GB), Qwen3.5 9B (6.6 GB, needs Ollama 0.17.5 or newer), Qwen3 14B (9.3 GB) | 2.5 GB | Ollama registry | Layers verified by digest |
| Speech model | Whisper large-v3-turbo. On demand: large-v3 (3.1 GB) | 1.6 GB | Hugging Face | Fixed revision (a commit of the repository), downloaded once, then offline (`HF_HUB_OFFLINE=1`) |

About 5.5 GB in total on a clean Mac and 7 GB on Windows (estimates). An existing Ollama and Qwen3 model are reused. Optional models download only when you confirm in the app. The install page shows the exact minimum version and sizes for your system.

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- One folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only, and the self test refuses any other address.
- The web interface is served on `127.0.0.1` only, behind a session key (HttpOnly, SameSite strict cookie), a Host check, a custom header on every change and a strict content security policy.
- A network guard refuses any outside connection in the app and the speech engine, except the daily version check, and a daily privacy check observes Cairn, the speech engine and the model server. Details: [docs/PRIVACY.md](docs/PRIVACY.md).
- Checks on every change: shell and Python static analysis, secrets scan, and a full install test on macOS and Windows.

## How it is checked

An internal review, not a third-party audit.

- **Automated, on every change:** unit and end-to-end tests with a stub speech engine and model server, a test that loads and drives the page script, shell and Python static analysis (shellcheck, bandit), a scan for secrets and personal paths, and a complete install and application test on macOS and Windows.
- **Reviewed by hand and by test:** the local API (session, Host check, change header, content security policy), path handling on the Pocket (links are not followed), escaping of every export format, the update check, the installers and their downloads, the response to a disconnected Pocket, a stopped model server, a full disk, a corrupted note and a deleted recording.
- **Accessibility:** automated WCAG 2.1 AA checks (axe-core) on every screen, light and dark, and a keyboard walk. A test with a screen reader has not been done.
- **Dependencies:** pinned by hash, watched by Dependabot. Open alerts and why they do not apply are listed below.

## Known limits

- The network guard works inside the program. A proxy set in the environment (`HTTPS_PROXY` pointing at this computer) would carry connections through that proxy: the daily privacy check observes the real connections and reports it.
- Dependabot reports `setuptools` (legacy wheel installation) and `mlx` (`load_gguf`, `load`). Cairn never calls them: it loads fixed speech models, no GGUF file, and installs only hashed wheels. Updating `mlx` means rebuilding the pinned package list for macOS 14, the minimum system, and is planned. `torch` ships only if you turn on speaker identification (below); Cairn calls it solely through the pyannote pipeline, never `torch.jit.script` directly.
- The Pocket battery reading (macOS) runs as a separate small program (Bluetooth only, read only), outside the in-program network guard. It opens no network connection, and the daily privacy check still covers the app and the speech engine. The optional Pocket status reading (firmware, state, storage, from your own session key) runs the same way, in its own small program, sending only the documented read commands.
- Speaker identification is off by default and optional. Installing its model is the one case where Cairn reaches the network beyond the daily version check: it runs `pip install pyannote.audio` and downloads the model's weights from Hugging Face, using the token you provide, in a separate process outside the in-program network guard (the same pattern as installing a speech or summary model). Once installed, recognition runs fully offline.
- A summary written by a language model can contain errors: the fidelity indicator catches invented numbers and names, not every mistake.
- Anyone who can run programs as you on this computer can read your notes: Cairn protects against the network and other web pages, not against a compromised account.

## Read before you run

Piping a script into a shell means trusting it. To read it first:

```
curl --proto '=https' --tlsv1.2 -fsSLO https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/v0.2.0/install.sh
less install.sh
bash install.sh
```

`install.ps1` can be read and run the same way.

## Limits

Cairn trusts its upstream components (uv, Ollama, the models and their publishers): review their security notices for your own risk assessment. Protect your data folder with full disk encryption.

## Known dependency advisories

A pip-audit of the locked, hash-pinned dependencies (2026-10-25) reported advisories on the Apple silicon build only: mlx 0.29.3, torch 2.11.0 and setuptools 81.0.0 (build time). Fixed versions cannot yet be locked together with mlx-whisper. Exposure is low: Cairn loads only the models of its own catalog and never opens model files supplied by a user. The lock files will be refreshed as soon as compatible versions exist. The Windows and Intel Mac builds have no known advisories.
