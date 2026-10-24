# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue for security problems.

## What the installer downloads

| Component | Version | Size | From | Protection |
|---|---|---|---|---|
| Cairn files | Latest `main`, or the tag in `CAIRN_REF` | Under 1 MB | GitHub | HTTPS only (TLS 1.2 or later) |
| Python manager (uv) | Latest | About 30 MB | astral.sh | Official installer, kept inside the Cairn folder, your shell profile is not modified |
| Python | 3.11 | About 90 MB | uv | Kept inside the Cairn folder |
| Python packages | Pinned in `requirements/` | About 1 GB | PyPI | Versions and SHA-256 hashes pinned, installed with `--require-hashes` |
| Local model server (Ollama) | Latest | 0.2 to 1.7 GB, depending on your system | ollama.com | Code signature checked before use, installed for your user only |
| Language model | Qwen3 8B (`CAIRN_LLM`, default `qwen3:8b`), 5.2 GB. Qwen3 4B: 2.5 GB | 5.2 GB | Ollama registry | Layers verified by digest |
| Speech model | Whisper large-v3-turbo | 1.6 GB | Hugging Face | Downloaded once, then used offline (`HF_HUB_OFFLINE=1`) |

About 9 GB in total on a clean computer. If Ollama and the language model are already installed, Cairn reuses them and only downloads the speech model and the Python packages. The install page shows the exact minimum version and the sizes for your system.

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- Everything lives in one folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only (your own computer). The self test refuses any other address.
- The web interface is served on `127.0.0.1` only, behind a one-time session key (HttpOnly, SameSite strict cookie), a Host check, a custom header on every change and a strict content security policy.
- No telemetry and no outgoing connection in everyday use. The only optional request is the update check you trigger yourself.
- Continuous checks on every change: shell and Python static analysis, secrets scan, and a full install test on both families of systems.

## Read before you run

Piping a script into a shell asks you to trust it. To inspect it first:

```
curl --proto '=https' --tlsv1.2 -fsSLO https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/main/install.sh
less install.sh
bash install.sh
```

The PowerShell installer, `install.ps1`, can be read and run the same way.

## Limits

Cairn trusts its upstream components (uv, Ollama, the models and their publishers). Review their security notices for your own risk assessment. Protect your data folder with full disk encryption.
