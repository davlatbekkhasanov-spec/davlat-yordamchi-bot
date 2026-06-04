"""Forward import parser tests."""

from forward_import import aggregate_hub_events, parse_forward_text

EMPS = [
    "Ruziboev Sindor",
    "Mustafoev Abdullo",
    "Sagdullaev Yunus",
]


def test_ombor_card():
    text = """👀 Mijozga qarang #12
Xizmat ko'rsatyapti: Ruziboev sindorbek
✅ Tugadi: 2026-06-03 22:23
⏱️ Xizmat vaqti: 1 soat 38 daqiqa 27 soniya"""
    out = parse_forward_text(text, employees=EMPS)
    assert len(out) == 1
    assert out[0]["bot_key"] == "ombor"
    assert out[0]["day"] == "2026-06-03"
    assert out[0]["service_sec"] == 5907


def test_omborga_compact():
    text = "Reys 3, yuk 120m, ish 75:39, dam 12:05"
    out = parse_forward_text(
        text,
        employees=EMPS,
        fallback_day="2026-06-03",
    )
    assert not out  # xodim yo'q

    text2 = (
        "🏁 Mustafoev Abdullo ishini yakunladi\n\n"
        "Reys 3, yuk 120m, ish 75:39, dam 12:05"
    )
    out2 = parse_forward_text(text2, employees=EMPS, fallback_day="2026-06-03")
    assert len(out2) == 1
    assert out2[0]["bot_key"] == "omborga"
    assert "Reys 3" in out2[0]["summary_override"]


def test_yuk_reyting_multi():
    text = """🏆 REYTING
│ 🥇 Ruziboev Sindor
│     ⏱ 45:30
│ 🥈 Mustafoev Abdullo
│     ⏱ 1 soat 10 daq"""
    out = parse_forward_text(text, employees=EMPS, fallback_day="2026-06-04")
    assert len(out) >= 1
    keys = {x["bot_key"] for x in out}
    assert "yuk" in keys


def test_sklad():
    text = """✅ ТЕКШИРУВ — АЪЛО
👤 Mustafoev Abdullo
📁 Papka-A
✅ Саналди: 3"""
    out = parse_forward_text(text, employees=EMPS, fallback_day="2026-06-04")
    assert len(out) == 1
    assert out[0]["bot_key"] == "sklad"
    merged = aggregate_hub_events(out)
    assert "sanaldi 3" in merged[0]["summary"].lower()


def test_hub_line():
    text = "HUB|2026-06-03|123|yuk|Yuk (bugun jami): ish vaqti 120 soniya"
    out = parse_forward_text(text, employees=EMPS)
    assert len(out) == 1
    assert out[0]["bot_key"] == "yuk"
