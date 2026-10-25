# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue.

## What the installer downloads

| Component | Version | Size | From | Protection |
|---|---|---|---|---|
| Cairn files | Latest `main`, or the tag in `CAIRN_REF` | Under 1 MB | GitHub | HTTPS only (TLS 1.2 or later) |
| Python manager (uv) | Latest | About 30 MB | astral.sh | Official installer, kept in the Cairn folder, your shell profile is untouched |
| Python | 3.11 | About 90 MB | uv | Kept in the Cairn folder |
| Python packages | Pinned in `requirements/` | About 1 GB | PyPI | Versions and SHA-256 hashes pinned, installed with `--require-hashes` |
| Model server (Ollama) | Latest | 0.2 to 1.7 GB, by system | ollama.com | Code signature checked before use, installed for your user only |
| Language model | Qwen3 4B (`qwen3:4b`, default). On demand: Qwen3 8B (5.2 GB), 14B (9.3 GB) | 2.5 GB | Ollama registry | Layers verified by digest |
| Speech model | Whisper large-v3-turbo. On demand: large-v3 (3.1 GB) | 1.6 GB | Hugging Face | Downloaded once, then offline (`HF_HUB_OFFLINE=1`) |

About 5.5 GB in total on a clean Mac and 7 GB on Windows (estimates). An existing Ollama and Qwen3 model are reused. Optional models download only when you confirm in the app. The install page shows the exact minimum version and sizes for your system.

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- One folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only, and the self test refuses any other address.
- The web interface is served on `127.0.0.1` only, behind a session key (HttpOnly, SameSite strict cookie), a Host check, a custom header on every change and a strict content security policy.
- A network guard refuses any outside connection in the app and the speech engine, except the daily version check, and a daily privacy check observes Cairn, the speech engine and the model server. Details: [docs/PRIVACY.md](docs/PRIVACY.md).
- Checks on every change: shell and Python static analysis, secrets scan, and a full install test on macOS and Windows.

## Read before you run

Piping a script into a shell means trusting it. To read it first:

```
curl --proto '=https' --tlsv1.2 -fsSLO https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.sh
less install.sh
bash install.sh
```

`install.ps1` can be read and run the same way.

## Limits

Cairn trusts its upstream components (uv, Ollama, the models and their publishers): review their security notices for your own risk assessment. Protect your data folder with full disk encryption.

## Known dependency advisories

A pip-audit of the locked, hash-pinned dependencies (2026-10-25) reported advisories on the Apple silicon build only: mlx 0.29.3, torch 2.11.0 and setuptools 81.0.0 (build time). Fixed versions cannot yet be locked together with mlx-whisper. Exposure is low: Cairn loads only the models of its own catalog and never opens model files supplied by a user. The lock files will be refreshed as soon as compatible versions exist. The Windows and Intel Mac builds have no known advisories.
