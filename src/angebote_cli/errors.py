"""Fehlerklassen mit festen Exit-Codes."""

from __future__ import annotations


class AngeboteError(Exception):
    exit_code = 1
    error_type = "usage"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UsageError(AngeboteError):
    exit_code = 1
    error_type = "usage"


class NetworkError(AngeboteError):
    exit_code = 2
    error_type = "network"


class NotFoundError(AngeboteError):
    exit_code = 3
    error_type = "not_found"


class ParseError(AngeboteError):
    exit_code = 4
    error_type = "parse"


class StateError(AngeboteError):
    exit_code = 1
    error_type = "state"
