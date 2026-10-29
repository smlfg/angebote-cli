from __future__ import annotations

from datetime import datetime
from pathlib import Path

from angebote_cli.parser import (
    parse_brochures,
    parse_offers,
    parse_page_information,
    slugify_city,
    slugify_keyword,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_offers_butter() -> None:
    info = parse_page_information(read_fixture("angebote_butter.html"))
    offers = parse_offers(info)

    assert len(offers) >= 10
    for offer in offers:
        assert offer.id
        assert offer.titel
        assert offer.haendler
        if offer.preis is not None:
            assert isinstance(offer.preis, float)
            assert 0 < offer.preis < 50

    with_price = [offer for offer in offers if offer.preis is not None]
    assert len(with_price) >= 10


def test_offer_fields_and_location() -> None:
    info = parse_page_information(read_fixture("angebote_butter.html"))
    offers = parse_offers(info)
    offer = offers[0]

    assert offer.preis_text
    assert offer.grundpreis is not None
    assert offer.gueltig_von and offer.gueltig_von.endswith("+00:00")
    assert offer.gueltig_bis and offer.gueltig_bis.endswith("+00:00")
    assert offer.prospekt_id
    assert isinstance(offer.seite, int)
    assert offer.url.startswith("https://www.kaufda.de/Angebote/")

    data = offer.to_dict()
    for key in (
        "id",
        "titel",
        "marke",
        "haendler",
        "preis",
        "preis_text",
        "grundpreis",
        "gueltig_von",
        "gueltig_bis",
        "prospekt_id",
        "seite",
        "url",
    ):
        assert key in data

    location = info["location"]
    assert location["city"] == "Stuttgart"
    assert location["zip"] == "70174"


def test_brochures_rewe() -> None:
    info = parse_page_information(read_fixture("geschaeft_rewe.html"))
    brochures = parse_brochures(info, "REWE")

    assert len(brochures) >= 1
    for brochure in brochures:
        assert brochure.titel
        assert brochure.id
        assert brochure.url.startswith("https://www.kaufda.de/Geschaefte/REWE")
        assert brochure.gueltig_von
        assert brochure.gueltig_bis
        datetime.fromisoformat(brochure.gueltig_von)
        datetime.fromisoformat(brochure.gueltig_bis)


def test_offers_include_other_sections_and_dedupe_by_id() -> None:
    info = parse_page_information(read_fixture("angebote_butter.html"))
    main_items = info["offers"]["main"]["items"]
    first = main_items[0]
    duplicate = dict(first)
    second = dict(main_items[1])
    second["id"] = "other-publisher-only"
    info["offers"]["otherPublishers"] = {
        "items": [duplicate, second],
        "totalItems": 2,
    }
    info["offers"]["topRanked"] = {
        "items": [dict(main_items[2])],
        "totalItems": 1,
    }

    offers = parse_offers(info)

    ids = [offer.id for offer in offers]
    assert len(ids) == len(set(ids))
    assert "other-publisher-only" in ids
    assert len(offers) == len(main_items) + 1


def test_slugify_keyword() -> None:
    assert slugify_keyword("Irische Butter") == "Irische-Butter"
    assert slugify_keyword("Käse") == "Kaese"
    assert slugify_keyword("  irische   butter ") == "Irische-Butter"
    assert slugify_keyword("Müsli & Obst") == "Muesli-&-Obst"


def test_slugify_city() -> None:
    assert slugify_city("München") == "Muenchen"
    assert slugify_city("Frankfurt am Main") == "Frankfurt-Am-Main"
