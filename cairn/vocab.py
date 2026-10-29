"""A personal vocabulary: names of people and places and rare terms the speech engine often writes wrongly.

One entry per line. "Acme" is a name to look for: a word that sounds close to it is written as "Acme". "Sion => Acme" is an
exact rule: "Sion" is always written "Acme". Every correction is kept with the note and shown, so nothing changes silently.
The speech engine cannot be told the names itself: with the setting Cairn uses (each 30 s window decoded on its own, which
avoids repetition loops) its prompt only reaches the first window."""

import difflib
import hashlib
import re
import unicodedata

MAX_TERMS = 300
MAX_LEN = 60
ARROW = "=>"
_WORD = re.compile(r"\w+", re.UNICODE)
_GAP = re.compile(r"^[\s'’-]*$")
_COMMON = frozenset("""le la les de du des un une et ou en au aux ce ces cet son sa ses mon ma mes ton ta tes il elle on nous vous ils
elles je tu que qui quoi dont ne pas plus pour par sur sous dans avec sans est sont etre avoir fait the a an and or of to in on at it is
are was were be for with by as from this that these those i you he she we they my your our their not but so if then than""".split())


def parse(value):
    """The list of entries from text (one per line, or separated by ; or ,) or from a list. Trimmed, no duplicates."""
    if isinstance(value, str):
        parts = re.split(r"[\n;,]+", value)
    elif isinstance(value, (list, tuple)):
        parts = [str(v) for v in value]
    else:
        raise ValueError("The vocabulary must be text, one entry per line.")
    out, seen = [], set()
    for part in parts:
        term = " ".join(part.split())
        if not term:
            continue
        if len(term) > MAX_LEN:
            raise ValueError("An entry is longer than %d characters." % MAX_LEN)
        if term.casefold() not in seen:
            seen.add(term.casefold())
            out.append(term)
    if len(out) > MAX_TERMS:
        raise ValueError("At most %d entries." % MAX_TERMS)
    return out


def key(terms):
    """A short value that changes when the vocabulary does, kept with each note."""
    return hashlib.sha1("\n".join(terms or []).encode("utf-8")).hexdigest()[:12]


def spellings(terms):
    """The spellings to impose on a summary: the entries, and the right-hand side of the exact rules."""
    out = []
    for term in terms or []:
        spelled = term.split(ARROW, 1)[1].strip() if ARROW in term else term
        if spelled and spelled not in out:
            out.append(spelled)
    return out


def _plain(text):
    text = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c) and ord(c) < 128)


def _skeleton(text):
    """What a word sounds like, roughly, in French and English: for telling a misheard name from a different one."""
    s = _plain(text)
    for old, new in (("ph", "f"), ("ck", "k"), ("qu", "k"), ("sh", "x"), ("ch", "x")):
        s = s.replace(old, new)
    s = re.sub(r"c(?=[eiy])", "s", s).replace("c", "k")
    s = s.replace("w", "v").replace("y", "i").replace("z", "s").replace("h", "")
    return re.sub(r"(.)\1+", r"\1", s)


def _close(surface, term):
    """True when `surface`, a run of words of the text, is probably `term` misheard."""
    cand, ref = _plain(surface), _plain(term)
    if len(ref) < 4 or not cand or cand == ref or abs(len(cand) - len(ref)) > 2:
        return False
    if all(_plain(w) in _COMMON for w in _WORD.findall(surface)):
        return False
    sc, sr = _skeleton(cand), _skeleton(ref)
    if not sc or sc[0] != sr[0]:
        return False
    if difflib.SequenceMatcher(None, cand, ref).ratio() < 0.7:
        return False
    need = 0.88 if len(ref) <= 5 else 0.84 if len(ref) < 8 else 0.80
    return difflib.SequenceMatcher(None, sc, sr).ratio() >= need


def _rules(terms):
    exact, fuzzy = [], []
    for term in terms or []:
        if ARROW in term:
            wrong, right = (p.strip() for p in term.split(ARROW, 1))
            if wrong and right:
                exact.append((re.compile(r"(?<!\w)" + re.escape(wrong) + r"(?!\w)", re.IGNORECASE), wrong, right))
        else:
            words = _WORD.findall(term)
            if words and len(_plain(term)) >= 4:
                fuzzy.append((term, words))
    return exact, sorted(fuzzy, key=lambda f: -len(f[1]))


def fix_text(text, terms):
    """(new text, corrections) for one text. A correction is {"from", "to"}."""
    exact, fuzzy = _rules(terms)
    found = []
    for pattern, wrong, right in exact:
        def swap(match, right=right):
            found.append({"from": match.group(0), "to": right})
            return right
        text = pattern.sub(swap, text)
    tokens = [(m.start(), m.end()) for m in _WORD.finditer(text)]
    taken, edits = [], []
    for term, words in fuzzy:
        n = len(words)
        for i in range(len(tokens) - n + 1):
            window = tokens[i:i + n]
            if any(not _GAP.match(text[window[k][1]:window[k + 1][0]]) for k in range(n - 1)):
                continue
            start, end = window[0][0], window[-1][1]
            if any(start < b and a < end for a, b in taken):
                continue
            surface = text[start:end]
            if surface != term and _close(surface, term):
                taken.append((start, end))
                edits.append((start, end, term, surface))
    for start, end, term, surface in sorted(edits, reverse=True):
        text = text[:start] + term + text[end:]
    found += [{"from": surface, "to": term} for _s, _e, term, surface in sorted(edits)]
    return text, found


def apply(segments, terms):
    """Correct the segments in place from the current vocabulary, starting again from what the speech engine wrote,
    so that removing an entry puts the original word back. Returns the corrections: [{"from", "to", "count"}]."""
    totals = {}
    for seg in segments or []:
        original = seg.get("orig", seg.get("text", ""))
        text, found = fix_text(original, terms)
        if text != original:
            seg["orig"], seg["text"] = original, text
        else:
            seg.pop("orig", None)
            seg["text"] = original
        for fix in found:
            pair = (fix["from"], fix["to"])
            totals[pair] = totals.get(pair, 0) + 1
    return [{"from": a, "to": b, "count": n} for (a, b), n in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]
