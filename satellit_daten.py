"""Oberflächentemperatur und Vegetation je Ortsteil aus Landsat-Satellitendaten.

Aufruf im Projektordner:
    uv run python satellit_daten.py            # rechnet nur neue Aufnahmen
    uv run python satellit_daten.py --force    # rechnet alles neu

Quelle: Landsat 8/9 Collection 2 Level-2 (USGS), bezogen über den Microsoft
Planetary Computer (frei, ohne Konto). Ausgewertet werden die Sommer
(Juni bis August) ab 2013.

Ergebnisse:
    data/raw/satellit/aufnahmen.csv           Zwischenergebnis je Aufnahme und Gebiet
    data/processed/satellit_lang.csv          gleiches Format wie kleinraeumig_lang.csv
    data/processed/indikatoren_satellit.csv   Beschreibung der neuen Indikatoren
"""

import argparse
import os
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from pystac_client import Client
from rasterio.features import rasterize
from rasterio.windows import from_bounds

# Workaround: Ist SSLKEYLOGFILE gesetzt, scheitert jede HTTPS-Verbindung (siehe download_data.py)
os.environ.pop("SSLKEYLOGFILE", None)


# ============================================================
# EINSTELLUNGEN
# ============================================================

ERSTES_JAHR = 2013           # Start von Landsat 8
MONATE = (6, 8)              # Juni bis August
MAX_WOLKEN_SZENE = 30        # Vorauswahl über die Wolkenangabe der ganzen Szene (%)
MIN_GUELTIG_STADT = 0.80     # Aufnahme zählt nur, wenn so viel der Stadt wolkenfrei ist
MIN_GUELTIG_GEBIET = 0.70    # Gebiet zählt nur, wenn so viel seiner Fläche wolkenfrei ist

RAW = Path("data/raw")
ZWISCHEN = RAW / "satellit" / "aufnahmen.csv"
PROCESSED = Path("data/processed")
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
STADT = "Stadt Leipzig"

# Landsat Collection 2 Level-2: Umrechnung der gespeicherten Ganzzahlen
LST_FAKTOR, LST_OFFSET = 0.00341802, 149.0        # -> Kelvin
SR_FAKTOR, SR_OFFSET = 0.0000275, -0.2            # -> Reflexion
# QA_PIXEL: Bit 0 Füllwert, 1 erweiterte Wolke, 3 Wolke, 4 Wolkenschatten, 5 Schnee
QA_AUSSCHLUSS = (1 << 0) | (1 << 1) | (1 << 3) | (1 << 4) | (1 << 5)


# ============================================================
# 1. Gebiete
# ============================================================

def gebiete_laden() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Ortsteile, Stadtbezirke und Gesamtstadt als Flächen plus Zuordnungstabelle."""
    ortsteile = gpd.read_file(RAW / "geodaten/ortsteile.geojson")
    bezirke = gpd.read_file(RAW / "geodaten/stadtbezirke.geojson")
    bezirk_name = bezirke.set_index("SBZ")["Name"]

    flaechen = pd.concat([
        gpd.GeoDataFrame({"gebiet": ortsteile["Name"], "geometry": ortsteile.geometry}, crs=ortsteile.crs),
        gpd.GeoDataFrame({"gebiet": bezirke["Name"], "geometry": bezirke.geometry}, crs=bezirke.crs),
        gpd.GeoDataFrame({"gebiet": [STADT], "geometry": [ortsteile.union_all()]}, crs=ortsteile.crs),
    ], ignore_index=True)

    info = pd.concat([
        pd.DataFrame({"gebiet": ortsteile["Name"], "ebene": "Ortsteil", "nummer": ortsteile["OT"],
                      "stadtbezirk": ortsteile["OT"].str[0].map(bezirk_name)}),
        pd.DataFrame({"gebiet": bezirke["Name"], "ebene": "Stadtbezirk", "nummer": bezirke["SBZ"],
                      "stadtbezirk": bezirke["Name"]}),
        pd.DataFrame({"gebiet": [STADT], "ebene": ["Stadt"], "nummer": [None], "stadtbezirk": [None]}),
    ], ignore_index=True)
    return flaechen, info


# ============================================================
# 2. Aufnahmen suchen und auswerten
# ============================================================

def aufnahmen_suchen(flaechen: gpd.GeoDataFrame) -> list:
    katalog = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    umriss = flaechen.to_crs(4326).union_all().envelope.__geo_interface__
    items = []
    for jahr in range(ERSTES_JAHR, date.today().year + 1):
        suche = katalog.search(
            collections=["landsat-c2-l2"],
            intersects=umriss,
            datetime=f"{jahr}-{MONATE[0]:02d}-01/{jahr}-{MONATE[1]:02d}-31",
            query={"eo:cloud_cover": {"lt": MAX_WOLKEN_SZENE}, "platform": {"in": ["landsat-8", "landsat-9"]}},
        )
        items += list(suche.items())
    return sorted(items, key=lambda i: i.datetime)


def band_lesen(item, band: str, flaechen: gpd.GeoDataFrame):
    """Liest nur den Ausschnitt um Leipzig aus der Cloud-optimierten Datei."""
    with rasterio.open(item.assets[band].href) as src:
        ausschnitt = from_bounds(*flaechen.to_crs(src.crs).total_bounds, transform=src.transform)
        ausschnitt = ausschnitt.round_offsets().round_lengths()
        return src.read(1, window=ausschnitt, boundless=True, fill_value=0), src.window_transform(ausschnitt), src.crs


def aufnahme_auswerten(item, flaechen: gpd.GeoDataFrame) -> pd.DataFrame | None:
    st, transform, crs = band_lesen(item, "lwir11", flaechen)
    qa, _, _ = band_lesen(item, "qa_pixel", flaechen)
    rot, _, _ = band_lesen(item, "red", flaechen)
    nir, _, _ = band_lesen(item, "nir08", flaechen)

    gueltig = (st > 0) & ((qa & QA_AUSSCHLUSS) == 0)
    lst = st * LST_FAKTOR + LST_OFFSET - 273.15
    r = rot * SR_FAKTOR + SR_OFFSET
    n = nir * SR_FAKTOR + SR_OFFSET
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (n - r) / (n + r)
    gueltig &= np.isfinite(ndvi)

    # Jedes Gebiet einzeln auf das Pixelraster bringen (Ortsteile und Bezirke überlappen sich)
    geo = flaechen.to_crs(crs)
    zeilen = []
    for gebiet, geometrie in zip(geo["gebiet"], geo.geometry):
        maske = rasterize([(geometrie, 1)], out_shape=st.shape, transform=transform, fill=0, dtype="uint8") == 1
        anteil = gueltig[maske].mean() if maske.any() else 0.0
        zeilen.append({
            "gebiet": gebiet,
            "anteil_gueltig": anteil,
            "lst": lst[maske & gueltig].mean() if anteil > 0 else np.nan,
            "ndvi": ndvi[maske & gueltig].mean() if anteil > 0 else np.nan,
        })
    df = pd.DataFrame(zeilen)

    stadt = df.loc[df["gebiet"] == STADT].iloc[0]
    if stadt["anteil_gueltig"] < MIN_GUELTIG_STADT:
        return None
    df["abweichung"] = df["lst"] - stadt["lst"]
    df.insert(0, "aufnahme", item.id)
    df.insert(1, "datum", item.datetime.date().isoformat())
    return df


# ============================================================
# 3. Je Jahr zusammenfassen, ins lange Format bringen
# ============================================================

def jahreswerte(aufnahmen: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    ok = aufnahmen[aufnahmen["anteil_gueltig"] >= MIN_GUELTIG_GEBIET].copy()
    ok["jahr"] = pd.to_datetime(ok["datum"]).dt.year

    jahr = ok.groupby(["gebiet", "jahr"]).agg(
        lst=("lst", "mean"), abweichung=("abweichung", "mean"), ndvi=("ndvi", "mean"), anzahl=("aufnahme", "nunique"),
    ).reset_index()

    merkmale = [
        ("oberflaechentemperatur", "abweichung", "Abweichung vom Stadtmittel (°C)"),
        ("oberflaechentemperatur", "lst", "Mittlere Oberflächentemperatur (°C)"),
        ("oberflaechentemperatur", "anzahl", "Anzahl ausgewerteter Aufnahmen"),
        ("vegetation", "ndvi", "Vegetationsindex NDVI (0 = kahl, 1 = dicht grün)"),
    ]
    teile = []
    for indikator, spalte, merkmal in merkmale:
        t = jahr[["gebiet", "jahr", spalte]].rename(columns={spalte: "wert"})
        t["indikator"], t["merkmal"] = indikator, merkmal
        teile.append(t)
    lang = pd.concat(teile, ignore_index=True)

    # Jedes Gebiet bekommt jedes Jahr, fehlende Jahre mit Hinweis
    alle = pd.MultiIndex.from_product(
        [[m[0] + "|" + m[2] for m in merkmale], info["gebiet"], sorted(jahr["jahr"].unique())],
        names=["schluessel", "gebiet", "jahr"],
    ).to_frame(index=False)
    alle[["indikator", "merkmal"]] = alle["schluessel"].str.split("|", expand=True)
    lang = alle.drop(columns="schluessel").merge(lang, on=["indikator", "merkmal", "gebiet", "jahr"], how="left")

    lang["zeichen"] = None
    lang["hinweis"] = np.where(lang["wert"].isna(), "keine wolkenfreie Aufnahme in diesem Sommer", None)
    lang["zeitart"] = "jahr"
    lang["zeitpunkt"] = lang["jahr"].astype(str)
    lang["datum"] = pd.NaT
    lang = lang.merge(info, on="gebiet", validate="many_to_one")

    spalten = ["indikator", "gebiet", "ebene", "nummer", "stadtbezirk", "merkmal",
               "zeitart", "zeitpunkt", "datum", "jahr", "wert", "zeichen", "hinweis"]
    return lang[spalten].sort_values(["indikator", "ebene", "nummer", "gebiet", "merkmal", "jahr"]).reset_index(drop=True)


INDIKATOREN = pd.DataFrame([
    ("oberflaechentemperatur", "Oberflächentemperatur im Sommer (Satellit)", "Umwelt", "jahr", False),
    ("vegetation", "Vegetation im Sommer (Satellit)", "Umwelt", "jahr", False),
], columns=["indikator", "titel", "thema", "zeitart", "umfrage"])


# ============================================================
# ABLAUF
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Satellitendaten je Ortsteil auswerten")
    parser.add_argument("--force", action="store_true", help="alle Aufnahmen neu auswerten")
    force = parser.parse_args().force

    flaechen, info = gebiete_laden()
    fertig = pd.read_csv(ZWISCHEN) if ZWISCHEN.exists() and not force else pd.DataFrame()
    bekannt = set(fertig["aufnahme"]) if len(fertig) else set()

    items = aufnahmen_suchen(flaechen)
    neu = [i for i in items if i.id not in bekannt]
    print(f"{len(items)} Sommeraufnahmen gefunden, {len(neu)} davon neu.\n")

    ergebnisse = [fertig] if len(fertig) else []
    for k, item in enumerate(neu, 1):
        try:
            df = aufnahme_auswerten(item, flaechen)
        except Exception as err:
            print(f"  [{k}/{len(neu)}] FEHLER     {item.id}: {err}")
            continue
        if df is None:
            # Als "verworfen" merken, damit sie beim nächsten Lauf nicht erneut geladen wird
            df = pd.DataFrame({"aufnahme": [item.id], "datum": [item.datetime.date().isoformat()],
                               "gebiet": [None], "anteil_gueltig": [np.nan]})
            print(f"  [{k}/{len(neu)}] verworfen  {item.id} (zu wenig wolkenfreie Fläche über der Stadt, Wolken oder Bildrand)")
        else:
            print(f"  [{k}/{len(neu)}] ausgewertet {item.id}")
        ergebnisse.append(df)

    aufnahmen = pd.concat(ergebnisse, ignore_index=True)
    ZWISCHEN.parent.mkdir(parents=True, exist_ok=True)
    aufnahmen.to_csv(ZWISCHEN, index=False)

    gueltige = aufnahmen.dropna(subset=["gebiet"])
    print(f"\n{gueltige['aufnahme'].nunique()} von {aufnahmen['aufnahme'].nunique()} Aufnahmen verwendbar.")
    print(gueltige.drop_duplicates("aufnahme").assign(jahr=lambda d: d["datum"].str[:4]).groupby("jahr").size().to_string())

    PROCESSED.mkdir(parents=True, exist_ok=True)
    lang = jahreswerte(gueltige, info)
    lang.to_csv(PROCESSED / "satellit_lang.csv", index=False, encoding="utf-8")
    INDIKATOREN.to_csv(PROCESSED / "indikatoren_satellit.csv", index=False, encoding="utf-8")
    print(f"\nGespeichert: {PROCESSED / 'satellit_lang.csv'} ({len(lang):,} Zeilen)")


if __name__ == "__main__":
    main()
