"""Parser für die in kaufDA-Seiten eingebetteten __NEXT_DATA__-Daten."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from .errors import ParseError

BASE_URL = "https://www.kaufda.de"

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)

_UMLAUTS = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "Ä": "Ae",
    "Ö": "Oe",
    "Ü": "Ue",
    "ß": "ss",
}


def slugify_keyword(value: str) -> str:
    """Wandelt einen Suchbegriff in einen kaufDA-Keyword-Slug um."""
    text = " ".join(value.strip().split())
    if not text:
        return ""
    for umlaut, replacement in _UMLAUTS.items():
        text = text.replace(umlaut, replacement)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return "-".join(part[:1].upper() + part[1:] for part in text.split("-") if part)


def slugify_city(value: str) -> str:
    return slugify_keyword(value)


def extract_next_data(html: str) -> dict[str, Any]:
    match = _NEXT_DATA_RE.search(html or "")
    if not match:
        raise ParseError(
            "Die Seite enthält keine __NEXT_DATA__-Daten (Struktur geändert?)."
        )
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError(f"__NEXT_DATA__ ist kein gültiges JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("__NEXT_DATA__ hat ein unerwartetes Format.")
    return data


def get_page_information(data: dict[str, Any]) -> dict[str, Any]:
    info = (
        data.get("props", {})
        .get("pageProps", {})
        .get("pageInformation")
    )
    if not isinstance(info, dict):
        raise ParseError("pageInformation fehlt in den Seitendaten.")
    return info


def parse_page_information(html: str) -> dict[str, Any]:
    return get_page_information(extract_next_data(html))


def parse_location(info: dict[str, Any]) -> dict[str, Any]:
    raw = info.get("location")
    if not isinstance(raw, dict):
        return {}
    return {
        "city": raw.get("city") or raw.get("cityDisplayName"),
        "zip": raw.get("zip"),
        "lat": raw.get("lat"),
        "lng": raw.get("lng"),
        "countryCode": raw.get("countryCode"),
    }


def _iso_datetime(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.isoformat()


def _as_price(prices: dict[str, Any]) -> float | None:
    value = prices.get("mainPrice")
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            return None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return None
    return round(number, 2)


def _price_text(prices: dict[str, Any], price: float | None) -> str | None:
    formatted = prices.get("mainPriceFormatted")
    if isinstance(formatted, str) and formatted.strip():
        return formatted.strip()
    if price is None:
        return None
    return f"{price:.2f}".replace(".", ",") + " €"


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def search_url(
    keyword_slug: str,
    city_slug: str | None = None,
    page: int | None = None,
) -> str:
    if city_slug:
        url = f"{BASE_URL}/{slugify_city(city_slug)}/Angebote/{keyword_slug}"
    else:
        url = f"{BASE_URL}/Angebote/{keyword_slug}"
    if page is not None and page > 1:
        url = f"{url}?page={page}"
    return url


def dealer_url(dealer_slug: str) -> str:
    return f"{BASE_URL}/Geschaefte/{slugify_city(dealer_slug)}"


@dataclass
class Offer:
    id: str
    titel: str
    marke: str | None
    haendler: str
    preis: float | None
    preis_text: str | None
    grundpreis: str | None
    gueltig_von: str | None
    gueltig_bis: str | None
    prospekt_id: str | None
    seite: int | None
    url: str
    beschreibung: str | None = None
    bild_url: str | None = None
    rabatt: float | None = None

    def to_dict(self, detailed: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "titel": self.titel,
            "marke": self.marke,
            "haendler": self.haendler,
            "preis": self.preis,
            "preis_text": self.preis_text,
            "grundpreis": self.grundpreis,
            "gueltig_von": self.gueltig_von,
            "gueltig_bis": self.gueltig_bis,
            "prospekt_id": self.prospekt_id,
            "seite": self.seite,
            "url": self.url,
        }
        if detailed:
            result["beschreibung"] = self.beschreibung
            result["bild_url"] = self.bild_url
        return result


@dataclass
class Brochure:
    id: str
    titel: str
    content_id: str | None
    gueltig_von: str | None
    gueltig_bis: str | None
    url: str
    bild_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "titel": self.titel,
            "content_id": self.content_id,
            "gueltig_von": self.gueltig_von,
            "gueltig_bis": self.gueltig_bis,
            "url": self.url,
            "bild_url": self.bild_url,
        }


def _offer_from_item(
    item: dict[str, Any], keyword_slug: str, city_slug: str | None
) -> Offer | None:
    if item.get("type") != "OFFER":
        return None
    offer_id = item.get("id")
    title = _text(item.get("title"))
    if not offer_id or not title:
        return None
    prices = item.get("prices")
    if not isinstance(prices, dict):
        prices = {}
    parent = item.get("parentContent")
    if not isinstance(parent, dict):
        parent = {}
    page_info = parent.get("page")
    if not isinstance(page_info, dict):
        page_info = {}
    page_number = page_info.get("number")
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        page_number = None
    publisher = _text(item.get("publisherName")) or "Unbekannt"
    prospekt_id = parent.get("id")
    if prospekt_id is not None and not isinstance(prospekt_id, str):
        prospekt_id = str(prospekt_id)
    if not prospekt_id:
        legacy = parent.get("legacyId")
        prospekt_id = str(legacy) if legacy is not None else None

    price = _as_price(prices)
    secondary = prices.get("secondaryPrice")
    discount = None
    if (
        price is not None
        and isinstance(secondary, (int, float))
        and not isinstance(secondary, bool)
        and math.isfinite(float(secondary))
        and float(secondary) > price
    ):
        discount = round(float(secondary) - price, 2)

    images = item.get("offerImages")
    image_url = None
    if isinstance(images, dict):
        urls = images.get("url")
        if isinstance(urls, dict):
            image_url = _text(urls.get("large") or urls.get("normal"))

    base = search_url(keyword_slug, city_slug)
    return Offer(
        id=str(offer_id),
        titel=title,
        marke=_text(item.get("brand")),
        haendler=publisher,
        preis=price,
        preis_text=_price_text(prices, price),
        grundpreis=_text(prices.get("priceByBaseUnit")),
        gueltig_von=_iso_datetime(item.get("validFrom")),
        gueltig_bis=_iso_datetime(item.get("validUntil")),
        prospekt_id=prospekt_id,
        seite=page_number,
        url=f"{base}?offerId={offer_id}",
        beschreibung=_text(item.get("description")),
        bild_url=image_url,
        rabatt=discount,
    )


def parse_offers(
    info: dict[str, Any],
    keyword_slug: str | None = None,
    city_slug: str | None = None,
) -> list[Offer]:
    keyword = info.get("keyword")
    if not keyword_slug and isinstance(keyword, dict):
        keyword_slug = _text(keyword.get("url")) or _text(keyword.get("name"))
    if not keyword_slug:
        keyword_slug = "Angebote"
    offers = info.get("offers")
    if not isinstance(offers, dict):
        raise ParseError("offers fehlt in den Seitendaten.")
    main = offers.get("main")
    if not isinstance(main, dict):
        raise ParseError("offers.main fehlt in den Seitendaten.")
    main_items = main.get("items")
    if not isinstance(main_items, list):
        raise ParseError("offers.main.items fehlt in den Seitendaten.")

    result: list[Offer] = []
    seen_ids: set[str] = set()
    for key in ("main", "otherPublishers", "topRanked"):
        section = offers.get(key)
        if not isinstance(section, dict):
            continue
        items = section.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            offer = _offer_from_item(item, keyword_slug, city_slug)
            if offer is None or offer.id in seen_ids:
                continue
            seen_ids.add(offer.id)
            result.append(offer)
    return result


def _brochure_from_item(
    item: dict[str, Any], dealer_slug: str
) -> Brochure | None:
    content_id = _text(item.get("contentId"))
    brochure_id = item.get("id")
    title = _text(item.get("title"))
    if not title or brochure_id is None:
        return None
    image_url = None
    pages = item.get("pages")
    if isinstance(pages, list) and pages:
        first = pages[0]
        if isinstance(first, dict):
            urls = first.get("url")
            if isinstance(urls, dict):
                image_url = _text(urls.get("normal") or urls.get("large"))
    anchor = f"#brochure-{content_id}" if content_id else ""
    return Brochure(
        id=str(brochure_id),
        titel=title,
        content_id=content_id,
        gueltig_von=_iso_datetime(item.get("validFrom")),
        gueltig_bis=_iso_datetime(item.get("validUntil")),
        url=dealer_url(dealer_slug) + anchor,
        bild_url=image_url,
    )


def _iter_brochure_lists(info: dict[str, Any]) -> Iterable[list[Any]]:
    brochures = info.get("brochures")
    if not isinstance(brochures, dict):
        return []
    lists = []
    for key in ("publisher", "viewer", "keyword"):
        value = brochures.get(key)
        if isinstance(value, list):
            lists.append(value)
    return lists


def parse_brochures(
    info: dict[str, Any], dealer_slug: str
) -> list[Brochure]:
    result: list[Brochure] = []
    seen: set[str] = set()
    for items in _iter_brochure_lists(info):
        for item in items:
            if not isinstance(item, dict):
                continue
            brochure = _brochure_from_item(item, dealer_slug)
            if brochure is None or brochure.id in seen:
                continue
            seen.add(brochure.id)
            result.append(brochure)
    return result
