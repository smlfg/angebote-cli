"""Persistenter Watch-State mit restriktiven Dateirechten."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .errors import StateError


def state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".local" / "state"
    return root / "angebote-cli" / "watch.json"


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"State-Datei {path} ist beschädigt: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"State-Datei {path} hat ein unerwartetes Format.")
    seen = data.get("seen")
    if not isinstance(seen, list) or not all(isinstance(item, str) for item in seen):
        raise StateError(f"State-Datei {path} hat kein gültiges seen-Feld.")
    return set(seen)


def save_seen(path: Path, seen: set[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
        payload = {"version": 1, "seen": sorted(seen)}
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise StateError(f"State-Datei {path} konnte nicht geschrieben werden: {exc}") from exc
