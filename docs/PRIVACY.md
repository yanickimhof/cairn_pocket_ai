# Privacy and sovereignty

One rule: **your recordings never leave your computer.**

## What Cairn does

- Reads the audio files from your Pocket over USB and copies them to a folder you choose. It deletes on the Pocket only what you ask it to delete.
- Transcribes, titles and summarizes them on your computer, with models that run offline.
- On macOS, shows the Pocket battery when it can be read: about every two minutes Cairn looks for a nearby Pocket and reads the battery level it publishes over Bluetooth. It is read only: Cairn sends no command, pairs with nothing, changes nothing on the Pocket, and keeps no history. Bluetooth is a local radio link, not an internet connection. macOS asks for Bluetooth access the first time; if you refuse, nothing is shown and nothing else changes.
- Optionally, if you enter your own Pocket session key in Settings (Cairn never captures or asks for one on its own), also reads the firmware version, device state and storage used, the same way: three documented read commands, no write command, no pairing, nothing sent anywhere. Clearing the field removes the key for good.
- Optionally, if you turn on speaker identification and install its model, runs it fully offline on your computer: your own Hugging Face token is used only once, to download the model, and never sent anywhere afterward. The recording's audio is never sent anywhere either.
- Stores everything in that folder: audio, transcripts, summaries, exports.

## What Cairn never does

- No cloud service, no account, no sign-in.
- No telemetry, analytics or crash reports.
- No call to a hosted AI service.
- No listening on the network. The interface and the model server answer on `127.0.0.1` only (this computer), so no other device can reach them. Technical safeguards: [SECURITY.md](../SECURITY.md).

## Network use

| When | Connections |
|---|---|
| Installation (once) | Downloads of the engines and models (see [SECURITY.md](../SECURITY.md)) |
| Everyday use | One request a day to GitHub to look for a new version (nothing about you is sent; turn it off in **Settings, Check for updates**) |
| When you ask for it | An optional model download (Ollama registry or Hugging Face), after your confirmation. The referral link in **About** opens Pocket's website in your browser only if you click it; Cairn sends nothing. |

The runtime sets `HF_HUB_OFFLINE=1` and `DO_NOT_TRACK=1`.

## Sharing is your decision

Cairn offers export (Markdown, HTML) and copy with formatting. What you do with an exported note is up to you. A button copies the doubtful passages of a transcript to your clipboard so you can have them checked elsewhere. That step is manual, optional and happens outside Cairn.

## Verify it yourself

1. Disconnect the Internet and run an import. It must work the same.
2. List open connections during processing: `lsof -i -n -P | grep -i -E "ollama|python"`. You should see only `127.0.0.1`.
3. Block all outgoing connections for Cairn and its models with a firewall.

Cairn also checks for you. Once a day, when idle, it runs a small local test and lists every connection that leaves this computer (expected: none). The shield next to **Local** shows the result: hover it for the date. The model server (Ollama) is a third party program: the check observes it but Cairn does not block it, so a firewall remains the absolute guarantee.

## Where your data lives

Under `~/Cairn` by default (audio, texts, exports). The audio folder can be changed in Settings. Use full disk encryption in case the computer is lost or stolen.

Deleting a recording in the app removes it from the Pocket and from this computer: the file on the Pocket (at its next connection if it is not connected), and the audio, transcript and summary on this computer. The Pocket has no protection of its own, so a file left on it can be read by anyone who holds the device. Nothing is kept: deleting cannot be undone. Copies held by the Pocket cloud account and its apps are out of Cairn's reach (it makes no outside connection). Cairn writes to the Pocket only when you ask for it, by deleting a recording.
