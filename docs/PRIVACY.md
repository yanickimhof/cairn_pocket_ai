# Privacy and sovereignty

One rule: **your recordings never leave your computer.**

## What Cairn does

- Reads the audio files from your Pocket over USB and copies them to a folder you choose. It deletes on the Pocket only what you ask it to delete.
- Transcribes, titles and summarizes them on your computer, with models that run offline.
- On macOS, shows the Pocket battery when it can be read: about every two minutes Cairn looks for a nearby Pocket and reads the battery level it publishes over Bluetooth. It is read only: Cairn sends no command, pairs with nothing, changes nothing on the Pocket, and keeps no history. Bluetooth is a local radio link, not an internet connection. macOS asks for Bluetooth access the first time; if you refuse, nothing is shown and nothing else changes.
- Optionally, if you enter your own Pocket session key in Settings (Cairn never captures or asks for one on its own), also reads the firmware version, device state and storage used, the same way: three documented read commands, no write command, no pairing, nothing sent anywhere. Clearing the field removes the key for good.
- Optionally, if you turn on speaker identification and install its model, runs it fully offline on your computer: your own Hugging Face token is used only once, to download the model, and never sent anywhere afterward. The recording's audio is never sent anywhere either.
- Takes audio files you drop on the page and keeps them in `Audio/Imported`, on this computer, like any other recording.
- Optionally, if you turn on the lock, encrypts your notes, settings, search index and recordings on this computer with a key that only your password, your recovery phrase or (on a Mac) Touch ID can open. The password is never stored, and none of it goes anywhere. Exports you save are not encrypted.
- On macOS, shows a small menu bar item that talks to Cairn on this computer only and shows no text of a note. A notification says when notes are ready.
- Searches your notes, plays the recording of a note in your browser and lists your actions, all on your computer. Writing a follow-up email, suggesting tags and applying your own note templates use the same local model: the text of a note never goes anywhere else.
- Optionally, if you secure the Pocket, encrypts its recordings with a password you choose (AES-256, 10 characters or more). The password is never stored; on a computer you trust, the key derived from it is kept in the system keychain (macOS Keychain, Windows Credential Manager). Nothing about this goes anywhere.
- Optionally, if you install a search model, finds your notes by meaning and answers your questions about them. The model runs in your local model server and the index of your notes (`Index` folder) stays on this computer. The passages go to your local model server only. That model has no tool: it cannot open a file, a link or the network. The conversation lives in the page and is never written to disk or to the log: it is gone when you clear it or close Cairn.
- Optionally, if you turn on voice memory, keeps a voiceprint for each person you name: 256 numbers computed by the speaker model, not the audio and not the words. They stay in `voices.json` and in the notes on this computer, are used only to name the next recordings, and are erased with one click per person or for everybody (turning the option off does not erase them).
- Keeps the Pocket session key and the Hugging Face token, if you entered them, in `settings.json` in that folder (never sent back to the page, never logged). Stores everything in that folder: audio, transcripts, summaries, exports, tags, templates and vocabulary (in `settings.json`), plus, only if you use these options, `voices.json`, `vault-index.json` and `Index`.

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
| When you ask for it | An optional model or package download (Ollama registry or Hugging Face for models, a search model and Parakeet included; PyPI for the packages of speaker identification and Parakeet), after your confirmation. The referral link in **About** opens a website in your browser only if you click them; Cairn sends nothing and attaches nothing. |

The runtime sets `HF_HUB_OFFLINE=1` and `DO_NOT_TRACK=1`.

## The contact page

The project's contact page (docs/contact.html, on GitHub Pages) is a separate web page, not part of Cairn. It sends what you type through Formspree, a form service, from your browser, only when you press Send. Cairn never opens it by itself and attaches nothing.

## Sharing is your decision

Cairn offers export (Markdown, HTML) and copy with formatting. What you do with an exported note is up to you. **Open in the Mail app** hands the draft of a follow-up email to your mail program, which Cairn then has no part in: Cairn sends nothing itself. A button copies the doubtful passages of a transcript to your clipboard so you can have them checked elsewhere. That step is manual, optional and happens outside Cairn.

## Verify it yourself

1. Disconnect the Internet and run an import. It must work the same.
2. List open connections during processing: `lsof -i -n -P | grep -i -E "ollama|python"`. You should see only `127.0.0.1`.
3. Block all outgoing connections for Cairn and its models with a firewall.

Cairn also checks for you. Once a day, when idle, it runs a small local test and lists every connection that leaves this computer (expected: none). The shield next to **Local** shows the result: hover it for the date. The model server (Ollama) is a third party program: the check observes it but Cairn does not block it, so a firewall remains the absolute guarantee.

## Where your data lives

Under `~/Cairn` by default (audio, texts, exports). The audio folder can be changed in Settings. With the lock on, audio, texts, settings and the index are encrypted there; exports are not. Use full disk encryption too, in case the computer is lost or stolen: it also covers what was stored before the lock was turned on.

Deleting a recording in the app removes it from the Pocket and from this computer: the file on the Pocket (at its next connection if it is not connected), and the audio, transcript and summary on this computer. The Pocket has no protection of its own, so a file left on it can be read by anyone who holds the device, unless you secured it (below). Nothing is kept: deleting cannot be undone. Copies held by the Pocket cloud account and its apps are out of Cairn's reach (it makes no outside connection). Cairn writes to the Pocket only when you ask for it, by deleting a recording.

## Securing the Pocket

The **Secure my Pocket** button (next to the battery) encrypts the recordings left on the Pocket with a password. The shield is orange while some are readable or when the Pocket is locked here, and green once all are protected.

- **What a thief finds:** a file `.cairn-vault` (the salt and a check value, nothing secret) and files with random names. The name, the date, the length of speech and the content are inside the encrypted files. File sizes remain visible.
- **On your computer:** the key is in the system keychain, so recordings are decrypted by themselves when the Pocket is connected. On another computer with Cairn, the password is asked once (and you choose whether to trust that computer).
- **Safe by order:** each recording is first copied to this computer and verified, then encrypted, read back and compared, and only then replaced. If the Pocket is unplugged halfway, nothing is lost and the next connection finishes the work.
- **Limits, plainly:** a recording made since the last connection stays readable on the Pocket until it next connects to Cairn (turn on **Secure the Pocket on connection** to do it each time). Lose the password and the recordings still on the Pocket are lost; those already copied into Cairn are not affected. The copies on this computer are encrypted by Cairn only if you turn on the lock (see the guide); otherwise full disk encryption does that. The Pocket firmware and its apps know nothing of this, and a password guessed offline is protected only by its strength and the cost of the key derivation (scrypt), so choose a long one.
