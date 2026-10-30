"""Speech worker: runs in its own process so the model memory can be freed.

One shot:  python -m cairn.speech_worker ENGINE MODEL_DIR AUDIO_FILE OUTPUT_JSON [PROGRESS_FILE]
Serving:   python -m cairn.speech_worker --serve ENGINE MODEL_DIR
           then one JSON request per line on stdin: {"audio", "output", "progress"}.
           The model stays loaded between recordings; each reply is a line starting with
           "@@CAIRN " followed by "ok" or "error <message>".
"""

import json
import os
import sys


def _writer(path):
    """Report progress (0 to 1) through a tiny file that the app polls."""
    state = {"last": -1.0}

    def write(value):
        value = max(0.0, min(1.0, float(value)))
        if path and value - state["last"] >= 0.005:
            state["last"] = value
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write("%.4f" % value)
            os.replace(tmp, path)

    return write


_MODELS = {}
_REPORT = {"fn": lambda value: None}


def run(engine, model_dir, audio, progress_path=None, language=None):
    report = _writer(progress_path)
    _REPORT["fn"] = report
    if engine == "mlx":
        import mlx_whisper

        verbose = None
        try:  # progress from the engine's own frame counter; falls back to no progress
            import tqdm

            base = tqdm.tqdm

            class Watch(base):
                def __init__(self, *args, **kwargs):
                    kwargs["file"] = open(os.devnull, "w")  # noqa: SIM115
                    super().__init__(*args, **kwargs)

                def update(self, n=1):
                    result = super().update(n)
                    if self.total:
                        _REPORT["fn"](self.n / self.total)
                    return result

            if not _MODELS.get("patched"):
                tqdm.tqdm = Watch
                _MODELS["patched"] = True
            verbose = False
        except Exception:  # the progress bar is optional
            verbose = None
        result = mlx_whisper.transcribe(
            audio, path_or_hf_repo=model_dir, condition_on_previous_text=False, verbose=verbose, language=language
        )
        segments = [
            {
                "start": s["start"],
                "end": s["end"],
                "text": s["text"].strip(),
                "logprob": s.get("avg_logprob", -1.0),
                "no_speech": s.get("no_speech_prob", 0.0),
                "compression": s.get("compression_ratio", 1.0),
            }
            for s in result.get("segments", [])
        ]
        return {"language": result.get("language"), "segments": segments}
    if engine == "parakeet":
        return _parakeet(model_dir, audio, report)
    if engine == "faster":
        from faster_whisper import WhisperModel

        model = _MODELS.get(model_dir)
        if model is None:
            model = _MODELS[model_dir] = WhisperModel(model_dir, device="cpu", compute_type="int8")
        found, info = model.transcribe(audio, condition_on_previous_text=False, vad_filter=True, language=language)
        segments = []
        for s in found:
            segments.append(
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text.strip(),
                    "logprob": s.avg_logprob,
                    "no_speech": s.no_speech_prob,
                    "compression": s.compression_ratio,
                }
            )
            if info.duration:
                report(s.end / info.duration)
        return {"language": info.language, "segments": segments}
    raise SystemExit("Unknown speech engine: %r" % engine)


def _parakeet(model_dir, audio, report):
    """Parakeet through its MLX port: sentences with a start, an end and a confidence. It has no language setting; a long recording is
    cut in overlapping parts and joined again by the package itself."""
    import math

    from parakeet_mlx import DecodingConfig, SentenceConfig, from_pretrained

    model = _MODELS.get(("parakeet", model_dir))
    if model is None:
        model = _MODELS[("parakeet", model_dir)] = from_pretrained(model_dir)
    cut = SentenceConfig(max_duration=30.0, silence_gap=1.2)
    result = model.transcribe(audio, decoding_config=DecodingConfig(sentence=cut), chunk_duration=120.0, overlap_duration=15.0,
                              chunk_callback=lambda done, total: report(done / max(total, 1)))
    report(1.0)
    segments = [
        {"start": s.start, "end": s.end, "text": s.text.strip(), "logprob": math.log(max(float(s.confidence), 0.05)), "no_speech": 0.0, "compression": 1.0}
        for s in result.sentences if s.text.strip()
    ]
    return {"language": None, "segments": segments}


def serve(engine, model_dir):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
            data = run(engine, model_dir, job["audio"], job.get("progress"), job.get("language"))
            with open(job["output"], "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
            reply = "ok"
        except Exception as error:  # reported to the app, which then falls back
            reply = "error %s" % str(error).replace("\n", " ")[:300]
        sys.stdout.write("@@CAIRN %s\n" % reply)
        sys.stdout.flush()


def main(argv):
    from . import netguard

    netguard.install()  # the speech engine never needs the network
    if argv[1] == "--serve":
        return serve(argv[2], argv[3])
    engine, model_dir, audio, output = argv[1:5]
    data = run(engine, model_dir, audio, argv[5] if len(argv) > 5 else None)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv)
