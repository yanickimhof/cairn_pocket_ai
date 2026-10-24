# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue for security problems.

## What the installer downloads

| What | From | Protection |
|---|---|---|
| Cairn files | GitHub | HTTPS only (TLS 1.2 or later); you can pin a tag with `CAIRN_REF` |
| Python manager (uv) | astral.sh | Official installer, kept inside the Cairn folder, your shell profile is not modified |
| Python packages | PyPI | Versions and SHA-256 hashes pinned in `requirements/`, installed with `--require-hashes` |
| Local model server (Ollama) | ollama.com | Code signature checked before use, installed for your user only |
| Language model | Ollama registry | Layers verified by digest |
| Speech model | Hugging Face | Downloaded once, then used offline (`HF_HUB_OFFLINE=1`) |

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- Everything lives in one folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only. The self test refuses any other address.
- No telemetry, no email, no outgoing connection in everyday use.
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
