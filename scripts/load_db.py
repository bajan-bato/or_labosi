import json
import sqlite3

from poopmap_api import ROOT

DB = ROOT / "db.db"
USER_COLS = ["id", "username", "poopsCount", "pinColor", "createdAt", "badgesCount",
             "followersCount", "followingsCount", "countryCount", "isPro", "isPrivate", "poopsPerDay"]
POOP_COLS = ["id", "createdAt", "latitude", "longitude", "isAirplane", "note", "pinColor",
             "place", "rating", "aroma", "userId", "townId"]
COUNTRY_COLS = ["code", "name", "continent", "population", "areaKm2"]
TOWN_COLS = ["id", "name", "admin1", "countryCode", "latitude", "longitude", "population"]


def read_existing(con, table):
    try:
        cur = con.execute(f"SELECT * FROM {table}")
    except sqlite3.OperationalError:
        return {}
    cols = [d[0] for d in cur.description]
    key = cols[0]
    return {r[key]: r for r in (dict(zip(cols, row)) for row in cur)}


def as_int_bool(v):
    return None if v is None else int(bool(v))


def main():
    con = sqlite3.connect(DB)
    old = {t: read_existing(con, t) for t in ("country", "town", "user", "poop")}
    print("Postojeće:", {t: len(v) for t, v in old.items()})

    users = dict(old["user"])
    for u in json.loads((ROOT / "users100k.json").read_text(encoding="utf-8")):
        if u.get("fetchStatus") != "success" and u["id"] in users:
            continue  # ne prepisuj stari ispravan zapis praznim
        users[u["id"]] = u

    poops = dict(old["poop"])
    for p in json.loads((ROOT / "poops100k.json").read_text(encoding="utf-8")):
        p = dict(p)
        p["townId"] = old["poop"].get(p["id"], {}).get("townId")  # zadrži preslikavanje
        poops[p["id"]] = p

    # svaki userId mora postojati u user tablici
    for uid in {p["userId"] for p in poops.values()} - users.keys():
        users[uid] = {"id": uid}

    con.executescript((ROOT / "create.sql").read_text(encoding="utf-8"))

    def insert(table, cols, rows, fix=lambda r: r):
        con.executemany(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [tuple(fix(r).get(c) for c in cols) for r in rows])

    insert("country", COUNTRY_COLS, old["country"].values())
    insert("town", TOWN_COLS, old["town"].values())
    insert("user", USER_COLS, sorted(users.values(), key=lambda u: u["id"]),
           lambda u: {**u, "isPro": as_int_bool(u.get("isPro")),
                      "isPrivate": as_int_bool(u.get("isPrivate"))})
    insert("poop", POOP_COLS, sorted(poops.values(), key=lambda p: p["id"]),
           lambda p: {**p, "isAirplane": as_int_bool(p.get("isAirplane"))})
    con.commit()

    bad = con.execute("PRAGMA foreign_key_check").fetchall()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("country", "town", "user", "poop")}
    print("Upisano:", counts, "| FK greške:", len(bad))
    con.close()


if __name__ == "__main__":
    main()
