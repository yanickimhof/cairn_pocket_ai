"""A personal vocabulary: names of people and places and rare terms the speech engine often writes wrongly.

One entry per line. "Acme" is a name to look for: a word that sounds close to it is written as "Acme". "Sion => Acme" is an
exact rule: "Sion" is always written "Acme". Several spellings can share one rule: "Sion, Cion, Scyon => Acme". "->", the
arrow character and ":" work like "=>". A rule can be limited to a context: "Science Day => ACME Day | awards, ceremony" replaces
the words only when one of the words after the bar is spoken close by (in the same line or the two before and after). Every correction is kept with the note and shown, so nothing changes silently.
The speech engine cannot be told the names itself: with the setting Cairn uses (each 30 s window decoded on its own, which
avoids repetition loops) its prompt only reaches the first window."""

import difflib
import hashlib
import re
import unicodedata

MAX_TERMS = 300
MAX_LEN = 60
MAX_RULE = 400
BAR = "|"
NEAR = 2  # lines on each side of a line that count as its context
ARROW = "=>"
ARROWS = ("=>", "->", "\u2192", ":")
_WORD = re.compile(r"\w+", re.UNICODE)
_GAP = re.compile(r"^[\s'’-]*$")
_COMMON = frozenset("""le la les de du des un une et ou en au aux ce ces cet son sa ses mon ma mes ton ta tes il elle on nous vous ils
elles je tu que qui quoi dont ne pas plus pour par sur sous dans avec sans est sont etre avoir fait the a an and or of to in on at it is
are was were be for with by as from this that these those i you he she we they my your our their not but so if then than""".split())


def split_rule(term):
    """(spellings to replace, the right spelling, context words) when the entry is an exact rule, else None.
    The context words are empty when the rule always applies."""
    hits = [(term.find(a), a) for a in ARROWS if a in term]
    if not hits:
        return None
    at, arrow = min(hits)
    wrong = [w.strip() for w in term[:at].split(",") if w.strip()]
    right, _bar, near = term[at + len(arrow):].partition(BAR)
    right = right.strip()
    context = [c.strip() for c in near.split(",") if c.strip()]
    return (wrong, right, context) if wrong and right else None


def parse(value):
    """The list of entries from text (one per line, or separated by ;) or from a list. A rule keeps its commas: they separate
    the spellings it replaces. Elsewhere a comma separates entries. Trimmed, no duplicates."""
    if isinstance(value, str):
        lines = re.split(r"[\n;]+", value)
    elif isinstance(value, (list, tuple)):
        lines = [str(v) for v in value]
    else:
        raise ValueError("The vocabulary must be text, one entry per line.")
    out, seen = [], set()
    for line in lines:
        line = " ".join(line.split())
        if not line:
            continue
        rule = split_rule(line)
        if rule:
            entries, limit = ["%s %s %s%s" % (", ".join(rule[0]), ARROW, rule[1], " %s %s" % (BAR, ", ".join(rule[2])) if rule[2] else "")], MAX_RULE
        elif any(a in line for a in ARROWS):
            continue  # an arrow with nothing on one side: not a rule, and not a name either
        elif isinstance(value, str):
            entries, limit = [p.strip() for p in line.split(",") if p.strip()], MAX_LEN
        else:
            entries, limit = [line], MAX_LEN
        for term in entries:
            if len(term) > limit:
                raise ValueError("An entry is longer than %d characters." % limit)
            if term.casefold() not in seen:
                seen.add(term.casefold())
                out.append(term)
    if len(out) > MAX_TERMS:
        raise ValueError("At most %d entries." % MAX_TERMS)
    return out


def key(terms):
    """A short value that changes when the vocabulary does, kept with each note."""
    return hashlib.sha1("\n".join(terms or []).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]


def spellings(terms):
    """The spellings to impose on a summary: the entries, and the right-hand side of the exact rules."""
    out = []
    for term in terms or []:
        rule = split_rule(term)
        spelled = rule[1] if rule else term
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
        rule = split_rule(term)
        if rule:
            for wrong in rule[0]:
                pattern = r"\s+".join(re.escape(w) for w in wrong.split())
                near = [re.compile(r"(?<!\w)" + re.escape(c) + r"(?!\w)", re.IGNORECASE) for c in rule[2]]
                exact.append((re.compile(r"(?<!\w)" + pattern + r"(?!\w)", re.IGNORECASE), wrong, rule[1], near))
        elif any(a in term for a in ARROWS):
            continue  # an arrow with nothing on one side: not a name to look for
        else:
            words = _WORD.findall(term)
            if words and len(_plain(term)) >= 4:
                fuzzy.append((term, words))
    return exact, sorted(fuzzy, key=lambda f: -len(f[1]))


def fix_text(text, terms, context=None):
    """(new text, corrections) for one text. A correction is {"from", "to"}. `context` is the text around it, for the rules
    that apply only near certain words (the text itself when it is not given)."""
    exact, fuzzy = _rules(terms)
    found = []
    around = text if context is None else context
    for pattern, wrong, right, near in exact:
        def swap(match, right=right, near=near):
            if near and not any(n.search(around) for n in near):
                return match.group(0)  # the words that make this the name are not spoken here
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
    segments = segments or []
    originals = [seg.get("orig", seg.get("text", "")) for seg in segments]
    for i, seg in enumerate(segments):
        original = originals[i]
        text, found = fix_text(original, terms, " ".join(originals[max(0, i - NEAR):i + NEAR + 1]))
        if text != original:
            seg["orig"], seg["text"] = original, text
        else:
            seg.pop("orig", None)
            seg["text"] = original
        for fix in found:
            pair = (fix["from"], fix["to"])
            totals[pair] = totals.get(pair, 0) + 1
    return [{"from": a, "to": b, "count": n} for (a, b), n in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]
