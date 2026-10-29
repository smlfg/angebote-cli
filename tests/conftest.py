from __future__ import annotations

from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("Echtes Netzwerk ist in Tests verboten")

    monkeypatch.setattr(httpx, "get", fail)
    monkeypatch.setattr(httpx.Client, "get", fail)


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
