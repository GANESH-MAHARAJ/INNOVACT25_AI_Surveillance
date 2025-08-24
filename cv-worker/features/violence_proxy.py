import math

def _center(b): x1,y1,x2,y2=b; return ((x1+x2)/2,(y1+y2)/2)

class ViolenceProxy:
    def __init__(self, dist_thr=140.0, speed_thr=40.0, persist=6):
        self.dist_thr = dist_thr
        self.speed_thr = speed_thr
        self.persist = persist
        self.prev_centers = {}  # track_id -> (x,y)
        self.state = {}         # (a,b) -> frames

    def step(self, tracks, ts, camera_id):
        events = []
        persons = [t for t in tracks if t["class_name"] == "person"]
        centers = {t["track_id"]: _center(t["xyxy"]) for t in persons}
        speeds = {tid: math.hypot(centers[tid][0]-self.prev_centers.get(tid, centers[tid])[0],
                                  centers[tid][1]-self.prev_centers.get(tid, centers[tid])[1])
                  for tid in centers}

        for i in range(len(persons)):
            for j in range(i+1, len(persons)):
                a = persons[i]["track_id"]; b = persons[j]["track_id"]
                ax,ay = centers[a]; bx,by = centers[b]
                d = math.hypot(ax-bx, ay-by)
                ssum = speeds.get(a,0.0) + speeds.get(b,0.0)
                key = (min(a,b), max(a,b))
                if d < self.dist_thr and ssum > self.speed_thr:
                    c = self.state.get(key, 0) + 1
                    self.state[key] = c
                    if c == self.persist:
                        events.append({
                            "ts_utc": ts, "camera_id": camera_id,
                            "event_type": "violence_proxy", "severity": "med",
                            "zone": None,
                            "tracks": [{"track_id": a, "klass":"person"},{"track_id": b, "klass":"person"}],
                            "metrics": {"pair_distance_px": round(d,1), "speed_sum": round(ssum,1), "frames": c},
                            "explanation": f"Close & high-motion interaction between #{a} and #{b}"
                        })
                else:
                    self.state.pop(key, None)

        self.prev_centers = centers
        return events
