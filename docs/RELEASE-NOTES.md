# Release notes

## 0.2.1: faster, steadier, and it learns your names

- **Your names, finally spelled right.** Add the people, places and terms Whisper gets wrong. Cairn fixes them in the transcript, spells them right in the summary, and lists every change so you can undo it.
- **Speakers identified 4.5 times faster.** The graphics chip of your Mac does the work, with the same result. One button goes back to the processor.
- **Walk away, it finishes.** Processing starts the moment the copy ends, the Mac stays awake, and a failed recording is retried by itself without redoing what is already done.
- **Problems show in seconds, not after an hour.** The summary model is checked before any long job, and an engine that freezes is cut off.
- **Made for a 16 GB Mac.** Memory is freed between steps: the speaker pass takes 22 s instead of 82 s.
- **Stop means stop.** A speaker pass ends at once, and an interrupted recording goes back to waiting instead of spinning for ever.
- **One recording, one recording.** With automatic processing off, processing a single note no longer launches the whole queue.
- **Fix who said what, afterwards.** Redo the speakers of a finished note and rename them.
- **Speaker identification works with pyannote 4.** Every pass used to fail at the very end.
- **What you see is what is installed.** Models and About show real sizes, the Ollama version installed and running, and the right names.
- **Errors that say what is wrong.** A model without structured output is named as such. Qwen3.5 9B waits until Ollama supports it.
- **Know where the time goes.** Each note keeps the duration of every step, never its content.
- **Measured, not guessed.** Identifying speakers during the transcription saved 4 s and cost 1.4 GB of swap, so Cairn does not do it.

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
