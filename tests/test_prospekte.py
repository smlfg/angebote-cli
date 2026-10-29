import json
import pathlib

import pytest

import angebote_cli.cli as cli
import angebote_cli.client as client_mod
from angebote_cli.errors import NotFoundError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REWE_HTML = (FIXTURES / "geschaeft_rewe.html").read_text(encoding="utf-8")


def fixture_fetch(url, timeout=15.0):
    if "/Geschaefte/" in url:
        slug = url.rsplit("/", 1)[1]
        if slug == "REWE":
            return REWE_HTML
        raise NotFoundError(f"Seite nicht gefunden (404): {url}")
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


def test_prospekte_rewe(no_net, capsys):
    assert run(["prospekte", "rewe", "--json"]) == 0
    data = single_json(out(capsys))
    assert data["ok"] is True
    assert data["anzahl"] >= 1
    for b in data["prospekte"]:
        assert b["titel"]
        assert b["gueltig_von"] and b["gueltig_bis"]
        assert b["gueltig_von"] < b["gueltig_bis"]
        assert b["id"] is not None


def test_prospekte_uppercase_fallback(no_net, capsys):
    # "REWE" wird als Kandidat probiert, wenn Titel-Case 404 liefert
    assert run(["prospekte", "REWE", "--json"]) == 0
    data = single_json(out(capsys))
    assert data["anzahl"] >= 1


def test_prospekte_unknown_haendler(no_net, capsys):
    assert run(["prospekte", "gibtsnicht", "--json"]) == 3
    data = single_json(out(capsys))
    assert data["error"]["type"] == "not_found"


def test_prospekte_text(no_net, capsys):
    assert run(["prospekte", "rewe"]) == 0
    text = out(capsys)
    assert "REWE" in text or "Dein Markt" in text
    assert "Ort:" in text
