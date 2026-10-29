from __future__ import annotations

import json

import pytest

from angebote_cli import cli

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


def test_suche_slug_url(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    fake = install_client(monkeypatch, read_fixture("angebote_butter.html"))
    run_json(capsys, ["suche", "Irische Butter", "--json"])

    assert fake.urls == ["https://www.kaufda.de/Angebote/Irische-Butter"]


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
