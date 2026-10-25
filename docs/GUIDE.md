# Guide

## Importing and processing

- **Import:** as soon as the Pocket is connected, Cairn copies and verifies the new recordings and lists them as waiting. Nothing is transcribed until you decide. This can be turned off in Settings (**Import on connect**, on by default).
- **Pocket battery (macOS):** when a Pocket is on and in range, a small battery appears next to the Local badge: green from 50 %, orange from 20 %, red below, with a bolt while the Pocket is plugged in and not full (it does not publish its real charging state, so this follows the USB connection). The exact level is in its tooltip. Nothing is shown when the Pocket cannot be read, and there is no setting. Cairn only reads the level the Pocket publishes over Bluetooth: no pairing, no command, nothing leaves your computer. The Pocket accepts one Bluetooth connection at a time, so nothing shows while the Pocket app on your phone is connected to it (closing the app is not enough: switch the phone to airplane mode, or turn its Bluetooth off). macOS asks for Bluetooth access the first time.

### Pocket status (macOS, optional)

The battery above needs nothing from you. If you also want to see the Pocket's **firmware version**, **device state** and **storage used**, Settings has an optional field, **Pocket session key**, that unlocks this.

- **What the key is:** a 16-character key the Pocket's own vendor app uses to authenticate itself over Bluetooth. Cairn does not capture it, does not know how to, and will not try to: you obtain your own key yourself, with your own tools, outside Cairn (for example with the open-source [pocket-libre](https://github.com/shahcolate/pocket-libre) project, which documents how). Cairn only accepts a key you paste in, 16 characters, nothing more.
- **What Cairn does with it:** once set, Cairn sends your key once per reading, then exactly three documented read commands (firmware, device state, storage). Nothing else, ever: no clock is set, no Wi-Fi command is sent, no other command exists in this code path. You can check this yourself; `cairn/pocket_status_worker.py` is short and has no write command in it.
- **Where it lives:** the key stays in your local `settings.json`, like every other setting. It is never logged, never sent anywhere, and clearing the field in Settings removes it for good.
- **If it stops working:** the Pocket accepts one Bluetooth connection at a time, same as the battery above. A key that firmware update has invalidated, or one that never matched your device, will show as "rejected" rather than silently guessing.

### Speaker identification (diarization, optional)

Off by default. Settings has **Identify speakers**, plus **Hugging Face token** and a model under Models to turn it on.

- **What it adds:** each transcript line and the note itself can say who is speaking ("Speaker 1", "Speaker 2", …), from the local [pyannote](https://github.com/pyannote/pyannote-audio) model. Speakers are numbered by the order they first speak, not identified by name.
- **Setup, once:** install the diarization model from Settings > Models. It is gated on Hugging Face, so you need your own free account and a token (a **read-only, fine-grained** token is enough; paste it in Settings). The token is used only for this one download, never logged, and clearing the field removes it.
- **Afterward:** diarization runs fully on your computer, offline (the model is read from Cairn's own folder, with `HF_HUB_OFFLINE` set). Turning the feature off at any time stops it being used; the model stays installed until you remove it from Settings > Models.
- **Cost:** the first install pulls `pyannote.audio` (and PyTorch) into Cairn's own environment, a sizeable download done only when you turn this on, not part of the base install.
- **A failure here never fails the recording:** if diarization cannot run for any reason, the note is written exactly as before, without speaker labels.

- **Process:** the badge on the central button counts the recordings waiting. Press the button to process them all, newest first, or tap one recording to process it first. Settings, **Process automatically** (off by default), does it without your click; **Stop** then pauses it until new recordings arrive or you start a job yourself.
- **Skip:** leave a recording out of the queue; it can be put back.
- **Progress:** the central ring and the status line show the step (transcribing, then writing the note) with a percentage. On a long recording the note is written in several parts, so the percentage moves in steps and is smoothed in between.
- **Stop:** interrupts the current job.

## One note, one set of choices

Each recording has its own **level of detail** (short, standard, detailed), its own **language** (FR or EN, the interface language by default) and its own **type** (meeting, call, presentation, idea, note; chosen by the model). Tap a button on the note to change its choice: each tap moves to the next one. Your choices are kept.

On a finished note, **Redo** rewrites it with the choices you made and keeps your name and type. The audio is transcribed again only if you changed the speech model since the note was made; otherwise the transcript is reused, which takes seconds.

**Language of a recording:** the list shows the language heard in the audio (for example FR, or FR+EN when two languages are mixed; hover for the shares). The language button on a note (Auto, FR, EN) sets the language the speech engine should expect. Auto lets it detect the language. On a bilingual recording, choose the main language and press **Redo**: the audio is transcribed again with it.

The document icon opens the transcript in a window: doubtful passages are highlighted, and the confidence of the raw transcript is shown at the top.

## Reading the indicators

Each finished note shows up to three pills on its row, with an explanation on hover:

| Pill | Meaning |
|---|---|
| Check | **Fidelity of the note** to the transcript: the share of its numbers and names found in the transcribed text. Green from 90 %, amber from 75 %, red below. It catches invented details, not misheard words. A note with few numbers and names is measured on its key terms instead, and the tooltip says so. A grey dash means it cannot be measured, for instance when the note is in another language than the recording: redo the note in the recording's language to get a score. |
| Waveform | **Confidence of the raw transcript**, the speech engine's own estimate. It is deliberately cautious on spontaneous speech, so 55 to 70 % is common on a lively meeting and does not mean the note is poor. |
| Warning | Number of passages worth checking, when there are some. |

Both scores appear in the exports (Markdown, HTML, copy). Secure mode hides the list of notes until you reveal it.

## Deleting

The trash icon on a note deletes it for good, on the Pocket and on this computer: the file on the Pocket, and the audio, transcript and summary here. Cairn never reaches the Pocket cloud account or its apps: a recording kept there is yours to delete there. If the Pocket is not connected, its file is erased the next time it is. Exports already saved in `~/Cairn/Exports` are not touched. The Pocket has no protection of its own, which is why deleting there matters.

## Models

The default install is the smallest that gives good results: Whisper large-v3-turbo (1.6 GB) and Qwen3 4B (2.5 GB). On a French recording, smaller speech models misheard names and produced wrong actions, so Cairn does not offer them.

For sharper notes, open **Settings, Models**, pick a larger model (Qwen3 8B or 14B, Whisper large-v3), confirm the download, then press **Use**. Nothing downloads without your click, and a model can be removed from the same screen to free disk space. If Qwen3 8B is already in your Ollama, Cairn uses it. It never modifies your existing Ollama or models.

## Speed

The speech model stays loaded between recordings and is released after five idle minutes.

## Background mode and web app (macOS)

Cairn runs as a small background service that starts at login and restarts if it stops. If the page does not answer, open `Cairn.app` again, or run `~/Cairn/bin/cairn service restart` (`service uninstall` removes the background mode).

It is also an installable web app: Chrome, Install Cairn; Safari, File, Add to Dock. It then opens in its own window, still served from your computer.

## "Not secure" in the address bar?

Cairn is served over plain `http` on `127.0.0.1`, an address that exists only inside your computer. Nothing travels over a network, so there is nothing to intercept, and browsers treat it as trustworthy. Chrome still labels any `http` page "not secure". Switching to `https` would mean installing a certificate authority on your computer, which weakens your security far more than this label does, so Cairn does not do it. The installed web app has no address bar.
