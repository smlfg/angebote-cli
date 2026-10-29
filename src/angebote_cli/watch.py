"""Watch-State fuer beobachtete Angebote."""

from __future__ import annotations

import json
import os
from pathlib import Path

STATE_DIRNAME = "angebote-cli/watch.json"


class StateError(Exception):
    """Kaputte oder unlesbare State-Datei."""


def state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser(
        "~/.local/state"
    )
    return Path(base) / STATE_DIRNAME


def load_ids(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError, OSError) as exc:
        raise StateError(f"State-Datei {path} ist kaputt: {exc}") from exc
    ids = None
    if isinstance(data, dict):
        raw = data.get("ids")
        if isinstance(raw, dict):
            ids = {
                k: (v if isinstance(v, str) else "") for k, v in raw.items()
                if isinstance(k, str)
            }
    if ids is None:
        raise StateError(
            f"State-Datei {path} hat ein unerwartetes Format "
            "(erwartet: Objekt mit Feld 'ids')"
        )
    return ids


def save_ids(path: Path, ids: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps({"version": 1, "ids": ids}, ensure_ascii=False)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
    finally:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def first_seen_now() -> str:
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S+00:00")
    )
