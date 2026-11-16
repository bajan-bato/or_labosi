# Poopmap Global Dataset

## Opis skupa podataka
Ovaj skup podataka sadrži javno dostupne informacije o korisnicima i njihovim "poopsima" (lokacijama) s platforme Poopmap. Podaci su prikupljeni putem službenog Poopmap API-ja. Skup je strukturiran kroz četiri entiteta: `user`, `poop`, `town` i `country`.

## Autor
- **Ime i prezime:** Toni Bajan
- **GitHub:** [@bajan-bato](https://github.com/bajan-bato)
- **Kontakt:** toni.bajan@fer.hr

## Verzija skupa
- **Trenutna verzija:** v2.0
- **Datum izdavanja:** 16.11.2026.
- **Broj zapisa:** 18 670 korisnika, 100 674 poopsa

## Jezik
- **Jezik podataka:** Engleski (podaci preuzeti s međunarodne platforme).
- **Jezik dokumentacije:** Hrvatski.

## Licenca
Ovaj skup podataka licenciran je pod **Creative Commons Attribution 4.0 International (CC BY 4.0)** licencom. Detalji se nalaze u datoteci `LICENSE`.

## Struktura i atributi

### Entitet: `user`
| Atribut           | Tip       | Opis                                                        |
| :---              | :---      | :---                                                        |
| `id`              | Integer   | Jedinstveni identifikator korisnika                         |
| `username`        | String    | Korisničko ime na platformi                                 |
| `poopsCount`      | Integer   | Ukupan broj zabilježenih poopsa korisnika                   |
| `pinColor`        | String    | Hex kod boje pina na karti                                  |
| `createdAt`       | DateTime  | Datum i vrijeme kreiranja računa (ISO 8601)                 |
| `badgesCount`     | Integer   | Broj osvojenih značaka                                      |
| `followersCount`  | Integer   | Broj pratitelja                                             |
| `followingsCount` | Integer   | Broj praćenih korisnika                                     |
| `countryCount`    | Integer   | Broj različitih država u kojima je korisnik zabilježio poop |
| `isPro`           | Boolean   | Ima li korisnik Pro pretplatu                               |
| `isPrivate`       | Boolean   | Je li profil privatan                                       |
| `poopsPerDay`     | Float     | Prosječan broj poopsa po danu                               |

### Entitet: `poop`
| Atribut       | Tip       | Opis                                                         |
| :---          | :---      | :---                                                         |
| `id`          | Integer   | Jedinstveni identifikator poopa                              |
| `createdAt`   | DateTime  | Datum i vrijeme nastanka poopa (ISO 8601)                    |
| `latitude`    | Float     | Geografska širina (0 ako je lokacija skrivena)               |
| `longitude`   | Float     | Geografska dužina (0 ako je lokacija skrivena)               |
| `isAirplane`  | Boolean   | Je li poop nastao u zrakoplovu                               |
| `note`        | String    | Kratka tekstualna bilješka korisnika                         |
| `pinColor`    | String    | Hex kod boje pina specifičan za ovaj poop                    |
| `place`       | String    | Naziv mjesta koji je upisao korisnik (npr. "home")           |
| `rating`      | Integer   | Ocjena poopa (1-5)                                           |
| `aroma`       | String    | Intenzitet mirisa (`low_key`, `noticeable`, `clear_the_room`)|
| `userId`      | Integer   | Strani ključ na `user.id`                                    |
| `townId`      | Integer   | Strani ključ na `town.id` (najbliže naselje)                 |

### Entitet: `town`
| Atribut       | Tip       | Opis                                         |
| :---          | :---      | :---                                         |
| `id`          | Integer   | GeoNames identifikator naselja               |
| `name`        | String    | Naziv naselja                                |
| `admin1`      | String    | Regija / savezna država / županija           |
| `countryCode` | String    | Strani ključ na `country.code`               |
| `latitude`    | Float     | Geografska širina naselja                    |
| `longitude`   | Float     | Geografska dužina naselja                    |
| `population`  | Integer   | Broj stanovnika                              |

### Entitet: `country`
| Atribut       | Tip       | Opis                                         |
| :---          | :---      | :---                                         |
| `code`        | String    | ISO 3166-1 alpha-2 kod države                |
| `name`        | String    | Naziv države                                 |
| `continent`   | String    | Kontinent                                    |
| `population`  | Integer   | Broj stanovnika                              |
| `areaKm2`     | Float     | Površina u km²                               |

## Relacije
- **`user` (1) : (N) `poop`**, preko `poop.userId` → `user.id`
- **`town` (1) : (N) `poop`**, preko `poop.townId` → `town.id`
- **`country` (1) : (N) `town`**, preko `town.countryCode` → `country.code`

## Preslikavanje lokacija
Svaki poop preslikan je na najbliže naselje iz GeoNames skupa `cities1000` (naselja s barem 1000 stanovnika, bez gradskih četvrti), a naselje na svoju državu. Udaljenost se računa po velikom krugu. Poopsi udaljeniji od 10 km od svakog naselja (more, divljina) preslikani su na posebno naselje `id = 0`, `name = "wilderness"`, koje nema državu. Bez naselja (`townId = NULL`) ostaju samo poopsi sa skrivenom lokacijom (0, 0) i poopsi u zrakoplovu. U bazi su samo naselja i države koje imaju barem jedan poop.

## Datoteke u repozitoriju
- `README.md`: ova datoteka
- `LICENSE`: tekst licence
- `dump.sql`: SQL dump baze podataka (SQLite, UTF-8)
- `create.sql`: shema baze
- `poops100k.json`: sirovi poopsi prikupljeni s API-ja
- `users100k.json`: sirovi profili korisnika tih poopsa
- `progress.txt`: zadnji ID do kojeg je stigao dohvat poopsa
- `scripts/`: skripte za prikupljanje i obradu

## Postupak izgradnje
Skripte se pokreću iz mape `scripts/`. Za dohvat s API-ja potrebna je datoteka `.env` u korijenu s varijablama `POOPMAP_USERNAME` i `POOPMAP_PASSWORD`.

1. `fetch_poops.py`: dohvaća poopse po ID-u (silazno) u `poops100k.json` i nastavlja od `progress.txt`
2. `fetch_users.py`: dohvaća profile svih jedinstvenih korisnika u `users100k.json`
3. `load_db.py`: gradi `db.db` po `create.sql` i puni je iz JSON datoteka (čuva postojeća preslikavanja lokacija)
4. `geocode.py`: preuzima GeoNames podatke u `geodata/` i puni `town`, `country` i `poop.townId` izravno u bazi
5. `export.py`: iz baze generira `dump.sql` i datoteke u `exports/`:
   - `poopmap.json`: svi podaci u jednom JSON-u. Korisnik sadrži listu poopsa (1:N), a svaki poop ugniježđeno sadrži svoje naselje i državu.
   - `poopmap.csv`: svi podaci u jednom CSV-u, jedan redak po poopu spojen s korisnikom, naseljem i državom
   - `countries.json` / `countries.csv`: država sadrži listu naselja (1:N), uz broj poopsa i korisnika te broj poopsa na milijun stanovnika

## Izvor podataka
Podaci o lokacijama (naselja i države) preuzeti su s [GeoNames](https://www.geonames.org/) pod licencom CC BY 4.0.

Ostali podaci su prikupljeni putem Poopmap API-ja (v1) vlastitim skriptama. Poopsi su dohvaćani pojedinačno po ID-u u rasponu 252 217 127 – 252 770 265 (zapisi nastali krajem listopada i početkom studenog 2026.), a za svakog autora dohvaćen je javni profil.
