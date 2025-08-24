class AbandonedDetector:
    def __init__(self, T_seconds=8, owner_dist=180.0):  # easier to trigger for tests
        self.T = T_seconds
        self.owner_dist = owner_dist
        self.state = {}  # bag_track_id -> {"owner": track_id|None, "since": ts}

    def step(self, tracks, ts, camera_id):
        events = []
        persons = [t for t in tracks if t["class_name"] == "person"]
        bags    = [t for t in tracks if t["class_name"] in ("backpack","handbag","suitcase")]
        for b in bags:
            bx1,by1,bx2,by2 = b["xyxy"]
            bc = ((bx1+bx2)/2,(by1+by2)/2)
            best, bestd = None, 1e9
            for p in persons:
                px1,py1,px2,py2 = p["xyxy"]
                pc = ((px1+px2)/2,(py1+py2)/2)
                d = ((pc[0]-bc[0])**2 + (pc[1]-bc[1])**2)**0.5
                if d < bestd: best, bestd = p, d

            st = self.state.get(b["track_id"], {"owner": None, "since": ts})
            owner_present = bestd < self.owner_dist if best else False
            if owner_present:
                st["owner"] = best["track_id"]
                st["since"] = ts   # reset while owner near
            else:
                # alone long enough?
                if (ts - st["since"]) >= self.T:
                    events.append({
                        "ts_utc": ts,
                        "camera_id": camera_id,
                        "event_type": "abandoned_object",
                        "severity": "high",
                        "zone": None,
                        "tracks": [
                          {"track_id": b["track_id"], "klass": b["class_name"], "role":"bag"},
                          *([{"track_id": st["owner"], "klass":"person", "role":"owner"}] if st["owner"] else [])
                        ],
                        "metrics": {"persistence_sec": round(ts-st["since"],2), "owner_distance_px": bestd if best else None},
                        "explanation": f"Bag #{b['track_id']} alone for {round(ts-st['since'])}s"
                    })
                    st["since"] = ts + 9999  # stop refiring immediately
            self.state[b["track_id"]] = st

        # cleanup
        seen = {b["track_id"] for b in bags}
        for bid in list(self.state.keys()):
            if bid not in seen:
                del self.state[bid]
        return events
