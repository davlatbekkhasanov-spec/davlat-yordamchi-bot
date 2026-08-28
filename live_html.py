"""Jonli holat — HTML dashboard."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ASSETS = Path(__file__).resolve().parent / "assets" / "report"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS)),
        autoescape=select_autoescape(["html"]),
    )


def _logo_b64() -> str:
    svg = (ASSETS / "kanstik-logo.svg").read_bytes()
    return base64.b64encode(svg).decode("ascii")


def build_live_html(*, token: str = "") -> str:
    css = (ASSETS / "live.css").read_text(encoding="utf-8")
    tpl = _env().get_template("live.html")
    return tpl.render(css=css, logo_b64=_logo_b64(), token=token)
