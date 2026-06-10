"""Kaizen analytics — HTML dashboard."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from analytics_queries import build_dashboard

ASSETS = Path(__file__).resolve().parent / "assets" / "report"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS)),
        autoescape=select_autoescape(["html"]),
    )


def _logo_b64() -> str:
    svg = (ASSETS / "kanstik-logo.svg").read_bytes()
    return base64.b64encode(svg).decode("ascii")


def build_analytics_html(*, day: str | None = None, token: str = "") -> str:
    d = build_dashboard(day)
    css = (ASSETS / "analytics.css").read_text(encoding="utf-8")
    tpl = _env().get_template("analytics.html")
    return tpl.render(
        css=css,
        logo_b64=_logo_b64(),
        token=token,
        d=d,
    )
