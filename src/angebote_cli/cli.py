"""Kommandozeilen-Schnittstelle für angebote-cli."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="angebote",
        description="Aktuelle Prospekt-Angebote deutscher Händler über kaufDA.de.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"angebote {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
