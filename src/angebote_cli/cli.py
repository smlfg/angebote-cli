"""Kommandozeilen-Schnittstelle für angebote-cli."""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any, Sequence

from . import __version__
from .client import KaufdaClient
from .errors import AngeboteError, NotFoundError, UsageError
from .parser import (
    Offer,
    parse_location,
    parse_offers,
    parse_page_information,
    search_url,
    slugify_keyword,
)


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


def _finite_float(value: str) -> float:
    try:
        number = float(value.replace(",", "."))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"ungültige Zahl: {value}") from exc
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError(f"ungültige Zahl: {value}")
    return number


def _max_price(value: str) -> float:
    number = _finite_float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("--max-preis muss >= 0 sein")
    return number


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"ungültige Ganzzahl: {value}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("Wert muss positiv sein")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = ArgumentParser(
        prog="angebote",
        description="Aktuelle Prospekt-Angebote deutscher Händler über kaufDA.de.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"angebote {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    suche = subparsers.add_parser(
        "suche",
        help="Angebote zu einem Begriff suchen",
        description="Sucht aktuelle Angebote zu einem Begriff bei kaufDA.",
    )
    suche.add_argument("begriff", help="Suchbegriff, z. B. Butter")
    suche.add_argument(
        "--haendler",
        nargs="+",
        metavar="NAME",
        help="Nur Händler, deren Name den Text enthält (mehrere möglich)",
    )
    suche.add_argument(
        "--max-preis",
        type=_max_price,
        metavar="EUR",
        help="Nur Angebote bis zu diesem Preis",
    )
    suche.add_argument("--marke", metavar="NAME", help="Nur diese Marke")
    suche.add_argument(
        "--sort",
        choices=("preis", "rabatt"),
        help="Sortierung: preis aufsteigend, rabatt absteigend",
    )
    suche.add_argument(
        "--limit",
        type=_positive_int,
        metavar="N",
        help="Maximale Anzahl Treffer",
    )
    suche.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    return parser


def _filter_offers(
    offers: list[Offer],
    haendler: list[str] | None = None,
    max_preis: float | None = None,
    marke: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
) -> list[Offer]:
    result = list(offers)
    if haendler:
        needles = [value.casefold() for value in haendler if value.strip()]
        if needles:
            result = [
                offer
                for offer in result
                if any(needle in offer.haendler.casefold() for needle in needles)
            ]
    if max_preis is not None:
        result = [
            offer
            for offer in result
            if offer.preis is not None and offer.preis <= max_preis
        ]
    if marke:
        needle = marke.casefold()
        result = [
            offer
            for offer in result
            if offer.marke is not None and needle in offer.marke.casefold()
        ]
    if sort == "preis":
        result.sort(
            key=lambda offer: (
                offer.preis is None,
                offer.preis if offer.preis is not None else float("inf"),
            )
        )
    elif sort == "rabatt":
        result.sort(
            key=lambda offer: (
                offer.rabatt is None,
                -(offer.rabatt or 0.0),
            )
        )
    if limit is not None:
        result = result[:limit]
    return result


def _format_valid_until(offer: Offer) -> str:
    if not offer.gueltig_bis:
        return "unbekannt"
    return offer.gueltig_bis[:10]


def _print_offers(offers: list[Offer], location: dict[str, Any]) -> None:
    city = location.get("city")
    zip_code = location.get("zip")
    if city:
        suffix = f" ({zip_code})" if zip_code else ""
        print(f"Ort: {city}{suffix}")
    if not offers:
        print("Keine Angebote gefunden.")
        return
    for offer in offers:
        price = offer.preis_text or "—"
        brand = offer.marke or "—"
        print(
            f"{price}  {offer.titel}  {brand}  {offer.haendler}  "
            f"gültig bis {_format_valid_until(offer)}"
        )


def _run_suche(args: argparse.Namespace) -> int:
    keyword = slugify_keyword(args.begriff)
    if not keyword:
        raise UsageError("Der Suchbegriff darf nicht leer sein.")
    client = KaufdaClient()
    html = client.get(search_url(keyword))
    info = parse_page_information(html)
    offers = parse_offers(info, keyword)
    if not offers:
        raise NotFoundError(
            f"Keine Angebote für „{args.begriff}“ gefunden. "
            "Versuch es mit einem allgemeineren Begriff."
        )
    offers = _filter_offers(
        offers,
        haendler=args.haendler,
        max_preis=args.max_preis,
        marke=args.marke,
        sort=args.sort,
        limit=args.limit,
    )
    location = parse_location(info)
    if args.json:
        payload = {
            "ok": True,
            "begriff": args.begriff,
            "keyword": keyword,
            "location": location,
            "anzahl": len(offers),
            "angebote": [offer.to_dict() for offer in offers],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        _print_offers(offers, location)
    return 0


def _emit_error(error: AngeboteError, json_mode: bool) -> int:
    if json_mode:
        payload = {
            "ok": False,
            "error": {
                "type": error.error_type,
                "message": error.message,
            },
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Fehler: {error.message}", file=sys.stderr)
    return error.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in arguments
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
        if args.command == "suche":
            return _run_suche(args)
        parser.print_help()
        return 0
    except AngeboteError as error:
        return _emit_error(error, json_mode)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        fallback = AngeboteError(f"Unerwarteter Fehler: {exc}")
        return _emit_error(fallback, json_mode)


if __name__ == "__main__":
    sys.exit(main())
