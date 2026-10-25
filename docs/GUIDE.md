# Guide

## Importing and processing

- **Import:** as soon as the Pocket is connected, Cairn copies and verifies the new recordings and lists them as waiting. Nothing is transcribed until you decide. This can be turned off in Settings (**Import on connect**, on by default).
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

The trash icon on a note deletes it everywhere, for good: the file on the Pocket, and the audio, transcript and summary on this computer. If the Pocket is not connected, its file is erased the next time it is. Exports already saved in `~/Cairn/Exports` are not touched. The Pocket has no protection of its own, which is why deleting there matters.

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
