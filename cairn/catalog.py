"""The models Cairn can use. Only models that do a good job are listed."""

GB = 1_000_000_000

LLM = [
    {"id": "qwen3:4b", "label": "Qwen3 4B", "bytes": int(2.5 * GB), "ram": 8, "tier": "light"},
    {"id": "qwen3:8b", "label": "Qwen3 8B", "bytes": int(5.2 * GB), "ram": 16, "tier": "standard"},
    {"id": "qwen3:14b", "label": "Qwen3 14B", "bytes": int(9.3 * GB), "ram": 32, "tier": "high"},
]

SPEECH = {
    "mlx": [
        {"id": "turbo", "label": "Whisper large-v3-turbo", "repo": "mlx-community/whisper-large-v3-turbo", "bytes": int(1.61 * GB), "ram": 8, "tier": "standard"},
        {"id": "large", "label": "Whisper large-v3", "repo": "mlx-community/whisper-large-v3-mlx", "bytes": int(3.08 * GB), "ram": 16, "tier": "high"},
    ],
    "faster": [
        {"id": "turbo", "label": "Whisper large-v3-turbo", "repo": "deepdml/faster-whisper-large-v3-turbo-ct2", "bytes": int(1.62 * GB), "ram": 8, "tier": "standard"},
        {"id": "large", "label": "Whisper large-v3", "repo": "Systran/faster-whisper-large-v3", "bytes": int(3.09 * GB), "ram": 16, "tier": "high"},
    ],
}

LLM_IDS = tuple(m["id"] for m in LLM)
SPEECH_IDS = ("turbo", "large")
