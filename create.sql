PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS poop;
DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS town;
DROP TABLE IF EXISTS country;

-- Država (ISO 3166-1 alpha-2)
CREATE TABLE country(
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    continent   TEXT,
    population  INTEGER,
    areaKm2     REAL
);

-- Naselje (id = GeoNames ID); poop se preslikava na najbliže naselje
CREATE TABLE town(
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    admin1      TEXT,
    countryCode TEXT REFERENCES country(code),
    latitude    REAL,
    longitude   REAL,
    population  INTEGER
);

CREATE TABLE user(
    id              INTEGER PRIMARY KEY,
    username        TEXT,
    poopsCount      INTEGER,
    pinColor        TEXT,
    createdAt       DATETIME,
    badgesCount     INTEGER,
    followersCount  INTEGER,
    followingsCount INTEGER,
    countryCount    INTEGER,
    isPro           BOOLEAN,
    isPrivate       BOOLEAN,
    poopsPerDay     REAL
);

CREATE TABLE poop(
    id          INTEGER PRIMARY KEY,
    createdAt   DATETIME,
    latitude    REAL,
    longitude   REAL,
    isAirplane  BOOLEAN,
    note        TEXT,
    pinColor    TEXT,
    place       TEXT,
    rating      INTEGER,
    aroma       TEXT,
    userId      INTEGER NOT NULL REFERENCES user(id),
    townId      INTEGER REFERENCES town(id)
);

CREATE INDEX idx_poop_user ON poop(userId);
CREATE INDEX idx_poop_town ON poop(townId);
CREATE INDEX idx_town_country ON town(countryCode);
