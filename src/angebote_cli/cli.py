"""angebote-cli: Prospekt-Angebote deutscher Händler über kaufDA.de."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="angebote",
        description="Aktuelle Prospekt-Angebote deutscher Händler über kaufDA.de (inoffiziell).",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_subparsers(dest="command")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
