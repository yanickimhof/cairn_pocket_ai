# Guide

## Importing and processing

- **Import:** as soon as the Pocket is connected, Cairn copies and verifies the new recordings and lists them as waiting. Nothing is transcribed until you decide. This can be turned off in Settings (**Import on connect**, on by default).
- **Pocket battery (macOS):** when a Pocket is on and in range, a small battery appears next to the Local badge: green from 50 %, orange from 20 %, red below, with a bolt while the Pocket is plugged in and not full (it does not publish its real charging state, so this follows the USB connection). The exact level is in its tooltip. Nothing is shown when the Pocket cannot be read, and there is no setting. Cairn only reads the level the Pocket publishes over Bluetooth: no pairing, no command, nothing leaves your computer. The Pocket accepts one Bluetooth connection at a time, so nothing shows while the Pocket app on your phone is connected to it (closing the app is not enough: switch the phone to airplane mode, or turn its Bluetooth off). macOS asks for Bluetooth access the first time.

### Pocket status (macOS, optional)

The battery above needs nothing from you. If you also want to see the Pocket's **firmware version**, **device state** and **storage used**, Settings has an optional Pocket session key (the Bluetooth icon, below the voice and people rows) that unlocks this: a plus to add one, a green check once it is set (hover it for the details), a warning if it is rejected.

- **What the key is:** a 16-character key the Pocket's own vendor app uses to authenticate itself over Bluetooth. Cairn does not capture it, does not know how to, and will not try to: you obtain your own key yourself, with your own tools, outside Cairn (for example with the open-source [pocket-libre](https://github.com/shahcolate/pocket-libre) project, which documents how). Cairn only accepts a key you paste in, 16 characters, nothing more.
- **What Cairn does with it:** once set, Cairn sends your key once per reading, then exactly three documented read commands (firmware, device state, storage). Nothing else, ever: no clock is set, no Wi-Fi command is sent, no other command exists in this code path. You can check this yourself; `cairn/pocket_status_worker.py` is short and has no write command in it.
- **Where it lives:** the key stays in your local `settings.json`, like every other setting. It is never logged, never sent anywhere, and clearing the field in Settings removes it for good.
- **If it stops working:** the Pocket accepts one Bluetooth connection at a time, same as the battery above. A key that firmware update has invalidated, or one that never matched your device, will show as "rejected" rather than silently guessing.

### Speaker identification (diarization, optional)

Off by default. Settings has the Hugging Face token (above the voice and people rows): a plus to add one, and once set, a pencil to edit it next to an On/Off toggle that turns speaker identification on or off.

- **What it adds:** each transcript line and the note itself can say who is speaking ("Speaker 1", "Speaker 2", …), from the local [pyannote](https://github.com/pyannote/pyannote-audio) model. Speakers are numbered by the order they first speak; you give them names, and with voice memory Cairn can name a known voice by itself.
- **Setup, once:** paste your Hugging Face token in Settings, then install the diarization model from Settings > Models (a **read-only, fine-grained** token is enough). The model is gated: on huggingface.co, while signed in with the account the token belongs to, accept the access conditions on both [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) and [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) (the pipeline loads the second one as a dependency; skipping it fails the install with the same "restricted" error). The token is used only for this one download, never logged, and clearing the field removes it.
- **Afterward:** diarization runs fully on your computer, offline (the model is read from Cairn's own folder, with `HF_HUB_OFFLINE` set). Turning the feature off at any time stops it being used; the model stays installed until you remove it from Settings > Models.
- **Cost:** the first install pulls `pyannote.audio` (and PyTorch) into Cairn's own environment, a sizeable download done only when you turn this on, not part of the base install.
- **Speed:** on a Mac with Apple silicon, speaker identification runs on the graphics chip, 4.5 times faster in a measurement on an M4, with the same result. Once it is on and its model installed, a GPU or CPU button on that row switches to the processor.
- **A failure here never fails the recording:** if diarization cannot run for any reason, the note is written exactly as before, without speaker labels.
- **People:** Settings, **People** lists everyone named across your notes, with their notes and speaking time. The pencil renames a person in every note at once; typing the name of someone who already exists merges the two. Notes that still have unnamed speakers are listed below, to be reviewed. Names already written in a summary change when the note is written again.
- **Voice memory (optional):** Settings, **Remember voices** (with speaker identification on). Cairn then keeps a voiceprint of each person you name, and names the same voice in later recordings by itself, marked with a small sign you can correct. Run speaker identification again on a note to name it from the voices known. A voiceprint is 256 numbers, kept on this computer; the trash in **People** erases one person's, or everybody's.
- **Naming speakers:** open a note's transcript (the document icon) to see **Speakers detected**, one chip per speaker; tap its pencil to give it a real name. The name replaces the label everywhere for that note: the transcript, the HTML export and the copy for an email.
- **Older recordings:** a note made before this feature was installed, or before it was turned on, keeps no speaker labels: redoing the note only rewrites the summary, it does not retranscribe or diarize. Open such a note and press **Rediarize** (next to Redo, shown once the model is installed) to add speaker labels to its existing transcript, without a new transcription or a new summary. Rediarizing clears any names already given, since a fresh pass may not number the speakers the same way.

- **Process:** the badge on the central button counts the recordings waiting. Press the button to process them all, newest first, or tap one recording to process it first. Settings, **Process automatically** (off by default), does it without your click; **Stop** then pauses it until new recordings arrive or you start a job yourself.
- **Skip:** leave a recording out of the queue; it can be put back.
- **Progress:** the central ring and the status line show the step (transcribing, identifying speakers, writing the note), and the recording being processed has its own blue progress line, with a percentage when one is known. On a long recording the note is written in several parts, so the percentage moves in steps and is smoothed in between.
- **Stop:** interrupts the current job at once, speaker identification included.
- **If something fails:** a recording is tried again by itself, up to three attempts in all, after 5 then 10 minutes, and a transcript or speaker pass already made is never redone. Before any long job Cairn checks that the summary model answers, so a missing or incompatible model shows within seconds. A speech engine that stops moving for five minutes is cut off. On macOS the computer stays awake while a job runs. The note shows the reason, and **Process** tries it again.

## Securing the Pocket

The shield with a padlock, between the battery and the search, encrypts the recordings on the Pocket with a password, so that nobody who plugs it into another computer can read them. The shield, between the battery and the search, tells the state: orange while some recordings are readable or when the Pocket is locked on this computer, green once all are protected, grey when it is not connected. Hover it for the details.

- **First time:** with the Pocket connected, tap the shield, choose a password (10 characters or more, a long phrase is better), confirm it, and tap the check. Cairn copies what is new, checks each copy, then encrypts the recordings on the Pocket one by one. Imports and notes carry on as usual meanwhile.
- **Trust this computer:** the key is kept in the system keychain, so recordings are decrypted by themselves each time the Pocket is connected. Without it, the password is asked once per session.
- **Each time the Pocket is connected:** **Secure the Pocket on connection** (in the panel and in Settings) copies and encrypts new recordings as soon as the Pocket is plugged in. Without it, tap the shield after recording.
- **On another computer with Cairn:** the shield is orange. Tap it, type the password, and the recordings come in. Tick **Trust this computer** only for your own.
- **Forget the password here:** the trash in the panel removes the key from this computer's keychain.
- **Keep in mind:** a recording made since the last connection is readable on the Pocket until Cairn next sees it, and a lost password means the recordings left on the Pocket are lost. Those already in Cairn are safe. Details: [PRIVACY](PRIVACY.md).

## Tags

Tags are free words you give to notes to find them again: a project, a person, a topic. A note can have up to 12, and they stay with it when it is redone.

- **Add:** the tag icon on a note opens a field. Type a word and press Enter: the tags you already use are offered as you type. Tap a tag's cross to remove it.
- **Several notes at once:** in **Choose notes** (under the vocabulary in Settings), tick the notes, type a tag in the bar and tap the tag icon.
- **Find:** the tags of your notes appear as buttons above the list: tap one to show only those notes, tap it again to lift the filter. In the search, `#apollo` lists the notes tagged apollo, and `#apollo budget` searches the word budget among them. A tag is also found as a word.
- **Suggestions:** Settings, **Suggest tags** (off by default). After each note, Cairn offers up to three of your existing tags that fit, with one more call to the model. They show dashed, with a plus: tap one to add it, or the cross to ignore them all. Cairn never creates a tag you did not write.
- **Exports:** the tags appear with the date in Markdown and text (`#apollo`, spaces become dashes) and as chips in HTML.

## Your own note templates

Settings, **My note templates** (the plus) creates a template: a name and an instruction in everyday words, for example *Client report: goals, decisions, risks, next steps*. The summary model writes the note as the sections your instruction names, in that order, after the TL;DR and the actions. A section the recording says nothing about shows a dash: nothing is invented. The sections appear in the note and in every export.

- **On a note:** the template button (the second one, next to the pencil) goes through the built-in types, then through your templates. Choosing one of yours writes the note again with it, and the template is kept if the note is redone. Its name replaces the type in the exports.
- **Editing:** tap the pencil next to a template, or its name, to change it. The field under the instruction reminds you how to write one: name the sections you want, in order, and the note gets a TL;DR, the actions, then one section per name.
- **The star** makes a template the one used for every new note that has no choice of its own. Tap it again to go back to the automatic type.
- **Editing or deleting** a template does not change the notes already written with it.

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

## Finding, listening, following up

- **Search:** the magnifier in the header searches the title, the summary and the transcript of every finished note, without regard to accents. Every word you type must be there. Each result shows the lines found with your words marked: a transcript line opens the transcript at that moment, the others open the note. Secure mode hides the search like it hides the list.
- **Related passages:** with a search model installed (Settings, **Models**, Search by meaning), a pause in typing adds **Related passages** below the usual results: the lines that answer a question even when the words differ. The model runs in your local model server and the notes are read once, in the background.
- **Ask your notes:** with the same search model, type a question in the magnifier and press Enter (or tap the speech bubble). Cairn finds the passages that answer it, by meaning and by words, so a name, a figure or an acronym is found too, adds the lines before and after each one, and gives only those passages to your summary model, which writes a short answer. Every statement carries a number: tap it, or the matching source below the answer, to open the note at that minute. A number that does not match a passage is dropped. If nothing in your notes comes close to the question, Cairn says so and does not wake the model.
  - **Follow up:** the box empties after each question, ready for the next one: "and who tells the client?" is understood from what came before. The last three exchanges are kept, in the page only: the trash icon starts over, and closing Cairn clears them. Nothing is written to disk.
  - **What is still open?** A question about actions, to-dos or decisions is answered at once, with no model to wait for: the list is read from the summaries of your most recent notes, newest first, up to 30 lines, each with its source number. Only the open actions are listed; ask for the ones that are "done" to see them too, marked with a tick. When there are more, the last line says how many are left. A question that says "today", "this week", "this month" or "the last 30 days" (in English or French) looks only at that period.
  - **Narrow it down:** the two menus under the box limit a question to the last 7, 30 or 90 days, or to one tag.
  - **Speed:** the first question after a pause takes longer while the model loads, so Cairn loads it as you start typing. After that, the first word comes in a few seconds on a 16 GB Apple silicon Mac with Qwen3 8B. Qwen3 4B is quicker and a little less precise. The answer appears as it is written, and the cross stops it.
  - **Limits:** an answer is drawn from at most six passages, so a question about everything ("summarise my month") is better served by the list of actions or by a single note. A language model can be wrong: check the passage behind a statement that matters.
- **Listen:** when the recording is still on this computer, the transcript window has a player. Tap a time stamp to play from that line. The lines to check are highlighted, so a doubtful word is verified in seconds.
- **Correct a passage:** in the transcript window, the pencil beside a line opens it for editing. The check (**Only here**) changes that line; the arrows (**Always**) also adds a rule to the vocabulary from what you changed, tied to nearby words when the changed word is short, and writes the other notes again. A line corrected by hand is kept when the vocabulary changes.
- **All my actions:** the checklist icon lists the actions of every finished note, grouped by person, newest note first. Tick one when it is done: the tick is kept with its note. Tap the text of an action to correct it (the action, who, when), or use the trash to delete it after a confirmation: the change is made in the note itself, so its summary and its exports show it too. If the note is redone, its summary is written again and your corrections are replaced. The copy button copies the open actions as text. If a note is redone and the wording of an action changes, it shows as open again.
- **Follow-up email:** the envelope on a note writes a short email from its summary, in the language of the note, with the summary model. The draft is kept with the note: copy it, open it in your mail app, or write it again. Cairn never sends anything.

## Audio files

The icon at the top, or a drop anywhere on the page, adds `.wav`, `.mp3`, `.m4a`, `.opus`, `.ogg` and `.flac` files, with or without a Pocket. A file is checked by its first bytes, not by its name; the same recording added twice is kept once. Files go to `Audio/Imported` and wait like Pocket recordings. Deleting one of these notes never touches a Pocket.

## First steps

On a first launch with no note, and from **About**, a list shows what Cairn needs: the speech model, the model server and notes model, ffmpeg, memory, disk space and the Pocket. Each missing item says what to do. The Pocket is advisory: with no Pocket, add audio files. A drive that looks like a Pocket but shows no recordings usually means USB Mode (Web Sync) is off.

## Lock and encryption

**Settings, Lock.** Choose a password of 10 characters or more. Cairn shows a recovery phrase once: write it down away from this computer. Without the password or the phrase, the data cannot be read: there is no other way in.

- **What is sealed:** notes, settings (including the vocabulary and any token), voiceprints, the search index and every recording, with AES-256-GCM. Recordings are sealed in 1 MiB blocks, so playing from any time stamp opens only the blocks it needs.
- **When it locks:** at start, when you press the lock icon, and after the idle time you choose (5, 15 or 60 minutes, or never). Idle time counts from what you do, not from the page refreshing itself, and Cairn never locks while a job runs. Locked, the page answers nothing but the password.
- **Touch ID (Mac):** it confirms you are there before the key is read from the keychain. It does not replace the password: choose one, and use Touch ID for the daily opening. If Settings says the component is missing, update Cairn.
- **Password and phrase:** both can be changed in Settings; a new phrase replaces the old one and the password is asked again. Turning the lock off decrypts everything again.
- **Turning it on** seals what is already there, file by file, each only after the sealed copy was read back and matched; it can be stopped and resumes. Recordings that arrive later are sealed on arrival.
- **Limits:** a file that was in plain form before may remain recoverable from free disk space, so keep full disk encryption on. While a recording is being transcribed, a plain copy exists in a private temporary file that is overwritten and removed afterwards. Exports you save in `Exports` are plain. Malware running as you while Cairn is open can read what you can. Lose the password and the phrase, and the data is gone.

## Test bench

`cairn bench` measures the speech models you have installed on your own recordings: speed, memory, the model's own confidence, the share of French and English, and how much the models disagree. Run it from the Cairn folder:

```
~/Cairn/bin/cairn bench                      # your three latest recordings
~/Cairn/bin/cairn bench talk.m4a --max 1      # a file of your choice
```

Place a text next to a file (`talk.m4a.ref.txt`) and its difference from that text is added. The report is written to `~/Cairn/Exports/bench-DATE.md` and holds numbers only, never a word of a recording. With the lock on, the recordings are sealed: name the files.

## Deleting

The trash icon on a note deletes it for good, on the Pocket and on this computer: the file on the Pocket, and the audio, transcript and summary here. Cairn never reaches the Pocket cloud account or its apps: a recording kept there is yours to delete there. If the Pocket is not connected, its file is erased the next time it is. Exports already saved in `~/Cairn/Exports` are not touched. The Pocket has no protection of its own, which is why deleting there matters.

## Models

The default install is the smallest that gives good results: Whisper large-v3-turbo (1.6 GB) and Qwen3 4B (2.5 GB). On a French recording, smaller speech models misheard names and produced wrong actions, so Cairn does not offer them.

**Parakeet v3** (2.5 GB, Apple silicon only) is offered as an optional speech model. It is much faster on a recording in one language, but it cannot be told which language to hear and may drift on a recording that mixes two: Whisper stays the default. Installing it adds a small set of pinned packages from a hashed list and changes none of those already installed. Use `cairn bench` to compare on your own recordings.

For sharper notes, open **Settings, Models**, pick a larger model (Qwen3 8B or 14B, Whisper large-v3), confirm the download, then press **Use**. Nothing downloads without your click, and a model can be removed from the same screen to free disk space. If Qwen3 8B is already in your Ollama, Cairn uses it. It never modifies your existing Ollama or models.

**Search by meaning** is optional: Qwen3 Embedding 0.6B (0.6 GB) or BGE-M3 (1.2 GB, many languages). Install one and your notes are indexed in the background; remove it and the index is deleted. It also powers **Ask your notes**.

## Names and places

Rare names and places are the speech engine's weak spot, and the summary then repeats the error. In **Settings, Vocabulary**, list them, one per line.

- A name on its own, such as `Brandt`: a word that sounds close to it in the transcript is written as listed (`Brant` becomes `Brandt`). Cairn leaves alone a different name (`Laurence` is not turned into `Laurent`) and common words.
- An exact rule, such as `Brant => Brandt` (`->` and `:` work too): that word is always replaced. Use it for an error that keeps coming back.
- Several spellings, one right word: `Brant, Brand, Brandh => Brandt`. In a rule, commas separate the spellings to replace; a phrase such as `Open Day => BRANDT Day` works too, whatever the case.
- A rule that applies only in a context, for a spelling that is also a real word: `Open Day => BRANDT Day | awards, ceremony`. The words are replaced only when one of the words after the bar is spoken in the same line or in the two lines before and after. A genuine open day elsewhere is left alone.
- **Words to check:** the list icon beside the vocabulary (with a count) shows names written several ways across your notes and names the speech engine was unsure of. Type the right spelling, add words that must be nearby if the spelling is also a real word, and save: the rule is added and the notes that need it are written again. Ignore a word to stop seeing it.
- The summary is also told the spelling to use.
- Every correction is listed under the note, and the original word is kept: removing an entry puts it back. Keep entries distinctive: if you speak of both Brant the town and Brandt the association, use an exact rule only where it is safe.
- A new vocabulary applies to recordings processed afterwards. Under the vocabulary, Cairn says how many finished notes still use an older one. **Update all** brings them up to date and writes again only the notes whose words the vocabulary changes. **Choose notes** lets you tick the notes to update, and a range of dates does the same: those are always written again. The transcript and the speakers are kept, the words are corrected and the summary is rewritten, about half a minute per note. The redo button of a single note does the same.

## Speed

The speech model stays loaded between recordings and is released after five idle minutes. On a computer with less than 24 GB of memory it is released right after each transcription, so the speaker pass and the summary have the memory they need.

## Background mode and web app (macOS)

Cairn runs as a small background service that starts at login and restarts if it stops. If the page does not answer, open `Cairn.app` again, or run `~/Cairn/bin/cairn service restart` (`service uninstall` removes the background mode).

It is also an installable web app: Chrome, Install Cairn; Safari, File, Add to Dock. It then opens in its own window, still served from your computer.

## "Not secure" in the address bar?

Cairn is served over plain `http` on `127.0.0.1`, an address that exists only inside your computer. Nothing travels over a network, so there is nothing to intercept, and browsers treat it as trustworthy. Chrome still labels any `http` page "not secure". Switching to `https` would mean installing a certificate authority on your computer, which weakens your security far more than this label does, so Cairn does not do it. The installed web app has no address bar.
