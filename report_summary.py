"""Kunlik hisobot xulosasi — ma'lumotlarga asoslangan aqlli matn."""

from __future__ import annotations

import os

# Ichki mezon (100 ochko). Matnda ko'rsatilmaydi. Railway: DAILY_PLAN_POINTS=100
DAILY_PLAN_POINTS = max(1, int(os.getenv("DAILY_PLAN_POINTS", "100")))

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


def _day_total(data) -> int:
    total = int(getattr(data, "grand_total", 0) or 0)
    if total > 0:
        return total
    return int(getattr(data, "cat_total", 0) or 0) + int(getattr(data, "bot_total", 0) or 0)


def _performance_level(total: int, benchmark: int) -> str:
    """benchmark=100 ga nisbatan ichki daraja (matnda raqam ko'rsatilmaydi)."""
    ratio = total / benchmark if benchmark else 0
    if ratio >= 1.0:
        return "high"
    if ratio >= 0.85:
        return "good"
    if ratio >= 0.70:
        return "fair"
    if ratio >= 0.50:
        return "low"
    if ratio >= 0.30:
        return "poor"
    return "very_poor"


def _rating_summary(total: int, benchmark: int) -> str:
    level = _performance_level(total, benchmark)
    if level == "high":
        return (
            "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u044e\u049b\u043e\u0440\u0438 \u0431\u0430\u04b3\u043e\u043b\u0430\u043d\u0430\u0434\u0438 \u2014 \u0444\u0430\u043e\u043b \u0432\u0430 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448."
        )
    if level == "good":
        return (
            "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u044f\u0445\u0448\u0438 \u0431\u0430\u04b3\u043e\u043b\u0430\u043d\u0430\u0434\u0438."
        )
    if level == "fair":
        return (
            "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u049b\u043e\u043d\u0438\u049b\u0430\u0440\u043b\u0438, \u043b\u0435\u043a\u0438\u043d \u044f\u043d\u0430\u0434\u0430 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0438\u0448 \u043c\u0443\u043c\u043a\u0438\u043d."
        )
    if level == "low":
        return (
            "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u043e\u2018\u0440\u0442\u0430\u0447\u0430 \u0434\u0430\u0440\u0430\u0436\u0430\u0434\u0430 \u2014 \u0444\u0430\u043e\u043b\u043b\u0438\u043a \u0435\u0442\u0430\u0440\u043b\u0438 \u0435\u043c\u0430\u0441."
        )
    if level == "poor":
        return (
            "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u043f\u0430\u0441\u0442 \u0431\u0430\u04b3\u043e\u043b\u0430\u043d\u0430\u0434\u0438."
        )
    return (
        "\u041a\u0443\u043d \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 "
        "\u0436\u0443\u0434\u0430 \u043f\u0430\u0441\u0442 \u2014 \u0438\u0448 \u0444\u0430\u043e\u043b\u043b\u0438\u0433\u0438 \u0437\u0430\u0438\u0444."
    )


def _rating_recommendation(total: int, benchmark: int, weak_names: list[str]) -> str:
    level = _performance_level(total, benchmark)
    weak_hint = (
        f" \u00ab{weak_names[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0433\u0430 \u0430\u043b\u043e\u0445\u0438\u0434\u0430 \u0435\u0442\u0438\u0431\u043e\u0440 \u049b\u0430\u0440\u0430\u0442\u0438\u043d\u0433."
        if weak_names
        else ""
    )
    if level == "high":
        tail = weak_hint or (
            " \u0411\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448 \u0442\u0435\u043c\u043f\u043e \u0434\u0430\u0432\u043e\u043c \u044d\u0442\u0438\u043d\u0433."
        )
        return (
            "\u0428\u0443 \u0442\u0430\u0440\u0442\u0438\u0431 \u0441\u0430\u043b\u0430\u043d\u0441\u0438\u043d;" + tail
        ).strip()
    if level == "good":
        tail = weak_hint or (
            " \u0417\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u0434\u0430 \u0444\u0430\u043e\u043b\u043b\u0438\u043a\u043d\u0438 \u043e\u0448\u0438\u0440\u0438\u0448 \u043c\u0443\u043c\u043a\u0438\u043d."
        )
        return (
            "\u042f\u0445\u0448\u0438 \u0442\u0435\u043c\u043f\u043e \u0441\u0430\u043b\u0430\u043d\u0441\u0438\u043d;" + tail
        ).strip()
    if level == "fair":
        base = "\u0418\u0448 \u0444\u0430\u043e\u043b\u043b\u0438\u0433\u0438\u043d\u0438 \u043e\u0448\u0438\u0440\u0438\u0448 \u0432\u0430 \u0437\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u0433\u0430 \u0435\u0442\u0438\u0431\u043e\u0440 \u0431\u0435\u0440\u0438\u043d\u0433."
        return (base + weak_hint).strip()
    if level == "low":
        base = "\u0424\u0430\u043e\u043b\u043b\u0438\u043a \u0435\u0442\u0430\u0440\u043b\u0438 \u0435\u043c\u0430\u0441 \u2014 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448 \u0432\u0430 \u0437\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u0434\u0430 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0438\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        return (base + weak_hint).strip()
    if level == "poor":
        base = "\u041f\u0430\u0441\u0442 \u0431\u0430\u04b3\u043e \u2014 \u0431\u0430\u0440\u0447\u0430 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440 \u0431\u043e\u2018\u0439\u0438\u0447\u0430 \u0444\u0430\u043e\u043b \u0438\u0448\u043b\u0430\u0448 \u0437\u0430\u0440\u0443\u0440."
        return (base + weak_hint).strip()
    base = "\u0416\u0443\u0434\u0430 \u0437\u0430\u0438\u0444 \u043d\u0430\u0442\u0438\u0436\u0430 \u2014 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448 \u0436\u0430\u0440\u0430\u0451\u043d\u0438 \u0432\u0430 \u0444\u0430\u043e\u043b \u0438\u0448\u043b\u0430\u0448 \u0437\u0430\u0440\u0443\u0440."
    return (base + weak_hint).strip()


def build_summary_text(data) -> tuple[str, str]:
    cats = list(data.categories or [])
    n = len(cats)
    parts: list[str] = []
    plan = DAILY_PLAN_POINTS
    total = _day_total(data)
    level = _performance_level(total, plan)

    if total > 0 or n:
        parts.append(_rating_summary(total, plan))

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

    weak_names = [c.name for c in weak[:2]]
    rec_parts: list[str] = [_rating_recommendation(total, plan, weak_names)]

    if weak and level in ("high", "good"):
        rec_parts.append(
            f"\u00ab{weak[0].name}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0433\u0430 \u0430\u043b\u043e\u0445\u0438\u0434\u0430 "
            f"\u0435\u0442\u0438\u0431\u043e\u0440 \u049b\u0430\u0440\u0430\u0442\u0438\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )
    elif declined and level in ("low", "poor", "very_poor"):
        rec_parts.append(
            f"\u00ab{declined[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0434\u0430 \u043a\u0435\u0447\u0430\u0433\u0438 \u0442\u0435\u043c\u043f\u043d\u0438 "
            f"\u0442\u0438\u043a\u043b\u0430\u0448 \u043d\u0430\u0442\u0438\u0436\u0430\u043d\u0438 \u044f\u0445\u0448\u0438\u043b\u0430\u0439\u0434\u0438."
        )
    elif weak and level in ("fair", "low", "poor", "very_poor"):
        rec_parts.append(
            f"\u00ab{weak[0].name}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438 \u0430\u0432\u0432\u043e \u0437\u0430\u0438\u0444 \u2014 "
            f"\u0431\u0443 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0433\u0430 \u0431\u0438\u0440\u0438\u043d\u0447\u0438 \u043d\u0430\u0432\u0431\u0430\u0442\u0434\u0430 \u0435\u0442\u0438\u0431\u043e\u0440 \u0431\u0435\u0440\u0438\u043d\u0433."
        )
    elif declined and level in ("fair",):
        rec_parts.append(
            f"\u00ab{declined[0]}\u00bb \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u0438\u0434\u0430 \u043a\u0435\u0447\u0430\u0433\u0438 \u0442\u0435\u043c\u043f\u043d\u0438 \u0442\u0438\u043a\u043b\u0430\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )

    if data.rank == 1 and level in ("high", "good"):
        rec_parts.append(
            "\u041b\u0438\u0434\u0435\u0440\u043b\u0438\u043a \u0432\u0430 \u044e\u049b\u043e\u0440\u0438 \u043d\u0430\u0442\u0438\u0436\u0430 "
            "\u2014 \u0448\u0443 \u0442\u0430\u0440\u0442\u0438\u0431\u0434\u0430 \u0434\u0430\u0432\u043e\u043c \u044d\u0442\u0438\u043d\u0433."
        )
    elif data.rank == 1 and level in ("fair", "low", "poor", "very_poor"):
        rec_parts.append(
            "\u0416\u0430\u043c\u043e\u0430 \u0431\u043e\u2018\u0439\u0438\u0447\u0430 1-\u043e\u0440\u0438\u043d, "
            "\u043b\u0435\u043a\u0438\u043d \u0443\u043c\u0443\u043c\u0438\u0439 \u043d\u0430\u0442\u0438\u0436\u0430 \u044f\u043d\u0430\u0434\u0430 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0438\u043b\u0438\u0433\u0438 \u0437\u0430\u0440\u0443\u0440."
        )
    elif data.rank and data.rank <= 3 and level in ("fair", "low", "poor", "very_poor"):
        rec_parts.append(
            "\u042e\u049b\u043e\u0440\u0438 \u0433\u0443\u0440\u0443\u0445\u0434\u0430 \u049b\u043e\u043b\u0438\u0448 \u0443\u0447\u0443\u043d "
            "\u0438\u0448 \u0444\u0430\u043e\u043b\u043b\u0438\u0433\u0438 \u0432\u0430 \u0437\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u0434\u0430 \u0435\u0442\u0438\u0431\u043e\u0440 \u0431\u0435\u0440\u0438\u043d\u0433."
        )
    elif data.rank and level in ("low", "poor", "very_poor"):
        rec_parts.append(
            "\u0418\u0448 \u0436\u0430\u0440\u0430\u0451\u043d\u0438\u043d\u0438 \u0431\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0441\u0430\u043b\u0430\u0448 \u0432\u0430 "
            "\u0437\u0430\u0438\u0444 \u0439\u045e\u043d\u0430\u043b\u0438\u0448\u043b\u0430\u0440\u043d\u0438 \u043a\u0443\u0447\u0430\u0439\u0442\u0438\u0440\u0438\u0448 \u0442\u0430\u0432\u0441\u0438\u044f \u044d\u0442\u0438\u043b\u0430\u0434\u0438."
        )
    elif level in ("low", "poor", "very_poor"):
        rec_parts.append(
            "\u0411\u0430\u0440\u049b\u0430\u0440\u043e\u0440 \u0438\u0448 \u0436\u0430\u0440\u0430\u0451\u043d\u0438 \u0432\u0430 \u0444\u0430\u043e\u043b \u0438\u0448\u043b\u0430\u0448 "
            "\u0437\u0430\u0440\u0443\u0440 \u2014 \u0431\u0443 \u043d\u0430\u0442\u0438\u0436\u0430 \u0442\u0435\u0437 \u043a\u0443\u043d \u044f\u043d\u0430\u0434\u0430 \u044f\u0445\u0448\u0438\u043b\u0430\u043d\u0430\u0434\u0438."
        )

    seen: set[str] = set()
    unique_recs: list[str] = []
    for item in rec_parts:
        if item not in seen:
            seen.add(item)
            unique_recs.append(item)

    recommendation = " ".join(unique_recs[:2])
    return summary, recommendation
