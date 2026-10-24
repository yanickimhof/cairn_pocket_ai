"""Markdown, HTML and plain text versions of a note."""

import html

LABELS = {
    "fr": {
        "tldr": "En bref", "actions": "Actions", "context": "Contexte", "key_points": "Points clés",
        "decisions": "Décisions", "topics": "Détail par sujet", "doubtful": "Passages à vérifier",
        "transcript": "Transcription", "reliability": "Fiabilité estimée",
        "footer": "Note produite par Cairn. Rien n'a quitté cet ordinateur.",
        "empty": "Aucune parole détectée dans cet enregistrement.",
        "templates": {"meeting": "Réunion", "call": "Appel", "presentation": "Présentation", "idea": "Idée", "other": "Note"},
    },
    "en": {
        "tldr": "TL;DR", "actions": "Actions", "context": "Context", "key_points": "Key points",
        "decisions": "Decisions", "topics": "Detail by topic", "doubtful": "Passages to check",
        "transcript": "Transcript", "reliability": "Estimated reliability",
        "footer": "Note produced by Cairn. Nothing left this computer.",
        "empty": "No speech detected in this recording.",
        "templates": {"meeting": "Meeting", "call": "Call", "presentation": "Presentation", "idea": "Idea", "other": "Note"},
    },
}


def stamp(seconds):
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%02d:%02d" % (minutes, secs)


def labels(note):
    return LABELS.get(note.get("lang") if note.get("lang") in LABELS else "en", LABELS["en"])


def _meta(note, lab):
    parts = []
    if note.get("date"):
        parts.append(note["date"].replace("T", " ")[:16])
    if note.get("duration"):
        parts.append(stamp(note["duration"]))
    summary = note.get("summary") or {}
    if summary.get("template") in lab["templates"]:
        parts.append(lab["templates"][summary["template"]])
    if note.get("quality") is not None:
        parts.append("%s %d %%" % (lab["reliability"], note["quality"]))
    return " · ".join(parts)


def doubtful_text(note):
    return "\n".join("[%s] %s" % (stamp(p["start"]), p["text"]) for p in note.get("doubtful") or [])


def _action_line(item):
    extra = " ".join(x for x in (item.get("who"), item.get("when")) if x)
    return "%s (%s)" % (item.get("what", ""), extra) if extra else item.get("what", "")


def to_markdown(note, transcript=True):
    lab, s = labels(note), note.get("summary") or {}
    out = ["# %s" % (note.get("title") or note["id"]), "", _meta(note, lab), ""]
    if s.get("empty"):
        out += [lab["empty"], ""]
    if s.get("tldr"):
        out += ["## " + lab["tldr"], "", s["tldr"], ""]
    if s.get("actions"):
        out += ["## " + lab["actions"], ""] + ["- " + _action_line(a) for a in s["actions"]] + [""]
    if s.get("context"):
        out += ["## " + lab["context"], "", s["context"], ""]
    for key in ("key_points", "decisions"):
        if s.get(key):
            out += ["## " + lab[key], ""] + ["- " + x for x in s[key]] + [""]
    if s.get("topics"):
        out += ["## " + lab["topics"], ""]
        for topic in s["topics"]:
            out += ["### " + topic.get("name", ""), "", topic.get("summary", ""), ""]
    if note.get("doubtful"):
        out += ["## " + lab["doubtful"], ""] + ["- [%s] %s" % (stamp(p["start"]), p["text"]) for p in note["doubtful"]] + [""]
    if transcript and note.get("clean"):
        out += ["## " + lab["transcript"], "", note["clean"], ""]
    out += ["---", "", lab["footer"], ""]
    return "\n".join(out)


def to_text(note):
    """Plain text without formatting marks (used as the text flavour of a copy)."""
    lab, s = labels(note), note.get("summary") or {}
    out = [note.get("title") or note["id"], _meta(note, lab), ""]
    if s.get("tldr"):
        out += [s["tldr"], ""]
    if s.get("actions"):
        out += [lab["actions"] + ":"] + ["- " + _action_line(a) for a in s["actions"]] + [""]
    if s.get("context"):
        out += [s["context"], ""]
    for key in ("key_points", "decisions"):
        if s.get(key):
            out += [lab[key] + ":"] + ["- " + x for x in s[key]] + [""]
    return "\n".join(out).strip() + "\n"


_CSS = (
    "body{margin:0;background:#FBFBFD;color:#1D1D1F;font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}"
    "main{max-width:680px;margin:0 auto;padding:40px 24px 64px}h1{font-size:28px;letter-spacing:-.02em;margin:0 0 4px}"
    "h2{font-size:15px;color:#3368A0;margin:28px 0 8px;text-transform:uppercase;letter-spacing:.04em}h3{font-size:16px;margin:16px 0 4px}"
    ".meta{color:#6E6E73;font-size:14px}ul{padding-left:20px;margin:0}li{margin:4px 0}"
    "footer{margin-top:40px;padding-top:16px;border-top:1px solid #E5E5EA;color:#6E6E73;font-size:13px}"
    "details{margin-top:8px}summary{cursor:pointer;color:#3368A0;font-weight:600}.tr{white-space:pre-wrap}"
)


def _ul(items):
    return "<ul>" + "".join("<li>%s</li>" % html.escape(x) for x in items) + "</ul>"


def to_html(note, transcript=True, fragment=False):
    """Self-contained HTML, no external resource. fragment=True gives the body only (for rich copy)."""
    lab, s = labels(note), note.get("summary") or {}
    e = html.escape
    body = ["<h1>%s</h1>" % e(note.get("title") or note["id"]), '<div class="meta">%s</div>' % e(_meta(note, lab))]
    if s.get("empty"):
        body.append("<p>%s</p>" % e(lab["empty"]))
    if s.get("tldr"):
        body.append("<h2>%s</h2><p>%s</p>" % (e(lab["tldr"]), e(s["tldr"])))
    if s.get("actions"):
        body.append("<h2>%s</h2>%s" % (e(lab["actions"]), _ul([_action_line(a) for a in s["actions"]])))
    if s.get("context"):
        body.append("<h2>%s</h2><p>%s</p>" % (e(lab["context"]), e(s["context"])))
    for key in ("key_points", "decisions"):
        if s.get(key):
            body.append("<h2>%s</h2>%s" % (e(lab[key]), _ul(s[key])))
    if s.get("topics"):
        body.append("<h2>%s</h2>" % e(lab["topics"]))
        body += ["<h3>%s</h3><p>%s</p>" % (e(t.get("name", "")), e(t.get("summary", ""))) for t in s["topics"]]
    if note.get("doubtful"):
        body.append("<h2>%s</h2>%s" % (e(lab["doubtful"]), _ul(["[%s] %s" % (stamp(p["start"]), p["text"]) for p in note["doubtful"]])))
    if transcript and note.get("clean"):
        body.append('<h2>%s</h2><div class="tr">%s</div>' % (e(lab["transcript"]), e(note["clean"])))
    body.append("<footer>%s</footer>" % e(lab["footer"]))
    inner = "\n".join(body)
    if fragment:
        return inner
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s</title><style>%s</style></head><body><main>%s</main></body></html>"
    ) % (note.get("lang") or "en", e(note.get("title") or note["id"]), _CSS, inner)
