"""Words worth checking: the same name written several ways across the notes, and names the speech engine was not sure of.

Nothing here changes a note. The person decides how a name is written, and only then does it become an entry of the vocabulary.
No dictionary is needed: a name is a capitalised word inside a sentence, and two spellings are the same name when they sound close
(the same test the vocabulary uses to correct a misheard name)."""

import re
import unicodedata

from . import speech, vocab

MAX_ITEMS = 25
MAX_IGNORED = 500
_TOKEN = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)
_POSSESSIVE = re.compile("['’]s$")
_END = (".", "!", "?", "…", ":")
# capitalised words that are not names (French and English)
_NOT_NAMES = frozenset("""bonjour bonsoir merci salut hello thanks please monsieur madame lundi mardi mercredi jeudi vendredi samedi dimanche
monday tuesday wednesday thursday friday saturday sunday janvier fevrier mars avril juin juillet aout septembre octobre novembre decembre
january february april june july august september october november december voila alors ensuite donc okay super parfait exactement
oui non yeah yes""".split())


def _plain(text):
    return vocab._plain(text)


def weak(seg):
    """Whether the speech engine was unsure of this segment (the same test as the passages shown as doubtful)."""
    try:
        return (float(seg.get("logprob", -1.0)) < speech.DOUBTFUL_LOGPROB or float(seg.get("compression", 1.0)) > speech.DOUBTFUL_COMPRESSION
                or float(seg.get("no_speech", 0.0)) > 0.6)
    except (TypeError, ValueError):
        return False


def _names(text):
    """The capitalised words of a line that are not at the start of a sentence."""
    found, previous = [], ""
    for match in _TOKEN.finditer(text):
        word = _POSSESSIVE.sub("", match.group(0).strip("'’-"))  # Adrian's is Adrian
        starts = not previous or previous.endswith(_END)
        previous = text[match.start():match.end() + 1].strip()
        previous = previous if previous[-1:] in _END else match.group(0)
        if starts or len(word) < 3 or not word[0].isupper():
            continue
        plain = _plain(word)
        if len(plain) >= 4 and plain not in _NOT_NAMES and plain not in vocab._COMMON:
            found.append(word)
    return found


def _cluster(plains):
    """Group the spellings that sound alike: {plain form: group id}."""
    parent = {p: p for p in plains}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ordered = sorted(plains, key=lambda p: (len(p), p))
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if len(b) - len(a) > 2:
                break
            if b.startswith(a):
                continue  # Europe and European, State and States: the same word in another form, not a misheard name
            if vocab._close(a, b) or vocab._close(b, a):
                parent[find(a)] = find(b)
    return {p: find(p) for p in plains}


def contribution(note):
    """What one finished note says about names: (note id, {plain form: {"surfaces", "weak", "all", "examples"}}). It depends on the note
    alone, so it can be kept for as long as the note is not written again."""
    seen = {}
    if note.get("status") != "done":
        return note.get("id"), seen
    for seg in note.get("segments") or []:
        if seg.get("edit"):
            continue  # corrected by hand
        text = str(seg.get("text") or "")
        doubtful = weak(seg)
        for word in _names(text):
            info = seen.setdefault(_plain(word), {"surfaces": {}, "weak": 0, "all": 0, "examples": []})
            info["surfaces"][word] = info["surfaces"].get(word, 0) + 1
            info["all"] += 1
            info["weak"] += 1 if doubtful else 0
            if len(info["examples"]) < 3 and (doubtful or not info["examples"]):
                try:
                    start = float(seg.get("start") or 0)
                except (TypeError, ValueError):
                    start = 0.0
                info["examples"].append({"note": note.get("id"), "title": note.get("title") or "", "start": start, "text": text[:160], "word": word, "weak": doubtful})
    return note.get("id"), seen


def candidates(notes, terms, ignored=(), limit=MAX_ITEMS):
    """The names to check in these notes: [{"key", "forms": [{"text", "count"}], "suggest", "reason", "notes", "examples"}]."""
    return assemble([contribution(n) for n in notes], terms, ignored, limit)


def assemble(contributions, terms, ignored=(), limit=MAX_ITEMS):
    known = {_plain(s) for s in vocab.spellings(terms)}
    covered = set()  # spellings an exact rule already rewrites: the notes will show the right one once they are written again
    for term in terms or []:
        rule = vocab.split_rule(term)
        if rule:
            covered.update(_plain(w) for w in rule[0])
    seen = {}  # plain form -> {"surfaces", "weak", "all", "notes", "examples"}
    for note_id, mapping in contributions:
        for plain, part in mapping.items():
            if plain in covered:
                continue
            info = seen.setdefault(plain, {"surfaces": {}, "weak": 0, "all": 0, "notes": set(), "examples": []})
            for text, count in part["surfaces"].items():
                info["surfaces"][text] = info["surfaces"].get(text, 0) + count
            info["all"] += part["all"]
            info["weak"] += part["weak"]
            info["notes"].add(note_id)
            for example in part["examples"]:
                if len(info["examples"]) < 3 and (example["weak"] or not info["examples"]):
                    info["examples"].append(example)
    groups = {}
    for plain, group in _cluster(list(seen)).items():
        groups.setdefault(group, []).append(plain)
    out = []
    skip = {str(i) for i in ignored}
    for members in groups.values():
        infos = [seen[p] for p in members]
        total = sum(i["all"] for i in infos)
        weak_total = sum(i["weak"] for i in infos)
        primary = max(members, key=lambda p: (seen[p]["all"], len(p)))
        if primary in skip or any(p in skip for p in members):
            continue
        surfaces = {}
        for info in infos:
            for text, count in info["surfaces"].items():
                surfaces[text] = surfaces.get(text, 0) + count
        distinct = {_plain(t) for t in surfaces}
        in_vocabulary = [p for p in members if p in known]
        by_form = {}
        for text, count in surfaces.items():
            by_form[_plain(text)] = by_form.get(_plain(text), 0) + count
        dominant = max(by_form.values()) / total
        # one spelling clearly in the lead and a few strays: a misheard name. Two spellings said as often are two people (Anne, Anna).
        if len(distinct) >= 2 and total >= 3 and (dominant >= 0.6 or weak_total):
            reason = "variants"
        elif len(distinct) == 1 and weak_total == total and not in_vocabulary:
            reason = "doubtful"
        else:
            continue
        forms = sorted(({"text": t, "count": c} for t, c in surfaces.items()), key=lambda f: (-f["count"], f["text"]))
        suggest = next((f["text"] for f in forms if _plain(f["text"]) in known), forms[0]["text"])
        examples = sorted((e for i in infos for e in i["examples"]), key=lambda e: not e["weak"])[:2]
        out.append({"key": primary, "forms": forms, "suggest": suggest, "reason": reason, "notes": len(set().union(*(i["notes"] for i in infos))),
                    "examples": examples, "_rank": (reason != "variants", -total)})
    out.sort(key=lambda c: (c["_rank"], c["key"]))
    for item in out:
        item.pop("_rank")
    return out[:limit]


def normalise_key(value):
    return _plain(unicodedata.normalize("NFC", str(value)))[:60]
