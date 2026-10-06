# Gipfel und Talfahrt der Linie 8

Eine Fahrt durch Leipzigs Unterschiede: Wie verändern sich Sozialstruktur, Bildung und Lebensbedingungen von Haltestelle zu Haltestelle der Straßenbahnlinie 8?

Inspiriert von [„M29 – Berlins Buslinie der großen Unterschiede"](https://interaktiv.morgenpost.de/m29/) der Berliner Morgenpost.

> Status: in Arbeit. Datenbeschaffung, Aufbereitung und ein interaktives Test-Dashboard stehen.

## Schnellstart

```bash
uv sync                                  # Umgebung einrichten
uv run python download_data.py           # Rohdaten laden (einmalig)
# 02_aufbereitung.ipynb ausführen          # Statistik aufbereiten -> data/processed/
uv run python satellit_daten.py          # Satellitendaten auswerten (dauert einige Minuten)
uv run python test_dashboard.py          # Dashboard erzeugen und im Browser öffnen
```

Die Reihenfolge ist wichtig: Das Dashboard braucht die aufbereitete Statistik und die Satellitendaten in `data/processed/`. Rohdaten und aufbereitete Daten sind nicht im Repository enthalten, die Skripte laden sie direkt aus den Originalquellen.

## Installation

Voraussetzungen: Python 3.14 und [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

`uv sync` installiert alle Abhängigkeiten aus `pyproject.toml` (fest gepinnt in `uv.lock`):

| Zweck | Pakete |
|---|---|
| Daten laden und aufbereiten | `requests`, `pandas`, `geopandas` |
| Satellitendaten | `rasterio`, `pystac-client`, `planetary-computer` |
| Diagramme und Dashboard | `plotly` (das Dashboard lädt Plotly zusätzlich im Browser aus dem Internet) |
| Notebooks | `ipykernel`, `matplotlib`, `folium`, `mapclassify`, `seaborn`, `scikit-learn` |

## Projektstruktur

| Datei / Ordner | Zweck |
|---|---|
| `download_data.py` | Lädt alle Rohdaten nach `data/raw/` |
| `01_geodaten.ipynb` | Notebook: Ortsteile, Stadtbezirke und die Linie 8 auf der Karte |
| `karte_linie_8.html` | Interaktive Karte aus `01_geodaten.ipynb` |
| `02_aufbereitung.ipynb` | Notebook: bringt alle kleinräumigen Statistiken in ein einheitliches langes Format |
| `satellit_daten.py` | Wertet Landsat-Satellitendaten aus: Oberflächentemperatur und Vegetation je Ortsteil |
| `test_dashboard.py` | Erzeugt das Test-Dashboard (Daten zusammenstellen, Vorlage befüllen) |
| `test_dashboard_vorlage.html` | HTML-Vorlage des Dashboards: Layout, Diagramme, Karten, Bedienung |
| `test_dashboard.html` | Ergebnis von `test_dashboard.py`, eine einzelne Datei zum Öffnen im Browser |
| `test_diagramm.py` / `.html` | Erstes Testdiagramm: ein Indikator entlang der Linie |
| `data/raw/` | Rohdaten (nicht versioniert, außer `download_protokoll.json`) |
| `data/processed/` | Aufbereitete Daten (nicht versioniert) |

## Ablauf der Daten

```
Open-Data-Portal Leipzig ─┐
LVB-Fahrplan (GTFS) ──────┼─ download_data.py ──> data/raw/
Geodaten Ortsteile ───────┘                          │
                                                     ├─ 02_aufbereitung.ipynb ──> data/processed/kleinraeumig_lang.csv
Landsat 8/9 (Planetary Computer) ─ satellit_daten.py ─────────────────────────> data/processed/satellit_lang.csv
                                                     │
                                  test_dashboard.py ─┴─> test_dashboard.html
```

Alle aufbereiteten Daten haben dasselbe lange Format: eine Zeile pro Gebiet, Merkmal und Zeitpunkt, mit den Spalten `indikator`, `gebiet`, `ebene`, `nummer`, `stadtbezirk`, `merkmal`, `zeitart`, `zeitpunkt`, `datum`, `jahr`, `wert`, `zeichen`, `hinweis`. Beim Einlesen `dtype={"nummer": str, "zeitpunkt": str}` angeben, sonst wird aus der Ortsteilnummer `"05"` die Zahl `5`.

## Dashboard

```bash
uv run python test_dashboard.py
```

Das Skript bestimmt die Haltestellen der Linie 8, stellt die Daten für ihre 13 Ortsteile zusammen und schreibt alles in eine einzelne HTML-Datei (`test_dashboard.html`, rund 0,1 MB). Sie öffnet sich im Browser und braucht nur für Plotly eine Internetverbindung.

### Funktionen

- **Bis zu drei Kennzahlen gleichzeitig**, nebeneinander. Die Haltestellen laufen von links (Grünau-Nord) nach rechts (Paunsdorf Nord), sodass Gipfel und Täler sichtbar werden. Jedes Diagramm hat seine eigene Skala.
- **Reihenfolge:** Im Kopf jedes Diagramms lässt es sich mit ◀ ▶ verschieben, über die Auswahlliste ersetzen oder mit ✕ entfernen.
- **Ansichten:** „Ein Zeitpunkt“ mit Jahresregler oder „Heatmap“ mit allen Jahren auf einmal (Haltestellen × Zeitpunkte).
- **Kennzahlen im Kopf:** Gipfel, Tal, Faktor zwischen beiden und Wert der Gesamtstadt.
- **Hervorhebung:** Beim Darüberfahren wird die Haltestelle in allen Diagrammen gleichzeitig markiert.
- **Minikarte:** zeigt die aktuelle Haltestelle und lässt sich selbst überfahren. Umschaltbar zwischen dem Ausschnitt der Linie und ganz Leipzig.
- **Entwicklung über die Zeit:** Ein Ortsteil im Vergleich zur Gesamtstadt. Gewählt wird er per Klick auf eine zweite Karte, auf eine Haltestelle oder über eine Liste.
- **Bundestagswahl** als gestapelte Säulen je Haltestelle, mit eigenem Tooltip für alle Parteien.
- **Fußnoten**, die sich an die gewählten Kennzahlen anpassen, und eine Tabelle mit allen Werten.
- Helles und dunkles Design folgen der Systemeinstellung. Die aktuelle Auswahl steht in der Adresszeile und lässt sich als Link speichern.

### Kennzahlen

Aus über 150 aufbereiteten Merkmalen sind 15 Kennzahlen ausgewählt, bevorzugt Quoten, Anteile und Durchschnitte. Absolute Zahlen würden vor allem zeigen, wie groß ein Ortsteil ist.

| Thema | Kennzahl | Einheit | Zeitraum |
|---|---|---|---|
| Soziale Lage | SGB-II-Quote | % | 2008–2025 |
| Soziale Lage | Kinder in SGB II | % | 2008–2025 |
| Soziale Lage | Arbeitslosenanteil an den Erwerbsfähigen | % | 2000–2025 |
| Soziale Lage | Haushaltsnettoeinkommen \* | € / Monat | 2011–2023 |
| Bevölkerung | Durchschnittsalter | Jahre | 2000–2025 |
| Bevölkerung | Migrationshintergrund | % der Einwohner | 2008–2025 |
| Bevölkerung | Haushaltsgröße | Personen je Haushalt | 2006–2025 |
| Bildung | Hochschulabschluss \* | % | 2011–2023 |
| Wohnen | Gesamtmiete \* | € / m² | 2011–2023 |
| Lebensqualität | Lebenszufriedenheit \* | Note, niedriger = zufriedener | 2015–2023 |
| Mobilität | Privat-PKW | je 1.000 Einwohner | 2001–2025 |
| Umwelt | Hitze im Sommer (Satellit) | °C über/unter Stadtmittel | 2014–2026 |
| Umwelt | Vegetation im Sommer (Satellit) | NDVI, 0 = kahl, 1 = dicht grün | 2014–2026 |
| Sicherheit | Straftaten | je 1.000 Einwohner | 2004–2025 |
| Politik | Bundestagswahl, alle Parteien | Stimmenanteil in % | 1994–2025 |

\* beruht auf der Kommunalen Bürgerumfrage

Die Auswahl steht als Liste `KENNZAHLEN` oben in `test_dashboard.py`. Ein weiteres Merkmal aufzunehmen heißt, dort eine Zeile mit Indikator, Merkmal und Einheit zu ergänzen.

## Hinweise zu den Daten

Diese Punkte erscheinen auch als Fußnoten im Dashboard.

- **Einwohner** zählen nur **Hauptwohnsitze** (Datensatz Kategorie 2 / Rubrik 1). Der ähnliche Datensatz „Wohnberechtigte Einwohner“ enthält zusätzlich Nebenwohnsitze und wird bewusst nicht verwendet.
- **Haltestelle = Ortsteil:** Die Statistik liegt nur je Ortsteil vor. Haltestellen im selben Ortsteil haben denselben Wert, die Kurven verlaufen in Stufen. Die Zuordnung erfolgt räumlich und nicht über den Namen: Die Haltestelle „Grünau-Nord“ liegt zum Beispiel im Ortsteil Schönau.
- **Linienführung:** Der Fahrplan ist von Dezember 2022 und wird für alle Jahre verwendet.
- **Ortsteilgrenzen** wurden 2006, 2012 und 2014 angepasst, ältere Werte wurden nicht zurückgerechnet. Am deutlichsten ist das in Heiterblick: Dort verschwinden 2013 rund 300 Einwohner an Engelsdorf. Die Grenzjahre sind in den Zeitdiagrammen markiert.
- **Sonderzeichen der Quelle:** `-` bedeutet „nichts vorhanden“ und wird zu 0. `.` (unbekannt oder Datenschutz) und `x` (Angabe nicht sinnvoll, z. B. vor Eingemeindungen) werden zu „fehlend“. Das Originalzeichen bleibt in der Spalte `zeichen` erhalten. Quelle: Zeichenerklärung im [Ortsteilkatalog 2016](https://static.leipzig.de/fileadmin/mediendatenbank/leipzig-de/Stadt/02.1_Dez1_Allgemeine_Verwaltung/12_Statistik_und_Wahlen/Raumbezug/Ortsteilkatalog_2016.pdf).
- **Einheiten** liefert die Quelle nicht mit. Sie sind nach den Merkmalsbeschreibungen ergänzt.
- **Umfragedaten** (\*) sind eine Stichprobe und werden nur alle zwei Jahre erhoben. Pro Ortsteil antworten wenige Menschen, deshalb schwanken die Werte stärker.
- **Migrationshintergrund:** umfasst Ausländer und Deutsche mit Migrationshintergrund, auch in Deutschland geborene Kinder mit mindestens einem zugewanderten Elternteil. Die Quelle nennt das Merkmal „Migrantenanteil“. Der Begriff „Einwanderungsgeschichte“ (seit 2023 beim Statistischen Bundesamt) ist enger gefasst.
- **Straftaten** werden am Tatort gezählt, aber auf die Einwohner bezogen. Im Zentrum mit wenigen Einwohnern ergeben sich deshalb sehr hohe Werte, rund 2.800 je 1.000 Einwohner.
- **Wahlen:** „DIE LINKE“ umfasst bis 2005 die Vorgänger PDS bzw. Linkspartei.PDS. „Sonstige“ ist der Rest zu 100 %. Ist eine Partei nicht angetreten, ist ihr Wert leer und nicht 0.
- **Merkmale, die später hinzukamen**, sind in früheren Jahren leer. Beispiele sind Arbeitslose nach Abschluss (ab 2018) und Kfz nach Antrieb (ab 2015). Bei der Flächennutzung wurden 2016 die Kategorien umgestellt.

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
| `buergerumfrage/` | Kommunale Bürgerumfrage 2024, personen- und haushaltsgewichtet (noch nicht im Dashboard) | [Open-Data-Portal Leipzig](https://opendata.leipzig.de) |
| `satellit/` | Zwischenergebnis der Satellitenauswertung je Aufnahme (`satellit_daten.py`) | [Landsat 8/9, USGS](https://www.usgs.gov/landsat-missions), über den [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2) |

Die Daten der Stadt Leipzig stehen unter der [Datenlizenz Deutschland – Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0). Landsat-Daten mit freundlicher Genehmigung des U.S. Geological Survey.

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

Die beiden Nummern findest du auf dem [Open-Data-Portal](https://opendata.leipzig.de) (Suche nach „kleinräumig“) in der Download-URL des Datensatzes. Verlass dich dabei auf Titel und Download-Link, nicht auf die Adresse der Seite: Die Adressen sind auf dem Portal teilweise vertauscht (`…/stadtratswahlen-kleinraumig` enthält zum Beispiel die Landtagswahlen).

Wahlen gibt es nicht je Jahr, sondern je Wahltermin (`periode=d` statt `y` in der URL). Sie gehören deshalb in `WAHLEN` statt in `INDIKATOREN`.

## Satellitendaten

```bash
uv run python satellit_daten.py            # rechnet nur neue Aufnahmen
uv run python satellit_daten.py --force    # rechnet alles neu
```

Das Skript wertet alle Landsat-8/9-Aufnahmen aus den Sommermonaten (Juni bis August) seit 2013 aus:

- Wolken, Wolkenschatten und Schnee werden pixelgenau entfernt.
- Eine Aufnahme zählt nur, wenn mindestens 80 % der Stadt wolkenfrei sind. Ein Gebiet zählt nur, wenn mindestens 70 % seiner Fläche gültig sind.
- Je Ortsteil, Stadtbezirk und Gesamtstadt entstehen vier Merkmale: mittlere **Oberflächentemperatur**, **Abweichung vom Stadtmittel** am selben Tag, **Vegetationsindex (NDVI)** und Anzahl der ausgewerteten Aufnahmen.
- Gerechnet wird auf die heutigen Ortsteilgrenzen.

Die Abweichung vom Stadtmittel macht Jahre mit unterschiedlichem Wetter vergleichbar. Gemessen wird die Temperatur der Oberflächen (Dächer, Asphalt, Wiesen) am Vormittag, nicht die Lufttemperatur. Abgeerntete Felder am Stadtrand werden besonders heiß. 2013 und 2021 gab es keine verwendbare Aufnahme.

## Testdiagramm

`test_diagramm.py` war der erste Test, um einen Indikator entlang der Linie zu zeigen. Es nutzt die Rohdaten direkt und ist durch das Dashboard überholt.

```bash
uv run python test_diagramm.py
```

Einstellungen stehen oben im Skript unter `EINSTELLUNGEN`: `LINIE`, `UNTERNEHMEN`, `INDIKATOR` (Dateiname in `data/raw/kleinraeumig/`), `MERKMAL` (Wert aus der Spalte `Sachmerkmal`) und `EINHEIT`.

So wird die Linie bestimmt (gilt auch für das Dashboard):

1. **Linie finden:** über Liniennummer und Verkehrsunternehmen. Der GTFS-Feed enthält den ganzen Mitteldeutschen Verkehrsverbund, es gibt also zum Beispiel auch eine Linie 8 in Halle.
2. **Haltestellen bestimmen:** Vorlage ist die längste Haltestellenfolge, die am häufigsten gefahren wird. Kurzfahrten und seltene Varianten fallen so heraus.
3. **Ortsteile zuordnen:** Jede Haltestelle wird per räumlichem Join dem Ortsteil zugeordnet, in dem sie liegt.
