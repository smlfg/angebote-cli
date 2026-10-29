"""Ausgabeformate (Text / JSON)."""

from __future__ import annotations

import json
import sys
from typing import Any


def print_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def error_json(type: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"type": type, "message": message}}


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "?"
    return iso[:10]


def fmt_price(value: float | None, preis_text: str | None = None) -> str:
    if preis_text:
        return preis_text
    if value is None:
        return "?"
    return f"{value:.2f} €"


def hit_line(hit: dict[str, Any]) -> str:
    return (
        f"{fmt_price(hit.get('preis'), hit.get('preis_text'))} | "
        f"{hit.get('titel')} | {hit.get('marke') or '?'} | "
        f"{hit.get('haendler')} | bis {fmt_date(hit.get('gueltig_bis'))}"
    )


def brochure_line(b: dict[str, Any]) -> str:
    von, bis = b.get("gueltig_von"), b.get("gueltig_bis")
    span = f"{fmt_date(von)} - {fmt_date(bis)}" if von or bis else "?"
    seiten = f", {b['seiten']} Seiten" if b.get("seiten") else ""
    id_ = f" (id {b.get('id')})" if b.get("id") is not None else ""
    return f"{b.get('haendler') or '?'}: {b.get('titel')} | {span}{seiten}{id_}"
