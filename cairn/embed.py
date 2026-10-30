"""Search by meaning: an optional embedding model (run by the local model server, on this computer only) turns passages of the
notes into vectors, so that a question finds the passage that answers it even when the words differ.

Nothing is installed by default. The person installs a model in Settings, Models; the notes are then indexed in the background
(the index is a folder of small files in the Cairn folder) and the page offers related passages below the usual results."""

import array
import base64
import hashlib
import json
import math
import re
import threading
import unicodedata

from . import catalog, config, llm, lock

try:  # numpy is there with the speech engines; the search works without it, only slower
    import numpy as np
except ImportError:  # pragma: no cover - exercised by a test that hides it
    np = None

CHUNK_CHARS = 420
MAX_CHUNK = 1200
BATCH = 16
MIN_SCORE = 0.30
RELATIVE = 0.80  # a note is related when it scores at least this share of the best one
MAX_NOTES = 12
SNIPPET = 220
KEEP_ALIVE = "10m"  # the small model stays loaded between two questions: a question costs milliseconds, not a load
_lock = threading.Lock()
_cache = {}  # file -> (signature, chunks, vectors); at most CACHE_NOTES of them, the least recently used go first
lock.on_lock(_cache.clear)
CACHE_NOTES = 64
built = {}  # model -> the notes signature it was last indexed at


def _names():
    return {m.get("name", "") for m in llm.models()}


def installed(model_id):
    names = _names()
    return model_id in names or model_id + ":latest" in names


def chosen():
    """The embedding model in use: the one selected in the settings, if it is still installed."""
    wanted = config.load_settings().get("embed")
    return wanted if wanted in catalog.EMBED_IDS and installed(wanted) else None


def _folder(model):
    return config.home() / "Index" / re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def chunks(note):
    """(where, start seconds or None, text) for the passages of a finished note that are worth finding."""
    summary = note.get("summary") or {}
    out = []
    head = " ".join(x for x in [note.get("title") or "", " ".join(note.get("tags") or [])] if x).strip()
    if head:
        out.append(("title", None, head))
    for key in ("tldr", "context"):
        if summary.get(key):
            out.append(("summary", None, str(summary[key])[:MAX_CHUNK]))
    for key in ("key_points", "decisions"):
        out.extend(("summary", None, str(x)[:MAX_CHUNK]) for x in summary.get(key) or [] if str(x).strip())
    for action in summary.get("actions") or []:
        line = " ".join(str(action.get(k) or "") for k in ("what", "who", "when")).strip()
        if line:
            out.append(("summary", None, line[:MAX_CHUNK]))
    for section in summary.get("sections") or []:
        out.append(("summary", None, ("%s. %s" % (section.get("heading") or "", section.get("text") or ""))[:MAX_CHUNK]))
    names = note.get("speaker_names") or {}
    start, text = None, ""
    for seg in note.get("segments") or []:
        piece = str(seg.get("text") or "").strip()
        if not piece:
            continue
        who = names.get(seg.get("speaker"), seg.get("speaker"))
        if start is None:
            start = seg.get("start")
        text += (" " if text else "") + ((who + ": ") if who else "") + piece
        if len(text) >= CHUNK_CHARS:
            out.append(("transcript", start, text[:MAX_CHUNK]))
            start, text = None, ""
    if text:
        out.append(("transcript", start, text[:MAX_CHUNK]))
    return out


def _signature(items):
    return hashlib.sha1(json.dumps(items, ensure_ascii=False).encode("utf-8"), usedforsecurity=False).hexdigest()


def embed(model, texts):
    """Unit vectors for these texts, from the local model server."""
    answer = llm._post("/api/embed", {"model": model, "input": list(texts), "truncate": True, "keep_alive": KEEP_ALIVE}, timeout=600)
    vectors = answer.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise llm.LLMError("The embedding model returned an unexpected answer.")
    out = []
    for vector in vectors:
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        out.append([x / norm for x in vector])
    return out


def _pack(vectors):
    flat = array.array("f")
    for vector in vectors:
        flat.extend(vector)
    return base64.b64encode(flat.tobytes()).decode("ascii")


def _unpack(data, dim):
    flat = array.array("f")
    flat.frombytes(base64.b64decode(data))
    return flat, dim


def build(store, model, progress=None, cancelled=lambda: False):
    """Index every finished note that is new or changed, and forget the deleted ones. Returns how many notes were indexed."""
    folder = _folder(model)
    folder.mkdir(parents=True, exist_ok=True)
    notes = [n for n in store.all() if n.get("status") == "done"]
    todo = []
    for note in notes:
        items = chunks(note)
        path = folder / (note["id"] + ".json")
        old = config.read_json(path)
        sig = _signature(items)
        if items and old.get("sig") != sig:
            todo.append((note["id"], items, sig, path))
        elif not items and path.exists():
            path.unlink()
    alive = {n["id"] + ".json" for n in notes}
    for path in folder.glob("*.json"):
        if path.name not in alive:
            path.unlink()
            with _lock:
                _cache.pop(str(path), None)
    for index, (note_id, items, sig, path) in enumerate(todo):
        if cancelled():
            break
        if progress:
            progress(index, len(todo))
        vectors = []
        for at in range(0, len(items), BATCH):
            vectors += embed(model, [t for _w, _s, t in items[at:at + BATCH]])
        config.write_json(path, {"sig": sig, "dim": len(vectors[0]), "chunks": [{"w": w, "s": s, "t": t} for w, s, t in items], "vec": _pack(vectors)})
        with _lock:
            _cache.pop(str(path), None)
    return len(todo)


def _load(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    sig = (stat.st_mtime_ns, stat.st_size)
    with _lock:
        cached = _cache.get(str(path))
        if cached and cached[0] == sig:
            _cache[str(path)] = _cache.pop(str(path))  # most recently used goes last
            return cached[1], cached[2]
    data = config.read_json(path)
    if not data.get("chunks") or not data.get("vec"):
        return None
    flat, dim = _unpack(data["vec"], data["dim"])
    if len(flat) != dim * len(data["chunks"]):
        return None
    vectors = np.frombuffer(flat, dtype=np.float32).reshape(-1, dim) if np is not None else flat
    with _lock:
        _cache[str(path)] = (sig, data["chunks"], (vectors, dim))
        while len(_cache) > CACHE_NOTES:
            _cache.pop(next(iter(_cache)))  # memory stays bounded however many notes there are
    return data["chunks"], (vectors, dim)


def _scores(vectors, dim, query):
    if np is not None:
        return (vectors @ np.asarray(query, dtype=np.float32)).tolist()
    out = []
    for at in range(0, len(vectors), dim):
        out.append(sum(vectors[at + k] * query[k] for k in range(dim)))
    return out


def status(store, model):
    """{"model", "indexed", "total"}: how much of the notes the index covers."""
    total = sum(1 for n in store.slim() if n.get("status") == "done")
    if not model:
        return {"model": None, "indexed": 0, "total": total}
    folder = _folder(model)
    have = {p.stem for p in folder.glob("*.json")} if folder.is_dir() else set()
    return {"model": model, "indexed": sum(1 for n in store.slim() if n.get("status") == "done" and n["id"] in have), "total": total}


def search(store, query, model=None):
    """Related passages: [{"id", "title", "date", "score", "hits": [{"where", "start", "parts"}]}], best first."""
    model = model or chosen()
    query = " ".join(str(query or "").split())[:300]
    if not model or not query:
        return []
    vector = embed(model, [query])[0]
    folder = _folder(model)
    rows = {n["id"]: n for n in store.slim() if n.get("status") == "done"}
    found = []
    for note_id, row in rows.items():
        loaded = _load(folder / (note_id + ".json"))
        if not loaded:
            continue
        items, (vectors, dim) = loaded
        if dim != len(vector):
            continue
        scores = _scores(vectors, dim, vector)
        best = sorted(range(len(scores)), key=lambda i: -scores[i])[:3]
        found.append((scores[best[0]], note_id, [(i, scores[i]) for i in best], items))
    if not found:
        return []
    found.sort(key=lambda f: -f[0])
    top = found[0][0]
    out = []
    for score, note_id, best, items in found[:MAX_NOTES]:
        if score < max(MIN_SCORE, top * RELATIVE):
            break
        hits = []
        for i, s in best:
            if s < max(MIN_SCORE, top * RELATIVE):
                continue
            item = items[i]
            hits.append({"where": "similar" if item["w"] != "transcript" else "transcript", "start": item["s"], "parts": [{"t": item["t"][:SNIPPET] + ("…" if len(item["t"]) > SNIPPET else ""), "m": False}]})
        row = rows[note_id]
        out.append({"id": note_id, "title": row.get("title") or "", "date": row.get("date") or "", "score": round(score, 3), "hits": hits})
    return out


def forget(model):
    """Delete the index of this model."""
    import shutil

    shutil.rmtree(_folder(model), ignore_errors=True)
    built.pop(model, None)
    with _lock:
        _cache.clear()


PASSAGE_CHARS = 1500  # what one passage may hold once its neighbours are added
POOL = 40             # candidates kept from each of the two searches
STOP = frozenset((
    "le la les un une des du de d l et ou en au aux ce ces cet que qui quoi quel quelle quels quelles est sont etait ete pour par sur dans "
    "avec sans mes mon ma ton ta son sa nos notre plus pas ne se il elle ils elles on nous vous je tu me te dit dis parle ont "
    "what which who whom whose the an of to in for and or is are was were be been do did does with about from by at as it this that "
    "these those my our you we they he she how when where why tell said say talk").split())
_WORD = re.compile(r"[a-z0-9]{2,}")
_tokens = {}  # note file -> (items it was read from, one set of words per passage)


def fold(text):
    """Lower case without accents: 'Sécurité' and 'securite' are the same word."""
    return unicodedata.normalize("NFKD", str(text).casefold()).encode("ascii", "ignore").decode()


def terms(query):
    """The words of a question that say something: no filler, no repetition."""
    return [w for w in dict.fromkeys(_WORD.findall(fold(query))) if w not in STOP and (len(w) >= 3 or w.isdigit())]


def _word_sets(path, items):
    with _lock:
        cached = _tokens.get(str(path))
        if cached and cached[0] is items:
            return cached[1]
    sets = [frozenset(_WORD.findall(fold(item["t"]))) for item in items]
    with _lock:
        _tokens[str(path)] = (items, sets)
        while len(_tokens) > CACHE_NOTES * 4:
            _tokens.pop(next(iter(_tokens)))
    return sets


def passages(store, query, model=None, limit=6, per_note=3, note=None, since="", tag=""):
    """The passages that best answer a question, whole and in order of relevance, for the chat to read:
    [{"id", "title", "date", "where", "start", "text", "score"}].

    Two searches are made and merged: by meaning (the embedding model) and by words (names, numbers and acronyms that a
    meaning search can miss). A passage found by both comes first. The lines around a spoken passage are added, because the
    sentence that answers is often the one before or after. At most per_note passages come from one note, so that a long
    recording does not crowd out the others. note, since (a date) and tag narrow the notes that are read."""
    model = model or chosen()
    query = " ".join(str(query or "").split())[:500]
    if not model or not query:
        return []
    vector = embed(model, [query])[0]
    folder = _folder(model)
    wanted = str(tag or "").strip().casefold()
    rows = {}
    for n in store.slim():
        if n.get("status") != "done" or (note and n["id"] != note) or (since and (n.get("date") or "") < since):
            continue
        if wanted and wanted not in [str(t).casefold() for t in n.get("tags") or []]:
            continue
        rows[n["id"]] = n
    pool, meaning, words, total = {}, [], [], 0
    for note_id in rows:
        path = folder / (note_id + ".json")
        loaded = _load(path)
        if not loaded:
            continue
        items, (vectors, dim) = loaded
        if dim != len(vector):
            continue
        pool[note_id] = (items, _word_sets(path, items))
        total += len(items)
        for i, score in enumerate(_scores(vectors, dim, vector)):
            if score >= MIN_SCORE:
                meaning.append((score, note_id, i))
    if not pool:
        return []
    meaning.sort(reverse=True)
    if meaning:
        floor = max(MIN_SCORE, meaning[0][0] * 0.6)
        meaning = [m for m in meaning if m[0] >= floor][:POOL]
    wanted_terms = terms(query)
    if wanted_terms:
        frequency = {w: sum(1 for _, sets in pool.values() for s in sets if w in s) for w in wanted_terms}
        weight = {w: math.log(1 + total / (1 + frequency[w])) for w in wanted_terms}
        everything = sum(weight.values())
        for note_id, (items, sets) in pool.items():
            for i, present in enumerate(sets):
                got = sum(weight[w] for w in wanted_terms if w in present)
                if got and got >= 0.5 * everything:  # most of what the question is about is in the passage
                    words.append((got, note_id, i))
        words.sort(reverse=True)
        words = words[:POOL]
    fused, scores = {}, {}
    for ranking in (meaning, words):
        for rank, (score, note_id, i) in enumerate(ranking):
            fused[(note_id, i)] = fused.get((note_id, i), 0.0) + 1.0 / (60 + rank)
    for score, note_id, i in meaning:
        scores[(note_id, i)] = score
    chosen_ones, count = {}, {}
    for key in sorted(fused, key=lambda k: -fused[k]):
        if len(chosen_ones) >= limit:
            break
        if count.get(key[0], 0) >= per_note:
            continue
        count[key[0]] = count.get(key[0], 0) + 1
        chosen_ones[key] = fused[key]
    out = []
    for note_id in {k[0] for k in chosen_ones}:
        items = pool[note_id][0]
        picked = {i for (n, i) in chosen_ones if n == note_id}
        spoken = lambda j: 0 <= j < len(items) and items[j]["w"] == "transcript"
        reach = set(picked)
        for i in picked:
            if spoken(i):
                reach.update(j for j in (i - 1, i + 1) if spoken(j))
        run = []
        for i in sorted(reach) + [None]:
            if run and (i is None or i != run[-1] + 1 or not (spoken(i) and spoken(run[-1]))):
                members = [items[j] for j in run]
                text = " ".join(str(m["t"]) for m in members)
                best = max(chosen_ones.get((note_id, j), 0.0) for j in run)
                row = rows[note_id]
                out.append((best, {"id": note_id, "title": row.get("title") or "", "date": row.get("date") or "", "where": members[0]["w"],
                                   "start": members[0]["s"], "text": text[:PASSAGE_CHARS],
                                   "score": round(max([scores.get((note_id, j), 0.0) for j in run]), 3)}))
                run = []
            if i is not None:
                run.append(i)
    out.sort(key=lambda x: -x[0])
    return [p for _, p in out]
