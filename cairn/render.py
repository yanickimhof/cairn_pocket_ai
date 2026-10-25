"""Markdown, HTML and plain text versions of a note."""

import html
import re

LABELS = {
    "fr": {
        "tldr": "En bref", "actions": "Actions", "context": "Contexte", "key_points": "Points clés",
        "decisions": "Décisions", "topics": "Détail par sujet", "doubtful": "Passages à vérifier",
        "transcript": "Transcription", "raw": "Confiance de la transcription brute", "fidelity": "Fidélité de la note au transcript",
        "footer": "Note produite par Cairn · Pocket AI souverain. Rien n'a quitté cet ordinateur.", "words": "mots", "processed": "traité en", "models": "Modèles",
        "empty": "Aucune parole détectée dans cet enregistrement.",
        "templates": {"meeting": "Réunion", "call": "Appel", "presentation": "Présentation", "idea": "Idée", "other": "Note"},
    },
    "en": {
        "tldr": "TL;DR", "actions": "Actions", "context": "Context", "key_points": "Key points",
        "decisions": "Decisions", "topics": "Detail by topic", "doubtful": "Passages to check",
        "transcript": "Transcript", "raw": "Raw transcript confidence", "fidelity": "Note fidelity to the transcript",
        "footer": "Produced by Cairn · Sovereign Pocket AI. Nothing left this computer.", "words": "words", "processed": "processed in", "models": "Models",
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


def _scores(note, lab):
    """The two indicators, each with its own label: fidelity of the finished note and the speech
    engine's confidence in the raw transcript."""
    out = []
    if note.get("fidelity") is not None:
        out.append((lab["fidelity"], note["fidelity"]))
    if note.get("quality") is not None:
        out.append((lab["raw"], note["quality"]))
    return out


def _meta(note, lab):
    parts = []
    if note.get("date"):
        parts.append(note["date"].replace("T", " ")[:16])
    if note.get("duration"):
        parts.append(stamp(note["duration"]))
    summary = note.get("summary") or {}
    if summary.get("template") in lab["templates"]:
        parts.append(lab["templates"][summary["template"]])
    parts += ["%s %d %%" % (text, value) for text, value in _scores(note, lab)]
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
    info = _footer_info(note, lab)
    out += ["---", "", lab["footer"] + ((" " + info + ".") if info else ""), ""]
    # what the model wrote (or the audio said) must not become markup in a viewer that renders HTML inside markdown
    return re.sub(r"<(?=[A-Za-z/!?])", "&lt;", "\n".join(out))


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


def _footer_info(note, lab):
    parts = []
    models = note.get("models") or {}
    names = [m for m in (models.get("speech"), models.get("llm")) if m]
    if names:
        parts.append(" · ".join(names))
    if note.get("elapsed"):
        parts.append("%s %s" % (lab["processed"], stamp(note["elapsed"])))
    return " · ".join(parts)


_PAGE_CSS = (
    ":root{--bg:#F3F4F7;--card:#FFFFFF;--ink:#1D1D1F;--mute:#6E6E73;--line:#E5E5EA;--accent:#3368A0;--soft:#EEF3F9}"
    "@media(prefers-color-scheme:dark){:root{--bg:#111214;--card:#1B1C1F;--ink:#F2F2F4;--mute:#9A9AA2;--line:#2C2D31;--accent:#7FB0E6;--soft:#1F2833}}"
    "body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}"
    "main{max-width:720px;margin:0 auto;padding:32px 16px 56px}"
    ".card{background:var(--card);border-radius:20px;padding:36px 36px 28px;box-shadow:0 1px 2px rgba(0,0,0,.05),0 12px 40px rgba(0,0,0,.07)}"
    "details>summary{cursor:pointer;list-style:none}details>summary::-webkit-details-marker{display:none}"
    "details[open]>summary .chev{transform:rotate(90deg)}.chev{display:inline-block;transition:transform .15s}"
    "@media(max-width:560px){.card{padding:24px 20px}}"
    "@media print{body{background:#fff}.card{box-shadow:none;padding:0}details{display:block}}"
)

_LIGHT = {"ink": "#1D1D1F", "mute": "#6E6E73", "line": "#E5E5EA", "accent": "#3368A0", "soft": "#EEF3F9"}
_LOGO = (
    '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" style="vertical-align:-5px">'
    '<rect x="8" y="3" width="8" height="4.5" rx="2.2" fill="#9FBBDB"/><rect x="5.5" y="9" width="13" height="5" rx="2.5" fill="#5B8BC0"/>'
    '<rect x="3" y="15.5" width="18" height="5.5" rx="2.7" fill="#3368A0"/></svg>'
)


def to_html(note, transcript=True, fragment=False):
    """HTML version of a note. fragment=True gives inline-styled markup without the page, safe to paste in an email."""
    lab, s = labels(note), note.get("summary") or {}
    e = html.escape

    def c(name):
        return "var(--%s)" % name if not fragment else _LIGHT[name]

    h2 = "font-size:13px;font-weight:700;color:%s;margin:28px 0 8px;text-transform:uppercase;letter-spacing:.06em" % c("accent")
    body = []
    if not fragment:
        body.append(
            '<div style="font-size:13px;font-weight:600;color:%s;letter-spacing:.02em;margin-bottom:18px">%s Cairn <span style="color:%s;font-weight:400">· Sovereign Pocket AI</span></div>'
            % (c("accent"), _LOGO, c("mute"))
        )
    body.append('<h1 style="font-size:28px;line-height:1.2;letter-spacing:-.02em;margin:0 0 12px">%s</h1>' % e(note.get("title") or note["id"]))
    chips = []
    if note.get("date"):
        chips.append(e(note["date"].replace("T", " ")[:16]))
    if note.get("duration"):
        chips.append(e(stamp(note["duration"])))
    if s.get("template") in lab["templates"]:
        chips.append(e(lab["templates"][s["template"]]))
    if chips or _scores(note, lab):
        body.append(
            '<div style="display:flex;flex-wrap:wrap;gap:6px 8px;margin-bottom:4px">%s%s</div>'
            % (
                "".join('<span style="font-size:13px;color:%s;background:%s;border-radius:999px;padding:3px 12px">%s</span>' % (c("mute"), c("soft"), t) for t in chips),
                "".join(
                    '<span style="font-size:13px;color:%s;background:%s;border-radius:999px;padding:3px 12px">%s %d %%</span>'
                    % (c("mute"), c("soft"), e(text), value)
                    for text, value in _scores(note, lab)
                ),
            )
        )
    if s.get("empty"):
        body.append("<p>%s</p>" % e(lab["empty"]))
    if s.get("tldr"):
        body.append(
            '<div style="margin:22px 0 0;padding:14px 18px;background:%s;border-left:4px solid %s;border-radius:10px">'
            '<div style="font-size:12px;font-weight:700;color:%s;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">%s</div>%s</div>'
            % (c("soft"), c("accent"), c("accent"), e(lab["tldr"]), e(s["tldr"]))
        )
    if s.get("actions"):
        rows = []
        for a in s["actions"]:
            meta = " ".join(
                '<span style="font-size:12px;color:%s;background:%s;border-radius:999px;padding:1px 9px;white-space:nowrap">%s</span>' % (c("mute"), c("soft"), e(x))
                for x in (a.get("who"), a.get("when")) if x
            )
            rows.append(
                '<li style="margin:8px 0;list-style:none;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">'
                '<span style="color:%s">&#9744;</span><span style="flex:1;min-width:200px">%s</span>%s</li>' % (c("accent"), e(a.get("what", "")), meta)
            )
        body.append('<h2 style="%s">%s</h2><ul style="padding:0;margin:0">%s</ul>' % (h2, e(lab["actions"]), "".join(rows)))
    if s.get("context"):
        body.append('<h2 style="%s">%s</h2><p style="margin:0">%s</p>' % (h2, e(lab["context"]), e(s["context"])))
    for key in ("key_points", "decisions"):
        if s.get(key):
            items = "".join('<li style="margin:5px 0">%s</li>' % e(x) for x in s[key])
            body.append('<h2 style="%s">%s</h2><ul style="padding-left:20px;margin:0">%s</ul>' % (h2, e(lab[key]), items))
    if s.get("topics"):
        body.append('<h2 style="%s">%s</h2>' % (h2, e(lab["topics"])))
        body += [
            '<h3 style="font-size:16px;margin:14px 0 2px">%s</h3><p style="margin:0">%s</p>' % (e(t.get("name", "")), e(t.get("summary", "")))
            for t in s["topics"]
        ]
    if note.get("doubtful") and not fragment:
        items = "".join('<li style="margin:5px 0">[%s] %s</li>' % (stamp(p["start"]), e(p["text"])) for p in note["doubtful"])
        body.append('<h2 style="%s">%s</h2><ul style="padding-left:20px;margin:0">%s</ul>' % (h2, e(lab["doubtful"]), items))
    if transcript and note.get("clean"):
        words = len(note["clean"].split())
        text = '<div style="white-space:pre-wrap;margin-top:12px;color:%s">%s</div>' % (c("ink"), e(note["clean"]))
        if fragment:
            body.append('<h2 style="%s">%s</h2>%s' % (h2, e(lab["transcript"]), text))
        else:
            body.append(
                '<details style="margin-top:28px;border-top:1px solid %s;padding-top:16px"><summary style="font-size:13px;font-weight:700;color:%s;text-transform:uppercase;letter-spacing:.06em">'
                '<span class="chev">&#9656;</span> %s <span style="font-weight:400;color:%s;text-transform:none;letter-spacing:0">· %d %s</span></summary>%s</details>'
                % (c("line"), c("accent"), e(lab["transcript"]), c("mute"), words, e(lab["words"]), text)
            )
    info = _footer_info(note, lab)
    body.append(
        '<div style="margin-top:36px;padding-top:16px;border-top:1px solid %s;color:%s;font-size:13px">%s%s%s</div>'
        % (c("line"), c("mute"), "" if fragment else _LOGO + " ", e(lab["footer"]), ('<div style="margin-top:4px">%s</div>' % e(info)) if info else "")
    )
    inner = "\n".join(body)
    if fragment:
        return '<div style="font:16px/1.6 -apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;color:#1D1D1F;max-width:680px">%s</div>' % inner
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s</title><style>%s</style></head><body><main><div class=\"card\">%s</div></main></body></html>"
    ) % (e(note.get("lang") if note.get("lang") in LABELS else "en"), e(note.get("title") or note["id"]), _PAGE_CSS, inner)
