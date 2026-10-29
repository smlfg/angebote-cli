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
    dealer_url,
    parse_brochures,
    parse_location,
    parse_offers,
    parse_page_information,
    search_url,
    slugify_keyword,
)
from .state import load_seen, save_seen, state_path


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


def _timeout(value: str) -> float:
    number = _finite_float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("--timeout muss positiv sein")
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
    parser.add_argument(
        "--timeout",
        type=_timeout,
        default=argparse.SUPPRESS,
        metavar="SEC",
        help="HTTP-Timeout in Sekunden (muss positiv sein)",
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
    suche.add_argument(
        "--timeout",
        type=_timeout,
        default=argparse.SUPPRESS,
        metavar="SEC",
        help="HTTP-Timeout in Sekunden (muss positiv sein)",
    )

    prospekte = subparsers.add_parser(
        "prospekte",
        help="Aktuelle Prospekte eines Händlers anzeigen",
        description="Zeigt die aktuellen Prospekte eines Händlers bei kaufDA.",
    )
    prospekte.add_argument("haendler", help="Händlername, z. B. REWE")
    prospekte.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    prospekte.add_argument(
        "--timeout",
        type=_timeout,
        default=argparse.SUPPRESS,
        metavar="SEC",
        help="HTTP-Timeout in Sekunden (muss positiv sein)",
    )

    angebot = subparsers.add_parser(
        "angebot",
        help="Details zu einem einzelnen Angebot anzeigen",
        description=(
            "Zeigt Details zu einer Angebots-ID. kaufDA hat keine eigene "
            "Detailseite, daher wird die Suchseite des Begriffs verwendet."
        ),
    )
    angebot.add_argument("offer_id", metavar="OFFER-ID", help="Angebots-ID")
    angebot.add_argument(
        "--begriff",
        metavar="B",
        help="Suchbegriff zum Auffinden des Angebots (erforderlich)",
    )
    angebot.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    angebot.add_argument(
        "--timeout",
        type=_timeout,
        default=argparse.SUPPRESS,
        metavar="SEC",
        help="HTTP-Timeout in Sekunden (muss positiv sein)",
    )

    watch = subparsers.add_parser(
        "watch",
        help="Neue Angebote zu einem Begriff beobachten",
        description=(
            "Speichert gesehene Angebots-IDs und meldet nur neue Treffer."
        ),
    )
    watch.add_argument("begriff", help="Suchbegriff, z. B. Butter")
    watch.add_argument(
        "--haendler",
        nargs="+",
        metavar="NAME",
        help="Nur Händler, deren Name den Text enthält (mehrere möglich)",
    )
    watch.add_argument(
        "--max-preis",
        type=_max_price,
        metavar="EUR",
        help="Nur Angebote bis zu diesem Preis",
    )
    watch.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    watch.add_argument(
        "--timeout",
        type=_timeout,
        default=argparse.SUPPRESS,
        metavar="SEC",
        help="HTTP-Timeout in Sekunden (muss positiv sein)",
    )
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


def _make_client(timeout: float | None) -> KaufdaClient:
    if timeout is None:
        return KaufdaClient()
    return KaufdaClient(timeout=timeout)


def _search_offers(
    begriff: str, timeout: float | None = None
) -> tuple[str, list[Offer], dict[str, Any]]:
    keyword = slugify_keyword(begriff)
    if not keyword:
        raise UsageError("Der Suchbegriff darf nicht leer sein.")
    client = _make_client(timeout)
    html = client.get(search_url(keyword))
    info = parse_page_information(html)
    offers = parse_offers(info, keyword)
    if not offers:
        raise NotFoundError(
            f"Keine Angebote für „{begriff}“ gefunden. "
            "Versuch es mit einem allgemeineren Begriff."
        )
    return keyword, offers, parse_location(info)


def _run_suche(args: argparse.Namespace) -> int:
    keyword, offers, location = _search_offers(
        args.begriff, getattr(args, "timeout", None)
    )
    offers = _filter_offers(
        offers,
        haendler=args.haendler,
        max_preis=args.max_preis,
        marke=args.marke,
        sort=args.sort,
        limit=args.limit,
    )
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


def _run_prospekte(args: argparse.Namespace) -> int:
    client = _make_client(getattr(args, "timeout", None))
    html = client.get(dealer_url(args.haendler))
    info = parse_page_information(html)
    brochures = parse_brochures(info, args.haendler)
    if not brochures:
        raise NotFoundError(
            f"Keine aktuellen Prospekte für „{args.haendler}“ gefunden."
        )
    location = parse_location(info)
    if args.json:
        payload = {
            "ok": True,
            "haendler": args.haendler,
            "location": location,
            "anzahl": len(brochures),
            "prospekte": [brochure.to_dict() for brochure in brochures],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        city = location.get("city")
        zip_code = location.get("zip")
        if city:
            suffix = f" ({zip_code})" if zip_code else ""
            print(f"Ort: {city}{suffix}")
        for brochure in brochures:
            valid_from = (brochure.gueltig_von or "")[:10] or "?"
            valid_until = (brochure.gueltig_bis or "")[:10] or "?"
            print(
                f"{brochure.titel}  {valid_from} bis {valid_until}  "
                f"id {brochure.id}  {brochure.url}"
            )
    return 0


def _run_angebot(args: argparse.Namespace) -> int:
    if not args.begriff:
        raise UsageError(
            "Für „angebot“ wird --begriff benötigt: kaufDA hat keine eigene "
            "Angebots-Detailseite, daher wird das Angebot über die Suche "
            "gefunden."
        )
    keyword = slugify_keyword(args.begriff)
    if not keyword:
        raise UsageError("Der Suchbegriff darf nicht leer sein.")
    client = _make_client(getattr(args, "timeout", None))
    html = client.get(search_url(keyword))
    info = parse_page_information(html)
    offers = parse_offers(info, keyword)
    offer = next((item for item in offers if item.id == args.offer_id), None)
    if offer is None:
        raise NotFoundError(
            f"Angebot {args.offer_id} wurde bei der Suche nach "
            f"„{args.begriff}“ nicht gefunden."
        )
    location = parse_location(info)
    if args.json:
        payload = {
            "ok": True,
            "location": location,
            "angebot": offer.to_dict(detailed=True),
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        city = location.get("city")
        zip_code = location.get("zip")
        if city:
            suffix = f" ({zip_code})" if zip_code else ""
            print(f"Ort: {city}{suffix}")
        print(offer.titel)
        if offer.beschreibung:
            print(f"Beschreibung: {offer.beschreibung}")
        print(f"Preis: {offer.preis_text or '—'}")
        print(f"Marke: {offer.marke or '—'}")
        print(f"Händler: {offer.haendler}")
        valid_from = (offer.gueltig_von or "")[:10] or "?"
        valid_until = (offer.gueltig_bis or "")[:10] or "?"
        print(f"Gültig: {valid_from} bis {valid_until}")
        page = offer.seite if offer.seite is not None else "?"
        print(f"Prospekt: {offer.prospekt_id or '?'} (Seite {page})")
        if offer.bild_url:
            print(f"Bild: {offer.bild_url}")
        print(f"URL: {offer.url}")
    return 0


def _run_watch(args: argparse.Namespace) -> int:
    path = state_path()
    seen = load_seen(path)
    keyword, offers, location = _search_offers(
        args.begriff, getattr(args, "timeout", None)
    )
    offers = _filter_offers(
        offers,
        haendler=args.haendler,
        max_preis=args.max_preis,
    )
    new_offers = [offer for offer in offers if offer.id not in seen]
    save_seen(path, seen | {offer.id for offer in new_offers})
    changed = bool(new_offers)
    if args.json:
        payload = {
            "ok": True,
            "begriff": args.begriff,
            "keyword": keyword,
            "location": location,
            "changed": changed,
            "anzahl_neu": len(new_offers),
            "anzahl_gesamt": len(offers),
            "neu": [offer.to_dict() for offer in new_offers],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        city = location.get("city")
        zip_code = location.get("zip")
        if city:
            suffix = f" ({zip_code})" if zip_code else ""
            print(f"Ort: {city}{suffix}")
        if not new_offers:
            print("Keine neuen Angebote.")
        else:
            _print_offers(new_offers, {})
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
        if args.command == "prospekte":
            return _run_prospekte(args)
        if args.command == "angebot":
            return _run_angebot(args)
        if args.command == "watch":
            return _run_watch(args)
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
