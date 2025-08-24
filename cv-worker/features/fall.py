class FallDetector:
    def __init__(self, ar_thr=0.55, persist=10):
        self.ar_thr = ar_thr
        self.persist = persist
        self.state = {}  # track_id -> frames low aspect ratio

    def step(self, tracks, ts, camera_id):
        events = []
        for t in tracks:
            if t["class_name"] != "person": continue
            x1,y1,x2,y2 = t["xyxy"]
            h = (y2 - y1); w = (x2 - x1)
            ar = h / max(1.0, w)
            tid = t["track_id"]
            if ar < self.ar_thr:
                c = self.state.get(tid, 0) + 1
                self.state[tid] = c
                if c == self.persist:
                    events.append({
                        "ts_utc": ts, "camera_id": camera_id,
                        "event_type": "fall", "severity": "high",
                        "zone": None,
                        "tracks": [{"track_id": tid, "klass": "person"}],
                        "metrics": {"aspect_ratio": round(ar,2), "frames": c},
                        "explanation": f"Person #{tid} prone-like posture {c} frames"
                    })
            else:
                self.state.pop(tid, None)
        return events
