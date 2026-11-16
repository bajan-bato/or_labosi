import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from poopmap_api import ROOT, PoopmapClient

START_ID = 252770265
END_ID = 200000000
MAX_WORKERS = 16
BATCH_PAUSE = 0.2

OUT = ROOT / "poops100k.json"
PROGRESS = ROOT / "progress.txt"

client = PoopmapClient()
print("Inicijalni login...")
if not client.login():
    raise SystemExit("Kritična greška: ne mogu se ulogirati.")

svi_poopsi = {}
if OUT.exists():
    for p in json.loads(OUT.read_text(encoding="utf-8")):
        if p.get("id") is not None:
            svi_poopsi[p["id"]] = p
    print(f"Učitano {len(svi_poopsi)} poopsa.")

current_id = START_ID
if PROGRESS.exists():
    try:
        current_id = int(PROGRESS.read_text().strip())
        print(f"Nastavljam od ID-a: {current_id}")
    except ValueError:
        pass


def fetch_poop(pid):
    status, data = client.get(f"poops/{pid}")
    if status == "success" and "poop" in data:
        data = data["poop"]
    return pid, status, data


def safe_save():
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(list(svi_poopsi.values()), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OUT)
    PROGRESS.write_text(str(current_id))


processed = 0
novi = 0
print("Pokrećem obradu...")
try:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        while current_id > END_ID:
            batch = range(current_id, max(current_id - MAX_WORKERS, END_ID), -1)
            for fut in as_completed([ex.submit(fetch_poop, pid) for pid in batch]):
                pid, status, data = fut.result()
                if status == "success" and data and data.get("id"):
                    svi_poopsi[pid] = {
                        "id": data.get("id"),
                        "createdAt": data.get("created_at"),
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude"),
                        "isAirplane": data.get("is_airplane"),
                        "note": data.get("note"),
                        "pinColor": data.get("pin_color"),
                        "place": data.get("place"),
                        "rating": data.get("rating"),
                        "aroma": data.get("aroma"),
                        "userId": data.get("user_id"),
                    }
                    novi += 1
            current_id -= MAX_WORKERS
            processed += MAX_WORKERS
            if processed >= 100:
                safe_save()
                print(f"Spremljeno. Ukupno: {len(svi_poopsi)} (novih: {novi})")
                processed = novi = 0
            time.sleep(BATCH_PAUSE)
except KeyboardInterrupt:
    print("\nPrekinuto! Spremam stanje...")
finally:
    safe_save()
    print(f"\nUkupno u {OUT.name}: {len(svi_poopsi)}")
