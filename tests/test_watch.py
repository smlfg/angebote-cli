from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from angebote_cli import cli

from conftest import read_fixture


class FakeClient:
    def __init__(self, html: str):
        self.html = html
        self.calls = 0

    def get(self, url: str) -> str:
        self.calls += 1
        return self.html


def install_client(monkeypatch: pytest.MonkeyPatch, html: str) -> FakeClient:
    fake = FakeClient(html)

    def factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(cli, "KaufdaClient", factory)
    return fake


def test_watch_first_and_second_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    install_client(monkeypatch, read_fixture("angebote_butter.html"))
    state_file = tmp_path / "angebote-cli" / "watch.json"

    assert cli.main(["watch", "Butter", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["ok"] is True
    assert first["changed"] is True
    assert first["anzahl_neu"] >= 10
    assert state_file.exists()
    mode = stat.S_IMODE(state_file.stat().st_mode)
    assert mode == 0o600

    assert cli.main(["watch", "Butter", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["ok"] is True
    assert second["changed"] is False
    assert second["neu"] == []


def test_watch_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    install_client(monkeypatch, read_fixture("angebote_butter.html"))

    assert cli.main(
        ["watch", "Butter", "--max-preis", "1.5", "--haendler", "rewe", "--json"]
    ) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["neu"]
    for offer in data["neu"]:
        assert offer["preis"] is not None and offer["preis"] <= 1.5
        assert "rewe" in offer["haendler"].casefold()


def test_watch_corrupt_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    state_dir = tmp_path / "angebote-cli"
    state_dir.mkdir()
    (state_dir / "watch.json").write_text("{kaputt", encoding="utf-8")
    fake = install_client(monkeypatch, read_fixture("angebote_butter.html"))

    code = cli.main(["watch", "Butter", "--json"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert code == 1
    assert data["ok"] is False
    assert data["error"]["type"] == "state"
    assert fake.calls == 0


def test_watch_text_no_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    install_client(monkeypatch, read_fixture("angebote_butter.html"))

    assert cli.main(["watch", "Butter"]) == 0
    capsys.readouterr()
    assert cli.main(["watch", "Butter"]) == 0
    output = capsys.readouterr().out
    assert "Keine neuen Angebote." in output
