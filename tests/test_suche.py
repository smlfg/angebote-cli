from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from angebote_cli import cli
from angebote_cli.parser import extract_next_data

from conftest import read_fixture


class FakeClient:
    def __init__(self, html: str):
        self.html = html
        self.urls: list[str] = []

    def get(self, url: str) -> str:
        self.urls.append(url)
        return self.html


def install_client(monkeypatch: pytest.MonkeyPatch, html: str) -> FakeClient:
    fake = FakeClient(html)

    def factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(cli, "KaufdaClient", factory)
    return fake


def run_json(capsys: pytest.CaptureFixture[str], argv: list[str]) -> dict:
    code = cli.main(argv)
    captured = capsys.readouterr()
    assert code == 0
    return json.loads(captured.out)


def test_suche_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--json"])

    assert data["ok"] is True
    assert data["anzahl"] >= 10
    assert len(data["angebote"]) == data["anzahl"]
    assert data["location"]["city"] == "Stuttgart"
    first = data["angebote"][0]
    assert first["id"]
    assert first["titel"]
    assert first["haendler"]
    assert first["preis_text"]
    assert first["beschreibung"]
    assert isinstance(first["kategorien"], list) and first["kategorien"]


def test_suche_relevance_filters_unrelated(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--json"])

    titles = {offer["titel"] for offer in data["angebote"]}
    assert data["verworfen_irrelevant"] >= 1
    assert "3D-Puzzle Vase Organic sage" not in titles
    assert "Hazelnut Choco" not in titles
    for offer in data["angebote"]:
        haystack = cli._normalize_text(
            " ".join(
                [
                    offer["titel"],
                    offer["beschreibung"] or "",
                    offer["marke"] or "",
                    " ".join(offer["kategorien"]),
                ]
            )
        )
        assert "butter" in haystack


def test_suche_relevance_requires_own_word() -> None:
    toast = SimpleNamespace(
        titel="Vollkorn Toast",
        beschreibung="versch. Sorten",
        marke="Harry",
        kategorien=["Harry", "Buttertoast", "Vollkorntoast"],
    )
    butter = SimpleNamespace(
        titel="Butter",
        beschreibung=None,
        marke="Landliebe",
        kategorien=["Butter"],
    )

    kept, dropped = cli._filter_relevant([toast, butter], "Butter")

    assert kept == [butter]
    assert dropped == 1


def test_suche_locker_keeps_unrelated(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--locker", "--json"])

    titles = {offer["titel"] for offer in data["angebote"]}
    assert data["verworfen_irrelevant"] == 0
    assert "3D-Puzzle Vase Organic sage" in titles
    assert "Hazelnut Choco" in titles


def test_suche_haendler_filter(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--haendler", "rewe", "--json"])

    assert data["angebote"]
    assert all("rewe" in offer["haendler"].casefold() for offer in data["angebote"])


def test_suche_max_preis_filter(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(
        capsys, ["suche", "Butter", "--max-preis", "1.5", "--json"]
    )

    assert data["angebote"]
    assert all(
        offer["preis"] is not None and offer["preis"] <= 1.5
        for offer in data["angebote"]
    )


def test_suche_marke_filter(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--marke", "kerrygold", "--json"])

    assert data["angebote"]
    assert all("kerrygold" in offer["marke"].casefold() for offer in data["angebote"])


def test_suche_sort_preis(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--sort", "preis", "--json"])

    prices = [offer["preis"] for offer in data["angebote"] if offer["preis"] is not None]
    assert prices == sorted(prices)


def test_suche_limit(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(capsys, ["suche", "Butter", "--limit", "3", "--json"])

    assert data["anzahl"] == 3
    assert len(data["angebote"]) == 3


def _page_with(html: str, transform) -> str:
    data = extract_next_data(html)
    transform(data["props"]["pageProps"]["pageInformation"]["offers"]["main"]["items"])
    return f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'


def _page_with_location(html: str, location: dict) -> str:
    data = extract_next_data(html)
    data["props"]["pageProps"]["pageInformation"]["location"] = location
    return f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'


HEILBRONN = {
    "city": "Heilbronn, Neckar",
    "cityDisplayName": "Heilbronn",
    "countryCode": "DE",
    "lat": 49.1416,
    "lng": 9.22208,
    "zip": "74072",
}


def test_suche_ort_uses_city_url(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    html = _page_with_location(read_fixture("angebote_butter.html"), HEILBRONN)
    fake = install_client(monkeypatch, html)
    data = run_json(
        capsys,
        ["--ort", "Heilbronn", "suche", "Butter", "--seiten", "1", "--json"],
    )

    assert fake.urls == ["https://www.kaufda.de/Heilbronn/Angebote/Butter"]
    assert data["location"]["city"] == "Heilbronn, Neckar"
    assert data["location"]["zip"] == "74072"


def test_suche_plz_resolves_city(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    html = _page_with_location(read_fixture("angebote_butter.html"), HEILBRONN)
    fake = install_client(monkeypatch, html)
    monkeypatch.setattr(
        cli, "_resolve_zip_city", lambda plz, client: "Heilbronn"
    )
    data = run_json(
        capsys,
        ["suche", "Butter", "--plz", "74072", "--seiten", "1", "--json"],
    )

    assert fake.urls == ["https://www.kaufda.de/Heilbronn/Angebote/Butter"]
    assert data["location"]["zip"] == "74072"


def test_suche_invalid_plz_is_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fake = install_client(monkeypatch, read_fixture("angebote_butter.html"))
    code = cli.main(["suche", "Butter", "--plz", "7407", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert code == 1
    assert data["error"]["type"] == "usage"
    assert fake.urls == []


def test_suche_slug_url(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    fake = install_client(monkeypatch, read_fixture("angebote_butter.html"))
    run_json(capsys, ["suche", "Irische Butter", "--seiten", "1", "--json"])

    assert fake.urls == ["https://www.kaufda.de/Angebote/Irische-Butter"]


def test_suche_pagination_finds_offer_on_later_page(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fixture = read_fixture("angebote_butter.html")

    def make_page_two(items: list[dict]) -> None:
        for index, item in enumerate(items):
            item["id"] = f"page-2-{index}"
            parent = item.get("parentContent")
            if isinstance(parent, dict):
                parent["id"] = f"prospekt-2-{index}"
        items[0]["publisherName"] = "Lidl"
        items[0]["title"] = "Lidl Kaffee"

    page_two = _page_with(fixture, make_page_two)
    empty = _page_with(
        fixture,
        lambda items: items.clear(),
    )
    pages = {
        "https://www.kaufda.de/Angebote/Kaffee": fixture,
        "https://www.kaufda.de/Angebote/Kaffee?page=2": page_two,
        "https://www.kaufda.de/Angebote/Kaffee?page=3": empty,
    }

    class PagedClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, url: str) -> str:
            self.urls.append(url)
            return pages[url]

    fake = PagedClient()
    monkeypatch.setattr(cli, "KaufdaClient", lambda *args, **kwargs: fake)
    data = run_json(
        capsys, ["suche", "Kaffee", "--haendler", "lidl", "--json"]
    )

    assert fake.urls == [
        "https://www.kaufda.de/Angebote/Kaffee",
        "https://www.kaufda.de/Angebote/Kaffee?page=2",
        "https://www.kaufda.de/Angebote/Kaffee?page=3",
    ]
    assert data["anzahl"] == 1
    assert data["angebote"][0]["haendler"] == "Lidl"
    assert data["angebote"][0]["titel"] == "Lidl Kaffee"


def test_suche_pagination_falls_back_to_search_api(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fixture = read_fixture("angebote_butter.html")
    data = extract_next_data(fixture)
    api_offer = dict(
        data["props"]["pageProps"]["pageInformation"]["offers"]["main"]["items"][0]
    )
    api_offer["id"] = "api-lidl-kaffee"
    api_offer["publisherName"] = "Lidl"
    api_offer["title"] = "Lidl Kaffee"

    class FallbackClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def get(self, url: str) -> str:
            self.urls.append(url)
            if "/api/search?" in url:
                if "offset=20" in url:
                    offers = [api_offer]
                else:
                    offers = []
                return json.dumps(
                    {
                        "searchResults": {
                            "contents": {"brochures": [], "offers": offers}
                        }
                    }
                )
            return fixture

    fake = FallbackClient()
    monkeypatch.setattr(cli, "KaufdaClient", lambda *args, **kwargs: fake)
    data = run_json(
        capsys, ["suche", "Kaffee", "--haendler", "lidl", "--json"]
    )

    assert any("/api/search?" in url for url in fake.urls)
    assert data["anzahl"] == 1
    assert data["angebote"][0]["id"] == "api-lidl-kaffee"


def test_suche_seiten_limit_is_validated(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    code = cli.main(["suche", "Butter", "--seiten", "11", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert code == 1
    assert data["error"]["type"] == "usage"


def test_suche_deduplicates_regional_offers(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(
        capsys,
        ["suche", "Butter", "--haendler", "rewe", "--seiten", "1", "--json"],
    )

    offers = data["angebote"]
    keys = [
        (
            offer["titel"].casefold(),
            (offer["marke"] or "").casefold(),
            offer["haendler"].casefold(),
            offer["preis"],
            offer["gueltig_bis"],
        )
        for offer in offers
    ]
    assert len(keys) == len(set(keys))
    merged = next(offer for offer in offers if offer["weitere_ids"])
    assert merged["anzahl_prospekte"] == 2
    assert len(merged["weitere_ids"]) == 1


def test_suche_alle_keeps_regional_offers(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    data = run_json(
        capsys,
        [
            "suche",
            "Butter",
            "--haendler",
            "rewe",
            "--seiten",
            "1",
            "--alle",
            "--json",
        ],
    )

    offers = data["angebote"]
    assert len(offers) == 5
    assert all(offer["weitere_ids"] == [] for offer in offers)
    assert all(offer["anzahl_prospekte"] == 1 for offer in offers)


def test_suche_not_found(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    empty = json.dumps(
        {
            "props": {
                "pageProps": {
                    "pageInformation": {
                        "offers": {"main": {"items": []}},
                        "location": {"city": "Stuttgart", "zip": "70174"},
                    }
                }
            }
        }
    )
    html = f'<script id="__NEXT_DATA__">{empty}</script>'
    install_client(monkeypatch, html)

    code = cli.main(["suche", "Gibteseinicht", "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 3
    assert data["ok"] is False
    assert data["error"]["type"] == "not_found"


def test_suche_text_output(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    code = cli.main(["suche", "Butter", "--limit", "2"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Ort: Stuttgart (70174)" in captured.out
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 3
