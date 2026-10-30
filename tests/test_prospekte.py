from __future__ import annotations

import json
from datetime import datetime

import pytest

from angebote_cli import cli
from angebote_cli.errors import NotFoundError

from conftest import read_fixture


class FakeClient:
    def __init__(self, html: str):
        self.html = html
        self.urls: list[str] = []

    def get(self, url: str) -> str:
        self.urls.append(url)
        return self.html


class NotFoundOnceClient(FakeClient):
    def __init__(self, html: str, not_found_slug: str):
        super().__init__(html)
        self.not_found_slug = not_found_slug

    def get(self, url: str) -> str:
        self.urls.append(url)
        if url.endswith(f"/{self.not_found_slug}"):
            raise NotFoundError(f"Nicht gefunden: {url}")
        return self.html


def install_client(monkeypatch: pytest.MonkeyPatch, html: str) -> FakeClient:
    fake = FakeClient(html)

    def factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(cli, "KaufdaClient", factory)
    return fake


def install_fake(
    monkeypatch: pytest.MonkeyPatch, fake: FakeClient
) -> FakeClient:
    def factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(cli, "KaufdaClient", factory)
    return fake


def test_prospekte_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    fake = install_client(monkeypatch, read_fixture("geschaeft_rewe.html"))
    code = cli.main(["prospekte", "REWE", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["ok"] is True
    assert data["anzahl"] >= 1
    assert len(data["prospekte"]) == data["anzahl"]
    assert fake.urls == ["https://www.kaufda.de/Geschaefte/REWE"]
    for brochure in data["prospekte"]:
        assert brochure["titel"]
        assert brochure["id"]
        assert brochure["url"].startswith("https://www.kaufda.de/Geschaefte/REWE")
        datetime.fromisoformat(brochure["gueltig_von"])
        datetime.fromisoformat(brochure["gueltig_bis"])


def test_prospekte_haendler_case_insensitiv(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fake = install_client(monkeypatch, read_fixture("geschaeft_rewe.html"))
    code = cli.main(["prospekte", "rewe", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["ok"] is True
    assert data["anzahl"] >= 1
    assert fake.urls == ["https://www.kaufda.de/Geschaefte/REWE"]


def test_prospekte_fallback_bei_404(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fake = NotFoundOnceClient(
        read_fixture("geschaeft_rewe.html"), "Test-Markt"
    )
    install_fake(monkeypatch, fake)
    code = cli.main(["prospekte", "Test-Markt", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 0
    assert data["ok"] is True
    assert fake.urls == [
        "https://www.kaufda.de/Geschaefte/Test-Markt",
        "https://www.kaufda.de/Geschaefte/TEST-MARKT",
    ]


def test_prospekte_ort_uses_city_url(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fake = install_client(monkeypatch, read_fixture("geschaeft_rewe.html"))
    code = cli.main(["--ort", "Heilbronn", "prospekte", "REWE", "--json"])

    assert code == 0
    assert fake.urls == ["https://www.kaufda.de/Heilbronn/Geschaefte/REWE"]
    capsys.readouterr()


def test_prospekte_text(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    install_client(monkeypatch, read_fixture("geschaeft_rewe.html"))
    code = cli.main(["prospekte", "REWE"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Ort: Stuttgart (70174)" in captured.out
    assert "Dein Markt" in captured.out
