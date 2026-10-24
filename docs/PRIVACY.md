# Privacy and sovereignty

Cairn is built on one rule: **your recordings never leave your computer.**

## What Cairn does

- Reads the audio files from your Pocket over USB and copies them to a folder you choose.
- Transcribes, cleans, titles and summarizes them on your computer, with models that run offline.
- Stores everything in that folder: audio, transcripts, summaries, exports.

## What Cairn never does

- No cloud service, no account, no sign-in.
- No telemetry, analytics or crash reports.
- No call to a hosted AI service.
- The Cairn interface is a local page served on `127.0.0.1` only, with a one-time session key, a Host check and a strict content policy. Exports are saved in `~/Cairn/Exports`. The only optional outgoing request is the update check you trigger yourself (one request to GitHub).
- No listening on the network: the local model server is bound to `127.0.0.1`. This address means "this computer only" (also called localhost), so no other device can reach it.

## Network use

| When | Connections |
|---|---|
| Installation (once) | Downloads of the engines and models (see SECURITY.md) |
| Everyday use | None |

Runtime is configured with `HF_HUB_OFFLINE=1` and `DO_NOT_TRACK=1`.

## Sharing is always your decision

Cairn gives you export (Markdown, HTML) and copy with formatting. What you do with an exported note is up to you. Cairn also offers a button that copies the doubtful passages of a transcript to your clipboard, so that you can have them checked elsewhere if you choose. That step is manual, optional and happens outside Cairn.

## Verify it yourself

1. Disconnect the Internet and run an import. It must work the same.
2. List open connections during processing: `lsof -i -n -P | grep -i -E "ollama|python"`. You should see only `127.0.0.1`.
3. Use a firewall to block all outgoing connections for Cairn and its models.

A built-in check that confirms the absence of outgoing connections is planned (see the roadmap). Until it ships, treat the points above as the way to verify.

## Where your data lives

Everything is stored under `~/Cairn` by default (audio, texts, exports). You can change the audio folder in the settings. Use full disk encryption to protect it if the computer is lost or stolen.

Delete a recording from the app and its local files are removed. Emptying the Pocket is a separate action that is only offered once every copy is verified.
