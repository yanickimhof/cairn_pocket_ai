# Release notes

## 0.3.0: faster, steadier, and it learns your names

**Your names, finally spelled right**
- Tell Cairn the people, places and terms Whisper keeps getting wrong. It fixes them in the transcript and in the summary, and lists every change so you can undo it.

**Speed you feel**
- **Speakers identified 4.5 times faster.** Your Mac's graphics chip does the work, same result. One button goes back to the processor.
- **Starts the moment the copy ends.** No waiting, no clicking.
- **Made for a 16 GB Mac.** The speaker pass takes 22 seconds instead of 82.

**Walk away, it finishes**
- **The Mac stays awake** until your notes are ready.
- **A failed recording tries again by itself,** and never redoes what is already done.
- **A problem shows in seconds, not after an hour.** The summary model is checked before any long job, and a frozen engine is cut off.
- **Stop means stop,** and an interrupted recording goes back to waiting instead of spinning for ever.

**Fix who said what, afterwards**
- Redo the speakers of a finished note and rename them. Speaker identification also works with pyannote 4, where every pass used to fail at the very end.

**Honest about your machine**
- Models and About show what is really installed: real sizes, the Ollama version installed and running, the right names.
- A model that cannot give structured output is named as such, and Qwen3.5 9B waits until Ollama supports it.
- Each note keeps how long every step took, never its content.
- Processing one recording no longer launches the whole queue when automatic processing is off.
- Identifying speakers during the transcription saved 4 seconds and cost 1.4 GB of swap, so Cairn does not do it.

## 0.2: who said what

- **Know your Pocket.** Firmware, state and storage used, read only, from your own session key.
- **Who said what.** Speakers told apart on your computer, with the model installed only when you want it.
- **The install command installs the right version.** The default reference no longer points at the old release, on the command, the install page and SECURITY.md.

## 0.1: the first stable release

- **Install with one command** on macOS and Windows, with a self test.
- **Plug in, see it.** A green dot when the Pocket is connected, orange when it is not detected.
- **An import you can trust.** Resumable, verified byte for byte.
- **Transcripts with two scores.** Raw confidence and note fidelity on every recording.
- **Notes that get to the point.** Title, TL;DR, actions and key points, with the template (meeting, call, presentation, idea, other) chosen for you.
- **Your level of detail, your language.** Set per recording, and redo a note at another level.
- **Out in one click.** Rename, copy, export in Markdown or HTML.
- **Battery level** of the Pocket over Bluetooth on macOS.
- **Light to install, big when you want.** Larger models on demand, removable from the app.
- **Full control of the queue.** Process one recording, skip, restore or stop, newest first.
- **Secure mode and FR/EN.** The list is hidden by default.
- **One delete, gone everywhere.** From the Pocket (at its next connection if needed) and from this computer.
- **Copies by itself.** New recordings are copied when the Pocket connects. Automatic processing is optional and off by default.
- **See what runs.** A component list and a daily update check, one request to GitHub, which you can turn off.
- **A proof, not a promise.** A network guard and a daily privacy check.
- **Always there.** Runs in the background and installs as a web app on macOS.

## Coming next

- **Linux.**
- **A faster speech engine.** Update MLX to its latest version; the pinned package list has to be rebuilt for macOS 14.
- **Usable with a screen reader.** Tested, not assumed.
- **A list of components (SBOM)** with every release.
- **Install without Internet.** For computers that never go online.
- **Import from any folder** of audio files.
- **More languages** for the interface and the transcripts.
