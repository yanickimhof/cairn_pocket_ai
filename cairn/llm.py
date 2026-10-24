"""Local language model (Ollama on 127.0.0.1): clean, title and summarize."""

import json
import urllib.error
import urllib.request

from . import config

NAMES = {"fr": "French", "en": "English"}
TEMPLATES = ["meeting", "call", "presentation", "idea", "other"]
CHUNK_WORDS = 700
LONG_WORDS = 5000


class LLMError(RuntimeError):
    pass


def _host():
    host = config.install_config()["ollama_host"]
    if not config.LOOPBACK.fullmatch(host):
        raise LLMError("The model server must listen on 127.0.0.1, found %r" % host)
    return host


def _post(path, body, timeout=1800):
    request = urllib.request.Request(
        "http://%s%s" % (_host(), path), data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    # Loopback only, plain http, fixed scheme: the address is validated above.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return json.load(response)


def _get(path, timeout=5):
    # Loopback only, plain http, fixed scheme: the address is validated in _host().
    with urllib.request.urlopen("http://%s%s" % (_host(), path), timeout=timeout) as response:  # nosec B310
        return json.load(response)


def available():
    try:
        _get("/api/version", timeout=2)
        return True
    except (urllib.error.URLError, OSError, ValueError, LLMError):
        return False


def models():
    try:
        return _get("/api/tags").get("models", [])
    except (urllib.error.URLError, OSError, ValueError, LLMError):
        return []


def chat(system, user, schema=None, num_ctx=8192):
    body = {
        "model": config.install_config()["llm"],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": num_ctx},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if schema:
        body["format"] = schema
    try:
        try:
            data = _post("/api/chat", body)
        except urllib.error.HTTPError as error:
            if error.code == 400 and body.pop("think", None) is not None:  # model without thinking mode
                data = _post("/api/chat", body)
            else:
                raise
    except (urllib.error.URLError, OSError) as error:
        raise LLMError("The local model server is not reachable (%s)." % error) from error
    return (data.get("message", {}).get("content") or "").strip()


def _ctx(text):
    return 8192 if len(text.split()) < 3500 else 16384


def clean(lines, lang):
    """Rewrite raw recognized speech into readable text, chunk by chunk."""
    chunks, current, count = [], [], 0
    for line in lines:
        words = len(line.split())
        if count + words > CHUNK_WORDS and current:
            chunks.append(current)
            current, count = [], 0
        current.append(line)
        count += words
    if current:
        chunks.append(current)
    system = (
        "You correct raw speech-recognition transcripts of recorded conversations. Rewrite the excerpt in clean, "
        "readable %s: fix punctuation, obviously misrecognized words and filler repetitions. Do not invent anything, "
        "do not summarize, do not remove information. Translate passages in another language into %s. "
        "Keep the [mm:ss] markers at the start of paragraphs. Reply with the corrected text only." % (NAMES[lang], NAMES[lang])
    )
    return "\n\n".join(chat(system, "\n".join(chunk)) for chunk in chunks)


def _schema(level):
    text = {"type": "string"}
    lst = {"type": "array", "items": {"type": "string"}}
    action = {"type": "object", "properties": {"what": text, "who": text, "when": text}, "required": ["what"]}
    props = {"template": {"type": "string", "enum": TEMPLATES}, "title": text, "tldr": text, "actions": {"type": "array", "items": action}}
    if level in ("mid", "full"):
        props.update({"context": text, "key_points": lst, "decisions": lst})
    if level == "full":
        props["topics"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"name": text, "summary": text}, "required": ["name", "summary"]},
        }
    return {"type": "object", "properties": props, "required": ["template", "title", "tldr", "actions"]}


_FIELDS = {
    "short": "a short title, the type of conversation, a 1 or 2 sentence TL;DR and the actions to take",
    "mid": "a short title, the type of conversation, a 1 or 2 sentence TL;DR, the actions, a 2 sentence context, the key points and the decisions",
    "full": "a short title, the type of conversation, a TL;DR, the actions, a context, the key points, the decisions and a summary for each topic discussed",
}


def _condense(text, lang):
    """Very long recordings: reduce each part to its facts first, so the final prompt fits."""
    words = text.split()
    if len(words) <= LONG_WORDS:
        return text
    system = "Extract the facts, decisions, numbers, names and actions from this part of a conversation, as dense bullet points, in %s. Invent nothing." % NAMES[lang]
    parts = [" ".join(words[i : i + 3000]) for i in range(0, len(words), 3000)]
    return "\n".join(chat(system, part, num_ctx=8192) for part in parts)


def summarize(text, level, lang):
    """Structured note: title, type, TL;DR, actions and, depending on the level, more."""
    if len(text.split()) < 5:
        return {"empty": True, "template": "other", "title": "", "tldr": "", "actions": []}
    source = _condense(text, lang)
    system = (
        "You write professional notes from the transcript of a recorded conversation. Write in %s. "
        "Provide %s. Be factual and concise. Invent nothing: leave a field empty when the transcript does not say. "
        "Actions name who does what and by when only when the transcript says so." % (NAMES[lang], _FIELDS[level])
    )
    raw = chat(system, source, schema=_schema(level), num_ctx=_ctx(source))
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise LLMError("The model did not return a usable summary.") from error
    if not isinstance(data, dict):
        raise LLMError("The model did not return a usable summary.")
    data.setdefault("template", "other")
    if data["template"] not in TEMPLATES:
        data["template"] = "other"
    for key in ("title", "tldr"):
        data[key] = str(data.get(key) or "").strip()
    data["actions"] = [a for a in data.get("actions") or [] if isinstance(a, dict) and a.get("what")]
    return data
