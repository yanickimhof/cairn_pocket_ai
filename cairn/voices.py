"""Voice memory (optional, off by default): Cairn can remember what a person's voice sounds like, so that the next recordings
come with their name already on the right speaker.

What is kept is a voiceprint: 256 numbers that the speaker model computes from the voice, not the audio and not the words. It
is stored in the Cairn folder, on this computer, never sent anywhere, and erased with one click per person or for everybody.
A voiceprint is only learned when the person names a speaker by hand, never from a guess; a recognised name is shown as such
and can be corrected."""

import math
from datetime import datetime

from . import config

MATCH = 0.60       # cosine similarity needed to recognise a voice
MARGIN = 0.08      # and how far it must be ahead of the next person
MAX_SAMPLES = 8    # voiceprints kept per person (the most recent ones)
DIM_MAX = 1024


def _path():
    return config.home() / "voices.json"


def load():
    data = config.read_json(_path())
    people = data.get("people") if isinstance(data, dict) else None
    return people if isinstance(people, dict) else {}


def _save(people):
    config.write_json(_path(), {"v": 1, "people": people})


def clean(vector):
    """A list of floats of a sane size, or None."""
    if not isinstance(vector, (list, tuple)) or not 8 <= len(vector) <= DIM_MAX:
        return None
    try:
        out = [round(float(x), 5) for x in vector]
    except (TypeError, ValueError):
        return None
    return out if all(math.isfinite(x) for x in out) else None


def _unit(vector):
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def cosine(a, b):
    if len(a) != len(b):
        return -1.0
    a, b = _unit(a), _unit(b)
    return sum(x * y for x, y in zip(a, b))


def centroid(samples):
    dim = len(samples[0])
    acc = [0.0] * dim
    for sample in samples:
        if len(sample) == dim:
            for i, x in enumerate(_unit(sample)):
                acc[i] += x
    return _unit(acc)


def learn(name, vector):
    """Remember this voiceprint under this name."""
    name, vector = str(name or "").strip()[:60], clean(vector)
    if not name or vector is None:
        return False
    people = load()
    entry = people.setdefault(name, {"samples": []})
    entry["samples"] = [s for s in entry.get("samples", []) if len(s) == len(vector)] + [vector]
    entry["samples"] = entry["samples"][-MAX_SAMPLES:]
    entry["updated"] = datetime.now().isoformat(timespec="seconds")
    _save(people)
    return True


def forget(name=None):
    """Erase the voiceprints of one person, or of everybody when no name is given. Returns how many people were erased."""
    people = load()
    if name is None:
        count = len(people)
        people = {}
    else:
        count = 1 if people.pop(name, None) is not None else 0
    _save(people)
    return count


def rename(old, new):
    """The voiceprints follow a name that changes; two names that become one pool their voiceprints."""
    people = load()
    if old not in people or old == new:
        return
    moved = people.pop(old)
    kept = people.setdefault(new, {"samples": []})
    dims = {len(s) for s in kept["samples"]}
    kept["samples"] = (kept["samples"] + [s for s in moved.get("samples", []) if not dims or len(s) in dims])[-MAX_SAMPLES:]
    kept["updated"] = datetime.now().isoformat(timespec="seconds")
    _save(people)


def counts():
    return {name: len(entry.get("samples") or []) for name, entry in load().items()}


def best(vector, people=None):
    """(name, score) of the person this voiceprint is closest to, if it is clearly closer to them than to anybody else."""
    vector = clean(vector)
    people = load() if people is None else people
    if vector is None or not people:
        return None
    scored = []
    for name, entry in people.items():
        samples = [s for s in entry.get("samples") or [] if len(s) == len(vector)]
        if samples:
            scored.append((cosine(vector, centroid(samples)), name))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < MATCH:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < MARGIN:
        return None
    return scored[0][1], round(scored[0][0], 3)


def recognise(note):
    """Name the speakers of this note whose voice is known, and have no name yet. Returns {label: name} of what was named."""
    prints = note.get("voices") or {}
    people = load()
    names = dict(note.get("speaker_names") or {})
    auto, found, taken = dict(note.get("speaker_auto") or {}), {}, set(names.values())
    for label, vector in prints.items():
        if label in names:
            continue
        match = best(vector, people)
        if match and match[0] not in taken:  # one name for two speakers of the same recording would be a mistake
            names[label], auto[label] = match[0], match[1]
            found[label] = match[0]
            taken.add(match[0])
    if found:
        note["speaker_names"], note["speaker_auto"] = names, auto
    return found
