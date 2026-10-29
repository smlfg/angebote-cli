"""CLI: angebote — Befehle fuer kaufDA-Angebote."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from . import __version__, client, outputs, parser as kd
from .errors import (
    EXIT_OK,
    CliError,
    NotFoundError,
    UsageError,
)

# --- Parser ------------------------------------------------------------


class JsonArgParser(argparse.ArgumentParser):
    """Usage-Fehler werden nicht sofort ausgegeben, sondern gewrappt."""

    def error(self, message: str):
        raise UsageError(message)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="JSON-Ausgabe")


def build_parser() -> argparse.ArgumentParser:
    ap = JsonArgParser(
        prog="angebote",
        description=(
            "Aktuelle Prospekt-Angebote deutscher Haendler ueber kaufDA.de "
            "(inoffizieller Client)."
        ),
    )
    ap.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_suche = sub.add_parser(
        "suche", help="Angebote zu einem Begriff suchen"
    )
    _add_common(p_suche)
    p_suche.add_argument("begriff", help="Suchbegriff")
    p_suche.add_argument(
        "--haendler", nargs="+", default=None, metavar="NAME",
        help="Haendler-Filter (case-insensitive Teilstring), mehrfach moeglich",
    )
    p_suche.add_argument(
        "--max-preis", type=float, default=None, metavar="EUR",
        help="nur Angebote mit Preis <= EUR (ohne Preis ausgeschlossen)",
    )
    p_suche.add_argument(
        "--marke", default=None, metavar="NAME",
        help="Marken-Filter (case-insensitive Teilstring)",
    )
    p_suche.add_argument(
        "--sort", choices=("preis", "rabatt"), default=None,
        help="Sortierung (aufsteigend nach Preis bzw. absteigend nach Rabatt)",
    )
    p_suche.add_argument(
        "--limit", type=int, default=None, metavar="N", help="max. Treffer"
    )
    p_suche.set_defaults(func=cmd_suche)

    p_ang = sub.add_parser("angebot", help="Details zu einem Angebot per offer-id")
    _add_common(p_ang)
    p_ang.add_argument("offer_id", help="Angebots-ID (aus 'suche', z.B. UUID)")
    p_ang.add_argument(
        "--begriff",
        help="Suchbegriff, ueber dessen Suchseite das Angebot gefunden wird "
        "(Pflicht, da kaufDA keine eigene Angebots-Detailseite hat)",
    )
    p_ang.set_defaults(func=cmd_angebot)

    p_pros = sub.add_parser(
        "prospekte", help="aktuelle Prospekte eines Haendlers"
    )
    _add_common(p_pros)
    p_pros.add_argument("haendler", help="Haendlername (z.B. REWE, Lidl)")
    p_pros.set_defaults(func=cmd_prospekte)
    return ap


# --- URL-Hilfen --------------------------------------------------------


def _haendler_slugs(name: str) -> list[str]:
    """Kandidaten-Slugs fuer /Geschaefte/<Haendler> (kaufDA ist case-sensitive)."""
    seen, out = set(), []
    for cand in (
        kd.slugify(name),
        name.strip().replace(" ", "-").upper(),
        name.strip().replace(" ", "-"),
    ):
        if cand and cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


# --- Filter ------------------------------------------------------------


def _apply_filters(hits: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    out = []
    haendler = [h.lower() for h in args.haendler] if args.haendler else None
    marke = args.marke.lower() if args.marke else None
    for hit in hits:
        if haendler:
            name = (hit.get("haendler") or "").lower()
            if not any(name.find(h) != -1 for h in haendler):
                continue
        if marke:
            brand = (hit.get("marke") or "").lower()
            if marke not in brand:
                continue
        if args.max_preis is not None:
            if hit.get("preis") is None or hit["preis"] > args.max_preis:
                continue
        out.append(hit)
    return out


def _sort_hits(hits: list[dict[str, Any]], mode: str | None) -> list[dict[str, Any]]:
    if mode == "preis":
        return sorted(
            hits,
            key=lambda h: h.get("preis") if h.get("preis") is not None else float("inf"),
        )
    if mode == "rabatt":
        return sorted(
            hits,
            key=lambda h: (h.get("rabatt") or 0.0),
            reverse=True,
        )
    return hits


# --- Befehle -----------------------------------------------------------


def cmd_suche(args: argparse.Namespace) -> int:
    slug = kd.slugify(args.begriff)
    if not slug:
        raise UsageError(f"Nicht-verwendbarer Suchbegriff: {args.begriff!r}")
    html = client.fetch_html(f"{kd.BASE_URL}/Angebote/{slug}")
    pi = kd.extract_page_information(html)
    hits = kd.parse_offers(pi)
    hits = _apply_filters(hits, args)
    hits = _sort_hits(hits, args.sort)
    if args.limit is not None:
        if args.limit < 0:
            raise UsageError("--limit muss >= 0 sein")
        hits = hits[: args.limit]
    ort = kd.parse_location(pi)
    if not hits:
        raise NotFoundError(
            f"Keine Treffer fuer {args.begriff!r}. Tipp: Schreibweise pruefen, "
            "Filters lockern, auch Synonyme nutzen (z.B. 'Milch' statt 'Vollmilch')."
        )
    treffer = [_public_hit(h) for h in hits]
    payload = {"ok": True, "begriff": args.begriff, "ort": ort, "anzahl": len(treffer), "treffer": treffer}
    if args.json:
        outputs.print_json(payload)
    else:
        print(f"Ort: {ort.get('city') or '?'} {ort.get('zip') or ''}".strip())
        for t in treffer:
            print(outputs.hit_line(t))
    return EXIT_OK


def cmd_prospekte(args: argparse.Namespace) -> int:
    name = args.haendler
    last_error: NotFoundError | None = None
    html = None
    slug_used = None
    for slug in _haendler_slugs(name):
        url = f"{kd.BASE_URL}/Geschaefte/{slug}"
        try:
            html = client.fetch_html(url)
            slug_used = slug
            break
        except NotFoundError as exc:
            last_error = exc
            continue
    if html is None:
        raise NotFoundError(
            f"Kein Haendler {name!r} gefunden. Probierte URLs: "
            + ", ".join(f"/Geschaefte/{s}" for s in _haendler_slugs(name))
            + f". ({last_error})"
        )
    pi = kd.extract_page_information(html)
    bros = kd.parse_brochures(pi, "publisher")
    if not bros:
        bros = kd.parse_brochures(pi, "keyword")
    if not bros:
        bros = kd.parse_brochures(pi)
    bros = [_public_brochure(b) for b in bros]
    ort = kd.parse_location(pi)
    page_url = kd.pi_url(pi)
    payload = {
        "ok": True,
        "haendler": name,
        "url": page_url,
        "ort": ort,
        "anzahl": len(bros),
        "prospekte": bros,
    }
    if args.json:
        outputs.print_json(payload)
    else:
        print(f"Ort: {ort.get('city') or '?'} {ort.get('zip') or ''}".strip())
        for b in bros:
            print(outputs.brochure_line(b))
    return EXIT_OK


def _public_brochure(b: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "titel", "haendler", "content_id", "gueltig_von", "gueltig_bis", "seiten", "url")
    return {k: b.get(k) for k in keys}


def cmd_angebot(args: argparse.Namespace) -> int:
    if not args.begriff:
        raise UsageError(
            "kaufDA hat keine eigene Angebots-Detailseite; das Angebot wird "
            "ueber die Suchseite gefunden. Bitte --begriff B angeben "
            "(z.B. den Begriff, den du bei 'suche' genutzt hast)."
        )
    slug = kd.slugify(args.begriff)
    if not slug:
        raise UsageError(f"Nicht-verwendbarer Suchbegriff: {args.begriff!r}")
    html = client.fetch_html(f"{kd.BASE_URL}/Angebote/{slug}")
    pi = kd.extract_page_information(html)
    ort = kd.parse_location(pi)
    angebot = None
    for hit in kd.parse_offers(pi):
        if str(hit.get("id")) == str(args.offer_id):
            angebot = hit
            break
    if angebot is None:
        raise NotFoundError(
            f"Angebots-ID {args.offer_id} auf der Suchseite fuer "
            f"{args.begriff!r} nicht gefunden. Angebote wechseln "
            "woechentlich: nutze den aktuellen Wert aus 'angebote suche' und "
            "den Begriff, mit dem das Angebot dort gelistet wurde."
        )
    public = _public_hit(angebot)
    public["beschreibung"] = angebot.get("beschreibung")
    payload = {"ok": True, "ort": ort, "angebot": public}
    if args.json:
        outputs.print_json(payload)
        return EXIT_OK
    print(f"Ort: {ort.get('city') or '?'} {ort.get('zip') or ''}".strip())
    prospekt_parts = []
    if public.get("prospekt_id"):
        prospekt_parts.append(f"id {public['prospekt_id']}")
    if public.get("seite"):
        prospekt_parts.append(f"Seite {public['seite']}")
    lines = [
        f"Titel: {public.get('titel')}",
        f"Beschreibung: {public.get('beschreibung') or '?'}",
        f"Marke: {public.get('marke') or '?'}",
        f"Preis: {outputs.fmt_price(public.get('preis'), public.get('preis_text'))}",
        f"Haendler: {public.get('haendler') or '?'}",
        f"Gueltig: {outputs.fmt_date(public.get('gueltig_von'))} bis "
        f"{outputs.fmt_date(public.get('gueltig_bis'))}",
        f"Prospekt: {', '.join(prospekt_parts) if prospekt_parts else '?'}",
        f"Bild: {public.get('bild') or '?'}",
        f"URL: {public.get('url')}",
    ]
    for line in lines:
        print(line)
    return EXIT_OK


def _public_hit(hit: dict[str, Any]) -> dict[str, Any]:
    required = (
        "id", "titel", "marke", "haendler", "preis", "preis_text",
        "grundpreis", "gueltig_von", "gueltig_bis", "prospekt_id",
        "seite", "url",
    )
    optional = ("statt_preis", "rabatt", "bild", "beschreibung")
    out = {k: hit.get(k) for k in required}
    out.update({k: hit[k] for k in optional if hit.get(k) is not None})
    return out


# --- Einstieg ----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_flag = "--json" in argv
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
        return args.func(args)
    except CliError as exc:
        if json_flag:
            outputs.print_json(outputs.error_json(exc.type, exc.message))
        else:
            print(f"Fehler: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except kd.ParseError as exc:
        message = f"Seitenstruktur geaendert, Parsing fehlgeschlagen: {exc}"
        if json_flag:
            outputs.print_json(outputs.error_json("parse", message))
        else:
            print(f"Fehler: {message}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:  # pragma: no cover
        print("Abgebrochen.", file=sys.stderr)
        return 130
