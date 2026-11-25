# --------------------------------------------------
# Grade logic shared by the home-page grades panel and the Progress view
# (pure Python: nothing in this file draws anything)
# --------------------------------------------------

# Grade ladders used by Focus, lowest grade first. Which one a course uses is
# worked out by pick_scale() below.
GRADE_SCALES = [
    ["U", "E", "D", "C", "B", "A", "A*"],
    ["U", "PP", "MP", "MM", "DM", "DD", "D*D", "D*D*"],
]

# Commitment levels, in the order they are shown
COMMIT_SCALE = ["3", "2", "1", "★"]


def scale_hint(title):
    # Course titles usually say which grading ladder applies (None = no clue)
    text = (title or "").lower()
    if any(word in text for word in ("btec", "diploma", "extended certificate", "cambridge technical")):
        return 1
    if any(word in text for word in ("a level", "a-level", "as level")):
        return 0
    return None


def resolve_grade_index(scale, grade):
    """Position of the grade on the ladder, or None if it isn't on it.

    A grade given as a single letter stands for the doubled grade, because
    Focus drops the second letter: "D" -> "DD", "M" -> "MM", "P" -> "PP".
    An exact match always wins, so A Level "D" stays a plain D.
    """
    grade = (grade or "").strip()
    if not grade:
        return None
    if grade in scale:
        return scale.index(grade)
    if grade + grade in scale:
        return scale.index(grade + grade)
    return None


def resolve_grade_indices(scale, grade):
    # Same as resolve_grade_index, as a list (empty when there is no match)
    index = resolve_grade_index(scale, grade)
    return [] if index is None else [index]


def pick_scale(title, grades):
    """The grade ladder that fits the most of the given grades.

    The title hint is tried first, so it decides any tie (for example a lone
    "D", which exists on both ladders).
    """
    order = list(range(len(GRADE_SCALES)))
    hint = scale_hint(title)
    if hint is not None:
        order.remove(hint)
        order.insert(0, hint)

    best, best_score = None, 0
    for index in order:
        scale = GRADE_SCALES[index]
        score = sum(resolve_grade_index(scale, grade) is not None for grade in grades)
        if score > best_score:
            best, best_score = scale, score
    return best


def course_history(course):
    """Every recorded grade for a course, oldest first.

    Older saved data has no history, so the latest values are used as one point.
    """
    history = course.get("history")
    if history:
        return history
    return [{key: course.get(key, "") for key in ("period", "label", "grade", "ttg", "commit")}]


def history_grades(points):
    # Every grade and target mentioned in the history (used to pick the ladder)
    return [value for point in points for value in (point["grade"], point["ttg"])]


def plural(count, word):
    return f"{count} {word}" + ("" if count == 1 else "s")


def summarise_history(scale, points):
    """Text for the Progress view's summary boxes.

    Returns a dict. The *_kind values are "good", "bad" or "plain" and decide
    the colour of each box.
    """
    last = points[-1]
    now = resolve_grade_index(scale, last["grade"])
    target = resolve_grade_index(scale, last["ttg"])

    info = {
        "current": scale[now] if now is not None else "—",
        "current_sub": " · ".join(part for part in (last["label"], last["period"]) if part),
        "change": "—", "change_sub": "", "change_kind": "plain",
        "target": scale[target] if target is not None else "—",
        "target_sub": "", "target_kind": "plain",
        "commit": normalise_commit(last["commit"]) or "—",
    }

    # Change since the last earlier point that had a readable grade
    if now is not None:
        before = next((p for p in reversed(points[:-1])
                       if resolve_grade_index(scale, p["grade"]) is not None), None)

        if before is None:
            info["change"], info["change_sub"] = "First grade", "nothing to compare yet"
        else:
            diff = now - resolve_grade_index(scale, before["grade"])
            since = f"since {before['label'] or before['period']}".strip()
            if diff > 0:
                info.update(change=f"▲ {plural(diff, 'grade')}", change_sub=since, change_kind="good")
            elif diff < 0:
                info.update(change=f"▼ {plural(-diff, 'grade')}", change_sub=since, change_kind="bad")
            else:
                info.update(change="No change", change_sub=since)

    # Distance to the target
    if now is not None and target is not None:
        gap = target - now
        if gap > 0:
            info["target_sub"] = f"{plural(gap, 'grade')} to go"
        elif gap == 0:
            info.update(target_sub="On target", target_kind="good")
        else:
            info.update(target_sub=f"{plural(-gap, 'grade')} above target", target_kind="good")

    return info


def plan_markers(now_idxs, target_idx):
    """Where the "Now" and "Target" labels go under the grade ladder.

    Returns [(text, kind, column, span)], all meant for the same row. When the
    target sits inside the highlighted range, "Now" is centred over the widest
    run of highlighted grades beside it so the two labels never overlap.
    """
    now_idxs = sorted(now_idxs)

    # Only a target, or only a current grade
    if not now_idxs:
        return [("Target", "target", target_idx, 1)] if target_idx is not None else []

    now_span = (now_idxs[0], now_idxs[-1] - now_idxs[0] + 1)

    if target_idx is None:
        return [("Now", "now", *now_span)]

    # Target is outside the highlighted range: two separate labels
    if target_idx not in now_idxs:
        return [("Now", "now", *now_span), ("Target", "target", target_idx, 1)]

    # Target is the only highlighted grade: one combined label
    rest = [i for i in now_idxs if i != target_idx]
    if not rest:
        return [("Now • Target", "target", target_idx, 1)]

    # Target is inside the range: put "Now" over the widest unbroken run beside it
    runs = []
    for index in rest:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    widest = max(runs, key=len)

    return [("Now", "now", widest[0], len(widest)), ("Target", "target", target_idx, 1)]


def normalise_commit(value):
    # Focus writes the top commitment level as "1*" or "*"; show it as a star
    value = (value or "").strip()
    return "★" if value in ("1*", "*", "★") else value