# Poopmap Global Dataset

## Opis skupa podataka
Ovaj skup podataka sadrži javno dostupne informacije o korisnicima i njihovim "poopsima" (lokacijama) s platforme Poopmap. Podaci su prikupljeni putem službenog Poopmap API-ja. Skup je strukturiran kroz dva entiteta - user i poop.

## Autor
- **Ime i prezime:** Toni Bajan
- **GitHub:** [@bajan-bato](https://github.com/bajan-bato) 
- **Kontakt:** toni.bajan@fer.hr

## Verzija skupa
- **Trenutna verzija:** v1.0
- **Datum izdavanja:** 01.11.2026.
- **Broj zapisa:** 248 korisnika, 300 poopsa

## Jezik
- **Jezik podataka:** Engleski (podaci preuzeti s međunarodne platforme).
- **Jezik dokumentacije:** Hrvatski.

## Licenca
Ovaj skup podataka licenciran je pod **Creative Commons Attribution 4.0 International (CC BY 4.0)** licencom. Detalji se nalaze u datoteci `LICENSE`.

## Struktura i atributi

### Entitet: `user` (Roditelj)
| Atribut       | Tip       | Opis                                                      |
| :---          | :---      | :---                                                      |
| `id`          | Integer   | Jedinstveni identifikator korisnika                       |
| `username`    | String    | Korisničko ime na platformi                               |
| `poopsCount`  | Integer   | Ukupan broj zabilježenih poopsa od strane korisnika       |
| `pinColor`    | String    | Hex kod boje pina na karti                                |
| `createdAt`   | DateTime  | Datum i vrijeme kreiranja korisničkog računa (ISO 8601)   |

### Entitet: `poop` (Dijete)
| Atribut       | Tip       | Opis                                                      |
| :---          | :---      | :---                                                      |
| `id`          | Integer   | Jedinstveni identifikator poopa                           |
| `createdAt`   | DateTime  | Datum i vrijeme nastanka poopa (ISO 8601)                 |
| `latitude`    | Float     | Geografska širina lokacije                                |
| `longitude`   | Float     | Geografska dužina lokacije                                |
| `isAirplane`  | Boolean   | Zastavica koja označava je li poop nastao u zrakoplovu    |
| `note`        | String    | Kratka tekstualna bilješka korisnika                      |
| `pinColor`    | String    | Hex kod boje pina specifičan za ovaj poop                 |
| `place`       | String    | Naziv mjesta ili lokacije                                 |
| `rating`      | Integer   | Ocjena poopa (0-5)                                        |
| `userId`      | Integer   | Strani ključ koji povezuje poop s korisnikom (`user.id`)  |

## Relacija
- **`user` (1) : (N) `poop`** — Jedan korisnik može imati više poopsa. Veza je ostvarena preko stranog ključa `poop.userId` koji referencira `user.id`.

## Datoteke u repozitoriju
- `README.md` — Ova datoteka
- `LICENSE` — Tekst licence
- `poopmap.json` - JSON zapis podataka
- `poopmap.csv` — CSV zapis podataka
- `dump.sql` — SQL dump baze podataka

## Izvor podataka
Podaci su prikupljeni putem Poopmap API-ja (v1), korištenjem vlastitih skripti za dohvat i obradu podataka. Zbog ograničenja API-ja na 300 zapisa po zahtjevu za "world" endpoint, skup sadrži mali uzorak javno dostupnih podataka.