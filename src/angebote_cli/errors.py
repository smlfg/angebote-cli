"""Fehlerklassen -> Exit-Codes."""

from __future__ import annotations

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NETWORK = 2
EXIT_NOT_FOUND = 3
EXIT_PARSE = 4


class CliError(Exception):
    """Basisklasse mit exit_code und error-type."""

    exit_code = 1
    type = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UsageError(CliError):
    exit_code = EXIT_USAGE
    type = "usage"


class NetworkError(CliError):
    exit_code = EXIT_NETWORK
    type = "network"


class NotFoundError(CliError):
    exit_code = EXIT_NOT_FOUND
    type = "not_found"


