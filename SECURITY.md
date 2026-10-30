# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue.

## What the installer downloads

| Component | Version | Size | From | Protection |
|---|---|---|---|---|
| Cairn files | The release named in the install command (`v0.6.0`), or the tag in `CAIRN_REF` | Under 1 MB | GitHub | HTTPS only (TLS 1.2 or later), fixed release rather than a moving branch |
| Python manager (uv) | 0.11.32 | About 30 MB | astral.sh | Official installer at a fixed version, kept in the Cairn folder, your shell profile is untouched |
| Python | 3.11 | About 90 MB | uv | Kept in the Cairn folder |
| Python packages | Pinned in `requirements/` | About 1 GB | PyPI | Versions and SHA-256 hashes pinned, installed with `--require-hashes` |
| Model server (Ollama) | Latest | 0.2 to 1.7 GB, by system | ollama.com | Code signature checked before use (macOS: also accepted as notarized by the system; Windows: signed by Ollama), installed for your user only |
| Search model (optional) | Qwen3 Embedding 0.6B or BGE-M3, only if you choose one in Settings | 0.6 or 1.2 GB | Ollama registry | Layers verified by digest |
| Language model | Qwen3 4B (`qwen3:4b`, default). On demand: Qwen3 8B (5.2 GB), 14B (9.3 GB) | 2.5 GB | Ollama registry | Layers verified by digest |
| Speech model | Whisper large-v3-turbo. On demand: large-v3 (3.1 GB) | 1.6 GB | Hugging Face | Fixed revision (a commit of the repository), downloaded once, then offline (`HF_HUB_OFFLINE=1`) |

About 5.5 GB in total on a clean Mac and 7 GB on Windows (estimates). An existing Ollama and Qwen3 model are reused. Optional models download only when you confirm in the app. The install page shows the exact minimum version and sizes for your system.

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- One folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only, and the self test refuses any other address.
- The web interface is served on `127.0.0.1` only, behind a session key (HttpOnly, SameSite strict cookie), a Host check, a custom header on every change and a strict content security policy.
- Ask your notes: what a recording says is treated as data, never as an order. Passages are fenced in the request and cannot close their own tag, the model has no tool and no network, and its answer is shown as plain text, so a link or an image in it is never loaded. A citation that matches no passage is dropped. The conversation is kept in the page only, and the log keeps neither a question nor any text.
- A network guard refuses any outside connection in the app and the speech engine, except the daily version check, and a daily privacy check observes Cairn, the speech engine and the model server. Details: [docs/PRIVACY.md](docs/PRIVACY.md).
- Pocket vault: AES-256-GCM in 1 MiB chunks, one key per file derived with HKDF from a key that scrypt (N=131072, 128 MiB) derives from the password (10 characters at least; the vault header on the Pocket may not ask for more than that cost). Each chunk's position and an end marker are authenticated, so a file that was cut, reordered or extended is refused. The password is never stored; the key is kept only in the system keychain of a computer you trust. A recording on the Pocket is replaced only after the local copy was checked again, the encrypted copy read back and compared, and the recording found unchanged. The readable file is then overwritten with random bytes before it is deleted; on a flash drive this is best effort, because the drive may keep blocks it moved on its own. A vault is never replaced by another: a header that cannot be read blocks a new one.
- Checks on every change: shell and Python static analysis, secrets scan, and a full install test on macOS and Windows.

## How it is checked

An internal review, not a third-party audit.

- **Automated, on every change:** unit and end-to-end tests with a stub speech engine and model server, a test that loads and drives the page script, shell and Python static analysis (shellcheck, bandit), a scan for secrets and personal paths, and a complete install and application test on macOS and Windows.
- **Reviewed by hand and by test:** the local API (session, Host check, change header, content security policy), the audio of a note served to the page only as an audio file listed in that note, by byte ranges, path handling on the Pocket (links are not followed), escaping of every export format, the update check, the installers and their downloads, the response to a disconnected Pocket, a stopped model server, a full disk, a corrupted note and a deleted recording.
- **Accessibility:** automated checks (axe-core) on the main screens and a keyboard walk. A test with a screen reader has not been done.
- **Dependencies:** pinned by hash, watched by Dependabot. Open alerts and why they do not apply are listed below.

## Known limits

- The network guard works inside the program. A proxy set in the environment (`HTTPS_PROXY` pointing at this computer) would carry connections through that proxy: the daily privacy check observes the real connections and reports it.
- Dependabot reported `setuptools` (legacy wheel installation) and `mlx` (`load_gguf`, `load`). Cairn never called them: it loads fixed speech models, no GGUF file, and installs only hashed wheels. The pinned package list is built for macOS 14 and later (`mlx` 0.32, `torch` 2.15, `setuptools` 84), which closes these advisories in the packages you install. `torch` ships only if you turn on speaker identification (below); Cairn calls it solely through the pyannote pipeline, never `torch.jit.script` directly.
- The Pocket battery reading (macOS) runs as a separate small program (Bluetooth only, read only), outside the in-program network guard. It opens no network connection, and the daily privacy check still covers the app and the speech engine. The optional Pocket status reading (firmware, state, storage, from your own session key) runs the same way, in its own small program, sending only the documented read commands.
- Speaker identification is off by default and optional. Installing its model is the one case where Cairn reaches the network beyond the daily version check: it runs `pip install pyannote.audio` and downloads the model's weights from Hugging Face, using the token you provide, in a separate process outside the in-program network guard (the same pattern as installing a speech or summary model). Once installed, recognition runs fully offline.
- The vault protects recordings that sit on the Pocket, against someone who holds the Pocket. It does not protect against someone who holds the Pocket and knows the password, nor against malware on a computer where the key is trusted. File sizes and the number of recordings stay visible. A recording made since the last connection is plain until Cairn next sees the Pocket. The libraries it relies on are `cryptography` (AES-GCM, HKDF) and `keyring` (system keychain), installed with the other packages and pinned by hash.
- Voiceprints (optional) are biometric data: they stay in `voices.json` and in the notes, in the Cairn folder, as plain files protected by the owner-only permissions. Erasing a person, or everybody, from People removes them there and in the notes. Turning **Remember voices** off stops new ones but erases nothing by itself. There is no lockout after wrong vault passwords, only the cost of each try.
- A summary written by a language model can contain errors: the fidelity indicator catches invented numbers and names, not every mistake.
- Anyone who can run programs as you on this computer can read your notes: Cairn protects against the network and other web pages, not against a compromised account.

## Read before you run

Piping a script into a shell means trusting it. To read it first:

```
curl --proto '=https' --tlsv1.2 -fsSLO https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/v0.6.0/install.sh
less install.sh
bash install.sh
```

`install.ps1` can be read and run the same way.

## Limits

Cairn trusts its upstream components (uv, Ollama, the models and their publishers): review their security notices for your own risk assessment. Protect your data folder with full disk encryption.

## Known dependency advisories

A pip-audit of the locked, hash-pinned dependencies (2026-10-25) reported advisories on the Apple silicon build only: mlx 0.29.3, torch 2.11.0 and setuptools 81.0.0 (build time). Fixed versions cannot yet be locked together with mlx-whisper. Exposure is low: Cairn loads only the models of its own catalog and never opens model files supplied by a user. The lock files will be refreshed as soon as compatible versions exist. The Windows and Intel Mac builds have no known advisories.
