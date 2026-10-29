"""HTTP-Client (httpx) mit Timeout, Rate-Limit, ehrlichem User-Agent."""

from __future__ import annotations

import time

import httpx

from .errors import NetworkError, NotFoundError
from . import __version__

USER_AGENT = (
    f"angebote-cli/{__version__} (https://github.com/smlfg/angebote-cli; "
    "inoffiziell, kaufDA.de)"
)

_MIN_INTERVAL = 1.0  # max. 1 Request/Sekunde
_last_request = 0.0


def fetch_html(url: str, timeout: float = 15.0) -> str:
    global _last_request
    wait = max(0.0, _MIN_INTERVAL - (time.monotonic() - _last_request))
    if wait:
        time.sleep(wait)
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"user-agent": USER_AGENT, "accept-language": "de-DE,de;q=0.9"},
            follow_redirects=True,
        ) as c:
            resp = c.get(url)
    except httpx.TimeoutException as exc:
        raise NetworkError(f"Zeitueberschreitung bei {url}") from exc
    except httpx.HTTPError as exc:
        raise NetworkError(f"Netzwerkfehler bei {url}: {exc}") from exc
    _last_request = time.monotonic()
    if resp.status_code == 404:
        raise NotFoundError(f"Seite nicht gefunden (404): {url}")
    if resp.status_code >= 400:
        raise NetworkError(f"HTTP {resp.status_code} bei {url}")
    return resp.text
