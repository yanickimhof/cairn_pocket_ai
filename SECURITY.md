# Security

## Report a vulnerability

Use GitHub's private vulnerability reporting (Security tab, "Report a vulnerability"). Please do not open a public issue.

## What the installer downloads

| Component | Version | Size | From | Protection |
|---|---|---|---|---|
| Cairn files | The release named in the install command (`v0.7.0`), or the tag in `CAIRN_REF` | Under 1 MB | GitHub | HTTPS only (TLS 1.2 or later), fixed release rather than a moving branch |
| Python manager (uv) | 0.11.32 | About 30 MB | GitHub (astral-sh/uv releases) | Fixed version, SHA-256 checked before use, kept in the Cairn folder, your shell profile is untouched; no installer script is run |
| Python | 3.11 | About 90 MB | uv | Kept in the Cairn folder |
| Python packages | Pinned in `requirements/` | Under 1 GB | PyPI | Versions and SHA-256 hashes pinned, installed with `--require-hashes --no-deps`, so nothing outside the hashed list is pulled in. `torch` is not part of this list: speaker identification adds it, with its own packages, from a second hashed list |
| Model server (Ollama) | 0.40.13 | 0.2 to 1.7 GB, by system | GitHub (ollama/ollama releases) | Fixed release, SHA-256 checked, then code signature checked before use (macOS: also accepted as notarized by the system; Windows: signed by Ollama), installed for your user only |
| Search model (optional) | Qwen3 Embedding 0.6B or BGE-M3, only if you choose one in Settings | 0.6 or 1.2 GB | Ollama registry | Layers verified by digest |
| Language model | Qwen3 4B (`qwen3:4b`, default). On demand: Qwen3 8B (5.2 GB), 14B (9.3 GB) | 2.5 GB | Ollama registry | Layers verified by digest |
| Speech model | Whisper large-v3-turbo. On demand: large-v3 (3.1 GB), and on Apple silicon Parakeet v3 (2.5 GB, with `parakeet-mlx` from a hashed list that changes no package already installed) | 1.6 GB | Hugging Face | Fixed revision (a commit of the repository), downloaded once, then offline (`HF_HUB_OFFLINE=1`) |

About 4.8 GB in total on a clean Mac and 7 GB on Windows (estimates). An existing Ollama and Qwen3 model are reused. Optional models download only when you confirm in the app. The install page shows the exact minimum version and sizes for your system.

## Safeguards

- No `sudo`, no administrator rights, no change to system settings.
- One folder with owner-only permissions. Delete it to uninstall.
- The model server listens on `127.0.0.1` only, and the self test refuses any other address.
- The web interface is served on `127.0.0.1` only, behind a session key (HttpOnly, SameSite strict cookie), a Host check, a custom header on every change and a strict content security policy.
- Ask your notes: what a recording says is treated as data, never as an order. Passages are fenced in the request and cannot close their own tag, the model has no tool and no network, and its answer is shown as plain text, so a link or an image in it is never loaded. A citation that matches no passage is dropped. The conversation is kept in the page only, and the log keeps neither a question nor any text.
- A network guard refuses any outside connection in the app and the speech engine (connect, send, and name resolution through `getaddrinfo` and the `gethostbyname` family), except the daily version check, and a daily privacy check observes Cairn, the speech engine and the model server. Details: [docs/PRIVACY.md](docs/PRIVACY.md).
- Pocket vault: AES-256-GCM in 1 MiB chunks, one key per file derived with HKDF from a key that scrypt (N=131072, 128 MiB) derives from the password (10 characters at least; the vault header on the Pocket may not ask for more than that cost). Each chunk's position and an end marker are authenticated, so a file that was cut, reordered or extended is refused. The password is never stored; the key is kept only in the system keychain of a computer you trust. A recording on the Pocket is replaced only after the local copy was checked again, the encrypted copy read back and compared, and the recording found unchanged. The readable file is then overwritten with random bytes before it is deleted; on a flash drive this is best effort, because the drive may keep blocks it moved on its own. A vault is never replaced by another: a header that cannot be read blocks a new one.
- Audio files added by hand: received as a stream and written under a temporary name, capped at 4 GiB, hashed on the way, checked against the first bytes of the declared type, named after a sanitized file name (never a path), kept once if already present, and sealed on arrival when the lock is on. The request passes the same guards as any change (session cookie, Host check, `X-Cairn` header, `application/octet-stream`).
- App lock and encryption at rest: one random 256-bit data key seals notes, settings, voiceprints, the search index and recordings with AES-256-GCM. Small files carry a random 96-bit nonce and their relative path as authenticated data, so a sealed note cannot be moved under another name. Recordings use 1 MiB blocks under a per-file key (HKDF-SHA256 from the data key and a random file id), with the block position, the last-block flag and the declared size authenticated; a file that was cut, extended or reordered is refused. The data key sits in `lock.json` wrapped twice with AES-256-GCM, under keys derived by scrypt (N=131072, r=8, p=1) from the password (10 characters or more) and from a 128-bit recovery phrase shown once; the password is never stored. Locked, the data key is not in memory and the API answers 423 to everything but the unlock routes; wrong tries slow down; the idle lock never fires during a job. Turning the lock on or off, and the sealing of files already on disk, replace each file only after the new copy was read back and matched, and resume after a stop. Touch ID (macOS) asks the system to confirm the owner before a keychain copy of the key is read.
- The menu bar item (macOS) is a separate local process that talks to the server with the page's own session key, on `127.0.0.1` only, and shows no note text.
- Checks on every change: shell and Python static analysis, secrets scan, and a full install test on macOS and Windows.

## How it is checked

An internal review, not a third-party audit.

- **Automated, on every change:** unit and end-to-end tests with a stub speech engine and model server, a test that loads and drives the page script, shell and Python static analysis (shellcheck, bandit), a scan for secrets and personal paths, and a complete install and application test on macOS and Windows.
- **Reviewed by hand and by test:** the local API (session, Host check, change header, content security policy), the audio of a note served to the page only as an audio file listed in that note, by byte ranges, path handling on the Pocket (links are not followed), escaping of every export format, the update check, the installers and their downloads, the response to a disconnected Pocket, a stopped model server, a full disk, a corrupted note and a deleted recording.
- **Accessibility:** automated checks (axe-core) on the main screens and a keyboard walk. A test with a screen reader has not been done.
- **Dependencies:** pinned by hash, watched by Dependabot. Open alerts and why they do not apply are listed below.

## Known limits

- The network guard works inside the Python processes of Cairn. A proxy set in the environment (`HTTPS_PROXY` pointing at this computer) would carry connections through that proxy, and programs it starts (ffmpeg, the model server, package installers) are outside it: the daily privacy check observes the real connections and reports them.
- Dependabot earlier reported `setuptools` and `mlx` advisories. The pinned list is built for macOS 14 and later (`mlx` 0.32); `torch` and `setuptools` now come only with speaker identification (below), and Cairn calls `torch` solely through the pyannote pipeline, never `torch.jit.script` directly.
- The Pocket battery reading (macOS) runs as a separate small program (Bluetooth only, read only), outside the in-program network guard. It opens no network connection, and the daily privacy check still covers the app and the speech engine. The optional Pocket status reading (firmware, state, storage, from your own session key) runs the same way, in its own small program, sending only the documented read commands.
- Speaker identification is off by default and optional. Installing its model is the one case where Cairn reaches the network beyond the daily version check: it installs `pyannote.audio` and its packages from a hashed list (PyPI) and downloads the model's weights from Hugging Face, using the token you provide, in a separate process outside the in-program network guard (the same pattern as installing a speech or summary model). Once installed, recognition runs fully offline.
- The vault protects recordings that sit on the Pocket, against someone who holds the Pocket. It does not protect against someone who holds the Pocket and knows the password, nor against malware on a computer where the key is trusted. File sizes and the number of recordings stay visible. A recording made since the last connection is plain until Cairn next sees the Pocket. The libraries it relies on are `cryptography` (AES-GCM, HKDF) and `keyring` (system keychain), installed with the other packages and pinned by hash.
- Voiceprints (optional) are biometric data: they stay in `voices.json` and in the notes, in the Cairn folder, as plain files protected by the owner-only permissions. Erasing a person, or everybody, from People removes them there and in the notes. Turning **Remember voices** off stops new ones but erases nothing by itself. There is no lockout after wrong vault passwords, only the cost of each try.
- A summary written by a language model can contain errors: the fidelity indicator catches invented numbers and names, not every mistake.
- Lock and encryption: a file that was stored in plain form before it was sealed may remain recoverable from free disk space (no overwrite can be promised on an SSD), so keep full disk encryption on. While a recording is transcribed, a plain copy exists in a private temporary file (`.tmp`, owner only) that is overwritten and removed afterwards, and the speech engine writes its text to a temporary folder for the same time. Exports saved in `Exports` are plain. Touch ID gates a keychain copy of the data key: a process running as you could read that copy without it, so the password and the sealed files are what protect against someone who holds the disk. File names, sizes and dates remain visible, and so does the number of notes. Recovery is possible only with the password or the phrase: lose both and the data is gone.
- Anyone who can run programs as you on this computer while Cairn is open can read your notes: Cairn protects against the network, other web pages and, with the lock on, a disk or backup taken away, not against a compromised account.

## Read before you run

Piping a script into a shell means trusting it. To read it first:

```
curl --proto '=https' --tlsv1.2 -fsSLO https://raw.githubusercontent.com/yanickimhof/cairn_pocket_ai/v0.7.0/install.sh
less install.sh
bash install.sh
```

`install.ps1` can be read and run the same way.

## Limits

Cairn trusts its upstream components (uv, Ollama, the models and their publishers): review their security notices for your own risk assessment. Protect your data folder with full disk encryption.

## Known dependency advisories

A pip-audit of each locked, hash-pinned list (Apple silicon, Intel Mac, Windows, and the lists for speaker identification and Parakeet), run on 2026-10-31, reported no known advisory. The lists are rebuilt when an advisory appears; `cryptography`, which now protects your data at rest, is held at 50 or later for that reason.
