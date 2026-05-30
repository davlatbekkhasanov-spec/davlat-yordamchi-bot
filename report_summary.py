"""Kunlik hisobot xulosasi — ma'lumotlarga asoslangan aqlli matn."""

from __future__ import annotations

BOT_NAMES = {
    "omborga": "\u041e\u043c\u0431\u043e\u0440\u0433\u0430 \u043a\u0438\u0440\u0438\u0442\u0438\u0448",
    "ombor": "\u041e\u043c\u0431\u043e\u0440 \u0445\u0438\u0437\u043c\u0430\u0442\u0438",
    "yuk": "\u042e\u043a \u0436\u0430\u0440\u0430\u0451\u043d\u0438",
    "sklad": "\u0421\u043a\u043b\u0430\u0434 \u043d\u0430\u0437\u043e\u0440\u0430\u0442",
    "ishxona": "\u0418\u0448\u0445\u043e\u043d\u0430 \u043d\u0430\u0437\u043e\u0440\u0430\u0442",
}


def _yesterday_points(text: str) -> int | None:
    t = (text or "").strip().lower()
    if not t or t in ("\u0439\u045e\u049b", "yo'q", "\u2014", "-", "\u2013", "\u043d\u0435\u0442"):
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _join_names(names: list[str], limit: int = 2) -> str:
    picked = names[:limit]
    if len(picked) == 1:
        return f"\u00ab{picked[0]}\u00bb"
    return " \u0432\u0430 ".join(f"\u00ab{n}\u00bb" for n in picked)


def build_summary_text(data) -> tuple[str, str]:
    cats = list(data.categories or [])
    n = len(cats)
    parts: list[str] = []

    if n and data.cat_total:
        line = (
            f"\u0411\u0443\u0433\u0443\u043d {n} \u0442\u0430 \u0439\u045e\u043d\u0430\u043b\u0438\u0448 "
            f"\u0431\u045e\u0439\u0438\u0447\u0430 \u0436\u0430\u043c\u0438 +{data.cat_total} \u043e\u0447\u043a\u043e \u049b\u0430\u0439\u0434 \u044d\u0442\u0438\u043b\u0434\u0438."
        )
        if data.rank and data.rank_total:
            if data.rank == 1:
                line += (
                    f" \u0416\u0430\u043c\u043e\u0430 \u0438\u0447\u0438\u0434\u0430 {data.rank}-\u043e\u0440\u0438\u043d "
                    f"({data.rank_total} \u0445\u043e\u0434\u0438\u043c) \u2014 \u0435\u043d\u0433 \u044e\u049b\u043e\u0440\u0438 \u043d\u0430\u0442\u0438\u0436\u0430."
                )
            elif data.rank <= 3:
                line += (
                    f" \u0416\u0430\u043c\u043e\u0430 \u0438\u0447\u0438\u0434\u0430 {data.rank}-\u043e\u0440\u0438\u043d "
                    f"({data.rank_total} \u0445\u043e\u0434\u0438\u043c) \u2014 \u044e\u049b\u043e\u0440\u0438 \u0433\u0443\u0440\u0443\u0445\u0434\u0430."
                )
            else:
                line += (
                    f" \u0416\u0430\u043c\u043e\u0430 \u0438\u0447\u0438\u0434\u0430 {data.rank}-\u043e\u0440\u0438\u043d "
                    f"({data.rank_total} \u0445\u043e\u0434\u0438\u043c)."
                )
        parts.append(line)

    if data.best_cat and data.best_add:
        parts.append(
            f"\u042d\u043d\u0433 \u043a\u0443\u0447\u043b\u0438 \u0439\u045e\u043d\u0430\u043b\u0438\u0448 \u2014 "
            f"\u00ab{data.best_cat}\u00bb (+{data.best_add})."
        )

    weak: list = []
    if n >= 2 and data.best_add:
        threshold = max(2, data.best_add // 2)
        weak = [c for c in sorted(cats, key=lambda x: x.added) if c.added < threshold]
        if weak:
            weak_text = ", ".join(f"\u00ab{c.name}\u00bb (+{c.added})" for c in weak[:2])
            parts.append(f"\u041f\u0430\u0441\u0442 \u043d\u0430\u0442\u0438\u0436\u0430: {weak_text}.")

    improved: list[str] = []
    declined: list[str] = []
    for c in cats:
        y = _yesterday_points(c.yesterday)
        if y is None:
            continue
        if c.today > y:
            improved.append(c.name)
        elif c.today < y:
            declined.append(c.name)

    if len(improved) >= 2:
        tail = " \u0432\u0430 \u0431\u043e\u0448\u049b\u0430\u043b\u0430\u0440" if len(improved) > 2 else ""
        parts.append(
            f"\u041a\u0435\u0447\u0430\u0433\u0430 \u043d\u0438\u0441\u0431\u0430\u0442\u0430\u043d \u043e\u0441\u0438\u0448: "
            f"{_join_names(improved, 2)}{tail}."
        )
    elif len(improved) == 1:
        parts.append(
            f"\u041a\u0435\u0447\u0430\u0433\u0430 \u043d\u0438\u0441\u0431\u0430\u0442\u0430\u043d "
            f"\u00ab{improved[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0434\u0430 \u044f\u0445\u0448\u0438\u043b\u0430\u043d\u0438\u0448 \u0431\u043e\u0440."
        )

    if len(declined) >= 2:
        parts.append(
            f"\u041a\u0435\u0447\u0430\u0433\u0430 \u043d\u0438\u0441\u0431\u0430\u0442\u0430\u043d \u043f\u0430\u0441\u0430\u0439\u0438\u0448: {_join_names(declined, 2)}."
        )
    elif len(declined) == 1:
        parts.append(
            f"\u041a\u0435\u0447\u0430\u0433\u0430 \u043d\u0438\u0441\u0431\u0430\u0442\u0430\u043d "
            f"\u00ab{declined[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0434\u0430 \u043f\u0430\u0441\u0430\u0439\u0438\u0448 \u043a\u0443\u0437\u0430\u0442\u0438\u043b\u0434\u0438."
        )

    active_bots = [
        b
        for b in (data.bots or [])
        if (getattr(b, "summary", "") or "").strip() and b.score > 0
    ]
    if data.bot_total > 0 and active_bots:
        labels = ", ".join(BOT_NAMES.get(b.key, b.label) for b in active_bots[:3])
        parts.append(
            f"\u0411\u043e\u0448\u049b\u0430 \u0431\u043e\u0442\u043b\u0430\u0440 \u0431\u045e\u0439\u0438\u0447\u0430 "
            f"+{data.bot_total} \u043e\u0447\u043a\u043e ({labels})."
        )

    if data.total_work and data.total_work not in ("00:00:00", "0:00:00"):
        parts.append(f"\u0423\u043c\u0443\u043c\u0438\u0439 \u0438\u0448 \u0432\u0430\u049b\u0442\u0438: {data.total_work}.")

    summary = (
        " ".join(parts)
        if parts
        else "\u0411\u0443\u0433\u0443\u043d\u0433\u0438 \u043a\u0443\u043d \u0431\u045e\u0439\u0438\u0447\u0430 \u04b3\u0438\u0441\u043e\u0431\u043e\u0442 \u0448\u0430\u043a\u043b\u043b\u0430\u043d\u0442\u0438\u0440\u0438\u043b\u0434\u0438."
    )

    rec_parts: list[str] = []
    if weak:
        rec_parts.append(
            f"\u042d\u0440\u0442\u0430\u0433\u0430 \u00ab{weak[0].name}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0433\u0430 "
            f"\u0430\u043b\u043e\u0445\u0438\u0434\u0430 \u044d\u0442\u0438\u0431\u043e\u0440 \u049b\u0430\u0440\u0430\u0442\u0438\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )
    elif declined:
        rec_parts.append(
            f"\u042d\u0440\u0442\u0430\u0433\u0430 \u00ab{declined[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0434\u0430 "
            f"\u043a\u0435\u0447\u0430\u0433\u0438 \u0442\u0435\u043c\u043f\u043d\u0438 \u0442\u0438\u043a\u043b\u0430\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )

    if data.rank == 1:
        rec_parts.append(
            "\u041b\u0438\u0434\u0435\u0440\u043b\u0438\u043a \u0441\u0430\u043b\u0430\u043d\u0441\u0438\u043d \u2014 \u0448\u0443 \u0442\u0430\u0440\u0442\u0438\u0431\u0434\u0430 \u0438\u0448 \u0434\u0430\u0432\u043e\u043c \u044d\u0442\u0442\u0438\u0440\u0438\u043b\u0441\u0438\u043d."
        )
    elif data.rank and data.rank <= 3:
        if weak:
            rec_parts.append(
                "\u0417\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u043d\u0438 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0441\u0430\u043d\u0433\u0438\u0437, "
                "1-\u043e\u0440\u0438\u043d \u0443\u0447\u0443\u043d \u0440\u0435\u0430\u043b \u0438\u043c\u043a\u043e\u043d \u0431\u043e\u043b\u0430\u0434\u0438."
            )
        else:
            rec_parts.append(
                "\u0411\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u043d\u0430\u0442\u0438\u0436\u0430 \u2014 \u0448\u0443 \u0442\u0435\u043c\u043f\u043e \u0441\u0430\u043b\u0430\u043d\u0441\u0438\u043d."
            )
    elif data.rank:
        rec_parts.append(
            "\u0418\u0448 \u0436\u0430\u0440\u0430\u0451\u043d\u0438\u043d\u0438 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0441\u0430\u043b\u0430\u0448 \u0432\u0430 "
            "\u0437\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u043d\u0438 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0438\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )
    else:
        rec_parts.append(
            "\u0420\u0435\u0436\u0430 \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448\u043b\u0430\u0448 \u0434\u0430\u0432\u043e\u043c \u044d\u0442\u0442\u0438\u0440\u0438\u043b\u0441\u0438\u043d."
        )

    seen: set[str] = set()
    unique_recs: list[str] = []
    for item in rec_parts:
        if item not in seen:
            seen.add(item)
            unique_recs.append(item)

    recommendation = " ".join(unique_recs[:2])
    return summary, recommendation
