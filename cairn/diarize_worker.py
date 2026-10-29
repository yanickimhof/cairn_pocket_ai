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


def speaker_turns(diarization):
    """Speaker turns from a pipeline result. pyannote 4 returns an object that holds the annotation in
    `speaker_diarization`; earlier versions return the annotation itself."""
    annotation = getattr(diarization, "speaker_diarization", diarization)
    return [
        {"start": round(turn.start, 2), "end": round(turn.end, 2), "speaker": speaker}
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]


def choose_device(setting, mps_available):
    """"mps", the graphics chip of an Apple silicon Mac, when it is allowed and available; otherwise "cpu".
    Same result, about four times faster in a measurement on an M4."""
    return "mps" if setting != "cpu" and mps_available else "cpu"


def run_pipeline(path, setting):
    from pyannote.audio import Pipeline
    import torch

    name = "pyannote/speaker-diarization-3.1"
    pipeline = Pipeline.from_pretrained(name)
    if choose_device(setting, torch.backends.mps.is_available()) == "mps":
        try:
            pipeline.to(torch.device("mps"))
            return pipeline(path)
        except Exception:  # the graphics chip could not do it: start again on the processor
            pipeline = Pipeline.from_pretrained(name)
    return pipeline(path)


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
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")  # an operation the graphics chip lacks runs on the processor
    try:
        from pyannote.audio import Pipeline  # noqa: F401  (only to know the package is installed)
    except ImportError:
        return 3
    try:
        diarization = run_pipeline(sys.argv[1], os.environ.get("CAIRN_DIARIZE_DEVICE", "auto"))
    except Exception as error:  # a bad file, a pipeline error, out of memory, and so on
        print("%s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return 1
    try:
        turns = speaker_turns(diarization)
    except AttributeError as error:  # a result shape this version does not know
        print("%s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return 1
    print(json.dumps(turns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
