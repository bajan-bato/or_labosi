"""Prebacuje db.db (SQLite) u PostgreSQL bazu iz DATABASE_URL (.env).

Tablice se brišu i ponovno stvaraju, podaci se kopiraju naredbom COPY.
Stvara se i materijalizirani pogled poopmap_flat (jedan redak po poopu spojen s
korisnikom, naseljem i državom) - isti stupci kao exports/poopmap.csv - koji koristi
web sučelje. Stupac search_text (s trigram indeksom) služi za brzu wildcard pretragu.

Uporaba: python load_pg.py   (pokreće se nakon geocode.py)
"""
import csv
import io
import os
import sqlite3

import psycopg2

from poopmap_api import ROOT  # učitava i .env

DB = ROOT / "db.db"

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CASCADE briše i pogled poopmap_flat (bio on običan ili materijaliziran)
DROP TABLE IF EXISTS poop, "user", town, country CASCADE;

CREATE TABLE country(
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    continent   TEXT,
    population  BIGINT,
    "areaKm2"   DOUBLE PRECISION
);

CREATE TABLE town(
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    admin1        TEXT,
    "countryCode" TEXT REFERENCES country(code),
    latitude      DOUBLE PRECISION,
    longitude     DOUBLE PRECISION,
    population    BIGINT
);

CREATE TABLE "user"(
    id                INTEGER PRIMARY KEY,
    username          TEXT,
    "poopsCount"      INTEGER,
    "pinColor"        TEXT,
    "createdAt"       TIMESTAMPTZ,
    "badgesCount"     INTEGER,
    "followersCount"  INTEGER,
    "followingsCount" INTEGER,
    "countryCount"    INTEGER,
    "isPro"           BOOLEAN,
    "isPrivate"       BOOLEAN,
    "poopsPerDay"     DOUBLE PRECISION
);

CREATE TABLE poop(
    id           INTEGER PRIMARY KEY,
    "createdAt"  TIMESTAMPTZ,
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    "isAirplane" BOOLEAN,
    note         TEXT,
    "pinColor"   TEXT,
    place        TEXT,
    rating       INTEGER,
    aroma        TEXT,
    "userId"     INTEGER NOT NULL REFERENCES "user"(id),
    "townId"     INTEGER REFERENCES town(id)
);

CREATE INDEX idx_poop_user ON poop("userId");
CREATE INDEX idx_poop_town ON poop("townId");
CREATE INDEX idx_town_country ON town("countryCode");
"""

ISO = """to_char({} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')"""

VIEW = f"""
CREATE MATERIALIZED VIEW poopmap_flat AS
SELECT f.*, lower(f::text) AS search_text FROM (   -- search_text: cijeli redak kao tekst (wildcard)
SELECT u.id                AS user_id,
       u.username          AS user_username,
       u."poopsCount"      AS "user_poopsCount",
       u."pinColor"        AS "user_pinColor",
       {ISO.format('u."createdAt"')} AS "user_createdAt",
       u."badgesCount"     AS "user_badgesCount",
       u."followersCount"  AS "user_followersCount",
       u."followingsCount" AS "user_followingsCount",
       u."countryCount"    AS "user_countryCount",
       u."isPro"           AS "user_isPro",
       u."isPrivate"       AS "user_isPrivate",
       u."poopsPerDay"     AS "user_poopsPerDay",
       p.id                AS poop_id,
       {ISO.format('p."createdAt"')} AS "poop_createdAt",
       p.latitude          AS poop_latitude,
       p.longitude         AS poop_longitude,
       p."isAirplane"      AS "poop_isAirplane",
       p.note              AS poop_note,
       p."pinColor"        AS "poop_pinColor",
       p.place             AS poop_place,
       p.rating            AS poop_rating,
       p.aroma             AS poop_aroma,
       t.id                AS town_id,
       t.name              AS town_name,
       t.admin1            AS town_admin1,
       t.latitude          AS town_latitude,
       t.longitude         AS town_longitude,
       t.population        AS town_population,
       c.code              AS country_code,
       c.name              AS country_name,
       c.continent         AS country_continent,
       c.population        AS country_population,
       c."areaKm2"         AS "country_areaKm2"
FROM poop p
JOIN "user" u       ON u.id = p."userId"
LEFT JOIN town t    ON t.id = p."townId"
LEFT JOIN country c ON c.code = t."countryCode"
) f;

CREATE INDEX idx_flat_search ON poopmap_flat USING gin (search_text gin_trgm_ops);
CREATE INDEX idx_flat_poop ON poopmap_flat (poop_id);
"""

# (tablica u SQLite, tablica u PG, stupci, bool stupci)
TABLES = [
    ("country", "country", ["code", "name", "continent", "population", "areaKm2"], []),
    ("town", "town", ["id", "name", "admin1", "countryCode", "latitude", "longitude", "population"], []),
    ("user", '"user"', ["id", "username", "poopsCount", "pinColor", "createdAt", "badgesCount",
                        "followersCount", "followingsCount", "countryCount", "isPro", "isPrivate",
                        "poopsPerDay"], ["isPro", "isPrivate"]),
    ("poop", "poop", ["id", "createdAt", "latitude", "longitude", "isAirplane", "note", "pinColor",
                      "place", "rating", "aroma", "userId", "townId"], ["isAirplane"]),
]


def copy_table(lite, cur, src, dst, cols, bools):
    buf = io.StringIO()
    w = csv.writer(buf)
    bidx = [cols.index(b) for b in bools]
    n = 0
    for row in lite.execute(f'SELECT {",".join(cols)} FROM "{src}"'):
        row = list(row)
        for i in bidx:
            if row[i] is not None:
                row[i] = "t" if row[i] else "f"
        # NULL -> prazno polje bez navodnika, prazan string -> ""
        w.writerow(["\\N" if v is None else v for v in row])
        n += 1
    buf.seek(0)
    collist = ",".join(f'"{c}"' for c in cols)
    cur.copy_expert(f"COPY {dst} ({collist}) FROM STDIN WITH (FORMAT csv, NULL '\\N')", buf)
    return n


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Nedostaje DATABASE_URL u .env")
    lite = sqlite3.connect(DB)
    con = psycopg2.connect(url, sslmode="require")
    with con, con.cursor() as cur:
        cur.execute(SCHEMA)
        for src, dst, cols, bools in TABLES:
            print(f"{dst}: {copy_table(lite, cur, src, dst, cols, bools)} redaka")
        cur.execute(VIEW)
        cur.execute("SELECT count(*) FROM poopmap_flat")
        print("poopmap_flat:", cur.fetchone()[0], "redaka")
    con.close()
    lite.close()


if __name__ == "__main__":
    main()
