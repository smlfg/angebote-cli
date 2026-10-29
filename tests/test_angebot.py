from __future__ import annotations

import json

import pytest

from angebote_cli import cli
from angebote_cli.parser import parse_offers, parse_page_information

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


def first_offer_id() -> str:
    info = parse_page_information(read_fixture("angebote_butter.html"))
    return parse_offers(info)[0].id


def test_angebot_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    fake = install_client(monkeypatch, read_fixture("angebote_butter.html"))
    offer_id = first_offer_id()
    code = cli.main(
        ["angebot", offer_id, "--begriff", "Butter", "--json"]
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["ok"] is True
    detail = data["angebot"]
    assert detail["id"] == offer_id
    assert detail["titel"]
    assert detail["beschreibung"] is not None
    assert detail["bild_url"].startswith("https://content-media.bonial.biz/")
    assert detail["haendler"]
    assert detail["gueltig_bis"]
    assert detail["prospekt_id"]
    assert detail["seite"] is not None
    assert fake.urls == ["https://www.kaufda.de/Angebote/Butter"]


def test_angebot_without_begriff_is_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    code = cli.main(["angebot", first_offer_id(), "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 1
    assert data["ok"] is False
    assert data["error"]["type"] == "usage"
    assert "--begriff" in data["error"]["message"]


def test_angebot_unknown_id(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    code = cli.main(
        ["angebot", "00000000-0000-0000-0000-000000000000", "--begriff", "Butter", "--json"]
    )

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 3
    assert data["error"]["type"] == "not_found"


def test_angebot_text(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    offer_id = first_offer_id()
    code = cli.main(["angebot", offer_id, "--begriff", "Butter"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Ort: Stuttgart (70174)" in captured.out
    assert "Beschreibung:" in captured.out
    assert "Preis:" in captured.out
    assert "URL: https://www.kaufda.de/Angebote/Butter?offerId=" in captured.out
