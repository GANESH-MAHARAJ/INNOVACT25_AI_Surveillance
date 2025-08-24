# cv-worker/utils/bus.py
import requests, time, json
from datetime import datetime

def _to_iso(ts):
    if ts is None:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    # assume already a string
    return ts

class EventBus:
    def __init__(self, api_url="http://localhost:8080"):
        self.api_url = api_url.rstrip("/")

    def post_event(self, ev: dict):
        # normalize timestamp
        if "ts_utc" in ev:
            ev["ts_utc"] = _to_iso(ev["ts_utc"])
        else:
            ev["ts_utc"] = _to_iso(time.time())

        url = f"{self.api_url}/events"
        try:
            r = requests.post(url, json=ev, timeout=2.5)
            print(f"[EventBus] POST {r.status_code} -> {url}")
            if r.status_code >= 300:
                print("[BUS] API error", r.status_code, r.text)
                print("[EventBus] body:",r.text[:500])
        except Exception as e:
            print("[BUS] POST failed, printing event locally. Err:", e)
            try:
                print(json.dumps(ev, indent=2)[:800])
            except Exception:
                print(str(ev)[:800])
