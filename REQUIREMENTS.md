# angebote-cli – Anforderungen + Akzeptanztests

Ziel: Agenten (und Menschen) bekommen echten, live Zugriff auf aktuelle Prospekt-Angebote deutscher Händler (REWE, Lidl, Aldi, Kaufland, Netto, EDEKA, dm, …) über kaufDA.de (Bonial). Paketname `angebote-cli`, Console-Script `angebote`, Python >= 3.10, MIT, nur `httpx` (oder stdlib) als Dependency, kein Browser nötig.

## Datenquelle (bereits erkundet)
- `https://www.kaufda.de/Angebote/<Keyword>` (z. B. `Butter`, `Kaffee`, `Irische-Butter`) liefert HTML mit `<script id="__NEXT_DATA__">`. Darin `props.pageProps.pageInformation`:
  - `offers.main.items[]` (type OFFER): `id`, `title`, `description`, `brand`, `publisherName` (Händler), `publisherId`, `parentContent` (Prospekt-id, Seite), Preisfelder, Gültigkeit, Bilder, `categories`.
  - `brochures.keyword[]`: Prospekte mit `title`, `id`, `contentId`, `validFrom`, `validUntil`.
  - `location`: `{lat,lng,city,zip}` (Default Stuttgart).
  - `template.content.ProductInfoTable.matching_offers` (Name, Marke, Händler, Preis, Preis/Einheit, Rabatt) und `ContentFreshnessBox`.
- Händlerseite `https://www.kaufda.de/Geschaefte/<Haendler>` (z. B. `REWE`, `Lidl`) mit aktuellen Prospekten.
- Fixtures: `tests/fixtures/angebote_butter.html`, `tests/fixtures/geschaeft_rewe.html` (echte Seiten vom 29.10.2026).
- Standort: herausfinden, wie kaufDA den Ort setzt (Cookie, Query-Parameter, Stadt-URL wie `/Filialen/<Stadt>`…). Wenn ein Ort per `--ort`/`--plz` sauber setzbar ist, umsetzen und live belegen; sonst ehrlich dokumentieren, dass Preise bundesweit/regional (Default-Ort) sind, und den genutzten Ort in jeder Ausgabe mitliefern.

## Befehle
- `angebote suche <begriff> [--haendler NAME ...] [--max-preis EUR] [--marke NAME] [--sort preis|rabatt] [--limit N] [--json]`: Angebote zum Begriff. Begriff → kaufDA-Keyword-Slug (Umlaute: ä→ae usw., Leerzeichen → `-`, Großschreibung je Wort). Unbekannter Begriff (404/keine Treffer) → Exit 3 „nicht gefunden“ mit Hinweis.
  Felder je Treffer: id, titel, marke, haendler, preis (float EUR oder null), preis_text, grundpreis, gueltig_von, gueltig_bis (ISO), prospekt_id, seite, url (Link zur Angebots-/Prospektseite).
  JEDER Filter wird clientseitig gegen jeden Treffer erzwungen (Händler case-insensitive Teilstring, max-preis, Marke).
- `angebote prospekte <haendler> [--json]`: aktuelle Prospekte des Händlers mit Titel, Gültigkeit, id, URL.
- `angebote angebot <offer-id> [--begriff B] [--json]`: Details zu einem Angebot (echter Inhalt: Titel, Beschreibung, Preis, Händler, Gültigkeit, Prospektseite, Bild-URL). Falls es keine eigene Detailseite gibt: Lookup über die Suchseite des Begriffs (dann `--begriff` Pflicht, sauberer Fehler ohne).
- `angebote watch <begriff> [--max-preis EUR] [--haendler ...] [--json]`: speichert gesehene Angebots-IDs in `$XDG_STATE_HOME/angebote-cli/watch.json` (Fallback `~/.local/state/...`), Rechte 0600; meldet nur neue Treffer; 2. Lauf ohne Änderung → `changed=false`, Exit 0. Kaputte State-Datei → Exit 1 + JSON-Fehler.
- `angebote --version`, `--help` und jedes `<cmd> --help` → Exit 0.

## Vertrag
- Mit `--json` genau ein JSON-Objekt auf stdout, auch bei Fehlern und Usage-Fehlern: `{"ok":false,"error":{"type":...,"message":...}}`. Nie Traceback.
- Exit-Codes: 0 ok, 1 Nutzungs-/Eingabefehler (inkl. argparse), 2 Netzwerk/HTTP-Fehler, 3 nicht gefunden, 4 Parse-Fehler (Seitenstruktur geändert).
- `--timeout SEC` global (positiv, sonst Exit 1), ehrlicher User-Agent mit Repo-URL, max. 1 Request/Sekunde.
- Text-Ausgabe ohne `--json` lesbar (eine Zeile pro Angebot: Preis, Titel, Marke, Händler, gültig bis).
- Keine Accounts, keine Schreibaktionen gegen den Service (es gibt keine sinnvolle). Keine Secrets.

## Akzeptanztests (pytest, nur Fixtures, kein Netz – Netz in Tests blockieren)
1. Parser liefert aus `angebote_butter.html` ≥ 10 Angebote, jedes mit id, titel, haendler; Preise float > 0 und < 50.
2. `--haendler rewe` liefert nur REWE-Treffer; `--max-preis 1.5` nur Treffer ≤ 1.5 (ohne Preis → ausgeschlossen).
3. `--sort preis` aufsteigend.
4. Slug: „Irische Butter“ → `Irische-Butter`, „Käse“ → `Kaese`.
5. Prospekte aus `geschaeft_rewe.html`: ≥ 1, mit gültigen ISO-Daten.
6. Watch: 1. Lauf neue IDs, 2. Lauf changed=false, Datei 0600; kaputte Datei → Exit 1 JSON.
7. Fehlerpfade: Usage-Fehler mit --json → ein JSON-Objekt Exit 1; HTTP 404 → Exit 3; HTTP 500/Timeout → Exit 2; kaputtes HTML → Exit 4; `--timeout -1` → Exit 1.
8. `--version`/`--help` Exit 0.
9. `pip install .` in frischem venv funktioniert; `angebote --version` danach.

## Live-Smoke (manuell, nach Tests)
`angebote suche butter --json`, `angebote suche kaffee --haendler lidl --json`, `angebote suche "irische butter" --max-preis 2 --sort preis`, `angebote prospekte rewe`, `angebote angebot <id aus suche> --begriff butter --json` – semantisch prüfen (Treffer passen zum Begriff, Filter eingehalten, Preise plausibel).
