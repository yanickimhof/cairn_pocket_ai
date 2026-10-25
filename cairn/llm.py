"""Local language model (Ollama on 127.0.0.1): title and summarize."""

import json
import os
import shutil
import urllib.error
import urllib.request

from pathlib import Path

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


def delete_model(name):
    """Remove one model from the local model server (loopback only)."""
    request = urllib.request.Request(
        "http://%s/api/delete" % _host(), data=json.dumps({"model": name}).encode(),
        headers={"Content-Type": "application/json"}, method="DELETE",
    )
    with urllib.request.urlopen(request, timeout=60):  # nosec B310 (loopback, fixed scheme)
        return True


def _get(path, timeout=5):
    # Loopback only, plain http, fixed scheme: the address is validated in _host().
    with urllib.request.urlopen("http://%s%s" % (_host(), path), timeout=timeout) as response:  # nosec B310
        return json.load(response)


def find_ollama(cfg=None):
    """Path of the Ollama program (configured, on the PATH, or in a usual place), or None."""
    cfg = cfg or config.install_config()
    home = config.home()
    candidates = [
        cfg.get("ollama_bin"), shutil.which("ollama"),
        home / "bin" / "ollama" / "ollama.exe",
        home / "bin" / "Ollama.app" / "Contents" / "Resources" / "ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


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


def parts_of(text):
    """Number of model calls needed to write the note: one per 3000 words of a very long recording, plus the final one."""
    words = len(text.split())
    return 1 if words <= LONG_WORDS else -(-words // 3000) + 1


def _condense(text, lang, progress=None):
    """Very long recordings: reduce each part to its facts first, so the final prompt fits."""
    words = text.split()
    if len(words) <= LONG_WORDS:
        return text
    system = "Extract the facts, decisions, numbers, names and actions from this part of a conversation, as dense bullet points, in %s. Invent nothing." % NAMES[lang]
    parts = [" ".join(words[i : i + 3000]) for i in range(0, len(words), 3000)]
    out = []
    for index, part in enumerate(parts):
        if progress:
            progress(index)
        out.append(chat(system, part, num_ctx=8192))
    return "\n".join(out)


def summarize(text, level, lang, progress=None):
    """Structured note: title, type, TL;DR, actions and, depending on the level, more."""
    if len(text.split()) < 5:
        return {"empty": True, "template": "other", "title": "", "tldr": "", "actions": []}
    source = _condense(text, lang, progress)
    if progress:
        progress(parts_of(text) - 1)  # the final call
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
