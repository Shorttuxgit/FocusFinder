# --------------------------------------------------
# Turns long course titles into short, unique button labels
# --------------------------------------------------

import re
from collections import defaultdict

# Words that only describe the qualification, never the subject
_NOISE_WORDS = {
    "a", "as", "aa", "gce", "gcse", "btec", "level", "lvl", "year", "yr", "yrs",
    "years", "hr", "hrs", "hour", "hours", "cambridge", "technical", "dip",
    "diploma", "certificate", "cert", "extended", "foundation", "award", "national",
    "ocr", "aqa", "edexcel", "pearson", "ib", "t", "resit", "re-sit", "and", "ext",
}

_NUMBER = re.compile(r"^\d+$|^l\d+$")
SEPARATORS = " - "
MAX_LABEL = 34


def _is_noise(part):
    # A part is "noise" when every word in it is a qualification word or a number
    words = re.findall(r"[a-z0-9*\-]+", part.lower())
    if not words:
        return True
    return all(word in _NOISE_WORDS or _NUMBER.match(word) for word in words)


def split_title(title):
    """Return (meaningful_parts, noise_parts) in the order they appear."""
    title = (title or "").strip()

    # Text in brackets is treated as an extra part
    brackets = re.findall(r"\(([^)]*)\)", title)
    rest = re.sub(r"\([^)]*\)", " ", title)

    parts = [p.strip(" -–—:,;") for p in re.split(r"\s*:\s*|\s+[-–—]\s+", rest)]
    parts += [b.strip(" -–—:,;") for b in brackets]
    parts = [p for p in parts if p]

    meaningful = [p for p in parts if not _is_noise(p)]
    noise = [p for p in parts if _is_noise(p)]
    return meaningful, noise


def _shorten(label, limit=MAX_LABEL):
    # Cut long labels with an ellipsis
    return label if len(label) <= limit else label[:limit - 1].rstrip() + "…"


def unique_short_names(titles):
    """Return one short, unique label per title (same order as `titles`)."""
    titles = list(titles)
    if not titles:
        return []

    # For each title: its parts (subject parts first) and how many are subject parts
    ordered = []
    meaningful_count = []
    for title in titles:
        meaningful, noise = split_title(title)
        parts = meaningful + noise
        if not parts:
            parts = meaningful = [(title or "").strip() or "Course"]
        ordered.append(parts)
        meaningful_count.append(len(meaningful))

    # Start with just the first part of every title
    depth = [1] * len(titles)

    def label(i):
        return SEPARATORS.join(ordered[i][:depth[i]])

    # Where two labels match, add another part to them until they differ
    for _ in range(max(len(p) for p in ordered) + 1):
        groups = defaultdict(list)
        for i in range(len(titles)):
            groups[label(i).casefold()].append(i)

        changed = False
        for members in groups.values():
            if len(members) < 2:
                continue

            # Prefer extending courses that still have subject detail to add;
            # fall back to qualification detail ("A Level" vs "AS Level").
            candidates = [i for i in members if depth[i] < meaningful_count[i]]
            if not candidates:
                candidates = [i for i in members if depth[i] < len(ordered[i])]

            for i in candidates:
                depth[i] += 1
                changed = True

        if not changed:
            break

    labels = [_shorten(label(i)) for i in range(len(titles))]

    # Last resort for genuinely identical (or truncation-identical) labels: add 1, 2, 3...
    totals = defaultdict(int)
    for text in labels:
        totals[text.casefold()] += 1

    seen = defaultdict(int)
    unique = []
    for text in labels:
        key = text.casefold()
        if totals[key] > 1:
            seen[key] += 1
            unique.append(f"{text} {seen[key]}")
        else:
            unique.append(text)
    return unique