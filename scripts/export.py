"""Iz db.db generira exporte u exports/ i SQL dump u korijenu.

exports/poopmap.json   - SVI podaci u jednom JSON-u: user (1) -> (N) poops,
                         a svaki poop nosi ugniježđen svoj town i country (N:1)
exports/poopmap.csv    - SVI podaci u jednom CSV-u: jedan redak po poopu,
                         spojen s korisnikom, naseljem i državom
exports/countries.json - country (1) -> (N) towns, sa statistikom poopsa
exports/countries.csv  - isto, jedan redak po naselju
dump.sql               - SQL dump baze (UTF-8)
"""
import csv
import json
import sqlite3
from collections import defaultdict

from poopmap_api import ROOT

DB = ROOT / "db.db"
OUT = ROOT / "exports"

USER_F = ["id", "username", "poopsCount", "pinColor", "createdAt", "badgesCount",
          "followersCount", "followingsCount", "countryCount", "isPro", "isPrivate", "poopsPerDay"]
POOP_F = ["id", "createdAt", "latitude", "longitude", "isAirplane", "note", "pinColor",
          "place", "rating", "aroma", "userId", "townId"]
TOWN_F = ["id", "name", "admin1", "countryCode", "latitude", "longitude", "population"]
COUNTRY_F = ["code", "name", "continent", "population", "areaKm2"]
BOOLS = {"isPro", "isPrivate", "isAirplane"}


def fetch(con, sql, fields):
    out = []
    for r in con.execute(sql):
        d = dict(zip(fields, r))
        for b in BOOLS & d.keys():
            if d[b] is not None:
                d[b] = bool(d[b])
        out.append(d)
    return out


def csv_val(v):
    return str(v).lower() if isinstance(v, bool) else v


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([csv_val(v) for v in r])


def main():
    OUT.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    users = fetch(con, f"SELECT {','.join(USER_F)} FROM user ORDER BY id", USER_F)
    poops = fetch(con, f"SELECT {','.join(POOP_F)} FROM poop ORDER BY userId, createdAt DESC", POOP_F)
    towns = {t["id"]: t for t in fetch(con, f"SELECT {','.join(TOWN_F)} FROM town ORDER BY countryCode, name", TOWN_F)}
    countries = {c["code"]: c for c in fetch(con, f"SELECT {','.join(COUNTRY_F)} FROM country ORDER BY name", COUNTRY_F)}

    by_user = defaultdict(list)
    for p in poops:
        by_user[p["userId"]].append(p)

    # --- statistika po naselju / državi (za countries.*) ---
    t_poops, t_users = defaultdict(int), defaultdict(set)
    for p in poops:
        if p["townId"] is not None:
            t_poops[p["townId"]] += 1
            t_users[p["townId"]].add(p["userId"])
    c_poops, c_users = defaultdict(int), defaultdict(set)
    for tid, t in towns.items():
        c_poops[t["countryCode"]] += t_poops[tid]
        c_users[t["countryCode"]] |= t_users[tid]

    # --- 1) sve u jednom: poopmap.json ---
    def town_obj(tid):
        if tid is None:
            return None
        t = towns[tid]
        return {**{k: t[k] for k in TOWN_F if k != "countryCode"},
                "country": countries.get(t["countryCode"])}

    write_json("poopmap.json", [
        {**u, "poops": [{**{k: p[k] for k in POOP_F if k not in ("userId", "townId")},
                         "town": town_obj(p["townId"])} for p in by_user.get(u["id"], [])]}
        for u in users])

    # --- 2) sve u jednom: poopmap.csv ---
    header = ([f"user_{f}" for f in USER_F]
              + [f"poop_{f}" for f in POOP_F if f not in ("userId", "townId")]
              + [f"town_{f}" for f in TOWN_F if f != "countryCode"]
              + [f"country_{f}" for f in COUNTRY_F])

    def poop_rows():
        empty_t = [None] * (len(TOWN_F) - 1)
        empty_c = [None] * len(COUNTRY_F)
        for u in users:
            for p in by_user.get(u["id"], []):
                t = towns.get(p["townId"])
                c = countries.get(t["countryCode"]) if t else None
                yield ([u[k] for k in USER_F]
                       + [p[k] for k in POOP_F if k not in ("userId", "townId")]
                       + ([t[k] for k in TOWN_F if k != "countryCode"] if t else empty_t)
                       + ([c[k] for k in COUNTRY_F] if c else empty_c))

    write_csv("poopmap.csv", header, poop_rows())

    # --- 3) country -> towns ---
    towns_by_c = defaultdict(list)
    for tid, t in towns.items():
        towns_by_c[t["countryCode"]].append({**{k: t[k] for k in TOWN_F if k != "countryCode"},
                                              "poopsCount": t_poops[tid], "usersCount": len(t_users[tid])})

    def per_million(n, pop):
        return round(n * 1e6 / pop, 2) if pop else None

    country_out = []
    for cc, c in countries.items():
        country_out.append({**c, "poopsCount": c_poops[cc], "usersCount": len(c_users[cc]),
                            "poopsPerMillion": per_million(c_poops[cc], c["population"]),
                            "towns": sorted(towns_by_c[cc], key=lambda t: -t["poopsCount"])})
    write_json("countries.json", country_out)
    write_csv("countries.csv",
              [f"country_{f}" for f in COUNTRY_F] + ["country_poopsCount", "country_usersCount",
               "country_poopsPerMillion"] + [f"town_{f}" for f in TOWN_F if f != "countryCode"]
              + ["town_poopsCount", "town_usersCount"],
              ([c[k] for k in COUNTRY_F] + [c["poopsCount"], c["usersCount"], c["poopsPerMillion"]]
               + [t[k] for k in TOWN_F if k != "countryCode"] + [t["poopsCount"], t["usersCount"]]
               for c in country_out for t in c["towns"]))

    # --- SQL dump ---
    with open(ROOT / "dump.sql", "w", encoding="utf-8", newline="\n") as f:
        for line in con.iterdump():
            f.write(line + "\n")
    con.close()
    print(f"Export: {len(users)} korisnika, {len(poops)} poopsa, {len(towns)} naselja, "
          f"{len(countries)} država -> exports/, dump.sql")


if __name__ == "__main__":
    main()
