"""Tags on notes: free words the person gives to find notes by (a project, a person, a topic)."""

import collections

MAX_TAGS = 12
MAX_LEN = 30


def clean(value):
    """The list of tags, checked: no #, no blanks, no duplicates (case does not matter), at most MAX_TAGS of MAX_LEN characters."""
    if not isinstance(value, (list, tuple)):
        raise ValueError("The tags must be a list.")
    out, seen = [], set()
    for item in value:
        tag = " ".join(str(item).replace("#", " ").split())[:MAX_LEN].strip()
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            out.append(tag)
    if len(out) > MAX_TAGS:
        raise ValueError("At most %d tags on a note." % MAX_TAGS)
    return out


def counts(rows):
    """[{"tag", "count"}] over the notes, the most used first. The spelling shown is the most common one."""
    spelled, total = collections.defaultdict(collections.Counter), collections.Counter()
    for row in rows:
        for tag in row.get("tags") or []:
            spelled[tag.casefold()][tag] += 1
            total[tag.casefold()] += 1
    out = [{"tag": spelled[k].most_common(1)[0][0], "count": n} for k, n in total.items()]
    return sorted(out, key=lambda x: (-x["count"], x["tag"].casefold()))
