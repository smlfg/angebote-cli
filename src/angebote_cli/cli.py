"""Kommandozeilen-Schnittstelle für angebote-cli."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from typing import Any, Sequence

from . import __version__
from .client import KaufdaClient
from .errors import AngeboteError, NotFoundError, UsageError
from .parser import (
    Offer,
    dealer_slug_candidates,
    dealer_url,
    parse_brochures,
    parse_location,
    parse_offers,
    parse_page_information,
    parse_search_api_offers,
    search_api_url,
    search_url,
    slugify_city,
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


def _page_count(value: str) -> int:
    number = _positive_int(value)
    if number > 10:
        raise argparse.ArgumentTypeError("--seiten darf höchstens 10 sein")
    return number


def _zip_code(value: str) -> str:
    text = value.strip()
    if not re.fullmatch(r"\d{5}", text):
        raise argparse.ArgumentTypeError("--plz muss eine fünfstellige PLZ sein")
    return text


def _add_location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ort",
        metavar="STADT",
        default=argparse.SUPPRESS,
        help="Ort über Stadtnamen setzen, z. B. Heilbronn (kaufDA-Stadt-URL)",
    )
    parser.add_argument(
        "--plz",
        type=_zip_code,
        metavar="PLZ",
        default=argparse.SUPPRESS,
        help="Ort über fünfstellige PLZ setzen (Auflösung via zippopotam.us)",
    )


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
    _add_location_args(parser)
    subparsers = parser.add_subparsers(dest="command")

    suche = subparsers.add_parser(
        "suche",
        help="Angebote zu einem Begriff suchen",
        description="Sucht aktuelle Angebote zu einem Begriff bei kaufDA.",
    )
    _add_location_args(suche)
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
    suche.add_argument(
        "--seiten",
        type=_page_count,
        default=3,
        metavar="N",
        help="Maximale Anzahl Ergebnisseiten (1-10, Standard 3)",
    )
    suche.add_argument(
        "--alle",
        action="store_true",
        help="Dubletten aus regionalen Prospekten nicht zusammenfassen",
    )
    suche.add_argument(
        "--locker",
        action="store_true",
        help="Relevanzfilter ausschalten (alle kaufDA-Treffer behalten)",
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
    _add_location_args(prospekte)
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
    _add_location_args(angebot)
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
    _add_location_args(watch)
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
    watch.add_argument(
        "--locker",
        action="store_true",
        help="Relevanzfilter ausschalten (alle kaufDA-Treffer behalten)",
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


_UMLAUTS = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
)


def _normalize_text(value: str) -> str:
    return value.casefold().translate(_UMLAUTS)


def _contains_word(haystack: str, word: str) -> bool:
    pattern = rf"(?<![0-9a-z]){re.escape(word)}(?![0-9a-z])"
    return re.search(pattern, haystack) is not None


def _filter_relevant(
    offers: list[Offer], begriff: str
) -> tuple[list[Offer], int]:
    words = [
        _normalize_text(word)
        for word in " ".join(begriff.split()).split(" ")
        if word
    ]
    if not words:
        return list(offers), 0
    kept: list[Offer] = []
    dropped = 0
    for offer in offers:
        haystack = _normalize_text(
            " ".join(
                [
                    offer.titel,
                    offer.beschreibung or "",
                    offer.marke or "",
                    " ".join(offer.kategorien),
                ]
            )
        )
        if all(_contains_word(haystack, word) for word in words):
            kept.append(offer)
        else:
            dropped += 1
    return kept, dropped


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


def _dedupe_offers(offers: list[Offer]) -> list[Offer]:
    result: list[Offer] = []
    seen: dict[tuple[Any, ...], Offer] = {}
    for offer in offers:
        key = (
            offer.titel.casefold().strip(),
            (offer.marke or "").casefold().strip(),
            offer.haendler.casefold().strip(),
            offer.preis,
            offer.gueltig_bis,
        )
        first = seen.get(key)
        if first is None:
            seen[key] = offer
            result.append(offer)
            continue
        if offer.id != first.id and offer.id not in first.weitere_ids:
            first.weitere_ids.append(offer.id)
            first.anzahl_prospekte += 1
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


def _fetch_api_page(
    client: Any,
    keyword: str,
    location: dict[str, Any],
    offset: int,
) -> list[Offer]:
    url = search_api_url(
        keyword.replace("-", " "),
        location.get("lat"),
        location.get("lng"),
        offset=offset,
    )
    try:
        text = client.get(url)
    except NotFoundError:
        return []
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    return parse_search_api_offers(payload, keyword)


def _resolve_zip_city(plz: str, client: Any) -> str:
    url = f"https://api.zippopotam.us/de/{plz}"
    try:
        text = client.get(url)
    except NotFoundError as exc:
        raise UsageError(f"Zur PLZ {plz} wurde kein Ort gefunden.") from exc
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise UsageError(
            f"Die PLZ {plz} konnte nicht aufgelöst werden. "
            "Nutze stattdessen --ort."
        ) from exc
    places = payload.get("places") if isinstance(payload, dict) else None
    if not isinstance(places, list) or not places:
        raise UsageError(
            f"Zur PLZ {plz} wurde kein Ort gefunden. "
            "Nutze stattdessen --ort."
        )
    first = places[0]
    city = first.get("place name") if isinstance(first, dict) else None
    if not isinstance(city, str) or not city.strip():
        raise UsageError(
            f"Zur PLZ {plz} wurde kein Ortsname geliefert. "
            "Nutze stattdessen --ort."
        )
    return city.strip()


def _location_city_slug(
    ort: str | None, plz: str | None, client: Any
) -> str | None:
    if ort:
        return slugify_city(ort)
    if plz:
        return slugify_city(_resolve_zip_city(plz, client))
    return None


def _search_offers(
    begriff: str,
    timeout: float | None = None,
    seiten: int = 3,
    ort: str | None = None,
    plz: str | None = None,
) -> tuple[str, list[Offer], dict[str, Any]]:
    keyword = slugify_keyword(begriff)
    if not keyword:
        raise UsageError("Der Suchbegriff darf nicht leer sein.")
    client = _make_client(timeout)
    city_slug = _location_city_slug(ort, plz, client)
    offers: list[Offer] = []
    seen_ids: set[str] = set()
    location: dict[str, Any] = {}
    use_api = False
    for page in range(1, seiten + 1):
        if use_api:
            page_offers = _fetch_api_page(
                client, keyword, location, len(offers)
            )
        else:
            try:
                html = client.get(search_url(keyword, city_slug, page=page))
            except NotFoundError:
                if page == 1:
                    raise
                break
            info = parse_page_information(html)
            if page == 1:
                location = parse_location(info)
            page_offers = parse_offers(info, keyword, city_slug)
            if page > 1 and page_offers:
                new_ids = {
                    offer.id for offer in page_offers
                    if offer.id not in seen_ids
                }
                if not new_ids:
                    use_api = True
                    page_offers = _fetch_api_page(
                        client, keyword, location, len(offers)
                    )
        if not page_offers:
            break
        added = False
        for offer in page_offers:
            if offer.id in seen_ids:
                continue
            seen_ids.add(offer.id)
            offers.append(offer)
            added = True
        if use_api and not added:
            break
    if not offers:
        raise NotFoundError(
            f"Keine Angebote für „{begriff}“ gefunden. "
            "Versuch es mit einem allgemeineren Begriff."
        )
    return keyword, offers, location


def _run_suche(args: argparse.Namespace) -> int:
    keyword, offers, location = _search_offers(
        args.begriff,
        getattr(args, "timeout", None),
        getattr(args, "seiten", 3),
        getattr(args, "ort", None),
        getattr(args, "plz", None),
    )
    verworfen_irrelevant = 0
    if not getattr(args, "locker", False):
        offers, verworfen_irrelevant = _filter_relevant(offers, args.begriff)
    offers = _filter_offers(
        offers,
        haendler=args.haendler,
        max_preis=args.max_preis,
        marke=args.marke,
        sort=args.sort,
    )
    if not args.alle:
        offers = _dedupe_offers(offers)
    if args.limit is not None:
        offers = offers[: args.limit]
    if args.json:
        payload = {
            "ok": True,
            "begriff": args.begriff,
            "keyword": keyword,
            "location": location,
            "anzahl": len(offers),
            "verworfen_irrelevant": verworfen_irrelevant,
            "angebote": [offer.to_dict() for offer in offers],
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        _print_offers(offers, location)
    return 0


def _run_prospekte(args: argparse.Namespace) -> int:
    client = _make_client(getattr(args, "timeout", None))
    city_slug = _location_city_slug(
        getattr(args, "ort", None),
        getattr(args, "plz", None),
        client,
    )
    info: dict[str, Any] | None = None
    brochures = []
    last_error: NotFoundError | None = None
    for dealer_slug in dealer_slug_candidates(args.haendler):
        try:
            html = client.get(dealer_url(dealer_slug, city_slug))
        except NotFoundError as exc:
            last_error = exc
            continue
        info = parse_page_information(html)
        brochures = parse_brochures(info, dealer_slug)
        break
    if info is None:
        if last_error is not None:
            raise last_error
        raise NotFoundError(
            f"Keine aktuellen Prospekte für „{args.haendler}“ gefunden."
        )
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
    city_slug = _location_city_slug(
        getattr(args, "ort", None),
        getattr(args, "plz", None),
        client,
    )
    html = client.get(search_url(keyword, city_slug))
    info = parse_page_information(html)
    offers = parse_offers(info, keyword, city_slug)
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
        args.begriff,
        getattr(args, "timeout", None),
        ort=getattr(args, "ort", None),
        plz=getattr(args, "plz", None),
    )
    verworfen_irrelevant = 0
    if not getattr(args, "locker", False):
        offers, verworfen_irrelevant = _filter_relevant(offers, args.begriff)
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
            "verworfen_irrelevant": verworfen_irrelevant,
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
