"""Search across every note: title, summary and transcript, on this computer only."""

import re
import unicodedata

from . import config

MAX_NOTES = 30
MAX_SNIPPETS = 3
CONTEXT = 70  # characters kept on each side of a match
_CACHE = {}  # file -> (signature, text index)


def fold(text):
    """Lower case, without accents, one output character per input character where possible, with the map back."""
    out, back = [], []
    for i, ch in enumerate(text or ""):
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)).lower()
        for c in base or " ":
            out.append(c)
            back.append(i)
    return "".join(out), back


def split_query(query):
    """(text of the query, tags asked for): "#orion budget" is the word budget among the notes tagged orion."""
    tags = [t for t in re.findall(r"#([^\s#]+)", query or "")][:5]
    return re.sub(r"#[^\s#]+", " ", query or ""), [fold(t)[0] for t in tags]


def terms(query):
    words = re.findall(r"\w+", fold(query)[0])
    return [w for w in dict.fromkeys(words) if len(w) > 1 or w.isdigit()][:8]


def _pieces(note):
    """(where, start seconds or None, text) for everything searchable in a note."""
    summary = note.get("summary") or {}
    out = [("title", None, note.get("title") or "")]
    if note.get("tags"):
        out.append(("title", None, " ".join(note["tags"])))  # a tag counts as much as a word of the title
    for key in ("tldr", "context"):
        if summary.get(key):
            out.append(("summary", None, str(summary[key])))
    for action in summary.get("actions") or []:
        line = " ".join(str(action.get(k) or "") for k in ("what", "who", "when")).strip()
        if line:
            out.append(("summary", None, line))
    for section in summary.get("sections") or []:
        out.append(("summary", None, "%s %s" % (section.get("heading") or "", section.get("text") or "")))
    for key in ("key_points", "decisions"):
        for item in summary.get(key) or []:
            out.append(("summary", None, str(item)))
    names = note.get("speaker_names") or {}
    segments = note.get("segments") or []
    if segments:
        for seg in segments:
            who = names.get(seg.get("speaker"), seg.get("speaker"))
            text = (who + ": " if who else "") + str(seg.get("text") or "").strip()
            out.append(("transcript", seg.get("start"), text))
    elif note.get("clean"):
        out.extend(("transcript", None, line) for line in str(note["clean"]).split("\n") if line.strip())
    return out


def _index(path, note):
    return [(where, start, text, fold(text)[0]) for where, start, text in _pieces(note)]


def _load(folder):
    seen = set()
    for path in sorted(folder.glob("*.json")):
        try:
            stat = path.stat()
        except OSError:
            continue
        seen.add(path)
        sig = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        cached = _CACHE.get(path)
        if not cached or cached[0] != sig:
            note = config.read_json(path, default=None)
            ok = note and note.get("id") and note.get("status") == "done"
            cached = _CACHE[path] = (sig, (note["id"], note.get("title") or "", note.get("date") or "", _index(path, note),
                                           {fold(t)[0] for t in note.get("tags") or []}) if ok else None)
        if cached[1]:
            yield cached[1]
    for gone in set(_CACHE) - seen:
        del _CACHE[gone]


def _marked(text, wanted):
    """The text as parts [{"t": ..., "m": bool}], the searched words marked, cut around the first match."""
    folded, back = fold(text)
    spans = []
    for word in wanted:
        for m in re.finditer(re.escape(word), folded):
            spans.append((back[m.start()], back[m.end() - 1] + 1))
    if not spans:
        return [{"t": text[:2 * CONTEXT], "m": False}]
    spans.sort()
    first = spans[0][0]
    lo, hi = max(0, first - CONTEXT), min(len(text), first + CONTEXT + 40)
    parts, pos = [], lo
    for a, b in spans:
        if b <= pos or a >= hi:
            continue
        a = max(a, pos)
        if a > pos:
            parts.append({"t": text[pos:a], "m": False})
        parts.append({"t": text[a:min(b, hi)], "m": True})
        pos = min(b, hi)
    if pos < hi:
        parts.append({"t": text[pos:hi], "m": False})
    if lo > 0:
        parts[0]["t"] = "…" + parts[0]["t"]
    if hi < len(text):
        parts[-1]["t"] += "…"
    return parts


def find(folder, query):
    text, asked = split_query(query)
    wanted = terms(text)
    if not wanted and not asked:
        return []
    results = []
    for note_id, title, date, pieces, tagset in _load(folder):
        if not all(t in tagset for t in asked):
            continue
        everything = " ".join(p[3] for p in pieces)
        if not all(w in everything for w in wanted):
            continue
        score, hits = 0, []
        for where, start, text, folded in pieces:
            matched = [w for w in wanted if w in folded]
            if not matched:
                continue
            score += len(matched) * {"title": 6, "summary": 3, "transcript": 1}[where]
            if where != "title" and len(hits) < MAX_SNIPPETS:
                hits.append({"where": where, "start": start, "parts": _marked(text, wanted)})
        # a note whose words are spread over different lines still counts, at a lower rank
        results.append({"id": note_id, "title": title, "date": date, "score": score, "hits": hits})
    results.sort(key=lambda r: (-r["score"], r["date"]), reverse=False)
    return results[:MAX_NOTES]
