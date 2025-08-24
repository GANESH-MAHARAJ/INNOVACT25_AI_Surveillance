from utils.geometry import bbox_center, point_in_poly
from datetime import datetime, timezone

def to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

class LoiteringDetector:
    def __init__(self, zones_cfg):
        self.general = [z for z in (zones_cfg or []) if z.get("type","general") == "general"]
        self.dwell = {}  # (zone_name, track_id) -> first_seen_ts (float seconds)

    def step(self, tracks, ts, camera_id):
        # ts is float seconds (epoch)
        events = []
        now = ts
        for t in tracks:
            if t["class_name"] != "person":
                continue
            cx, cy = bbox_center(t["xyxy"])
            for z in self.general:
                key = (z["name"], t["track_id"])
                if point_in_poly(cx, cy, z["polygon"]):
                    if key not in self.dwell:
                        self.dwell[key] = now
                    dwell_s = now - self.dwell[key]
                    thr = float(z.get("loiter_seconds", 30))
                    # fire once near threshold
                    if dwell_s >= thr and (dwell_s - thr) < 1.0:
                        events.append({
                            "ts_utc": to_iso(now),
                            "camera_id": camera_id,
                            "event_type": "loitering",
                            "severity": "med",
                            "zone": z["name"],
                            "tracks": [{"track_id": t["track_id"], "klass":"person"}],
                            "metrics": {"dwell_sec": round(dwell_s,2)},
                            "explanation": f"Person #{t['track_id']} loitering {round(dwell_s)}s in {z['name']}"
                        })
                else:
                    # left this zone: reset that pair’s dwell
                    self.dwell.pop(key, None)
        return events
