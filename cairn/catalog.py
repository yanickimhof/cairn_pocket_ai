"""The models Cairn can use. Only models that do a good job are listed.

A speech model is downloaded at a fixed revision (a commit of its Hugging Face repository), so what is
downloaded is what was reviewed, not whatever the repository holds on the day."""

GB = 1_000_000_000

LLM = [
    {"id": "qwen3:4b", "label": "Qwen3 4B", "bytes": int(2.5 * GB), "ram": 8, "tier": "light"},
    {"id": "qwen3:8b", "label": "Qwen3 8B", "bytes": int(5.2 * GB), "ram": 16, "tier": "standard"},
    {"id": "qwen3:14b", "label": "Qwen3 14B", "bytes": int(9.3 * GB), "ram": 32, "tier": "high"},
]

# Optional: finds notes by meaning, not only by the words used. Installed on request, kept in the model server's own folder.
EMBED = [
    {"id": "qwen3-embedding:0.6b", "label": "Qwen3 Embedding 0.6B", "bytes": int(0.64 * GB), "ram": 4, "tier": "light"},
    {"id": "bge-m3", "label": "BGE-M3", "bytes": int(1.2 * GB), "ram": 8, "tier": "standard"},
]

SPEECH = {
    "mlx": [
        {"id": "turbo", "label": "Whisper large-v3-turbo", "repo": "mlx-community/whisper-large-v3-turbo", "revision": "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb", "bytes": int(1.61 * GB), "ram": 8, "tier": "standard"},
        {"id": "large", "label": "Whisper large-v3", "repo": "mlx-community/whisper-large-v3-mlx", "revision": "49e6aa286ad60c14352c404340ded53710378a11", "bytes": int(3.08 * GB), "ram": 16, "tier": "high"},
        # Much faster than Whisper on a recording in one language; it cannot be told which language to hear, so it is offered, never the default.
        {"id": "parakeet", "label": "Parakeet v3 (fast)", "repo": "mlx-community/parakeet-tdt-0.6b-v3", "revision": "ed2b7e8c15f9aaa0b5772e2efb986255eaef7e15", "bytes": int(2.51 * GB), "ram": 8, "tier": "standard", "engine": "parakeet"},
    ],
    "faster": [
        {"id": "turbo", "label": "Whisper large-v3-turbo", "repo": "deepdml/faster-whisper-large-v3-turbo-ct2", "revision": "4df90f75321148c3a29a9e2351b7ddf8f5b115a8", "bytes": int(1.62 * GB), "ram": 8, "tier": "standard"},
        {"id": "large", "label": "Whisper large-v3", "repo": "Systran/faster-whisper-large-v3", "revision": "edaa852ec7e145841d8ffdb056a99866b5f0a478", "bytes": int(3.09 * GB), "ram": 16, "tier": "high"},
    ],
}

DIAR = [
    {"id": "pyannote-3.1", "label": "Diarisation (pyannote 3.1)", "repo": "pyannote/speaker-diarization-3.1",
     "bytes": int(0.032 * GB), "ram": 4, "tier": "light", "gated": True},
]

LLM_IDS = tuple(m["id"] for m in LLM)
EMBED_IDS = tuple(m["id"] for m in EMBED)
SPEECH_IDS = ("turbo", "large", "parakeet")
DIAR_IDS = tuple(m["id"] for m in DIAR)
