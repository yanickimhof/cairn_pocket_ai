# Guide

## Choosing what to process

Tap a waiting recording to process it now: Cairn does that one first, then carries on with every other waiting recording, newest first. Recordings you put back while it runs are picked up too. Each recording has its own level of detail (short, standard, detailed; standard by default) and its own language (FR or EN, the interface language by default): choose them before processing, in the same panel. Skip a recording to leave it out of the queue (it can be restored). Stop interrupts the current job. On a finished note, choose a level and press **Redo**: Cairn rewrites the note at that level and keeps your chosen name. The audio is transcribed again only if you changed the speech model since the note was made; otherwise the transcript is reused, which takes seconds. Secure mode hides the list of notes until you reveal it.

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
