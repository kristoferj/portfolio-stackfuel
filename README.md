# Gipfel und Talfahrt der Linie 8

Eine Fahrt durch Leipzigs Unterschiede: Wie verändern sich Sozialstruktur, Bildung und Lebensbedingungen von Haltestelle zu Haltestelle der Straßenbahnlinie 8?

Inspiriert von [„M29 – Berlins Buslinie der großen Unterschiede"](https://interaktiv.morgenpost.de/m29/) der Berliner Morgenpost.

> Status: in Arbeit. Aktuell enthält das Projekt die Datenbeschaffung und ein erstes Testdiagramm.

## Schnellstart

```bash
uv sync                                  # Umgebung einrichten
uv run python download_data.py           # Rohdaten laden (einmalig)
# danach 02_aufbereitung.ipynb ausführen   # Daten aufbereiten
uv run python satellit_daten.py          # Satellitendaten auswerten (dauert einige Minuten)
uv run python test_diagramm.py           # Testdiagramm erzeugen
```

Die Rohdaten sind nicht im Repository enthalten. `download_data.py` lädt sie direkt von den Portalen der Stadt Leipzig.

## Installation

Voraussetzungen: Python 3.14 und [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

`uv sync` installiert alle Abhängigkeiten aus `pyproject.toml` (fest gepinnt in `uv.lock`). Die Skripte brauchen `requests`, `pandas`, `geopandas` und `plotly`. Für die Notebooks kommen `ipykernel`, `matplotlib`, `folium`, `mapclassify`, `seaborn` und `scikit-learn` dazu.

## Projektstruktur

| Datei / Ordner | Zweck |
|---|---|
| `download_data.py` | Lädt alle Rohdaten nach `data/raw/` |
| `satellit_daten.py` | Wertet Landsat-Satellitendaten aus: Oberflächentemperatur und Vegetation je Ortsteil, Sommer ab 2013 |
| `test_diagramm.py` | Erstes Diagramm: ein Indikator entlang einer Linie |
| `test_diagramm.html` | Ergebnis von `test_diagramm.py` |
| `test_dashboard.py` | Test-Dashboard: alle aufbereiteten Indikatoren entlang der Linie 8, mit Zeitauswahl |
| `test_dashboard_vorlage.html` | HTML-Vorlage des Test-Dashboards (Layout und Diagramme) |
| `test_dashboard.html` | Ergebnis von `test_dashboard.py` |
| `01_geodaten.ipynb` | Notebook: Ortsteile, Stadtbezirke und die Linie 8 auf der Karte |
| `02_aufbereitung.ipynb` | Notebook: bringt alle kleinräumigen Daten in ein einheitliches langes Format (`data/processed/`) |
| `data/raw/` | Rohdaten, entsteht beim Download (nicht versioniert, außer `download_protokoll.json`) |
| `data/processed/` | Aufbereitete Daten, entsteht mit `02_aufbereitung.ipynb` (nicht versioniert) |

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
| `kleinraeumig/` | Statistik je Ortsteil und Stadtbezirk, 21 Datensätze zu Bevölkerung, sozialer Lage, Bildung, Wohnen, Verkehr, Sicherheit und Wahlen | [Amt für Statistik und Wahlen](https://statistik.leipzig.de) |
| `gtfs/` | Fahrplan der LVB im GTFS-Format, Stand 28.12.2022 | [LVB-Fahrplandaten](https://opendata.leipzig.de/dataset/lvb-fahrplandaten) |
| `buergerumfrage/` | Kommunale Bürgerumfrage 2024, personen- und haushaltsgewichtet | [Open-Data-Portal Leipzig](https://opendata.leipzig.de) |
| `satellit/` | Zwischenergebnis der Satellitenauswertung je Aufnahme (`satellit_daten.py`) | [Landsat 8/9, USGS](https://www.usgs.gov/landsat-missions), über den [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2) |

Alle Daten stehen unter der [Datenlizenz Deutschland – Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0). Quelle: Stadt Leipzig.

### Hinweise zu den Daten (für Fußnoten im Dashboard)

- **Einwohner** (`einwohner.csv`, Kategorie 2 / Rubrik 1) zählt nur **Hauptwohnsitze**. Der ähnliche Datensatz „Wohnberechtigte Einwohner“ (2 / 6) enthält zusätzlich Nebenwohnsitze und wird bewusst nicht verwendet.
- **Schul- und Berufsabschlüsse** beruhen auf Umfragedaten und liegen nur alle zwei Jahre vor (2011–2023).

### Verhalten

- Vorhandene Dateien werden übersprungen. `--force` lädt alles neu.
- Schlägt eine Quelle fehl, laufen die anderen weiter. Am Ende steht, was nicht geklappt hat.
- `data/raw/download_protokoll.json` hält fest, woher jede Datei stammt und wann sie geladen wurde.
- Halbe Downloads landen zuerst in einer `.part`-Datei und bekommen erst am Ende den richtigen Namen.
- Das Skript entfernt die Umgebungsvariable `SSLKEYLOGFILE` für seine eigene Laufzeit. Ist sie gesetzt, scheitern HTTPS-Verbindungen sonst mit `PermissionError`.

### Weitere Daten ergänzen

Alle Quellen stehen oben im Skript im Abschnitt `KONFIGURATION`. Einen neuen kleinräumigen Indikator trägst du in `INDIKATOREN` ein:

```python
"arbeitslose": (kategorie_nr, rubrik_nr),
```

Die beiden Nummern findest du auf dem [Open-Data-Portal](https://opendata.leipzig.de) (Suche nach „kleinräumig") in der Download-URL des Datensatzes. Verlass dich dabei auf Titel und Download-Link, nicht auf die Adresse der Seite: Die Adressen sind auf dem Portal teilweise vertauscht (`…/stadtratswahlen-kleinraumig` enthält zum Beispiel die Landtagswahlen).

Wahlen stehen nicht je Jahr, sondern je Wahltermin zur Verfügung (`periode=d` statt `y` in der URL). Sie gehören deshalb in `WAHLEN` statt in `INDIKATOREN`.

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
