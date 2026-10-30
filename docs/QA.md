# QA – angebote-cli

Stand: 2026-10-30 · Version 0.1.0 (main) · frisches venv, `pip install git+https://github.com/smlfg/angebote-cli` · alle Aufrufe live gegen kaufDA, Ausgaben semantisch per Skript geprüft (jeder Treffer gegen Suchwort/Filter, Preise, Gültigkeit, Exit-Codes, genau ein JSON-Objekt, kein Traceback).

## Verlauf

| Runde | Ergebnis | Befunde | Fix (Commit) |
|---|---|---|---|
| 1 | 3 Bugs | `prospekte rewe` (klein) → Exit 3; einzelne Treffer ohne Gültigkeit; Watch-State-Pfad undokumentiert | 45926ef, ae42483, 0873d85 |
| 2 | 34/34 OK | Orchestrator-Stichprobe: Relevanzfilter verwarf 47 von 59 Kaffee-Treffern (z. B. Jacobs Krönung, „Bohnenkaffee“) | a053d0d |
| 3 | **40/40 OK** | keine Bugs | – |

## Runde 3 (final)

| # | Aufruf | Erwartung | Ergebnis | OK/FEHLER |
|---|--------|-----------|----------|-----------|
| A1a | `angebote --version` | Exit 0, Versionsnummer | Exit 0, `angebote 0.1.0` | OK |
| A1b | `angebote --help` | Exit 0, Usage + Optionen | Exit 0, Usage und Unterbefehle vorhanden | OK |
| A2 | `angebote suche butter --json` | Preis 0.1–50; Gültigkeit vorhanden, Ende >= Start; Butter-Bezug oder keine `beschreibung`+`kategorien` | Exit 0, `anzahl`=26; Preise 26/26 plausibel; Gültigkeit 26/26 plausibel; 24/26 mit Butter-Bezug, 2 ohne Beschreibung/Kategorien (neu erlaubt) | OK |
| A3 | `angebote suche kaffee --haendler lidl rewe --json` | Exit 0; nur Händler mit „lidl“ oder „rewe“ | Exit 0, `anzahl`=4, Händler `REWE`, `REWE`, `Lidl`, `Lidl`; 0 Verstöße | OK |
| A4 | `angebote suche butter --max-preis 2 --sort preis --json` | Kein Preis >2 oder fehlend; aufsteigend | Exit 0, `anzahl`=16; Preise 0.88–1.99, alle vorhanden, strikt aufsteigend | OK |
| A5 | `angebote suche milch --marke weihenstephan --json` | Exit 0; alle Treffer Marke „weihenstephan“ | Exit 0, `anzahl`=1; Marke `Weihenstephan` | OK |
| B1 | `angebote suche butter --marke kerrygold --json` | Exit 0; Marke/Titel enthält „Kerrygold“ | Exit 0, `anzahl`=3; 3/3 Marke `Kerrygold` | OK |
| B2a | `angebote suche bier --json` | Exit 0; Default-Ort + Treffer | Exit 0, `location`=Berlin/10178, `anzahl`=37 | OK |
| B2b | `angebote suche bier --ort Heilbronn --json` | Exit 0; Ort Heilbronn + Treffer | Exit 0, `location`=Heilbronn, Neckar/74072, `anzahl`=40 | OK |
| B2c | `angebote suche bier --plz 74072 --json` | Exit 0; PLZ→Heilbronn + Treffer | Exit 0, `location`=Heilbronn, Neckar/74072, `anzahl`=40, IDs identisch zu B2b | OK |
| B3a | `angebote prospekte rewe --json` | Exit 0; echte REWE-Prospekte (Titel, Gültigkeit, URL) | Exit 0, `anzahl`=3, Titel „Dein Markt“, Gültigkeit 2026-10-25..2026-10-31, URL HTTP 200 | OK |
| B3a' | `angebote prospekte REWE --json` | Exit 0; echte REWE-Prospekte | Exit 0, `anzahl`=3, identisch zu B3a, URL HTTP 200 | OK |
| B3b | `angebote prospekte lidl --json` | Exit 0; echte Lidl-Prospekte | Exit 0, `anzahl`=4, Gültigkeiten plausibel, URL HTTP 200 | OK |
| B4 | `angebote angebot 43e08364-… --begriff Butter --json` | Exit 0; Inhalt identisch zum Suchtreffer | Exit 0; ID/Titel/Preis/Händler/Marke/Daten identisch zu B1 | OK |
| B5 | `angebote watch butter --json` (2×, `XDG_STATE_HOME=./out/state`) | Lauf 1 neue Treffer, Lauf 2 keine neuen; State JSON | Lauf 1 Exit 0, `changed`=true, `anzahl_neu`=30; Lauf 2 Exit 0, `changed`=false, `anzahl_neu`=0; State JSON, `seen`=30, Rechte 600 | OK |
| B6 | `angebote suche butter` | Exit 0; lesbare Textausgabe | Exit 0, 27 Zeilen inkl. `Ort:` und Preis/Titel/Marke/Händler/Gültigkeit | OK |
| C1 | `angebote suche "" --json` | usage, Exit 1 | Exit 1, `usage`: „Der Suchbegriff darf nicht leer sein.“ | OK |
| C2 | `angebote suche butter --max-preis abc --json` | usage, Exit 1 | Exit 1, `usage`: ungültige Zahl: abc | OK |
| C3 | `angebote suche butter --max-preis -5 --json` | usage, Exit 1 | Exit 1, `usage`: `--max-preis muss >= 0 sein` | OK |
| C4 | `angebote suche butter --seiten 99 --json` | usage, Exit 1 | Exit 1, `usage`: `--seiten darf höchstens 10 sein` | OK |
| C5 | `angebote suche butter --limit 0 --json` | usage, Exit 1 | Exit 1, `usage`: `Wert muss positiv sein` | OK |
| C6 | `angebote angebot 000-gibts-nicht --json` | usage, Exit 1 | Exit 1, `usage`: `--begriff` erforderlich | OK |
| C7 | `angebote prospekte xyzhaendlergibtsnicht --json` | not_found, Exit 3 | Exit 3, `not_found` | OK |
| C8a | `angebote foo --json` | usage (invalid choice), Exit 1 | Exit 1, `usage`: invalid choice `foo` | OK |
| C8b | `angebote` | Hilfe/kein Fehler, Exit 0 | Exit 0, Hilfetext auf stdout | OK |
| C8c | `angebote --json` | usage (unbekannte globale Option), Exit 1 | Exit 1, `usage`: unrecognized arguments `--json` | OK |
| C9 | `angebote suche butter --timeout 0.001 --json` | network, Exit 2 | Exit 2, `network`: Zeitüberschreitung | OK |
| C10a | `angebote suche butter --plz 1 --json` | usage, Exit 1 | Exit 1, `usage`: fünfstellige PLZ erforderlich | OK |
| C10b | `angebote suche butter --ort Xyzstadtgibtsnicht --json` | not_found, Exit 3 | Exit 3, `not_found` | OK |
| C11 | `angebote suche qwertzuiopasdf --json` | Exit 3 (keine Treffer) | Exit 3, `not_found` | OK |
| C12 | `angebote suche/prospekte/angebot/watch --help` | Dokumentierte Optionen vorhanden | Exit 0; alle geprüften Optionen vorhanden, keine fehlend | OK |
| Z1 | `angebote prospekte edeka --json` | Exit 0; echte EDEKA-Prospekte | Exit 0, `anzahl`=2, Titel „Aktuelle Angebote“, Gültigkeiten plausibel, URL HTTP 200 | OK |
| Z2 | `angebote suche butter --json` | 0 Treffer ohne `gueltig_bis` | Exit 0, `anzahl`=26, **0** Treffer ohne `gueltig_von`/`gueltig_bis` | OK |
| Z3 | `angebote watch --help` | Nennt State-Pfad/`XDG_STATE_HOME` | Exit 0, nennt `$XDG_STATE_HOME/angebote-cli/watch.json` und Default | OK |
| N1 | `angebote suche kaffee --json` | `anzahl` deutlich >12; Stichprobe Kaffee-Produkte oder nicht beurteilbar | Exit 0, `anzahl`=48; Stichprobe 12 Titel: 6 Kaffee-Produkte, 3 Kaffee-Geräte, 3 nicht beurteilbar | OK |
| N2 | `angebote suche butter --locker --json` | `anzahl` >= Standard (26) | Exit 0, `anzahl`=29 | OK |
| N3 | `angebote suche kaffee --locker --json` | `anzahl` >= Standard (48) | Exit 0, `anzahl`=56 | OK |
| N4 | `angebote suche milch --locker --json` | `anzahl` >= Standard (48) | Exit 0, `anzahl`=54 | OK |
| N5 | `angebote suche bier --locker --json` | `anzahl` >= Standard (37) | Exit 0, `anzahl`=40 | OK |
| N6 | `angebote suche butter --json` (Relevanzfilter) | Kein Treffer, dessen einziger Butter-Bezug ein Wortanfang ist (z. B. `Buttertoast`) | 0/26 Treffer mit ausschließlich Wortanfang-Bezug | OK |

**OK 40/40**

## Beobachtungen (keine Bugs)

- **Butter-Relevanz (A2):** 4/26 Treffer (15,4 %) passen semantisch klar nicht: `Lip Butter Intense Care` ×2 (Kosmetik), `Butter Beans` (Hülsenfrucht) und `Edelmarzipanstollen` (kein Butter-Wort in den Ausgabefeldern; bleibt wegen fehlender Beschreibung/Kategorien erhalten). Grenzwertig: `Finesse Aufschnitt Butter Chicken` (Geflügel-Aufschnitt) und `extra` (Marke Kerrygold, keine Details). Der Filter verwarf 4 Treffer (`verworfen_irrelevant`=4).
- **Kaffee (N1):** 3/48 Treffer (6,25 %) sind Kaffee-Geräte (`Filterkaffeemaschine`, 2× `Kaffeevollautomat`), also keine Kaffee-Produkte, aber klar kaffee-bezogen. Die übrige Stichprobe ist Kaffee-Produkt oder nicht beurteilbar; `Bohnenkaffee` wird wie vorgesehen behalten.
- **Butter-Wortanfang:** In A2 kein reiner Wortanfang-Treffer. Unter `--locker` (N2) erscheinen erwartungsgemäß u. a. `Vollkorn Toast` / `Sammy's Vollkorn Toast` mit Kategorie `Buttertoast`; das bestätigt die Filtergrenze.
- **B2-Mengen:** Die Bier-Trefferzahlen sind gegenüber Runde 2 deutlich gestiegen (Default 37 statt 9; Heilbronn 40 statt 3). Semantisch unauffällig, aber die Ergebnisgröße ist mit dem geänderten Relevanzfilter volatil.
- **B5:** `watch` meldet 30 Gesamttreffer bei 26 Suchtreffern in A2; Ursache sind regionale Prospekt-Dubletten. Lauf 2 bleibt korrekt leer.
- **Prospekte:** Lidl enthält weiterhin länger laufende Prospekte (bis 2026-12-24/2026-12-31); alle geprüften Prospekt-URLs liefern HTTP 200.
- **A4:** `Butter Beans` (0,89 €) erscheint in der Preissortierung; Sortierung und Preisgrenze selbst sind korrekt.
