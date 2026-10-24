"""Speech worker: runs in its own process so the model memory is freed after each recording.

Usage: python -m cairn.speech_worker ENGINE MODEL_DIR AUDIO_FILE OUTPUT_JSON
"""

import json
import sys


def run(engine, model_dir, audio):
    if engine == "mlx":
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio, path_or_hf_repo=model_dir, condition_on_previous_text=False, verbose=None
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
    if engine == "faster":
        from faster_whisper import WhisperModel

        model = WhisperModel(model_dir, device="cpu", compute_type="int8")
        found, info = model.transcribe(audio, condition_on_previous_text=False, vad_filter=True)
        segments = [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text.strip(),
                "logprob": s.avg_logprob,
                "no_speech": s.no_speech_prob,
                "compression": s.compression_ratio,
            }
            for s in found
        ]
        return {"language": info.language, "segments": segments}
    raise SystemExit("Unknown speech engine: %r" % engine)


def main(argv):
    engine, model_dir, audio, output = argv[1:5]
    data = run(engine, model_dir, audio)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv)
