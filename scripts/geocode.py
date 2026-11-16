"""Preslikava poopse na najbliže naselje (town) i državu (country) izravno u db.db.

Izvor: GeoNames (CC BY 4.0) - preuzima se automatski u geodata/ ako nedostaje:
  cities1000.zip         - sva naselja s >= 1000 stanovnika
  countryInfo.txt        - države (naziv, kontinent, populacija, površina)
  admin1CodesASCII.txt   - nazivi regija (admin1)

Za svaki poop traži se najbliže naselje (KD-stablo na jediničnoj sferi, tj. prava
udaljenost po velikom krugu). Ne preslikavaju se:
  - skrivene lokacije (0, 0)
  - poopsi u zrakoplovu
Poopsi dalje od MAX_KM od bilo kojeg naselja (more, divljina) dobivaju town
id=0 "wilderness" (bez države).
U bazu se upisuju samo naselja/države koje stvarno imaju poopse.

Uporaba: python geocode.py [--max-km 10]
Pokreće se nakon load_db.py (load_db.py čuva postojeća preslikavanja).
"""
import argparse
import csv
import io
import sqlite3
import urllib.request
import zipfile

import numpy as np
from scipy.spatial import cKDTree

from poopmap_api import ROOT

DB = ROOT / "db.db"
GEO = ROOT / "geodata"
BASE = "https://download.geonames.org/export/dump/"
FILES = ["cities1000.zip", "countryInfo.txt", "admin1CodesASCII.txt"]
EARTH_KM = 6371.0
CONTINENTS = {"AF": "Africa", "AS": "Asia", "EU": "Europe", "NA": "North America",
              "OC": "Oceania", "SA": "South America", "AN": "Antarctica"}
# četvrti, povijesna/napuštena/uništena naselja nisu "town"
SKIP_FEATURES = {"PPLX", "PPLH", "PPLQ", "PPLW", "PPLCH"}
# poopsi dalje od MAX_KM od svakog naselja dobivaju posebno "naselje" bez države
WILDERNESS_ID = 0
WILDERNESS_NAME = "wilderness"


def download():
    GEO.mkdir(exist_ok=True)
    for name in FILES:
        path = GEO / name
        if not path.exists():
            print(f"Preuzimam {name}...")
            urllib.request.urlretrieve(BASE + name, path)


def tsv(lines):
    return csv.reader((l for l in lines if l and not l.startswith("#")),
                      delimiter="\t", quoting=csv.QUOTE_NONE)


def load_geonames():
    with zipfile.ZipFile(GEO / "cities1000.zip") as z:
        text = io.TextIOWrapper(z.open("cities1000.txt"), encoding="utf-8")
        towns = [r for r in tsv(text) if r[7] not in SKIP_FEATURES]
    admin1 = {r[0]: r[1] for r in tsv((GEO / "admin1CodesASCII.txt").read_text(encoding="utf-8").splitlines())}
    countries = {}
    for r in tsv((GEO / "countryInfo.txt").read_text(encoding="utf-8").splitlines()):
        countries[r[0]] = {
            "code": r[0], "name": r[4], "continent": CONTINENTS.get(r[8], r[8]),
            "population": int(r[7]) if r[7] else None,
            "areaKm2": float(r[6]) if r[6] else None,
        }
    return towns, admin1, countries


def unit_xyz(lat, lon):
    lat, lon = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-km", type=float, default=10.0)
    args = ap.parse_args()

    download()
    towns, admin1, countries = load_geonames()
    print(f"GeoNames: {len(towns)} naselja, {len(countries)} država")

    t_lat = np.array([float(r[4]) for r in towns])
    t_lon = np.array([float(r[5]) for r in towns])
    tree = cKDTree(unit_xyz(t_lat, t_lon))

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    poops = con.execute("SELECT id, latitude, longitude, isAirplane FROM poop").fetchall()
    ids = np.array([p[0] for p in poops])
    lat = np.array([p[1] if p[1] is not None else 0.0 for p in poops])
    lon = np.array([p[2] if p[2] is not None else 0.0 for p in poops])
    hidden = (lat == 0) & (lon == 0)
    airplane = np.array([bool(p[3]) for p in poops])

    chord, idx = tree.query(unit_xyz(lat, lon))
    dist_km = 2 * EARTH_KM * np.arcsin(np.clip(chord / 2, 0, 1))
    far = dist_km > args.max_km
    ok = ~hidden & ~airplane & ~far

    used = sorted(set(idx[ok].tolist()))
    town_rows = []
    for i in used:
        r = towns[i]
        cc = r[8]
        town_rows.append((int(r[0]), r[1], admin1.get(f"{cc}.{r[10]}"), cc,
                          float(r[4]), float(r[5]), int(r[14]) if r[14] else None))
    used_cc = {t[3] for t in town_rows}
    missing = used_cc - countries.keys()  # npr. Kosovo (XK) nije uvijek u countryInfo
    for cc in missing:
        countries[cc] = {"code": cc, "name": cc, "continent": None, "population": None, "areaKm2": None}

    with con:
        con.execute("UPDATE poop SET townId = NULL")
        con.execute("DELETE FROM town")
        con.execute("DELETE FROM country")
        con.executemany("INSERT INTO country VALUES (:code, :name, :continent, :population, :areaKm2)",
                        [countries[cc] for cc in sorted(used_cc)])
        con.executemany("INSERT INTO town VALUES (?,?,?,?,?,?,?)", town_rows)
        con.executemany("UPDATE poop SET townId = ? WHERE id = ?",
                        [(int(towns[i][0]), int(pid)) for pid, i in zip(ids[ok], idx[ok])])
        wild = far & ~hidden & ~airplane
        if wild.any():
            con.execute("INSERT INTO town (id, name) VALUES (?, ?)", (WILDERNESS_ID, WILDERNESS_NAME))
            con.executemany("UPDATE poop SET townId = ? WHERE id = ?",
                            [(WILDERNESS_ID, int(pid)) for pid in ids[wild]])

    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print(f"Preslikano: {ok.sum()} / {len(poops)} poopsa -> {len(town_rows)} naselja u {len(used_cc)} država")
    print(f"Nepreslikano: skrivena lokacija {hidden.sum()}, zrakoplov {(airplane & ~hidden).sum()} "
          f"| wilderness (dalje od {args.max_km:g} km): {(far & ~hidden & ~airplane).sum()}")
    print(f"Udaljenost do naselja (km): medijan {np.median(dist_km[ok]):.1f}, "
          f"95. percentil {np.percentile(dist_km[ok], 95):.1f} | FK greške: {len(fk)}")
    if missing:
        print("Države bez podataka u countryInfo:", sorted(missing))
    con.close()


if __name__ == "__main__":
    main()
