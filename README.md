# Gipfel und Talfahrt der Linie 8

Eine Fahrt durch Leipzigs Unterschiede: Wie verändern sich Sozialstruktur, Bildung und Lebensbedingungen von Haltestelle zu Haltestelle der Straßenbahnlinie 8?

Inspiriert von [„M29 – Berlins Buslinie der großen Unterschiede"](https://interaktiv.morgenpost.de/m29/) der Berliner Morgenpost.

> Status: in Arbeit. Aktuell enthält das Projekt die Datenbeschaffung und ein erstes Testdiagramm.

## Installation

```bash
uv sync
```

Benötigt werden `requests`, `pandas`, `geopandas` und `plotly`.

## Datenbeschaffung

Das Skript `download_data.py` lädt alle Rohdaten nach `data/raw/`.

```bash
uv run python download_data.py            # lädt nur, was noch fehlt
uv run python download_data.py --force    # lädt alles neu
```

### Was geladen wird

| Ordner | Inhalt | Quelle |
|---|---|---|
| `geodaten/` | Grenzen der Ortsteile und Stadtbezirke (GeoJSON, UTM 33N) | [Open-Data-Portal Leipzig](https://opendata.leipzig.de/dataset/geodaten-ortsteile-leipzig) |
| `kleinraeumig/` | Statistik je Ortsteil und Stadtbezirk, Jahreswerte: Einwohnerdichte, Einwohner, Geborene und Gestorbene, Schul- und Berufsabschlüsse, Straftaten | [Amt für Statistik und Wahlen](https://statistik.leipzig.de) |
| `gtfs/` | Fahrplan der LVB im GTFS-Format, Stand 28.12.2022 | [LVB-Fahrplandaten](https://opendata.leipzig.de/dataset/lvb-fahrplandaten) |
| `buergerumfrage/` | Kommunale Bürgerumfrage 2024, personen- und haushaltsgewichtet | [Open-Data-Portal Leipzig](https://opendata.leipzig.de) |

Alle Daten stehen unter der [Datenlizenz Deutschland – Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0). Quelle: Stadt Leipzig.

### Verhalten

- Vorhandene Dateien werden übersprungen. `--force` lädt alles neu.
- Schlägt eine Quelle fehl, laufen die anderen weiter. Am Ende steht, was nicht geklappt hat.
- `data/raw/download_protokoll.json` hält fest, woher jede Datei stammt und wann sie geladen wurde.

### Weitere Daten ergänzen

Alle Quellen stehen oben im Skript im Abschnitt `KONFIGURATION`. Einen neuen kleinräumigen Indikator trägst du in `INDIKATOREN` ein:

```python
"arbeitslose": (kategorie_nr, rubrik_nr),
```

Die beiden Nummern findest du auf dem [Open-Data-Portal](https://opendata.leipzig.de) (Suche nach „kleinräumig") in der Download-URL des Datensatzes.

## Testdiagramm

Das Skript `test_diagramm.py` zeigt einen Indikator Haltestelle für Haltestelle entlang einer Straßenbahnlinie.

```bash
uv run python test_diagramm.py
```

Das Ergebnis ist `test_diagramm.html`, ein interaktives Diagramm, das sich im Browser öffnet.

### Ablauf

1. **Linie finden:** Die Linie wird über Liniennummer und Verkehrsunternehmen gesucht. Der GTFS-Feed enthält den gesamten Mitteldeutschen Verkehrsverbund, es gibt also zum Beispiel auch eine Linie 8 in Halle.
2. **Haltestellen bestimmen:** Als Vorlage dient die längste Haltestellenfolge, die am häufigsten gefahren wird. Kurzfahrten und seltene Varianten fallen so heraus.
3. **Ortsteile zuordnen:** Jede Haltestelle wird per räumlichem Join dem Ortsteil zugeordnet, in dem sie liegt.
4. **Indikator anhängen:** Der Wert des neuesten Jahres wird über den Ortsteilnamen verknüpft.

### Einstellungen

Oben im Skript unter `EINSTELLUNGEN`:

| Variable | Bedeutung | Beispiel |
|---|---|---|
| `LINIE` | Liniennummer | `"8"`, `"11"` |
| `UNTERNEHMEN` | Verkehrsunternehmen laut GTFS | `"Leipziger Verkehrsbetriebe"` |
| `INDIKATOR` | Dateiname in `data/raw/kleinraeumig/` | `"straftaten"` |
| `MERKMAL` | Wert aus der Spalte `Sachmerkmal` | `"Straftaten je Einwohner"` |
| `EINHEIT` | Beschriftung der y-Achse | `"Einwohner je km²"` |

### Einschränkung

Die Statistik liegt nur auf Ortsteilebene vor. Benachbarte Haltestellen im selben Ortsteil bekommen daher denselben Wert, die Kurve verläuft in Stufen.
