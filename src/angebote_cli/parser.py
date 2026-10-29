"""Parsing von kaufDA-SEO-Seiten (`<script id="__NEXT_DATA__">`)."""

from __future__ import annotations

import json
import re
from typing import Any

BASE_URL = "https://www.kaufda.de"


class ParseError(Exception):
    """Seitenstruktur unerwartet geaendert."""


def extract_page_information(html: str) -> dict[str, Any]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ParseError("__NEXT_DATA__ nicht gefunden")
    try:
        data = json.loads(m.group(1))
    except ValueError as exc:
        raise ParseError(f"__NEXT_DATA__ ist kein gueltiges JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("__NEXT_DATA__ enthaelt kein Objekt")
    pi = data.get("props", {}).get("pageProps", {}).get("pageInformation")
    if not isinstance(pi, dict):
        raise ParseError("pageInformation fehlt in __NEXT_DATA__")
    return pi


def normalize_iso(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v.endswith("+0000"):
        v = v[:-5] + "+00:00"
    return v


def slugify(keyword: str) -> str | None:
    if not keyword or not keyword.strip():
        return None
    s = keyword.strip()
    trans = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for src, dst in trans.items():
        s = s.replace(src, dst)
    words = [w.capitalize() for w in re.split(r"[\s_]+", s) if w]
    s = "-".join(re.sub(r"-+", "-", w) for w in words)
    if not s or not re.fullmatch(r"[\w-]+", s, re.UNICODE) or s.startswith("-"):
        return None
    return s


def pi_url(page_information: dict[str, Any]) -> str | None:
    url = page_information.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    return None


def _price_from_offer(offer: dict[str, Any]) -> float | None:
    prices = offer.get("prices") or {}
    raw = prices.get("mainPrice")
    if isinstance(raw, (int, float)):
        return float(raw) if float(raw) > 0 else None
    if isinstance(raw, str):
        try:
            v = float(raw.replace(",", "."))
            return v if v > 0 else None
        except ValueError:
            return None
    return None


def preis_text(offer: dict[str, Any]) -> str | None:
    prices = offer.get("prices") or {}
    main = prices.get("mainPriceFormatted") or ""
    if not main and prices.get("mainPrice") is not None:
        main = f"{prices['mainPrice']} €"
    if prices.get("mainPriceFrequency") == "PER_UNIT":
        cond = (prices.get("conditions") or [{}])[0]
        unit = cond.get("other") if isinstance(cond, dict) else None
        main = f"{main}/{unit or 'Einheit'}".replace(" €/", " € / ")
    return main or None


def offer_to_hit(offer: dict[str, Any], url: str) -> dict[str, Any]:
    pc = offer.get("parentContent") or {}
    page = (pc.get("page") or {}).get("number")
    urls = (offer.get("offerImages") or {}).get("url") or {}
    return {
        "id": offer.get("id"),
        "titel": offer.get("title"),
        "marke": offer.get("brand") or None,
        "haendler": offer.get("publisherName") or None,
        "preis": _price_from_offer(offer),
        "preis_text": preis_text(offer),
        "grundpreis": (offer.get("prices") or {}).get("priceByBaseUnit") or None,
        "gueltig_von": normalize_iso(offer.get("validFrom")),
        "gueltig_bis": normalize_iso(offer.get("validUntil")),
        "prospekt_id": pc.get("id"),
        "seite": page,
        "url": url,
        "bild": urls.get("normal") or urls.get("large") or None,
    }


def parse_offers(page_information: dict[str, Any], url: str | None = None) -> list[dict[str, Any]]:
    offers = (page_information.get("offers") or {}).get("main") or {}
    items = offers.get("items")
    if not isinstance(items, list):
        raise ParseError("offers.main.items fehlt")
    fallback = pi_url(page_information) or BASE_URL
    link = url or fallback
    hits = []
    for item in items:
        if not isinstance(item, dict):
            raise ParseError("offers.main.items: Eintrag ist kein Objekt")
        if not item.get("id") or not item.get("title"):
            raise ParseError("offers.main.items: id/titel fehlt")
        hits.append(offer_to_hit(item, link))
    return hits


def parse_brochures(page_information: dict[str, Any], key: str | None = None) -> list[dict[str, Any]]:
    brochures = page_information.get("brochures") or {}
    if key and isinstance(brochures.get(key), list):
        sources = [brochures[key]]
    else:
        sources = [
            v
            for k, v in brochures.items()
            if isinstance(v, list) and k in ("keyword", "publisher", "viewer")
        ]
    seen: set[Any] = set()
    default_haendler = (page_information.get("publisher") or {}).get("name")
    out = []
    for src in sources:
        for b in src:
            if not isinstance(b, dict):
                raise ParseError("brochures: Eintrag ist kein Objekt")
            cid = b.get("contentId") or b.get("id")
            if cid in seen:
                continue
            seen.add(cid)
            out.append(
                {
                    "id": b.get("id"),
                    "titel": b.get("title") or "",
                    "haendler": (b.get("publisher") or {}).get("name")
                    or default_haendler,
                    "content_id": b.get("contentId"),
                    "gueltig_von": normalize_iso(b.get("validFrom")),
                    "gueltig_bis": normalize_iso(b.get("validUntil")),
                    "seiten": b.get("pageCount"),
                    "url": pi_url(page_information),
                }
            )
    return out


def parse_location(page_information: dict[str, Any]) -> dict[str, Any]:
    loc = page_information.get("location") or {}
    return {
        "city": loc.get("cityDisplayName") or loc.get("city"),
        "zip": loc.get("zip"),
        "lat": loc.get("lat"),
        "lng": loc.get("lng"),
    }


def parse_matching_offers(page_information: dict[str, Any]) -> list[dict[str, Any]]:
    content = (page_information.get("template") or {}).get("content") or {}
    pit = content.get("ProductInfoTable") or {}
    rows = pit.get("matching_offers") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "name": row.get("offerName"),
                "marke": row.get("offerBrandName"),
                "haendler": row.get("offerRetailer"),
                "preis_text": row.get("price"),
                "grundpreis": row.get("pricePerUnit"),
            }
        )
    return out
