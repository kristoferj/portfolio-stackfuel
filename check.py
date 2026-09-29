import zipfile
import pandas as pd
from pathlib import Path

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

RAW = Path("data/raw")

# Welches Unternehmen steckt hinter 304 und 435?
with zipfile.ZipFile(RAW / "gtfs/lvb_gtfs.zip") as z:
    agency = pd.read_csv(z.open("agency.txt"))
print(agency.loc[agency["agency_id"].isin([304, 435]), ["agency_id", "agency_name"]])

# Nach welchen Gruppen ist die Bürgerumfrage aufgeschlüsselt?
bu = pd.read_csv(RAW / "buergerumfrage/buergerumfrage_2024_person.csv", dtype=str)
gruppen = bu["Merkmal"].str.split(":").str[0].str.strip()
print(gruppen.value_counts())

# Gibt es Stadtbezirke oder Ortsteile?
treffer = bu.loc[bu["Merkmal"].str.contains("Stadtbezirk|Ortsteil", case=False, na=False), "Merkmal"]
print(treffer.unique())