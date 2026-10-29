# angebote-cli

`angebote` gibt Agenten und Menschen live Zugriff auf aktuelle Prospekt-Angebote
deutscher Händler (REWE, Lidl, Aldi, Kaufland, Netto, EDEKA, dm, …). Die Daten
kommen von [kaufDA.de](https://www.kaufda.de), dem Portal der Bonial
International Group.

Das Projekt ist **inoffiziell** und steht in **keiner Verbindung zu Bonial**.
Es nutzt ausschließlich öffentlich abrufbare Seiten und stellt keine Accounts
oder Schreibaktionen bereit. Bitte respektiere die Nutzungsbedingungen von
kaufDA und halte die eingebaute Drosselung (maximal ein Request pro Sekunde)
sowie den ehrlichen User-Agent ein.

## Installation

```bash
pip install git+https://github.com/smlfg/angebote-cli
```

Voraussetzungen: Python >= 3.10, eine dependency (`httpx`). Kein Browser nötig.

```bash
angebote --version
angebote --help
```

## Befehle

### `angebote suche <begriff>`

Sucht aktuelle Angebote zu einem Begriff. Der Begriff wird intern zu einem
kaufDA-Keyword-Slug (Umlaute: ä→ae, ö→oe, ü→ue, ß→ss, Leerzeichen → `-`).

```bash
angebote suche butter
angebote suche "irische butter" --max-preis 2 --sort preis
angebote suche kaffee --haendler lidl rewe --limit 10 --json
angebote suche milch --marke weihenstephan --seiten 2
angebote suche butter --sort rabatt --json
angebote suche butter --alle --json
angebote suche butter --locker --json
```

Optionen:

| Option | Bedeutung |
| --- | --- |
| `--haendler NAME ...` | Nur Händler, deren Name den Text enthält (mehrere möglich, case-insensitive) |
| `--max-preis EUR` | Nur Angebote bis zu diesem Preis (ohne Preis werden ausgeschlossen) |
| `--marke NAME` | Nur diese Marke (Teilstring, case-insensitive) |
| `--sort preis\|rabatt` | `preis` aufsteigend, `rabatt` absteigend |
| `--limit N` | Maximale Anzahl Treffer |
| `--seiten N` | Ergebnisseiten 1–10 (Standard 3) |
| `--alle` | Regionale Dubletten nicht zusammenfassen |
| `--locker` | Relevanzfilter ausschalten und alle kaufDA-Treffer behalten |
| `--json` | JSON-Ausgabe |

Standardmäßig bleibt nur ein Treffer erhalten, wenn **jedes Wort** des
Suchbegriffs – case-insensitive und mit normalisierten Umlauten (ä=ae usw.) –
in `titel`, `beschreibung`, `marke` oder `kategorien` vorkommt. kaufDA mischt
gelegentlich unpassende Angebote bei; diese werden verworfen. `--locker`
schaltet den Filter ab. Die Anzahl der verworfenen Treffer steht im JSON unter
`verworfen_irrelevant`.

### `angebote prospekte <haendler>`

Zeigt die aktuellen Prospekte eines Händlers.

```bash
angebote prospekte rewe
angebote prospekte Lidl --json
angebote prospekte REWE --ort Heilbronn
```

### `angebote angebot <offer-id>`

Zeigt Details zu einem Angebot. kaufDA hat keine eigene Detailseite; das
Angebot wird über die Suchseite gefunden. Dafür ist `--begriff` erforderlich.

```bash
angebote angebot 01234567-89ab-cdef-0123-456789abcdef --begriff butter
angebote angebot <offer-id> --begriff kaffee --json
```

### `angebote watch <begriff>`

Beobachtet neue Angebote. Gesehene Angebots-IDs werden in
`$XDG_STATE_HOME/angebote-cli/watch.json` gespeichert (Fallback
`~/.local/state/angebote-cli/watch.json`, Rechte `0600`). Der zweite Lauf ohne
Änderungen liefert `changed=false` und Exit 0.

```bash
angebote watch butter
angebote watch kaffee --max-preis 10 --haendler lidl --json
angebote watch butter --locker
```

Optionen: `--haendler`, `--max-preis`, `--locker`, `--json`, `--ort`, `--plz`.

### Globale Optionen

| Option | Bedeutung |
| --- | --- |
| `--timeout SEC` | HTTP-Timeout in Sekunden (muss positiv sein) |
| `--ort STADT` | Ort über Stadtnamen setzen, z. B. `Heilbronn` |
| `--plz PLZ` | Ort über fünfstellige PLZ setzen, z. B. `74072` |
| `--version` | Version ausgeben |
| `--help` | Hilfe ausgeben |

`--ort` und `--plz` dürfen vor oder nach dem Unterbefehl stehen. Bei der
PLZ-Auflösung wird zuerst die PLZ über [zippopotam.us](https://api.zippopotam.us)
zu einem Ortsnamen aufgelöst; danach wird die kaufDA-Stadt-URL verwendet.
Schlägt die Auflösung fehl, nutze `--ort`.

## Ort und Region

kaufDA bestimmt den Ort ohne Angabe serverseitig (unter anderem anhand der
IP-Adresse) und liefert ihn in `props.pageProps.pageInformation.location`.
Der tatsächlich genutzte Ort steht deshalb in **jeder** Ausgabe unter
`location` (`city`, `zip`, `lat`, `lng`, `countryCode`).

Live belegt: Eine Stadt-URL wie
`https://www.kaufda.de/Heilbronn/Angebote/Butter` ändert die Location
nachweislich auf Heilbronn (`zip=74072`). Genau diesen Weg nutzt `--ort`;
`--plz` löst vorher die PLZ zum Ortsnamen auf. Query-Parameter wie
`?lat=…&lng=…`, `?zip=…` und ein selbst gesetztes `location`-Cookie werden
von kaufDA ignoriert.

## Ausgabe

Ohne `--json`: eine Zeile pro Angebot mit Preis, Titel, Marke, Händler und
Gültigkeitsdatum, davor der genutzte Ort.

Mit `--json`: genau **ein** JSON-Objekt auf stdout, auch bei Fehlern.

### Erfolgreiche Suche

```json
{
  "ok": true,
  "begriff": "butter",
  "keyword": "Butter",
  "location": {"city": "Heilbronn, Neckar", "zip": "74072", "lat": 49.1416, "lng": 9.22208, "countryCode": "DE"},
  "anzahl": 2,
  "verworfen_irrelevant": 1,
  "angebote": [
    {
      "id": "01234567-89ab-cdef-0123-456789abcdef",
      "titel": "Original Irische Butter",
      "beschreibung": "Irland versch. Sorten 250-g-Pckg./Becher",
      "kategorien": ["Irische Butter", "Kerrygold"],
      "marke": "Kerrygold",
      "haendler": "REWE",
      "preis": 2.49,
      "preis_text": "2,49 €",
      "grundpreis": "9,96 €/kg",
      "gueltig_von": "2026-10-26T00:00:00+00:00",
      "gueltig_bis": "2026-10-31T00:00:00+00:00",
      "prospekt_id": "abc123",
      "seite": 4,
      "url": "https://www.kaufda.de/Angebote/Butter?offerId=01234567-89ab-cdef-0123-456789abcdef",
      "weitere_ids": [],
      "anzahl_prospekte": 1
    }
  ]
}
```

`beschreibung` und `kategorien` sind in jedem Treffer enthalten (nicht nur in
der Detailansicht). `angebot --json` liefert zusätzlich `bild_url` im Objekt
`angebot`.

### Prospekte

```json
{
  "ok": true,
  "haendler": "REWE",
  "location": {"city": "Stuttgart", "zip": "70174"},
  "anzahl": 1,
  "prospekte": [
    {
      "id": "123",
      "titel": "Dein Markt",
      "content_id": "456",
      "gueltig_von": "2026-10-26T00:00:00+00:00",
      "gueltig_bis": "2026-10-31T00:00:00+00:00",
      "url": "https://www.kaufda.de/Geschaefte/REWE#brochure-456",
      "bild_url": "https://content-media.bonial.biz/..."
    }
  ]
}
```

### Watch

```json
{
  "ok": true,
  "begriff": "butter",
  "keyword": "Butter",
  "location": {"city": "Stuttgart", "zip": "70174"},
  "changed": true,
  "anzahl_neu": 3,
  "anzahl_gesamt": 12,
  "verworfen_irrelevant": 2,
  "neu": []
}
```

### Fehler

```json
{
  "ok": false,
  "error": {
    "type": "not_found",
    "message": "Keine Angebote für „quatsch“ gefunden. Versuch es mit einem allgemeineren Begriff."
  }
}
```

Fehlertypen: `usage`, `network`, `not_found`, `parse`, `state`.

## Exit-Codes

| Code | Bedeutung |
| --- | --- |
| 0 | Erfolg |
| 1 | Nutzungs-/Eingabefehler (inkl. argparse und kaputter Watch-State) |
| 2 | Netzwerk-/HTTP-Fehler |
| 3 | Nicht gefunden (404, keine Treffer) |
| 4 | Parse-Fehler (Seitenstruktur geändert) |

Auch Usage-Fehler liefern mit `--json` genau ein JSON-Objekt und niemals einen
Traceback.

## Grenzen

- **Ort:** Ohne `--ort`/`--plz` bestimmt kaufDA den Ort serverseitig; er kann
  je nach IP abweichen. Der genutzte Ort steht immer in `location`.
- **Seitenumfang:** kaufDA liefert regulär 20 Angebote pro Seite. `--seiten`
  erlaubt 1–10; bei ausbleibender Paginierung fällt der Client auf die
  Such-API zurück und dedupliziert nach Angebots-ID.
- **Preise:** Preise und Verfügbarkeit sind regional und an Prospekte bzw.
  Filialen gebunden. Es gibt keine Garantie auf Vollständigkeit oder
  Bundesweit-Gültigkeit.
- **Drosselung:** maximal ein Request pro Sekunde, ehrlicher User-Agent mit
  Repo-URL.
- **Datenquelle:** inoffizielle HTML-/JSON-Auswertung; Änderungen an kaufDA
  können Parse-Fehler (Exit 4) verursachen.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
