"""HTTP-Client für kaufDA mit Timeout, User-Agent und Rate-Limit."""

from __future__ import annotations

import time

import httpx

from . import __version__
from .errors import NetworkError, NotFoundError

USER_AGENT = (
    f"angebote-cli/{__version__} "
    "(+https://github.com/smlfg/angebote-cli)"
)


class KaufdaClient:
    def __init__(self, timeout: float = 15.0, rate_limit: float = 1.0):
        self.timeout = timeout
        self.rate_limit = rate_limit
        self._last_request = 0.0

    def _throttle(self) -> None:
        if self.rate_limit <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def get(self, url: str) -> str:
        self._throttle()
        try:
            response = httpx.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Zeitüberschreitung beim Abruf von {url}") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"Netzwerkfehler beim Abruf von {url}: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

        if response.status_code == 404:
            raise NotFoundError(f"Nicht gefunden: {url}")
        if response.status_code >= 400:
            raise NetworkError(
                f"HTTP {response.status_code} beim Abruf von {url}"
            )
        return response.text
