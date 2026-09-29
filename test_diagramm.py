"""Testdiagramm: ein Indikator entlang einer Straßenbahnlinie.

Aufruf im Projektordner:
    uv add geopandas plotly
    uv run python test_diagramm.py

Ergebnis: test_diagramm.html (öffnet sich im Browser)
"""

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.express as px

# ============================================================
# EINSTELLUNGEN
# ============================================================

LINIE = "8"
UNTERNEHMEN = "Leipziger Verkehrsbetriebe"
INDIKATOR = "einwohnerdichte"   # Dateiname in data/raw/kleinraeumig/
MERKMAL = "Einwohnerdichte"     # Wert aus der Spalte Sachmerkmal
EINHEIT = "Einwohner je km²"

RAW = Path("data/raw")


# ============================================================
# 1. Haltestellen der Linie aus dem GTFS holen
# ============================================================

def gtfs_lesen(z: zipfile.ZipFile, datei: str, **kwargs) -> pd.DataFrame:
    # Alles als Text lesen, damit IDs wie "00123" nicht zu Zahlen werden
    return pd.read_csv(z.open(datei), dtype=str, encoding="utf-8-sig", **kwargs)


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

# Alle Fahrten der Linie mit ihren Halten
fahrten = trips.loc[trips["route_id"] == route["route_id"].iloc[0], "trip_id"]
halte = stop_times[stop_times["trip_id"].isin(fahrten)].copy()
halte["stop_sequence"] = halte["stop_sequence"].astype(int)
halte = halte.merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id")
halte = halte.sort_values(["trip_id", "stop_sequence"])

# Vorlage-Fahrt: die längste Halte-Folge, die am häufigsten gefahren wird.
# So fallen Kurzfahrten (z. B. nur bis zum Depot) und seltene Varianten raus.
folgen = halte.groupby("trip_id")["stop_name"].apply(tuple)
laengste = folgen[folgen.str.len() == folgen.str.len().max()]
vorlage_trip = laengste.value_counts().index[0]
vorlage_id = laengste[laengste == vorlage_trip].index[0]

strecke = halte[halte["trip_id"] == vorlage_id].reset_index(drop=True)
strecke["position"] = range(1, len(strecke) + 1)
print(f"Linie {LINIE}: {len(strecke)} Haltestellen, {strecke['stop_name'].iloc[0]} → {strecke['stop_name'].iloc[-1]}")


# ============================================================
# 2. Haltestellen den Ortsteilen zuordnen
# ============================================================

punkte = gpd.GeoDataFrame(
    strecke,
    geometry=gpd.points_from_xy(strecke["stop_lon"].astype(float), strecke["stop_lat"].astype(float)),
    crs="EPSG:4326",  # GTFS nutzt immer GPS-Koordinaten
)
ortsteile = gpd.read_file(RAW / "geodaten/ortsteile.geojson")
punkte = punkte.to_crs(ortsteile.crs)  # beide ins gleiche Koordinatensystem

strecke = gpd.sjoin(punkte, ortsteile[["Name", "geometry"]], how="left", predicate="within")
strecke = strecke.rename(columns={"Name": "ortsteil"}).drop(columns=["index_right"])

ohne_ortsteil = strecke[strecke["ortsteil"].isna()]
if len(ohne_ortsteil):
    print("Ohne Ortsteil (evtl. außerhalb der Stadtgrenze):", ohne_ortsteil["stop_name"].tolist())


# ============================================================
# 3. Indikator anhängen
# ============================================================

daten = pd.read_csv(RAW / "kleinraeumig" / f"{INDIKATOR}.csv", dtype=str)
daten["Gebiet"] = daten["Gebiet"].str.strip()
daten["Sachmerkmal"] = daten["Sachmerkmal"].str.strip()
daten = daten[daten["Sachmerkmal"] == MERKMAL]

jahr = max(c for c in daten.columns if c.isdigit())  # neuestes Jahr
werte = daten[["Gebiet", jahr]].rename(columns={"Gebiet": "ortsteil", jahr: "wert"})
werte["wert"] = pd.to_numeric(werte["wert"].str.replace(",", "."), errors="coerce")

strecke = strecke.merge(werte, on="ortsteil", how="left")
fehlend = strecke.loc[strecke["wert"].isna() & strecke["ortsteil"].notna(), "ortsteil"].unique()
if len(fehlend):
    print("Kein Wert gefunden für:", list(fehlend))


# ============================================================
# 4. Diagramm
# ============================================================

fig = px.line(
    strecke,
    x="position",
    y="wert",
    markers=True,
    hover_name="stop_name",
    hover_data={"ortsteil": True, "position": False, "wert": ":,.0f"},
    title=f"{MERKMAL} entlang der Linie {LINIE} ({jahr})",
    labels={"wert": EINHEIT, "position": ""},
)
fig.update_traces(line_shape="hv")  # Stufen: Wert gilt für den ganzen Ortsteil
fig.update_xaxes(
    tickvals=strecke["position"],
    ticktext=strecke["stop_name"],
    tickangle=-60,
)
fig.update_layout(template="simple_white", height=600, margin=dict(b=200))

fig.write_html("test_diagramm.html", auto_open=True)
print("Gespeichert: test_diagramm.html")
