# Roadmap

## v0.2.1: done

- Personal vocabulary for rare names and places: close variants are corrected in the transcript, the summary is told the spelling, every correction is listed on the note and reversible
- A failed recording is retried by itself a few times only, with a growing delay, and a transcript or speaker pass already made is never redone
- The summary model is checked before any long work, so a problem shows in seconds and not after a transcription; a speech engine that stops moving is cut off; the computer is kept awake during a job (macOS)
- The time spent in each step is kept with the note and logged, without any content
- Faster: automatic processing starts as soon as the copy is done and checks are more frequent. Stop now ends a speaker pass at once. (Running the speaker pass during the transcription was measured on an M4 with 16 GB: 94 s against 98 s one after the other, with 1.4 GB more swap, so it is not done: the graphics chip is the shared limit.)
- Models and About show what is really installed on this computer: real sizes, installed and running Ollama versions, correct model names
- Speaker rediarization and renaming
- Processing one recording no longer carries on with the whole queue when automatic processing is off
- Speaker identification works with pyannote 4, which returns its result in a different shape and made every pass fail at the end
- Speaker identification runs on the Mac's graphics chip when there is one (4.5 times faster in a measurement on an M4, identical result), with a setting to use the processor instead
- A recording interrupted while identifying speakers goes back to waiting at the next start, instead of showing the spinner for ever
- A model that cannot give structured output with the Ollama now running is named as such, instead of "model server not reachable"

## v0.2: done

- Optional Pocket status (firmware, device state, storage used), read only, from your own session key
- Optional speaker identification (diarization), fully local, with the model installed on demand
- Fixed the installer's default reference, still pinned to v0.1.0 right after v0.2.0 shipped, which made the standard install command reinstall the old version; the install page ([docs/index.html](index.html)) and SECURITY.md had the same stale pin and are fixed too

## v0.1: done

- One-command installer for macOS and Windows, with a self test
- Pocket detection (green dot connected, orange dot not detected)
- Resumable import with byte-for-byte verification
- Local transcription with two indicators per recording: raw transcript confidence and note fidelity
- Title, TL;DR, actions, key points
- Automatic templates (meeting, call, presentation, idea, other)
- Level of detail and language chosen per recording, redo a note at another level
- Rename, copy, export (Markdown, HTML)
- Pocket battery level over Bluetooth (macOS, read only, shown when readable)
- Light default install, larger models on demand, removable from the app
- Process one recording, skip or restore, stop, newest first
- Secure mode (list hidden by default), FR/EN interface
- One delete on the Pocket (at its next connection if needed) and this computer, irreversible
- Automatic copy of new recordings when the Pocket is connected (on by default, no processing), and an optional automatic processing of the queue (off by default)
- Component list and daily update check (one request to GitHub, can be turned off)
- Network guard and automatic daily privacy check
- Background mode and installable web app (macOS)

## Later

- Linux
- Update the speech engine (MLX) to its latest version: the pinned package list has to be rebuilt for macOS 14
- Test with a screen reader
- A list of components (SBOM) with each release
- Offline installation for computers without Internet access
- Import from any folder of audio files
- More interface and transcript languages
