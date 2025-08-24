from utils.geometry import bbox_center, point_in_poly

class IntrusionDetector:
    def __init__(self, zones_cfg, persist_frames=8):
        self.restricted = [z for z in zones_cfg or [] if z.get("type") == "restricted"]
        self.persist = persist_frames
        self.state = {}  # (zone, track_id) -> frames inside

    def step(self, tracks, ts, camera_id):
        events = []
        for t in tracks:
            if t["class_name"] != "person":
                continue
            cx, cy = bbox_center(t["xyxy"])
            for z in self.restricted:
                key = (z["name"], t["track_id"])
                if point_in_poly(cx, cy, z["polygon"]):
                    c = self.state.get(key, 0) + 1
                    self.state[key] = c
                    if c == self.persist:
                        events.append({
                            "ts_utc": ts,
                            "camera_id": camera_id,
                            "event_type": "intrusion",
                            "severity": "high",
                            "zone": z["name"],
                            "tracks": [{"track_id": t["track_id"], "klass": "person"}],
                            "metrics": {"frames_persisted": c},
                            "explanation": f"Person #{t['track_id']} persisted {c} frames in restricted zone {z['name']}"
                        })
                else:
                    self.state.pop(key, None)
        return events
