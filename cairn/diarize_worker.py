"""Runs the local pyannote diarization pipeline on one audio file and prints the speaker turns as JSON.
Run by Cairn as a small separate program, only when the model has been installed and the feature is on.

Entirely offline: HF_HUB_OFFLINE is set, so this never reaches the network. If the cached model under
Cairn's folder is missing or the pyannote package is not installed, this exits with code 3 and nothing
is attempted. Exit code 1 covers any other failure (unreadable audio, a pipeline error, and so on); the
caller treats it the same way, as "no result", never as something that should stop the recording.
"""

import json
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("usage: diarize_worker.py <audio path>", file=sys.stderr)
        return 1
    home = Path(os.environ.get("CAIRN_HOME") or Path.home() / "Cairn")
    cache = home / "models" / "diar" / "hf_cache"
    if not cache.exists():
        return 3
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HOME"] = str(cache)
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        return 3
    try:
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
        diarization = pipeline(sys.argv[1])
    except Exception as error:  # a bad file, a pipeline error, out of memory, and so on
        print("%s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return 1
    turns = [
        {"start": round(turn.start, 2), "end": round(turn.end, 2), "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    print(json.dumps(turns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
