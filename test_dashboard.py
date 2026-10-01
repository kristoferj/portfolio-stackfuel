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

def daten_zusammenstellen(strecke: pd.DataFrame) -> dict:
    daten = pd.read_csv(
        PROCESSED / "kleinraeumig_lang.csv",
        dtype={"nummer": str, "zeitpunkt": str},
        parse_dates=["datum"],
    )
    indikatoren = pd.read_csv(PROCESSED / "indikatoren.csv")

    gebiete = list(dict.fromkeys(strecke["ortsteil"])) + [STADT]
    daten = daten[daten["gebiet"].isin(gebiete)]
    bezirk = daten.dropna(subset=["stadtbezirk"]).drop_duplicates("gebiet").set_index("gebiet")["stadtbezirk"]

    werte = {}
    for indikator, teil in daten.groupby("indikator", sort=False):
        werte[indikator] = {}
        for merkmal, m in teil.groupby("merkmal", sort=False):
            m = m.sort_values(["jahr", "datum"])
            zeiten = m.drop_duplicates("zeitpunkt")[["zeitpunkt", "jahr"]]
            # Tabellen Gebiet x Zeitpunkt für Wert und Zeichen
            w = m.pivot(index="gebiet", columns="zeitpunkt", values="wert")[zeiten["zeitpunkt"]]
            h = m.pivot(index="gebiet", columns="zeitpunkt", values="hinweis")[zeiten["zeitpunkt"]]
            werte[indikator][merkmal] = {
                "z": zeiten["zeitpunkt"].tolist(),
                "j": zeiten["jahr"].astype(int).tolist(),
                "w": {g: [None if pd.isna(x) else round(float(x), 4) for x in w.loc[g]] for g in gebiete},
                "h": {g: [None if pd.isna(x) else x for x in h.loc[g]] for g in gebiete},
            }

    return {
        "linie": LINIE,
        "stadt": STADT,
        "stops": [
            {"name": s["name"], "ortsteil": s["ortsteil"], "bezirk": bezirk[s["ortsteil"]]}
            for s in strecke.to_dict("records")
        ],
        "indikatoren": [
            {**ind, "merkmale": list(werte[ind["indikator"]].keys())}
            for ind in indikatoren.to_dict("records")
        ],
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
