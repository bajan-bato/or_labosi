import os
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.poopmap.net/api/v1"
USER_AGENT = "Poopmap/1.0"


def _load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


class PoopmapClient:
    def __init__(self):
        self.headers = {}
        self._lock = threading.Lock()
        self._last_refresh = 0.0
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
        self.session.mount("https://", adapter)

    def login(self):
        username = os.environ.get("POOPMAP_USERNAME")
        password = os.environ.get("POOPMAP_PASSWORD")
        if not username or not password:
            raise SystemExit("Nedostaju POOPMAP_USERNAME / POOPMAP_PASSWORD u .env")
        try:
            r_dev = requests.post(f"{API}/devices", headers={"user-agent": USER_AGENT}, timeout=10)
            token = r_dev.json()["device"]["token"]
            r_sess = requests.post(
                f"{API}/sessions",
                headers={"Authorization": f"Token {token}", "User-Agent": USER_AGENT,
                         "Content-Type": "application/json"},
                json={"user": {"username": username, "password": password}},
                timeout=10,
            )
            if r_sess.status_code == 200:
                self.headers = {"Authorization": f"Token {token}", "User-Agent": USER_AGENT,
                                "Accept": "application/json"}
                return True
        except Exception as e:  # noqa: BLE001
            print(f"\n[!] Greška pri prijavi: {e}")
        return False

    def _refresh(self, reason):
        with self._lock:
            if time.time() - self._last_refresh > 5:
                print(f"\n[!] {reason}. Osvježavam token...")
                if self.login():
                    print("[+] Token osvježen.")
                else:
                    time.sleep(5)
                self._last_refresh = time.time()
            else:
                time.sleep(1)

    def get(self, path, attempts=5):
        """Vraća (status, json|None). status: 'success', 'not_found', 'forbidden', 'failed'."""
        for _ in range(attempts):
            try:
                resp = self.session.get(f"{API}/{path}", headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    return "success", resp.json()
                if resp.status_code == 404:
                    return "not_found", None
                if resp.status_code == 403:
                    return "forbidden", None
                if resp.status_code == 429:
                    self._refresh(f"429 Rate limit na {path}")
                    continue
                if resp.status_code == 401:
                    self._refresh(f"401 Unauthorized na {path}")
                    continue
                time.sleep(1)
            except requests.exceptions.RequestException:
                time.sleep(1)
        return "failed", None
