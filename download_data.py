"""Lädt die Rohdaten für das Projekt „Gipfel und Talfahrt der Linie 8".

Aufruf im Projektordner:
    uv run python download_data.py            # lädt nur, was noch fehlt
    uv run python download_data.py --force    # lädt alles neu

Die Dateien landen in data/raw/. Welche Daten geladen werden, steht
im Abschnitt KONFIGURATION. Neue Quellen werden dort hinzugefügt.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import requests

# Workaround: Ist SSLKEYLOGFILE gesetzt, scheitert
# jede HTTPS-Verbindung mit PermissionError. Wirkt nur für dieses Skript.
os.environ.pop("SSLKEYLOGFILE", None)


# ============================================================
# KONFIGURATION
# ============================================================

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"

# Kleinräumige Statistik (Ortsteile + Stadtbezirke), eine CSV je Indikator.
# Kategorie- und Rubriknummer stehen in der URL auf dem Open-Data-Portal.
KDVALUES_URL = "https://statistik.leipzig.de/opendata/api/kdvalues"
INDIKATOREN = {
    # Name der Datei:      (kategorie_nr, rubrik_nr)
    "einwohnerdichte":     (2, 9),
    "einwohner":           (2, 1),   # nur Hauptwohnsitze; (2, 6) wären Haupt- + Nebenwohnsitze
    "geborene_gestorbene": (3, 1),
    "schulabschluesse":    (5, 3),   # Umfragedaten
    "straftaten":          (12, 1),
    # hier weitere ergänzen, z. B. Arbeitslose oder Einwohner nach Alter
}

# Wahlen liegen nicht je Jahr vor, sondern je Wahltermin (periode=d statt y).
# Gleiches Schema wie oben, landen ebenfalls in kleinraeumig/.
WAHLEN = {
    "landtagswahlen":      (15, 4),
    # weitere: Europa (15, 1), Bundestag (15, 3), Stadtrat (15, 5), OBM (15, 7)
}

# Einzelne Dateien mit fester URL
DATEIEN = {
    "geodaten/ortsteile.geojson": (
        "https://static.leipzig.de/fileadmin/mediendatenbank/leipzig-de/Stadt/"
        "02.1_Dez1_Allgemeine_Verwaltung/12_Statistik_und_Wahlen/Geodaten/"
        "Ortsteile_Leipzig_UTM33N.json"
    ),
    "geodaten/stadtbezirke.geojson": (
        "https://static.leipzig.de/fileadmin/mediendatenbank/leipzig-de/Stadt/"
        "02.1_Dez1_Allgemeine_Verwaltung/12_Statistik_und_Wahlen/Geodaten/"
        "Stadtbezirke_Leipzig_UTM33N.json"
    ),
    # LVB-Fahrplan im GTFS-Format, Stand 28.12.2022 (neuester auf dem Portal)
    "gtfs/lvb_gtfs.zip": (
        "https://opendata.leipzig.de/dataset/8803f612-2ce1-4643-82d1-213434889200/"
        "resource/b38955c4-431c-4e8b-a4ef-9964a3a2c95d/download/gtfsmdvlvb.zip"
    ),
}

# Datensätze, deren Download-Link erst über die Portal-API gesucht wird
CKAN_API = "https://opendata.leipzig.de/api/3/action"
CKAN_DATENSAETZE = {
    # Name der Datei:                (Datensatz auf dem Portal, Format)
    "buergerumfrage_2024_person":   ("kommunale-bugerumfrage-2024-personengewichtung", "CSV"),
    "buergerumfrage_2024_haushalt": ("kommunale-bugerumfrage-2024-haushaltsgewichtung", "CSV"),
}


# ============================================================
# FUNKTIONEN
# ============================================================

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "gipfel-und-talfahrt (Portfolio-Projekt, Open-Data-Auswertung)"
PROTOKOLL = RAW_DIR / "download_protokoll.json"


def protokollieren(ziel: Path, url: str) -> None:
    """Hält fest, woher eine Datei stammt und wann sie geladen wurde."""
    eintraege = json.loads(PROTOKOLL.read_text(encoding="utf-8")) if PROTOKOLL.exists() else {}
    eintraege[ziel.relative_to(RAW_DIR).as_posix()] = {
        "url": url,
        "geladen_am": datetime.now().isoformat(timespec="seconds"),
    }
    PROTOKOLL.write_text(json.dumps(eintraege, indent=2, ensure_ascii=False), encoding="utf-8")


def herunterladen(url: str, ziel: Path, params: dict | None = None, force: bool = False) -> None:
    """Lädt eine Datei, falls sie noch nicht vorhanden ist."""
    if ziel.exists() and not force:
        print(f"  vorhanden  {ziel.relative_to(RAW_DIR)}")
        return

    ziel.parent.mkdir(parents=True, exist_ok=True)
    temp = ziel.with_name(ziel.name + ".part")  # halbe Downloads nie unter dem echten Namen

    with SESSION.get(url, params=params, stream=True, timeout=60) as antwort:
        antwort.raise_for_status()
        with open(temp, "wb") as f:
            f.writelines(antwort.iter_content(chunk_size=1024 * 1024))
        tatsaechliche_url = antwort.url

    temp.replace(ziel)
    protokollieren(ziel, tatsaechliche_url)
    print(f"  geladen    {ziel.relative_to(RAW_DIR)}  ({ziel.stat().st_size / 1e6:.1f} MB)")


def ckan_link_finden(datensatz: str, format_: str) -> str:
    """Sucht über die Portal-API den Download-Link einer Ressource."""
    antwort = SESSION.get(f"{CKAN_API}/package_show", params={"id": datensatz}, timeout=60)
    antwort.raise_for_status()
    for ressource in antwort.json()["result"]["resources"]:
        if ressource.get("format", "").upper() == format_.upper():
            return ressource["url"]
    raise ValueError(f"Kein {format_} im Datensatz '{datensatz}' gefunden")


# ============================================================
# ABLAUF
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Rohdaten für das Linie-8-Projekt laden")
    parser.add_argument("--force", action="store_true", help="vorhandene Dateien neu laden")
    force = parser.parse_args().force

    # Jede Aufgabe: (Anzeigename, Funktion ohne Argumente)
    aufgaben = []

    for name, url in DATEIEN.items():
        aufgaben.append((name, lambda url=url, name=name: herunterladen(url, RAW_DIR / name, force=force)))

    kleinraeumig = [(name, nummern, "y") for name, nummern in INDIKATOREN.items()]
    kleinraeumig += [(name, nummern, "d") for name, nummern in WAHLEN.items()]
    for name, (kategorie, rubrik), periode in kleinraeumig:
        params = {"kategorie_nr": kategorie, "rubrik_nr": rubrik, "periode": periode, "format": "csv"}
        ziel = RAW_DIR / "kleinraeumig" / f"{name}.csv"
        aufgaben.append((name, lambda p=params, z=ziel: herunterladen(KDVALUES_URL, z, params=p, force=force)))

    for name, (datensatz, format_) in CKAN_DATENSAETZE.items():
        ziel = RAW_DIR / "buergerumfrage" / f"{name}.{format_.lower()}"

        def ckan_aufgabe(d=datensatz, f=format_, z=ziel):
            if z.exists() and not force:  # spart die API-Anfrage
                print(f"  vorhanden  {z.relative_to(RAW_DIR)}")
                return
            herunterladen(ckan_link_finden(d, f), z, force=force)

        aufgaben.append((name, ckan_aufgabe))

    # Ein Fehler bei einer Quelle stoppt die anderen nicht
    fehler = []
    print(f"Ziel: {RAW_DIR}\n")
    for name, aufgabe in aufgaben:
        try:
            aufgabe()
        except Exception as err:
            print(f"  FEHLER     {name}: {err}")
            fehler.append(name)

    print("\nFertig." if not fehler else f"\nFertig. Fehlgeschlagen: {', '.join(fehler)}")


if __name__ == "__main__":
    main()
