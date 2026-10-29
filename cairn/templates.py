"""The person's own note templates: a name and an instruction in everyday words, kept in the settings.

An instruction says what the summary should contain and how it should read ("client report: goals, decisions, risks, next
steps"). It is given to the summary model when a note is written with that template."""

import hashlib
import re

MAX_TEMPLATES = 20
MAX_NAME = 40
MAX_PROMPT = 800
PREFIX = "c-"


def new_id(name, taken):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:16] or "t"
    for n in range(1000):
        found = PREFIX + slug + "-" + hashlib.sha1((name + str(n)).encode("utf-8"), usedforsecurity=False).hexdigest()[:4]
        if found not in taken:
            return found
    raise ValueError("Too many templates.")


def parse(value):
    """The list of templates, checked: [{"id", "name", "prompt"}]. A template without an id gets one."""
    if not isinstance(value, (list, tuple)):
        raise ValueError("The templates must be a list.")
    out, ids, names = [], set(), set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("A template needs a name and an instruction.")
        name = " ".join(str(item.get("name") or "").split())
        prompt = " ".join(str(item.get("prompt") or "").split())
        if not name or not prompt:
            raise ValueError("A template needs a name and an instruction.")
        if len(name) > MAX_NAME:
            raise ValueError("A template name is longer than %d characters." % MAX_NAME)
        if len(prompt) > MAX_PROMPT:
            raise ValueError("A template instruction is longer than %d characters." % MAX_PROMPT)
        if name.casefold() in names:
            raise ValueError("Two templates have the same name.")
        names.add(name.casefold())
        tid = str(item.get("id") or "")
        if not re.fullmatch(PREFIX + r"[a-z0-9-]{1,40}", tid) or tid in ids:
            tid = new_id(name, ids)
        ids.add(tid)
        out.append({"id": tid, "name": name, "prompt": prompt})
    if len(out) > MAX_TEMPLATES:
        raise ValueError("At most %d templates." % MAX_TEMPLATES)
    return out


def find(templates, template_id):
    return next((t for t in templates or [] if t.get("id") == template_id), None)
