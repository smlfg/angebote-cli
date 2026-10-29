import json
import os
import pathlib
import stat

import pytest

import angebote_cli.cli as cli
import angebote_cli.client as client_mod
import angebote_cli.watch as watch_mod
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


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path / "angebote-cli" / "watch.json"


def run(argv):
    return cli.main(argv)


def out(capsys):
    return capsys.readouterr().out


def single_json(text):
    return json.loads(text.strip().splitlines()[0])


def test_watch_first_run_new_hits(no_net, state_dir, capsys):
    assert run(["watch", "butter", "--json"]) == 0
    data = single_json(out(capsys))
    assert data["ok"] is True
    assert data["changed"] is True
    assert data["anzahl_neu"] >= 10
    assert state_dir.exists()
    mode = stat.S_IMODE(os.stat(state_dir).st_mode)
    assert mode == 0o600
    state = json.loads(state_dir.read_text())
    assert state["version"] == 1
    assert len(state["ids"]) == data["anzahl_neu"]


def test_watch_second_run_no_change(no_net, state_dir, capsys):
    run(["watch", "butter", "--json"])
    capsys.readouterr()
    assert run(["watch", "butter", "--json"]) == 0
    data = single_json(out(capsys))
    assert data["changed"] is False
    assert data["anzahl_neu"] == 0
    assert data["neu"] == []


def test_watch_broken_state_file(no_net, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path = tmp_path / "angebote-cli" / "watch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{kein json", encoding="utf-8")
    assert run(["watch", "butter", "--json"]) == 1
    data = single_json(out(capsys))
    assert data["ok"] is False
    assert data["error"]["type"] == "state"
    assert "kaputt" in data["error"]["message"].lower()


def test_watch_wrong_state_format(no_net, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    path = tmp_path / "angebote-cli" / "watch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert run(["watch", "butter", "--json"]) == 1
    data = single_json(out(capsys))
    assert data["error"]["type"] == "state"


def test_watch_filters(no_net, state_dir, capsys):
    assert run(["watch", "butter", "--haendler", "rewe", "--max-preis", "1.5", "--json"]) == 0
    data = single_json(out(capsys))
    for h in data["neu"]:
        assert "rewe" in (h["haendler"] or "").lower()
        assert h["preis"] <= 1.5


def test_watch_text(no_net, state_dir, capsys):
    assert run(["watch", "butter"]) == 0
    text = out(capsys)
    assert "Neue Treffer" in text
    capsys.readouterr()
    assert run(["watch", "butter"]) == 0
    assert "keine neuen Treffer" in out(capsys)


def test_state_path_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = watch_mod.state_path()
    assert str(p).endswith(".local/state/angebote-cli/watch.json")
