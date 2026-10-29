from __future__ import annotations

import json

import httpx
import pytest

from angebote_cli import cli

from conftest import read_fixture


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def run_json(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, dict]:
    code = cli.main(argv)
    output = capsys.readouterr().out
    lines = [line for line in output.splitlines() if line.strip()]
    assert len(lines) == 1
    return code, json.loads(lines[0])


def test_http_404_not_found(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse(404))
    code, data = run_json(capsys, ["suche", "Butter", "--json"])

    assert code == 3
    assert data["ok"] is False
    assert data["error"]["type"] == "not_found"


def test_http_500_network(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse(500))
    code, data = run_json(capsys, ["suche", "Butter", "--json"])

    assert code == 2
    assert data["error"]["type"] == "network"


def test_timeout_network(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def timeout(*args, **kwargs):
        raise httpx.TimeoutException("zu langsam")

    monkeypatch.setattr(httpx, "get", timeout)
    code, data = run_json(capsys, ["suche", "Butter", "--json"])

    assert code == 2
    assert data["error"]["type"] == "network"


def test_broken_html_parse(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *args, **kwargs: FakeResponse(200, "<html>kaputt</html>")
    )
    code, data = run_json(capsys, ["suche", "Butter", "--json"])

    assert code == 4
    assert data["error"]["type"] == "parse"


def test_invalid_timeout_is_usage_error(capsys) -> None:
    code, data = run_json(
        capsys, ["--timeout", "-1", "suche", "Butter", "--json"]
    )

    assert code == 1
    assert data["error"]["type"] == "usage"


def test_invalid_timeout_after_command(capsys) -> None:
    code, data = run_json(
        capsys, ["suche", "Butter", "--timeout", "0", "--json"]
    )

    assert code == 1
    assert data["error"]["type"] == "usage"


def test_invalid_max_price_is_json_usage_error(capsys) -> None:
    code, data = run_json(
        capsys, ["suche", "Butter", "--max-preis", "nan", "--json"]
    )

    assert code == 1
    assert data["error"]["type"] == "usage"


def test_unknown_command_is_json_usage_error(capsys) -> None:
    code, data = run_json(capsys, ["quatsch", "--json"])

    assert code == 1
    assert data["error"]["type"] == "usage"


def test_text_error_has_no_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: FakeResponse(404))
    code = cli.main(["suche", "Butter"])

    captured = capsys.readouterr()
    assert code == 3
    assert captured.out == ""
    assert "Fehler:" in captured.err


def test_version_exits_zero(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "angebote 0.1.0" in capsys.readouterr().out


def test_help_exits_zero(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out.lower()


def test_subcommand_help_exits_zero(capsys) -> None:
    for command in ("suche", "prospekte", "angebot", "watch"):
        with pytest.raises(SystemExit) as exc:
            cli.main([command, "--help"])
        assert exc.value.code == 0
        assert "usage:" in capsys.readouterr().out.lower()


def test_timeout_is_passed_to_client(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    captured: dict = {}

    class FakeClient:
        def __init__(self, timeout=15.0, rate_limit=1.0):
            captured["timeout"] = timeout

        def get(self, url: str) -> str:
            return read_fixture("angebote_butter.html")

    monkeypatch.setattr(cli, "KaufdaClient", FakeClient)
    code = cli.main(["suche", "Butter", "--timeout", "7", "--json"])

    assert code == 0
    assert captured["timeout"] == 7.0
