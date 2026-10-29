import pathlib

import pytest

from angebote_cli.parser import (
    extract_page_information,
    normalize_iso,
    parse_brochures,
    parse_location,
    parse_matching_offers,
    parse_offers,
    slugify,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def butter_pi():
    return extract_page_information(load("angebote_butter.html"))


def rewe_pi():
    return extract_page_information(load("geschaeft_rewe.html"))


def test_extract_page_information():
    pi = butter_pi()
    assert "offers" in pi and "location" in pi


def test_extract_missing_script():
    with pytest.raises(Exception):
        extract_page_information("<html></html>")


def test_offers_fixture_have_ids_and_prices():
    hits = parse_offers(butter_pi())
    assert len(hits) >= 10
    for h in hits:
        assert h["id"]
        assert h["titel"]
        assert h["haendler"]
        if h["preis"] is not None:
            assert 0 < h["preis"] < 50


def test_validity_iso():
    hits = parse_offers(butter_pi())
    with_valid = [h for h in hits if h["gueltig_bis"]]
    assert with_valid
    for h in with_valid:
        assert h["gueltig_von"].endswith("+00:00")


def test_slug():
    assert slugify("Irische Butter") == "Irische-Butter"
    assert slugify("Käse") == "Kaese"
    assert slugify("irische butter") == "Irische-Butter"
    assert slugify("Grün ß") == "Gruen-Ss"
    assert slugify("") is None
    assert slugify("   ") is None
    assert slugify("!#?") is None


def test_brochures_keyword():
    bros = parse_brochures(butter_pi(), "keyword")
    assert len(bros) >= 1
    for b in bros:
        assert b["id"]
        assert b["gueltig_von"] and b["gueltig_bis"]
        assert b["gueltig_von"].endswith("+00:00")
        assert b["titel"]


def test_brochures_publisher_rewe():
    bros = parse_brochures(rewe_pi(), "publisher")
    assert len(bros) >= 1
    assert bros[0]["haendler"] == "REWE"
    assert bros[0]["gueltig_bis"].endswith("+00:00")


def test_location_default():
    loc = parse_location(butter_pi())
    assert loc["city"] == "Stuttgart"
    assert loc["zip"] == "70174"


def test_matching_offers():
    rows = parse_matching_offers(butter_pi())
    assert len(rows) >= 1
    assert rows[0]["name"]


def test_broken_html():
    import re

    html = load("angebote_butter.html")
    broken = re.sub(
        r"<script id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>", "", html, flags=re.S
    )
    with pytest.raises(Exception):
        extract_page_information(broken)


def test_normalize_iso():
    assert normalize_iso("2026-10-31T22:00:00.000+0000") == "2026-10-31T22:00:00.000+00:00"
    assert normalize_iso(None) is None
