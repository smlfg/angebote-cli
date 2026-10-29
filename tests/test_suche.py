import json
import pathlib

import pytest

import angebote_cli.cli as cli
import angebote_cli.client as client_mod
from angebote_cli.errors import NotFoundError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
BUTTER_HTML = (FIXTURES / "angebote_butter.html").read_text(encoding="utf-8")


def fixture_fetch(url, timeout=15.0):
    if "/Angebote/Butter" in url:
        return BUTTER_HTML
    raise NotFoundError(f"Seite nicht gefunden (404): {url}")


@pytest.fixture
def no_net(monkeypatch):
    monkeypatch.setattr(client_mod, "fetch_html", fixture_fetch)


def run(argv):
    return cli.main(argv)


def out(capsys):
    return capsys.readouterr().out


def single_json(text):
    lines = text.strip().splitlines()
    assert len(lines) == 1, f"erwartet genau ein JSON-Objekt, got: {text[:200]}"
    return json.loads(lines[0])


def test_version_and_help():
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    with pytest.raises(SystemExit) as e:
        cli.main(["suche", "--help"])
    assert e.value.code == 0


def test_suche_finds_at_least_10(no_net, capsys):
    assert run(["suche", "butter", "--json"]) == 0
    data = single_json(out(capsys))
    assert data["ok"] is True
    assert data["anzahl"] >= 10
    for h in data["treffer"]:
        assert h["id"] and h["titel"] and h["haendler"]


def test_filter_haendler(no_net, capsys):
    run(["suche", "butter", "--haendler", "rewe", "--json"])
    data = single_json(out(capsys))
    assert data["treffer"]
    assert all("rewe" in (h["haendler"] or "").lower() for h in data["treffer"])


def test_filter_haendler_multiple(no_net, capsys):
    run(["suche", "butter", "--haendler", "rewe", "netto", "--json"])
    data = single_json(out(capsys))
    assert data["treffer"]
    assert all(
        ("rewe" in (h["haendler"] or "").lower())
        or ("netto" in (h["haendler"] or "").lower())
        for h in data["treffer"]
    )


def test_filter_max_preis_excludes_missing_price(no_net, capsys):
    run(["suche", "butter", "--max-preis", "1.5", "--json"])
    data = single_json(out(capsys))
    assert data["treffer"]
    for h in data["treffer"]:
        assert h.get("preis") is not None and h["preis"] <= 1.5


def test_filter_marke(no_net, capsys):
    run(["suche", "butter", "--marke", "kerrygold", "--json"])
    data = single_json(out(capsys))
    assert data["treffer"]
    assert all("kerrygold" in (h["marke"] or "").lower() for h in data["treffer"])


def test_filter_haendler_case_insensitive(no_net, capsys):
    run(["suche", "butter", "--haendler", "NETTO", "--json"])
    data = single_json(out(capsys))
    assert data["treffer"]
    assert all("netto" in (h["haendler"] or "").lower() for h in data["treffer"])


def test_sort_preis(no_net, capsys):
    run(["suche", "butter", "--sort", "preis", "--json"])
    data = single_json(out(capsys))
    prices = [h["preis"] if h["preis"] is not None else float("inf") for h in data["treffer"]]
    assert prices == sorted(prices)


def test_sort_rabatt(no_net, capsys):
    run(["suche", "butter", "--sort", "rabatt", "--json"])
    data = single_json(out(capsys))
    rab = [h.get("rabatt") or 0.0 for h in data["treffer"]]
    assert rab == sorted(rab, reverse=True)


def test_limit(no_net, capsys):
    run(["suche", "butter", "--limit", "3", "--json"])
    data = single_json(out(capsys))
    assert data["anzahl"] == 3


def test_zero_hits_filters_not_found(no_net):
    assert run(["suche", "butter", "--max-preis", "0.01"]) == 3


def test_unknown_keyword_not_found(no_net, capsys):
    assert run(["suche", "nichtvorhanden-begriff", "--json"]) == 3
    data = single_json(out(capsys))
    assert data["ok"] is False
    assert data["error"]["type"] == "not_found"


def test_text_output(no_net, capsys):
    assert run(["suche", "butter"]) == 0
    text = out(capsys)
    assert "Ort:" in text
    assert "REWE" in text
