"""Boshqa botlardan kelgan kunlik xulosalar — davlat-yordamchi yakunida qo'shiladi."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tashkent"))

from persist_data import bootstrap_persistence, resolve_db_path

DB_PATH = resolve_db_path(default_filename="data.db")
HUB_SECRET = os.getenv("YORDAMCHI_HUB_SECRET", "").strip()
MAX_SUMMARY_LEN = 420
MAX_APPENDIX_CHARS = 1050

BOT_LABELS = {
    "omborga": "Omborga kiritish",
    "ombor": "Ombor xizmat",
    "yuk": "Yuk jarayoni",
    "sklad": "Sklad nazorat",
    "ishxona": "Ishxona nazorat",
    "mesta": "Mesta",
    "inventarizatsiya": "Inventarizatsiya",
    "navbatchi": "Navbatchi nazorat",
    "faceid": "Face ID davomat",
}

_BOT_KEY_ALIASES = {
    "omborga": {"omborga", "omborga_kiritish", "omborgakiritish", "kirim", "prihod"},
    "ombor": {"ombor", "omborxizmat", "ombor_xizmat"},
    "yuk": {"yuk", "yukjarayoni", "yuk_jarayoni"},
    "sklad": {"sklad", "skladnazorat", "sklad_nazorat"},
    "ishxona": {"ishxona", "ishxonanazorat", "ishxona_nazorat"},
    "mesta": {"mesta", "mesta_nazorat", "mestanazorat"},
    "inventarizatsiya": {
        "inventarizatsiya",
        "inventarizatsiya_nazorat",
        "inventarizatsiyanazorat",
        "hisobchi",
        "pereschet",
    },
    "navbatchi": {
        "navbatchi",
        "navbatchi_control",
        "navbatchi_control_bot",
        "navbatchilik",
        "navbatchi_nazorat",
    },
    "faceid": {"faceid", "face_id", "face-id", "faceidbot", "davomat"},
}

_PERSIST = bootstrap_persistence(DB_PATH, legacy_names=("data.db",))
DB_PATH = _PERSIST["db_path"]

_conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
_conn.row_factory = sqlite3.Row
_lock = asyncio.Lock()


def init_schema() -> None:
    cur = _conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_bot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            tg_id INTEGER NOT NULL,
            bot_key TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cross_bot_day_tg ON cross_bot_events(day, tg_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_cross_bot_bot_day ON cross_bot_events(bot_key, day, tg_id)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_seed_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0,
            applied_at TEXT
        )
        """
    )
    _conn.commit()


def _parse_duration_seconds(sl: str) -> int:
    """'50 daqiqa 26 soniya', '1 soat 30 daqiqa', '5907 soniya'."""
    sm = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
    if sm:
        return int(sm.group(1))
    total = 0
    h = re.search(r"(\d+)\s*soat", sl)
    daq = re.search(r"(\d+)\s*daqiqa", sl)
    son = re.search(r"(\d+)\s*soniya", sl)
    if h:
        total += int(h.group(1)) * 3600
    if daq:
        total += int(daq.group(1)) * 60
    if son:
        total += int(son.group(1))
    return total


def _parse_omborga_ish_sec(sl: str) -> int:
    """Omborga: ish 3:29 yoki 1:15:29."""
    from time_display import parse_colon_token, parse_duration_text

    ish_m = re.search(r"ish\s+([\d:]+)", sl)
    if not ish_m:
        return 0
    token = ish_m.group(1).strip()
    sec = parse_colon_token(token)
    if sec:
        return sec
    return parse_duration_text(f"ish vaqti {token}")


_MAX_DAILY_WORK_SEC = 12 * 3600

# Kunlik bitta kanonik yozuv — analytics 100% izchillik
CANONICAL_UPSERT_KEYS = frozenset({"yuk", "ombor", "omborga", "faceid"})


def _is_ombor_cumulative(summary: str) -> bool:
    sl = (summary or "").lower()
    return "jami" in sl and "ish vaqti" in sl and "soniya" in sl


def _parse_yuk_ish_sec(sl: str) -> int:
    """Yuk: 'N soniya', '48:30' (daq:son), '1 soat 30 daq', '1:23:45'."""
    text = (sl or "").lower()
    m = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", text)
    if m:
        return int(m.group(1))
    m = re.search(r"ish\s+vaqti\s+(\d+)\s*soat\s+(\d+)\s*daq", text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    m = re.search(r"ish\s+vaqti\s+(\d+):(\d{2}):(\d{2})", text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"ish\s+vaqti\s+(\d+):(\d{2})(?!\d)", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return 0


def _yuk_looks_daily_total(summary: str) -> bool:
    sl = (summary or "").lower()
    return "ish vaqti" in sl and ("yakun" in sl or "forward jami" in sl or "jami" in sl)


def _yuk_is_official(summary: str) -> bool:
    """Faqat sessiya yakuni / backfill / forward — jonli taymer emas."""
    sl = (summary or "").lower()
    if not sl or "jonli" in sl:
        return False
    if "yakun" in sl or "forward jami" in sl:
        return True
    return False


def _yuk_live_inflation(summaries: list[str]) -> bool:
    """Ko'p ketma-ket o'suvchi bugun jami = ochiq taymerdan jonli push."""
    secs: list[int] = []
    for s in summaries:
        sl = (s or "").lower()
        if "jonli" in sl or _yuk_is_official(s):
            continue
        sec = _parse_yuk_ish_sec(sl)
        if sec > 0:
            secs.append(sec)
    if len(secs) < 5:
        return False
    return all(secs[i] >= secs[i - 1] for i in range(1, len(secs))) and secs[-1] >= 3600


def _parse_count_sec(summary: str, bot_key: str) -> tuple[int, int]:
    """ombor/yuk — jami yoki bitta ariza (#47 bajarildi, ...) formatidan."""
    sl = (summary or "").lower()
    cnt = 0
    sec = 0
    if bot_key == "ombor":
        if _is_ombor_cumulative(summary):
            cm = re.search(r"(\d+)\s*ta", sl)
            if cm:
                cnt = int(cm.group(1))
            sec = _parse_duration_seconds(sl)
            return cnt, sec
        if "#" in summary and "bajarildi" in sl:
            return 1, _parse_duration_seconds(sl)
        return 0, 0
    cm = re.search(r"(\d+)\s*ta", sl)
    if cm:
        cnt = int(cm.group(1))
    if bot_key == "yuk":
        sec = _parse_yuk_ish_sec(sl)
    else:
        sm = re.search(r"ish\s+vaqti\s+(\d+)\s*soniya", sl)
        if sm:
            sec = int(sm.group(1))
    return cnt, sec


def _parse_omborga_totals(summary: str) -> tuple[int, int]:
    sl = (summary or "").lower()
    reys_m = re.search(r"reys\s*(\d+)", sl)
    reys = int(reys_m.group(1)) if reys_m else 0
    return reys, _parse_omborga_ish_sec(sl)


def _parse_mesta_hub_summary(summary: str) -> tuple[int, int, int, int, int]:
    """poz, ish_sec, dam_sec, tejash_sec, bekor_sec."""
    from time_display import parse_duration_text

    sl = (summary or "").lower()

    def _field(name: str) -> int:
        m = re.search(rf"{name}\s+([^,]+)", sl)
        return parse_duration_text(m.group(1).strip()) if m else 0

    poz_m = re.search(r"poz\s*(\d+)", sl)
    poz = int(poz_m.group(1)) if poz_m else 0
    return poz, _field("ish"), _field("dam"), _field("tejash"), _field("bekor")


def _merge_mesta_daily(summaries: list[str]) -> str:
    """Bir kunda bir nechta mesta sessiyasi — botdagi kabi ball yig'indisi."""
    from time_display import fmt_duration

    clean = [s for s in summaries if s and re.search(r"poz\s*\d+", (s or "").lower())]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0][:MAX_SUMMARY_LEN]

    from daily_report_card import MESTA_NORM_MIN, hub_teje_bonus

    total_poz = total_ish = total_dam = total_tej = total_bek = 0
    for s in clean:
        p, i, d, t, b = _parse_mesta_hub_summary(s)
        total_poz += p
        total_ish += i
        total_dam += d
        total_tej += t
        total_bek += b
    total_bonus = hub_teje_bonus(total_poz, total_ish, total_dam, MESTA_NORM_MIN)

    merged = (
        f"Mesta: poz {total_poz}, ish {fmt_duration(total_ish)}, dam {fmt_duration(total_dam)}, "
        f"tejash {fmt_duration(total_tej)}, bekor {fmt_duration(total_bek)}, kaizen {total_bonus}"
    )
    return merged[:MAX_SUMMARY_LEN]


def _merge_inventarizatsiya_daily(summaries: list[str]) -> str:
    """Bir kunda bir nechta inventarizatsiya sessiyasi."""
    from time_display import fmt_duration

    clean = [s for s in summaries if s and re.search(r"poz\s*\d+", (s or "").lower())]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0][:MAX_SUMMARY_LEN]

    from daily_report_card import INV_NORM_MIN, hub_teje_bonus

    total_poz = total_ish = total_dam = total_tej = total_bek = 0
    for s in clean:
        p, i, d, t, b = _parse_mesta_hub_summary(s)
        total_poz += p
        total_ish += i
        total_dam += d
        total_tej += t
        total_bek += b
    total_bonus = hub_teje_bonus(total_poz, total_ish, total_dam, INV_NORM_MIN)

    merged = (
        f"Inventarizatsiya: poz {total_poz}, ish {fmt_duration(total_ish)}, dam {fmt_duration(total_dam)}, "
        f"tejash {fmt_duration(total_tej)}, bekor {fmt_duration(total_bek)}, kaizen {total_bonus}"
    )
    return merged[:MAX_SUMMARY_LEN]


def _parse_navbatchi_ball(summary: str) -> int:
    sl = (summary or "").lower()
    ball_m = re.search(r"ball\s*[=:]?\s*([+-]?\d+)", sl)
    return int(ball_m.group(1)) if ball_m else 0


def _merge_navbatchi_daily(summaries: list[str]) -> str:
    """Bir kunda bir nechta navbatchi yozuvi — oxirgisi (yoki eng katta ball)."""
    clean = [s for s in summaries if s and s.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0][:MAX_SUMMARY_LEN]
    best = max(clean, key=_parse_navbatchi_ball)
    return best[:MAX_SUMMARY_LEN]


def _merge_hub_summary(bot_key: str, old: str, new: str) -> str:
    """Bir xil kun+xodim+bot uchun yangi hisobotni eskisiga qo'shish."""
    key = normalize_bot_key(bot_key)
    if not old:
        return new
    if key == "mesta":
        return _merge_mesta_daily([old, new])
    if key == "inventarizatsiya":
        return _merge_inventarizatsiya_daily([old, new])
    if key == "navbatchi":
        return _merge_navbatchi_daily([old, new])
    if key == "faceid":
        return new or old
    if key == "ombor":
        if _is_ombor_cumulative(new):
            nc, ns = _parse_count_sec(new, key)
            if ns > 0 or nc > 0:
                return new
            oc, os_ = _parse_count_sec(old, key)
            if os_ > 0 or oc > 0:
                return old
            return new
        oc, os_ = _parse_count_sec(old, key)
        nc, ns = _parse_count_sec(new, key)
        total_c = oc + nc
        total_s = os_ + ns
        if total_s <= 0 and total_c <= 0:
            return old if (os_ > 0 or oc > 0) else new
        return f"Ombor (jami): {total_c} ta, ish vaqti {total_s} soniya"
    if key == "yuk":
        oc, os_ = _parse_count_sec(old, key)
        nc, ns = _parse_count_sec(new, key)
        best = max(os_, ns)
        if best <= 0:
            return old if os_ > 0 else new
        return f"Yuk (jami): ish vaqti {best} soniya"
    if key == "omborga":
        or_, oi = _parse_omborga_totals(old)
        nr, ni = _parse_omborga_totals(new)
        # Kunlik jami (seed / yakuniy) — qo'shmasdan kattasini olish
        if _omborga_looks_daily_total(old) or _omborga_looks_daily_total(new):
            if (nr, ni) >= (or_, oi):
                return new
            return old
        from time_display import fmt_duration

        total_reys = or_ + nr
        total_ish = oi + ni
        return f"Reys {total_reys}, ish {fmt_duration(total_ish)}, dam 00:00"
    return new


def _omborga_looks_daily_total(summary: str) -> bool:
    """Kunlik yakuniy xulosa (seed/forward) — jonli sessiya pushi emas."""
    sl = (summary or "").lower()
    if "forward" in sl or "yakun" in sl or "kunlik jami" in sl:
        return True
    # Jonli push: reys o'sadi, odatda «yuk Nm» ham bor — buni kunlik jami deb olmang
    if re.search(r"yuk\s+\d", sl):
        return False
    reys, ish = _parse_omborga_totals(summary)
    if "dam 0:00" in sl and reys >= 8:
        return True
    if reys >= 8 and ish >= 3 * 3600:
        return True
    return False


def _best_yuk_daily(summaries: list[str]) -> str:
    """
    Yuk kunlik vaqt — faqat rasmiy yakun/backfill.
    Eski jonli pushlar (o'sib boruvchi bugun jami) va shubhali yakka 3+ soat yozuvlar hisobga olinmaydi.
    """
    from hub_sanity import hub_summary_blocked

    clean = [s for s in summaries if s and not hub_summary_blocked(s, bot_key="yuk")]
    if not clean:
        return ""

    official = [s for s in clean if _yuk_is_official(s)]
    if official:
        best = max(_parse_yuk_ish_sec(s.lower()) for s in official)
        if best > 0:
            return f"Yuk (jami): ish vaqti {best} soniya"
        for s in reversed(official):
            if _parse_yuk_ish_sec(s.lower()) <= 0:
                return s
        return ""

    legacy = [s for s in clean if "jonli" not in (s or "").lower()]
    if _yuk_live_inflation(legacy):
        return "Yuk (jami): ish vaqti 0 soniya"

    legacy_secs = [_parse_yuk_ish_sec(s.lower()) for s in legacy]
    best = max(legacy_secs) if legacy_secs else 0
    # Yakun belgisisiz 3+ soat — odatda ochiq taymer xatosi
    if best >= 10800:
        return "Yuk (jami): ish vaqti 0 soniya"
    if best <= 0:
        for s in reversed(legacy):
            if _parse_yuk_ish_sec(s.lower()) <= 0:
                return s
        return ""
    return f"Yuk (jami): ish vaqti {best} soniya"


def _omborga_parse_dam_sec(summary: str) -> int:
    from time_display import parse_colon_token

    sl = (summary or "").lower()
    dam_m = re.search(r"dam\s+([\d:]+)", sl)
    if not dam_m:
        return 0
    return parse_colon_token(dam_m.group(1).strip())


def _format_omborga_summary(reys: int, ish_sec: int, dam_sec: int = 0) -> str:
    from time_display import fmt_duration

    ish_sec = min(max(0, ish_sec), _MAX_DAILY_WORK_SEC)
    dam_sec = min(max(0, dam_sec), _MAX_DAILY_WORK_SEC)
    return f"Reys {reys}, ish {fmt_duration(ish_sec)}, dam {fmt_duration(dam_sec)}"


def _omborga_sessions_daily(summaries: list[str]) -> str:
    """Har sessiya piki, keyin kunlik jami (reys/ish qo'shiladi)."""
    peaks: list[tuple[int, int, str]] = []
    cur = (0, 0, "")
    prev_reys = 0
    for s in summaries:
        r, i = _parse_omborga_totals(s)
        if r <= 0 and i <= 0:
            continue
        if prev_reys > 0 and r < prev_reys:
            if cur[0] > 0 or cur[1] > 0:
                peaks.append(cur)
            cur = (r, i, s)
        elif (r, i) >= (cur[0], cur[1]):
            cur = (r, i, s)
        prev_reys = r
    if cur[0] > 0 or cur[1] > 0:
        peaks.append(cur)
    if not peaks:
        return ""
    if len(peaks) == 1:
        r, i, src = peaks[0]
        return src if src else _format_omborga_summary(r, i, _omborga_parse_dam_sec(src))
    total_reys = sum(p[0] for p in peaks)
    total_ish = min(sum(p[1] for p in peaks), _MAX_DAILY_WORK_SEC)
    return _format_omborga_summary(total_reys, total_ish, 0)


def _ombor_is_order(summary: str) -> bool:
    sl = (summary or "").lower()
    return "#" in (summary or "") and "bajarildi" in sl


def _best_ombor_daily(summaries: list[str]) -> str:
    """Kunlik jami (bugun jami) yoki barcha #buyurtmalar yig'indisi; 0 spam e'tiborsiz."""
    from hub_sanity import hub_summary_blocked

    clean = [s for s in summaries if s and not hub_summary_blocked(s, bot_key="ombor")]
    if not clean:
        return ""
    cumulatives = [s for s in clean if _is_ombor_cumulative(s)]
    good_cum = [s for s in cumulatives if _parse_count_sec(s, "ombor")[1] > 0]
    if good_cum:
        best = max(good_cum, key=lambda s: _parse_count_sec(s, "ombor")[1])
        nc, ns = _parse_count_sec(best, "ombor")
        return f"Ombor (jami): {nc} ta, ish vaqti {ns} soniya"
    orders = [s for s in clean if _ombor_is_order(s)]
    total_c = len(orders)
    total_s = 0
    for s in orders:
        _, sec = _parse_count_sec(s, "ombor")
        total_s += sec
    total_s = min(total_s, _MAX_DAILY_WORK_SEC)
    if total_s <= 0 and total_c <= 0:
        for s in reversed(clean):
            if "0 soniya" in s.lower():
                return s
        return ""
    return f"Ombor (jami): {total_c} ta, ish vaqti {total_s} soniya"


def _best_sklad_daily(summaries: list[str]) -> str:
    """Har papka alohida — sanaldi yig'indisi."""
    from hub_sanity import hub_summary_blocked

    clean = [s for s in summaries if s and not hub_summary_blocked(s, bot_key="sklad")]
    if not clean:
        return ""
    total_n = 0
    last = clean[-1]
    for s in clean:
        sm = re.search(r"sanaldi\s*(\d+)", (s or "").lower())
        if sm:
            total_n += int(sm.group(1))
    if total_n <= 0:
        return last
    out = re.sub(r"sanaldi\s*\d+", f"sanaldi {total_n}", last, count=1, flags=re.I)
    return out if out else last


def _best_omborga_daily(summaries: list[str]) -> str:
    from hub_sanity import hub_summary_blocked

    clean = [s for s in summaries if s and not hub_summary_blocked(s, bot_key="omborga")]
    if not clean:
        return ""
    totals = [s for s in clean if _omborga_looks_daily_total(s)]
    if totals:
        return max(totals, key=lambda s: _parse_omborga_totals(s))
    return _omborga_sessions_daily(clean)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_bot_key(raw: str) -> str:
    key = "".join(ch for ch in str(raw or "").strip().lower() if ch.isalnum() or ch == "_")
    if not key:
        return ""
    for canonical, aliases in _BOT_KEY_ALIASES.items():
        if key == canonical:
            return canonical
        if key in aliases:
            return canonical
    return key[:32]


async def record_event(
    *,
    tg_id: int,
    day: str,
    bot_key: str,
    summary: str,
) -> None:
    text = " ".join(str(summary or "").split())
    if not text:
        return
    key = normalize_bot_key(bot_key)
    if not key:
        return
    from hub_sanity import hub_summary_blocked

    if hub_summary_blocked(text, bot_key=key):
        log.warning(
            "Hub rad etildi (noto'g'ri vaqt): tg=%s %s %s — %s",
            tg_id,
            day,
            key,
            text[:120],
        )
        return
    text = text[:MAX_SUMMARY_LEN]
    day_s = str(day or "").strip()[:10]
    if len(day_s) != 10:
        day_s = datetime.now(TZ).date().isoformat()

    async with _lock:
        cur = _conn.cursor()
        if key == "yuk" and "jonli" in text.lower():
            return
        if key in CANONICAL_UPSERT_KEYS:
            cur.execute(
                """
                SELECT summary FROM cross_bot_events
                WHERE day = ? AND tg_id = ? AND bot_key = ?
                ORDER BY id ASC
                """,
                (day_s, int(tg_id), key),
            )
            prev = [str(r[0]) for r in cur.fetchall()]
            rows = [{"bot_key": key, "summary": s} for s in prev + [text]]
            merged = _replay_merged_by_bot(rows).get(key, "") or text
            cur.execute(
                "DELETE FROM cross_bot_events WHERE day = ? AND tg_id = ? AND bot_key = ?",
                (day_s, int(tg_id), key),
            )
            cur.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day_s, int(tg_id), key, merged[:MAX_SUMMARY_LEN], _now_iso()),
            )
        else:
            cur.execute(
                """
                INSERT INTO cross_bot_events(day, tg_id, bot_key, summary, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day_s, int(tg_id), key, text, _now_iso()),
            )
        _conn.commit()

    if key in ("mesta", "inventarizatsiya"):
        try:
            from hub_reports_sync import sync_hub_categories_for_tg

            await sync_hub_categories_for_tg(int(tg_id), day_s)
        except Exception:
            log.exception("Hub→reports sync xato tg=%s day=%s key=%s", tg_id, day_s, key)


async def ensure_hub_seed() -> int:
    """Kod ichidagi boshlang'ich yozuvlar — faqat bo'sh slotlarga, bir marta."""
    from hub_seed import HUB_SEED_ROWS, HUB_SEED_VERSION

    init_schema()
    async with _lock:
        cur = _conn.cursor()
        row = cur.execute("SELECT version FROM hub_seed_meta WHERE id = 1").fetchone()
        applied_ver = int(row["version"]) if row else 0

    added = 0
    for day, tg_id, bot_key, summary in HUB_SEED_ROWS:
        key = normalize_bot_key(bot_key)
        existing = await fetch_latest_by_bot(int(tg_id), day)
        if key in existing:
            continue
        await record_event(tg_id=int(tg_id), day=day, bot_key=bot_key, summary=summary)
        added += 1

    if added or applied_ver < HUB_SEED_VERSION:
        async with _lock:
            cur = _conn.cursor()
            cur.execute(
                """
                INSERT INTO hub_seed_meta(id, version, applied_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    applied_at = excluded.applied_at
                """,
                (HUB_SEED_VERSION, _now_iso()),
            )
            _conn.commit()

    if added:
        log.info("Hub seed: %s yozuv (v%s)", added, HUB_SEED_VERSION)
    return added


def _replay_merged_by_bot(rows: list) -> dict[str, str]:
    """Kunlik xulosa: omborga — kunlik jami; ombor — ketma-ket merge."""
    groups: dict[str, list[str]] = {}
    from hub_sanity import hub_summary_blocked

    for row in rows:
        k = row["bot_key"]
        s = str(row["summary"] or "").strip()
        if not s or hub_summary_blocked(s, bot_key=k):
            continue
        groups.setdefault(k, []).append(s)
    out: dict[str, str] = {}
    for k, summaries in groups.items():
        if k == "omborga":
            merged = _best_omborga_daily(summaries)
        elif k == "yuk":
            merged = _best_yuk_daily(summaries)
        elif k == "ombor":
            merged = _best_ombor_daily(summaries)
        elif k == "sklad":
            merged = _best_sklad_daily(summaries)
        elif k == "mesta":
            merged = _merge_mesta_daily(summaries)
        elif k == "inventarizatsiya":
            merged = _merge_inventarizatsiya_daily(summaries)
        elif k == "navbatchi":
            merged = _merge_navbatchi_daily(summaries)
        else:
            merged = ""
            for s in summaries:
                merged = _merge_hub_summary(k, merged, s) if merged else s
        if merged:
            out[k] = merged
    return out


async def fetch_merged_latest_by_bot(tg_ids: set[int] | list[int], day: str) -> dict[str, str]:
    """Bir nechta tg_id uchun har bot_key bo'yicha kunlik birlashtirilgan xulosa."""
    ids = sorted({int(x) for x in tg_ids if x})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            f"""
            SELECT bot_key, summary, id FROM cross_bot_events
            WHERE day = ? AND tg_id IN ({placeholders})
            ORDER BY id ASC
            """,
            (day, *ids),
        )
        rows = cur.fetchall()
    return _replay_merged_by_bot(rows)


def _latest_by_bot_sync(tg_id: int, day: str) -> dict[str, str]:
    cur = _conn.cursor()
    cur.execute(
        """
        SELECT bot_key, summary, id FROM cross_bot_events
        WHERE day = ? AND tg_id = ?
        ORDER BY id DESC
        """,
        (day, int(tg_id)),
    )
    rows = cur.fetchall()
    out: dict[str, str] = {}
    for row in rows:
        k = row["bot_key"]
        if k not in out:
            out[k] = row["summary"]
    return out


async def fetch_latest_by_bot(tg_id: int, day: str) -> dict[str, str]:
    async with _lock:
        return _latest_by_bot_sync(tg_id, day)


async def build_appendix_lines_async(tg_id: int | set[int], day_iso: str) -> list[str]:
    tg_ids = {int(tg_id)} if isinstance(tg_id, int) else {int(x) for x in tg_id if x}
    events = await fetch_merged_latest_by_bot(tg_ids, day_iso)
    if not events:
        return []

    order = ("omborga", "ombor", "yuk", "sklad", "mesta", "inventarizatsiya", "navbatchi", "ishxona", "faceid")
    lines = ["", "── Boshqa botlar (bugun) ──"]
    used = 0
    for key in order:
        if key not in events:
            continue
        label = BOT_LABELS.get(key, key)
        chunk = f"• {label}: {events[key]}"
        if used + len(chunk) + 1 > MAX_APPENDIX_CHARS:
            lines.append("• … (qisqartirildi)")
            break
        lines.append(chunk)
        used += len(chunk) + 1
    for key, summary in events.items():
        if key in order:
            continue
        label = BOT_LABELS.get(key, key)
        chunk = f"• {label}: {summary}"
        if used + len(chunk) + 1 > MAX_APPENDIX_CHARS:
            break
        lines.append(chunk)
        used += len(chunk) + 1
    return lines


def hub_secret_ok(provided: str) -> bool:
    if not HUB_SECRET:
        return False
    return str(provided or "").strip() == HUB_SECRET


async def count_employee_links() -> int:
    async with _lock:
        cur = _conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM employee_links")
        row = cur.fetchone()
    return int(row["c"]) if row else 0


async def hub_events_for_day(day: str, *, limit: int = 80) -> list[dict]:
    """Admin diagnostika: bugungi barcha hub eventlar (yangidan eskiga)."""
    lim = max(1, min(int(limit), 500))
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            SELECT tg_id, bot_key, summary, created_at
            FROM cross_bot_events
            WHERE day = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (day, lim),
        )
        rows = cur.fetchall()
    return [
        {
            "tg_id": int(r["tg_id"]),
            "bot_key": r["bot_key"],
            "summary": r["summary"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def hub_stats_today(day: str) -> dict[str, tuple[int, str | None]]:
    """bot_key → (event_soni, oxirgi vaqt)."""
    async with _lock:
        cur = _conn.cursor()
        cur.execute(
            """
            SELECT bot_key, COUNT(*) AS cnt, MAX(created_at) AS last_at
            FROM cross_bot_events
            WHERE day = ?
            GROUP BY bot_key
            """,
            (day,),
        )
        rows = cur.fetchall()
    out: dict[str, tuple[int, str | None]] = {}
    for row in rows:
        out[row["bot_key"]] = (int(row["cnt"]), row["last_at"])
    return out


def faceid_events_in_range_sync(from_day: str, to_day: str) -> list[dict]:
    """Face ID keldi/ketdi — kun + tg_id bo'yicha birlashtirilgan xulosa."""
    from collections import defaultdict

    cur = _conn.cursor()
    cur.execute(
        """
        SELECT day, tg_id, bot_key, summary, id
        FROM cross_bot_events
        WHERE bot_key = 'faceid' AND day >= ? AND day <= ?
        ORDER BY day ASC, id ASC
        """,
        (from_day, to_day),
    )
    rows = cur.fetchall()
    groups: dict[tuple[str, int], list] = defaultdict(list)
    for r in rows:
        groups[(str(r["day"]), int(r["tg_id"]))].append(r)
    out: list[dict] = []
    for (day, tg_id), evs in sorted(groups.items()):
        merged = _replay_merged_by_bot(evs).get("faceid", "")
        if merged:
            out.append({"day": day, "tg_id": tg_id, "summary": merged})
    return out
