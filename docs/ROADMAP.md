# Roadmap

## v0.2: done

- Optional Pocket status (firmware, device state, storage used), read only, from your own session key
- Optional speaker identification (diarization), fully local, with the model installed on demand

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
