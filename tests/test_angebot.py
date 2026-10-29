import pathlib

import pytest

import angebote_cli.cli as cli
import angebote_cli.client as client_mod
from angebote_cli.errors import NotFoundError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
BUTTER_HTML = (FIXTURES / "angebote_butter.html").read_text(encoding="utf-8")

KNOWN_ID = "f33d8959-0979-4d6c-b4ca-08f15918b7ce"  # Original Irische Butter, REWE


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


def test_angebot_details_json(no_net, capsys):
    assert run(["angebot", KNOWN_ID, "--begriff", "butter", "--json"]) == 0
    import json

    data = json.loads(out(capsys).strip().splitlines()[0])
    assert data["ok"] is True
    a = data["angebot"]
    assert a["id"] == KNOWN_ID
    assert a["titel"] == "Original Irische Butter"
    assert a["beschreibung"]
    assert a["haendler"] == "REWE"
    assert a["preis"] == 1.59
    assert a["gueltig_bis"]
    assert a["prospekt_id"]
    assert a["seite"] is None or isinstance(a["seite"], int)
    assert a["bild"].startswith("http")
    assert data["ort"]["city"] == "Stuttgart"


def test_angebot_text(no_net, capsys):
    assert run(["angebot", KNOWN_ID, "--begriff", "butter"]) == 0
    text = out(capsys)
    assert "Original Irische Butter" in text
    assert "REWE" in text
    assert "1,59" in text or "1.59" in text


def test_angebot_missing_begriff(no_net, capsys):
    assert run(["angebot", KNOWN_ID]) == 1


def test_angebot_missing_begriff_json(no_net, capsys):
    assert run(["angebot", KNOWN_ID, "--json"]) == 1
    import json

    data = json.loads(out(capsys).strip().splitlines()[0])
    assert data["ok"] is False
    assert data["error"]["type"] == "usage"


def test_angebot_unknown_id(no_net, capsys):
    assert run(["angebot", "deadbeef-0000", "--begriff", "butter", "--json"]) == 3
    import json

    data = json.loads(out(capsys).strip().splitlines()[0])
    assert data["error"]["type"] == "not_found"
    assert "angebote suche" in data["error"]["message"]
