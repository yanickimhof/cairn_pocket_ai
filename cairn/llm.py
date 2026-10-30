"""Local language model (Ollama on 127.0.0.1): title and summarize."""

import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request

from pathlib import Path

from . import config
from . import system as machine

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


def version():
    """Version of the running model server, e.g. "0.40.11", or "" if it cannot be read."""
    try:
        return str(_get("/api/version", timeout=2).get("version", ""))
    except (urllib.error.URLError, OSError, ValueError, LLMError):
        return ""


def parse_ollama_version(text):
    """Version shown by `ollama --version`: the installed program, and the server running now if it differs
    ("ollama version is X" is the server, "Warning: client version is Y" the installed program)."""
    server = re.search(r"ollama version is (\d+(?:\.\d+)+)", text)
    client = re.search(r"client version is (\d+(?:\.\d+)+)", text)
    installed = (client or server)
    installed = installed.group(1) if installed else "-"
    running = server.group(1) if server else ""
    return installed, running if running and running != installed else ""


def _numbers(text):
    out = []
    for piece in str(text).split("-")[0].split("."):
        if not piece.isdigit():
            break
        out.append(int(piece))
    return tuple(out)


def at_least(found, minimum):
    """True if version `found` is `minimum` or newer. An unreadable version is not held against the model:
    the server's own error will say what is wrong."""
    return not _numbers(found) or _numbers(found) >= _numbers(minimum)


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


CHAT_TIMEOUT = 900  # seconds one call may take before the model server is taken for stuck
KEEP_ALIVE = "30m"      # how long the model stays loaded between two notes of a batch
KEEP_ALIVE_MIN_GB = 24  # only on a computer with this much memory: loading it again costs about 15 s, holding it costs 6 GB


def chat(system, user, schema=None, num_ctx=8192, timeout=CHAT_TIMEOUT, num_predict=None):
    body = {
        "model": config.install_config()["llm"],
        "stream": False,
        "think": False,
        "options": dict({"temperature": 0.2, "num_ctx": num_ctx}, **({"num_predict": num_predict} if num_predict else {})),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if schema:
        body["format"] = schema
    if machine.ram_gb() >= KEEP_ALIVE_MIN_GB:
        body["keep_alive"] = KEEP_ALIVE
    try:
        try:
            data = _post("/api/chat", body, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code == 400 and body.pop("think", None) is not None:  # model without thinking mode
                data = _post("/api/chat", body, timeout=timeout)
            elif error.code == 501 and schema:  # the server cannot give structured output for this model
                raise LLMError(
                    "This model cannot return structured notes with the Ollama now running (structured output "
                    "unavailable). Choose another model in Settings > Models, or update Ollama and restart it."
                ) from error
            else:
                raise
    except (urllib.error.URLError, OSError) as error:
        if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError):
            raise LLMError("The summary model did not answer within %d minutes. Check Ollama, then try again." % (timeout // 60)) from error
        raise LLMError("The local model server is not reachable (%s)." % error) from error
    return (data.get("message", {}).get("content") or "").strip()


STREAM_TIMEOUT = 300  # seconds without a word from the model before a streamed answer is given up


def chat_stream(messages, num_ctx=8192, num_predict=None, timeout=STREAM_TIMEOUT):
    """The answer of the model, piece by piece (a generator of text). Closing the generator closes the connection, which stops the
    model at once: a question the person has left costs nothing more."""
    body = {
        "model": config.install_config()["llm"],
        "stream": True,
        "think": False,
        "options": dict({"temperature": 0.2, "num_ctx": num_ctx}, **({"num_predict": num_predict} if num_predict else {})),
        "messages": list(messages),
    }
    if machine.ram_gb() >= KEEP_ALIVE_MIN_GB:
        body["keep_alive"] = KEEP_ALIVE

    def open_stream():
        request = urllib.request.Request(
            "http://%s/api/chat" % _host(), data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        # Loopback only, plain http, fixed scheme: the address is validated in _host().
        return urllib.request.urlopen(request, timeout=timeout)  # nosec B310

    try:
        try:
            response = open_stream()
        except urllib.error.HTTPError as error:
            if error.code == 400 and body.pop("think", None) is not None:  # model without thinking mode
                response = open_stream()
            else:
                raise
    except (urllib.error.URLError, OSError) as error:
        if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError):
            raise LLMError("The model did not answer. Check Ollama, then try again.") from error
        raise LLMError("The local model server is not reachable (%s)." % error) from error
    with response:
        try:
            for line in response:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if data.get("error"):
                    raise LLMError(str(data["error"])[:200])
                piece = (data.get("message") or {}).get("content") or ""
                if piece:
                    yield piece
                if data.get("done"):
                    return
        except (urllib.error.URLError, OSError) as error:
            raise LLMError("The model stopped answering (%s)." % error) from error


def load(model, num_ctx=None, keep_alive="10m"):
    """Load a model into memory ahead of use (an empty request), so that the first question does not wait for it."""
    body = {"model": model, "messages": [], "keep_alive": keep_alive}
    if num_ctx:
        body["options"] = {"num_ctx": num_ctx}
    try:
        _post("/api/chat", body, timeout=120)
    except (urllib.error.URLError, OSError, ValueError, LLMError):
        pass


PROBE_CTX = 8192
_READY = {"model": None, "at": 0.0}
_CAPABLE = {}  # (model, server version) once it has returned structured notes in this run: that does not change, so it is asked once
_PROBE = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def unload():
    """Free the model's memory now."""
    try:
        _post("/api/chat", {"model": config.install_config()["llm"], "messages": [], "keep_alive": 0}, timeout=30)
    except (urllib.error.URLError, OSError, ValueError, LLMError):
        pass


def preflight(max_age=120):
    """Say now, in a few seconds, whether a note can be written: the model server answers, the chosen model is
    installed, and it can return structured notes. Run before any long work, so a problem is not found only after
    a transcription. The structured notes are tried once per model and server version. On a computer with little
    memory the model is unloaded right after: held beside the speech and speaker models it slowed the speaker pass
    from 22 s to 82 s in a measurement on 16 GB; the summary loads it when it is needed."""
    name = config.install_config()["llm"]
    if _READY["model"] == name and time.time() - _READY["at"] < max_age:
        return
    if not available():
        raise LLMError("The local model server (Ollama) is not running. Start it, then try again.")
    have = {m.get("name") for m in models()}
    if name not in have and name + ":latest" not in have:
        raise LLMError("The summary model %s is not installed in Ollama. Choose another one in Settings > Models." % name)
    ident = (name, version())
    if ident not in _CAPABLE:
        # the same context as a short note: the model server loads the model again when the context asked for changes
        chat("Answer with a JSON object.", "Is this working? Answer yes.", schema=_PROBE, num_ctx=PROBE_CTX, num_predict=16, timeout=300)
        _CAPABLE[ident] = True
        if machine.ram_gb() < KEEP_ALIVE_MIN_GB:
            unload()
    _READY.update(model=name, at=time.time())


def _ctx(text):
    return 8192 if len(text.split()) < 3500 else 16384


def _schema(level, custom=False):
    text = {"type": "string"}
    lst = {"type": "array", "items": {"type": "string"}}
    action = {"type": "object", "properties": {"what": text, "who": text, "when": text}, "required": ["what"]}
    props = {"template": {"type": "string", "enum": TEMPLATES}, "title": text, "tldr": text, "actions": {"type": "array", "items": action}}
    if custom:  # the person's own template: the sections it asks for, in its order, instead of the usual fields
        props["sections"] = {"type": "array", "items": {"type": "object", "properties": {"heading": text, "text": text}, "required": ["heading", "text"]}}
        return {"type": "object", "properties": props, "required": ["template", "title", "tldr", "actions", "sections"]}
    if level in ("mid", "full"):
        props.update({"context": text, "key_points": lst, "decisions": lst})
    if level == "full":
        props["topics"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"name": text, "summary": text}, "required": ["name", "summary"]},
        }
    return {"type": "object", "properties": props, "required": ["template", "title", "tldr", "actions"]}


_CUSTOM_FIELDS = {
    "short": "a short title, the type of conversation, a 1 or 2 sentence TL;DR, the actions to take and the sections asked for, one line each",
    "mid": "a short title, the type of conversation, a 1 or 2 sentence TL;DR, the actions to take and the sections asked for, a few sentences each",
    "full": "a short title, the type of conversation, a TL;DR, the actions to take and the sections asked for, detailed",
}

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


_MAIL = {"type": "object", "properties": {"subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["subject", "body"]}


def followup(note, lang):
    """A short follow-up email for a finished note: {"subject", "body"}."""
    summary = note.get("summary") or {}
    facts = {"title": note.get("title") or "", "summary": summary.get("tldr") or "", "actions": summary.get("actions") or [],
             "key_points": summary.get("key_points") or [], "decisions": summary.get("decisions") or [],
             "speakers": sorted({v for v in (note.get("speaker_names") or {}).values() if v})}
    system = (
        "You write the follow-up email sent after a meeting or call. Write in %s. Reply with a subject and a body. The body is plain text "
        "with line breaks, laid out exactly like this:\n"
        "a greeting line\n\n"
        "two or three sentences on what was decided or agreed\n\n"
        "Actions: (only when there are actions, one line each, starting with a dash, saying who does what and by when)\n\n"
        "a short closing line\n\n"
        "Short and factual: no filler, no thanks for their time, nothing invented, no markdown. The subject names the topic." % NAMES[lang]
    )
    raw = chat(system, json.dumps(facts, ensure_ascii=False), schema=_MAIL, num_ctx=4096, timeout=300)
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise LLMError("The model did not return a usable email.") from error
    if not isinstance(data, dict) or not str(data.get("body") or "").strip():
        raise LLMError("The model did not return a usable email.")
    body = str(data["body"]).replace("\\n", "\n").strip()
    return {"subject": str(data.get("subject") or "").strip()[:200], "body": body}


def suggest_tags(note, existing):
    """At most 3 of the person's existing tags that fit a finished note, none when none fits. `existing` is [{"tag", "count"}]."""
    names = [x["tag"] for x in existing or []]
    have = {t.casefold() for t in note.get("tags") or []}
    names = [n for n in names if n.casefold() not in have]
    summary = note.get("summary") or {}
    if not names or not summary.get("tldr"):
        return []
    facts = {"title": note.get("title") or "", "summary": summary.get("tldr") or "", "key_points": summary.get("key_points") or [],
             "actions": [a.get("what") for a in summary.get("actions") or [] if isinstance(a, dict)]}
    schema = {"type": "object", "properties": {"tags": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": names}}}, "required": ["tags"]}
    system = ("You file notes. From the list of tags given by the person, pick at most 3 that clearly fit the note, and none when none fits. "
              "Only use tags from this list: %s." % ", ".join(names[:60]))
    raw = chat(system, json.dumps(facts, ensure_ascii=False), schema=schema, num_ctx=4096, timeout=120)
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    picked = data.get("tags") if isinstance(data, dict) else None
    return [t for t in dict.fromkeys(picked or []) if t in names][:3]


def summarize(text, level, lang, progress=None, vocabulary=None, instructions=None):
    """Structured note: title, type, TL;DR, actions and, depending on the level, more."""
    if len(text.split()) < 5:
        return {"empty": True, "template": "other", "title": "", "tldr": "", "actions": []}
    source = _condense(text, lang, progress)
    if progress:
        progress(parts_of(text) - 1)  # the final call
    system = (
        "You write professional notes from the transcript of a recorded conversation. Write in %s. "
        "Provide %s. Be factual and concise. Invent nothing: leave a field empty when the transcript does not say. "
        "Actions name who does what and by when only when the transcript says so."
        % (NAMES[lang], _CUSTOM_FIELDS[level] if instructions else _FIELDS[level])
    )
    if vocabulary:
        system += (" Spell these names and terms exactly as listed, and use the listed spelling whenever the transcript has a close "
                   "variant of one of them: %s." % "; ".join(vocabulary[:300]))
    if instructions:
        system += (" The person asked for this kind of note: %s. Write it as the sections that ask names, one entry of `sections` each, "
                   "with a short heading and its text, in the order of the request; a section the transcript says nothing about "
                   "gets the text \"-\"." % instructions)
    raw = chat(system, source, schema=_schema(level, bool(instructions)), num_ctx=_ctx(source))
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
    if instructions:
        data["sections"] = [{"heading": str(x.get("heading") or "").strip(), "text": str(x.get("text") or "").strip()}
                            for x in data.get("sections") or [] if isinstance(x, dict) and str(x.get("heading") or "").strip()]
    return data
