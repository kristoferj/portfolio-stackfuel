"""Test-Dashboard: alle aufbereiteten Indikatoren entlang der Linie 8.

Aufruf im Projektordner:
    uv run python test_dashboard.py

Voraussetzung: data/processed/ existiert (02_aufbereitung.ipynb ausgeführt).
Ergebnis: test_dashboard.html (öffnet sich im Browser, braucht Internet für Plotly)
"""

import json
import webbrowser
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

# ============================================================
# EINSTELLUNGEN
# ============================================================

LINIE = "8"
UNTERNEHMEN = "Leipziger Verkehrsbetriebe"
STADT = "Stadt Leipzig"

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
VORLAGE = Path("test_dashboard_vorlage.html")
ZIEL = Path("test_dashboard.html")


# ============================================================
# 1. Haltestellen der Linie und ihre Ortsteile
# ============================================================

def gtfs_lesen(z: zipfile.ZipFile, datei: str, **kwargs) -> pd.DataFrame:
    # Alles als Text lesen, damit IDs wie "00123" nicht zu Zahlen werden
    return pd.read_csv(z.open(datei), dtype=str, encoding="utf-8-sig", **kwargs)


def strecke_bestimmen() -> pd.DataFrame:
    """Haltestellen der Vorlage-Fahrt mit Ortsteil (Vorgehen wie in test_diagramm.py)."""
    with zipfile.ZipFile(RAW / "gtfs/lvb_gtfs.zip") as z:
        agency = gtfs_lesen(z, "agency.txt")
        routes = gtfs_lesen(z, "routes.txt")
        trips = gtfs_lesen(z, "trips.txt")
        stops = gtfs_lesen(z, "stops.txt")
        stop_times = gtfs_lesen(z, "stop_times.txt", usecols=["trip_id", "stop_id", "stop_sequence"])

    # Linie finden: Nummer UND Unternehmen, sonst erwischen wir die 8 in Halle
    agency_ids = agency.loc[agency["agency_name"] == UNTERNEHMEN, "agency_id"]
    route = routes[(routes["route_short_name"] == LINIE) & routes["agency_id"].isin(agency_ids)]
    if len(route) != 1:
        raise ValueError(f"Linie {LINIE} nicht eindeutig gefunden:\n{route}")

    fahrten = trips.loc[trips["route_id"] == route["route_id"].iloc[0], "trip_id"]
    halte = stop_times[stop_times["trip_id"].isin(fahrten)].copy()
    halte["stop_sequence"] = halte["stop_sequence"].astype(int)
    halte = halte.merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id")
    halte = halte.sort_values(["trip_id", "stop_sequence"])

    # Vorlage-Fahrt: die längste Halte-Folge, die am häufigsten gefahren wird
    folgen = halte.groupby("trip_id")["stop_name"].apply(tuple)
    laengste = folgen[folgen.str.len() == folgen.str.len().max()]
    vorlage = laengste.value_counts().index[0]
    vorlage_id = laengste[laengste == vorlage].index[0]
    strecke = halte[halte["trip_id"] == vorlage_id].reset_index(drop=True)

    # Haltestellen räumlich den Ortsteilen zuordnen
    ortsteile = gpd.read_file(RAW / "geodaten/ortsteile.geojson")
    punkte = gpd.GeoDataFrame(
        strecke,
        geometry=gpd.points_from_xy(strecke["stop_lon"].astype(float), strecke["stop_lat"].astype(float)),
        crs="EPSG:4326",  # GTFS nutzt immer GPS-Koordinaten
    ).to_crs(ortsteile.crs)
    strecke = gpd.sjoin(punkte, ortsteile[["Name", "geometry"]], how="left", predicate="within")
    if strecke["Name"].isna().any():
        raise ValueError(f"Haltestellen ohne Ortsteil: {strecke.loc[strecke['Name'].isna(), 'stop_name'].tolist()}")

    return pd.DataFrame({
        "name": strecke["stop_name"].str.replace("Leipzig, ", "", regex=False),
        "ortsteil": strecke["Name"],
    }).reset_index(drop=True)


# ============================================================
# 2. Daten für die Ortsteile der Linie zusammenstellen
# ============================================================

# Kuratierte Auswahl fürs Dashboard (Entscheidungsprotokoll Nr. 19). Alle übrigen Merkmale
# bleiben in data/processed/ erhalten und lassen sich hier jederzeit wieder aufnehmen.
# Die Quelle liefert keine Einheiten, sie sind hier nach den Merkmalsbeschreibungen ergänzt.
KENNZAHLEN = [
    # id,              thema,            titel,                                  indikator,                merkmal,                            einheit
    ("sgb2_quote",     "Soziale Lage",   "SGB-II-Quote",                         "sgb2",                   "SGB-II-Quote",                     "%"),
    ("sgb2_kinder",    "Soziale Lage",   "Kinder in SGB II",                     "sgb2",                   "Anteil an Kindern",                "%"),
    ("arbeitslose",    "Soziale Lage",   "Arbeitslosenanteil",                   "arbeitslose",            "Anteil an den Erwerbsfähigen",     "%"),
    ("einkommen",      "Soziale Lage",   "Haushaltsnettoeinkommen",              "nettoeinkommen",         "Haushaltseinkommen",               "€ / Monat"),
    ("alter",          "Bevölkerung",    "Durchschnittsalter",                   "einwohner_alter",        "Durchschnittsalter",               "Jahre"),
    ("migration",      "Bevölkerung",    "Migrantenanteil",                      "migrationshintergrund",  "Migrantenanteil",                  "%"),
    ("einpersonen",    "Bevölkerung",    "Einpersonenhaushalte",                 "haushalte",              "Haushalte mit 1 Person (Anteil in %)", "%"),
    ("hochschule",     "Bildung",        "Hochschulabschluss",                   "schulabschluesse",       "Hochschulabschluss",               "%"),
    ("miete",          "Wohnen",         "Gesamtmiete",                          "mieten",                 "Gesamtmiete",                      "€ / m²"),
    ("zufriedenheit",  "Lebensqualität", "Lebenszufriedenheit",                  "zufriedenheit",          "Lebenszufriedenheit",              "Note, niedriger = zufriedener"),
    ("pkw",            "Mobilität",      "Privat-PKW",                           "kfz_bestand",            "Privat-PKW je 1 000 Einwohner",    "je 1.000 Einwohner"),
    ("hitze",          "Umwelt",         "Hitze im Sommer",                      "oberflaechentemperatur", "Abweichung vom Stadtmittel (°C)",  "°C über/unter Stadtmittel"),
    ("gruen",          "Umwelt",         "Vegetation im Sommer",                 "vegetation",             "Vegetationsindex NDVI (0 = kahl, 1 = dicht grün)", "NDVI, 0 = kahl, 1 = dicht grün"),
    ("straftaten",     "Sicherheit",     "Straftaten",                           "straftaten",             "Straftaten je Einwohner",          "je 1.000 Einwohner"),
]

# Bundestagswahl als gestapelte Balken: Parteien in fester Reihenfolge, Rest = Sonstige
WAHL = ("bundestagswahl", "Politik", "Bundestagswahl", "bundestagswahlen", "Stimmenanteil in %")
PARTEIEN = ["CDU", "SPD", "DIE LINKE", "GRÜNE", "FDP", "AfD", "BSW"]


def tabelle(m: pd.DataFrame, gebiete: list, spalte: str, zeiten: list) -> dict:
    """Gebiet -> Liste der Werte in Zeitreihenfolge (None für fehlend)."""
    t = m.pivot(index="gebiet", columns="zeitpunkt", values=spalte)[zeiten]
    zahl = spalte == "wert"
    return {g: [None if pd.isna(x) else (round(float(x), 4) if zahl else x) for x in t.loc[g]] for g in gebiete}


def daten_zusammenstellen(strecke: pd.DataFrame) -> dict:
    daten = pd.concat([
        pd.read_csv(PROCESSED / d, dtype={"nummer": str, "zeitpunkt": str}, parse_dates=["datum"])
        for d in ["kleinraeumig_lang.csv", "satellit_lang.csv"]
    ], ignore_index=True)
    umfrage = set(pd.read_csv(PROCESSED / "indikatoren.csv").query("umfrage")["indikator"])

    gebiete = list(dict.fromkeys(strecke["ortsteil"])) + [STADT]
    daten = daten[daten["gebiet"].isin(gebiete)]
    bezirk = daten.dropna(subset=["stadtbezirk"]).drop_duplicates("gebiet").set_index("gebiet")["stadtbezirk"]

    def zeitachse(m):
        zeiten = m.sort_values(["jahr", "datum"]).drop_duplicates("zeitpunkt")
        return zeiten["zeitpunkt"].tolist(), zeiten["jahr"].astype(int).tolist()

    kennzahlen, werte = [], {}
    for kid, thema, titel, indikator, merkmal, einheit in KENNZAHLEN:
        m = daten[(daten["indikator"] == indikator) & (daten["merkmal"] == merkmal)]
        if m.empty:
            raise ValueError(f"Kennzahl {kid}: {indikator} / {merkmal} nicht gefunden")
        z, j = zeitachse(m)
        werte[kid] = {"z": z, "j": j, "w": tabelle(m, gebiete, "wert", z), "h": tabelle(m, gebiete, "hinweis", z)}
        kennzahlen.append({"id": kid, "thema": thema, "titel": titel, "einheit": einheit, "typ": "linie",
                           "indikator": indikator, "zeitart": m["zeitart"].iloc[0], "umfrage": indikator in umfrage})

    # Wahl: je Partei eine Tabelle, dazu "Sonstige" als Rest zu 100 %
    kid, thema, titel, indikator, einheit = WAHL
    w = daten[daten["indikator"] == indikator]
    z, j = zeitachse(w)
    breit = lambda merkmal: w[w["merkmal"] == merkmal].pivot(index="gebiet", columns="zeitpunkt", values="wert")[z]
    anteile = {partei: breit(f"Stimmenanteile {partei}") for partei in PARTEIEN}
    anteile["Sonstige"] = (100 - sum(a.fillna(0) for a in anteile.values())).clip(lower=0)
    als_liste = lambda t: {g: [None if pd.isna(x) else round(float(x), 4) for x in t.loc[g]] for g in gebiete}
    werte[kid] = {"z": z, "j": j, "parteien": list(anteile),
                  "w": {p: als_liste(t) for p, t in anteile.items()},
                  "beteiligung": als_liste(breit("Wahlbeteiligung"))}
    kennzahlen.append({"id": kid, "thema": thema, "titel": titel, "einheit": einheit, "typ": "parteien",
                       "indikator": indikator, "zeitart": "wahl", "umfrage": False})

    return {
        "linie": LINIE,
        "stadt": STADT,
        "stops": [
            {"name": s["name"], "ortsteil": s["ortsteil"], "bezirk": bezirk[s["ortsteil"]]}
            for s in strecke.to_dict("records")
        ],
        "kennzahlen": kennzahlen,
        "daten": werte,
    }


# ============================================================
# ABLAUF
# ============================================================

def main() -> None:
    strecke = strecke_bestimmen()
    print(f"Linie {LINIE}: {len(strecke)} Haltestellen, {strecke['ortsteil'].nunique()} Ortsteile")

    inhalt = daten_zusammenstellen(strecke)
    html = VORLAGE.read_text(encoding="utf-8").replace(
        "/*DATEN*/null", json.dumps(inhalt, ensure_ascii=False, separators=(",", ":"))
    )
    ZIEL.write_text(html, encoding="utf-8")
    print(f"Gespeichert: {ZIEL} ({ZIEL.stat().st_size / 1e6:.1f} MB)")
    webbrowser.open(ZIEL.resolve().as_uri())


if __name__ == "__main__":
    main()
