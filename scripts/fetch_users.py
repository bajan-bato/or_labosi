import argparse
import json
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from poopmap_api import ROOT, PoopmapClient

POOPS = ROOT / "poops100k.json"
OUT = ROOT / "users100k.json"
DB = ROOT / "db.db"
MAX_WORKERS = 16
SAVE_EVERY = 200


def to_record(u):
    stats = u.get("stats") or {}
    per_day = (stats.get("poops") or {}).get("per_day")
    return {
        "id": u.get("id"),
        "username": u.get("username"),
        "poopsCount": u.get("poops_count"),
        "pinColor": u.get("pin_color"),
        "createdAt": u.get("created_at"),
        "badgesCount": u.get("badges_count"),
        "followersCount": u.get("followers_count"),
        "followingsCount": u.get("followings_count"),
        "countryCount": u.get("country_count"),
        "isPro": u.get("is_pro"),
        "isPrivate": u.get("is_private"),
        "poopsPerDay": per_day,
        "fetchStatus": "success",
    }


def wanted_ids():
    ids = {p["userId"] for p in json.loads(POOPS.read_text(encoding="utf-8")) if p.get("userId")}
    if DB.exists():  # korisnici postojećih poopsa u bazi (prvih 300)
        con = sqlite3.connect(DB)
        try:
            ids |= {r[0] for r in con.execute("SELECT DISTINCT userId FROM poop WHERE userId IS NOT NULL")}
        finally:
            con.close()
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="dohvati najviše N korisnika (za test)")
    ap.add_argument("--retry-failed", action="store_true", help="ponovno pokušaj 'failed' zapise")
    args = ap.parse_args()

    users = {}
    if OUT.exists():
        users = {u["id"]: u for u in json.loads(OUT.read_text(encoding="utf-8"))}
    done = {i for i, u in users.items()
            if not (args.retry_failed and u.get("fetchStatus") == "failed")}
    todo = sorted(wanted_ids() - done)
    if args.limit:
        todo = todo[: args.limit]
    print(f"Već imam {len(users)}, za dohvatiti {len(todo)} korisnika.")
    if not todo:
        return

    client = PoopmapClient()
    if not client.login():
        raise SystemExit("Ne mogu se ulogirati.")

    def save():
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(users.values(), key=lambda u: u["id"]),
                                  indent=2, ensure_ascii=False), encoding="utf-8")
        for attempt in range(20):  # Windows: datoteku zna nakratko zaključati antivirus/editor
            try:
                os.replace(tmp, OUT)
                return
            except PermissionError:
                time.sleep(0.5)
        os.replace(tmp, OUT)  # zadnji pokušaj: neka greška ispliva

    def fetch(uid):
        status, data = client.get(f"users/{uid}")
        return uid, status, data

    t0, n = time.time(), 0
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for start in range(0, len(todo), SAVE_EVERY):
                chunk = todo[start:start + SAVE_EVERY]
                for fut in as_completed([ex.submit(fetch, uid) for uid in chunk]):
                    uid, status, data = fut.result()
                    if status == "success" and data:
                        users[uid] = to_record(data.get("user", data))
                    else:
                        users[uid] = {"id": uid, "username": None, "fetchStatus": status}
                    n += 1
                save()
                rate = n / (time.time() - t0)
                left = (len(todo) - n) / rate if rate else 0
                print(f"{n}/{len(todo)}  ({rate:.1f}/s, još ~{left / 60:.0f} min)", flush=True)
    except KeyboardInterrupt:
        print("\nPrekinuto, spremam...")
    finally:
        save()
        from collections import Counter
        print("Gotovo:", len(users), dict(Counter(u.get("fetchStatus") for u in users.values())))


if __name__ == "__main__":
    main()
