"""Yordamchi bot kategoriya yozuvlari (02–03.06.2026) — deployda avtomatik."""

from __future__ import annotations

METRICS_SEED_VERSION = 2

# (day, employee, category, value) — faqat Ёрдамчи бот
METRICS_SEED_ROWS: tuple[tuple[str, str, str, int], ...] = (
    # 2026-06-02
    ("2026-06-02", "Sagdullaev Yunus", "Приход", 29),
    ("2026-06-02", "Sagdullaev Yunus", "Перемещение", 193),
    ("2026-06-02", "Sagdullaev Yunus", "Переоценка", 20),
    ("2026-06-02", "Toxirov Muslimbek", "Перемещение", 12),
    ("2026-06-02", "Toxirov Muslimbek", "Счет ТСД", 32),
    ("2026-06-02", "Toxirov Muslimbek", "АРМ диспетчер", 44),
    ("2026-06-02", "Toxirov Muslimbek", "Пересчет товаров", 54),
    ("2026-06-02", "Toxirov Muslimbek", "Места хр", 58),
    ("2026-06-02", "Ravshanov Oxunjon", "Счет ТСД", 18),
    ("2026-06-02", "Samadov To'lqin", "Счет ТСД", 94),
    ("2026-06-02", "Shernazarov Tolib", "Счет ТСД", 65),
    ("2026-06-02", "Mustafoev Abdullo", "Счет ТСД", 21),
    ("2026-06-02", "Mustafoev Abdullo", "Переоценка", 65),
    ("2026-06-02", "Mustafoev Abdullo", "Места хр", 21),
    ("2026-06-02", "Ravshanov Ziyodullo", "Перемещение", 5),
    ("2026-06-02", "Ravshanov Ziyodullo", "Счет ТСД", 15),
    ("2026-06-02", "Ravshanov Ziyodullo", "Места хр", 35),
    ("2026-06-02", "Ruziboev Sindor", "Пересчет товаров", 100),
    # 2026-06-03
    ("2026-06-03", "Ruziboev Sindor", "Перемещение", 10),
    ("2026-06-03", "Yadullaev Umidjon", "Пересчет товаров", 95),
    ("2026-06-03", "Yadullaev Umidjon", "Фото ТМЦ", 103),
    ("2026-06-03", "Sagdullaev Yunus", "Приход", 55),
    ("2026-06-03", "Sagdullaev Yunus", "Перемещение", 171),
    ("2026-06-03", "Sagdullaev Yunus", "Переоценка", 45),
    ("2026-06-03", "Ravshanov Oxunjon", "Счет ТСД", 78),
    ("2026-06-03", "Samadov To'lqin", "Счет ТСД", 90),
    ("2026-06-03", "Shernazarov Tolib", "Счет ТСД", 40),
    ("2026-06-03", "Mustafoev Abdullo", "Счет ТСД", 32),
    ("2026-06-03", "Mustafoev Abdullo", "Фасовка", 108),
    ("2026-06-03", "Mustafoev Abdullo", "Пересчет товаров", 44),
    ("2026-06-03", "Mustafoev Abdullo", "Места хр", 113),
    ("2026-06-03", "Toxirov Muslimbek", "Перемещение", 52),
    ("2026-06-03", "Toxirov Muslimbek", "Счет ТСД", 16),
    ("2026-06-03", "Toxirov Muslimbek", "АРМ диспетчер", 34),
    ("2026-06-03", "Toxirov Muslimbek", "Пересчет товаров", 48),
    ("2026-06-03", "Toxirov Muslimbek", "Места хр", 18),
    ("2026-06-03", "Ravshanov Ziyodullo", "Места хр", 100),
    # 2026-06-04 — yordamchi (kunlik hisobot)
    ("2026-06-04", "Sagdullaev Yunus", "Приход", 59),
    ("2026-06-04", "Sagdullaev Yunus", "Перемещение", 214),
    ("2026-06-04", "Sagdullaev Yunus", "Переоценка", 50),
)
