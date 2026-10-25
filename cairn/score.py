"""Fidelity of a finished note to its transcript.

The speech engine's confidence says how sure it was of each word. This module answers a different
question: does the written note stay true to what was transcribed? It takes the checkable details of the
note (numbers and proper names) and measures how many of them appear in the transcript. Everything is
local and instant. It is a guide, not a proof of accuracy.
"""

import re
import unicodedata

MIN_ANCHORS = 3
_SPOKEN = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8,
    "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20,
    "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100, "mille": 1000,
}
_TOKEN = re.compile(r"[\w][\w'’.,-]*", re.UNICODE)


def _norm(word):
    word = unicodedata.normalize("NFKD", word.lower())
    return "".join(c for c in word if not unicodedata.combining(c)).strip(".,'’-")


def _pieces(summary):
    """Every sentence of the note that carries facts, as plain strings."""
    out = []
    for key in ("tldr", "context"):
        if summary.get(key):
            out.append(summary[key])
    for key in ("key_points", "decisions"):
        out += [x for x in summary.get(key) or [] if isinstance(x, str)]
    for action in summary.get("actions") or []:
        out += [str(action.get(k)) for k in ("what", "who", "when") if action.get(k)]
    for topic in summary.get("topics") or []:
        out += [str(topic.get(k)) for k in ("name", "summary") if topic.get(k)]
    return out


_CLOCK = re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b")


def _clock(match):
    """A time of day is checked by its hour; 00:MM is a position in the recording, not a fact to verify."""
    return "" if match.group(1) in ("0", "00") else match.group(1)


def anchors(summary):
    """Numbers and proper names of the note, each one a checkable detail."""
    found = []
    for piece in _pieces(summary or {}):
        piece = _CLOCK.sub(_clock, piece)
        start = True
        for raw in _TOKEN.findall(piece):
            word = raw.strip(".,'’-")
            if not word:
                continue
            if any(c.isdigit() for c in word):
                digits = re.sub(r"\D", "", word)
                if digits:
                    found.append(("n", digits))
            elif not start and len(word) >= 3 and word[0].isupper():
                found.append(("w", _norm(word)))
            start = raw[-1] in ".!?"
    return found


def _index(text):
    words, digits = set(), set()
    for raw in _TOKEN.findall(text or ""):
        word = raw.strip(".,'’-")
        if any(c.isdigit() for c in word):
            digits.add(re.sub(r"\D", "", word))
        else:
            words.add(_norm(word))
            if _norm(word) in _SPOKEN:  # numbers the engine wrote out in letters
                digits.add(str(_SPOKEN[_norm(word)]))
    stems = {w[:5] for w in words if len(w) >= 6}
    return words, digits, stems


def fidelity(summary, transcript):
    """Share (0 to 100) of the note's numbers and names found in the transcript, or None when the
    note carries too few details to tell."""
    items = anchors(summary)
    if len(items) < MIN_ANCHORS or not transcript:
        return None
    words, digits, stems = _index(transcript)
    hit = 0
    for kind, value in items:
        if kind == "n":
            hit += value in digits or any(value in d for d in digits if len(d) > len(value))
        else:
            hit += value in words or (len(value) >= 6 and value[:5] in stems)
    return round(100 * hit / len(items))
