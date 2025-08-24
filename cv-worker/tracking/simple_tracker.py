# cv-worker/tracking/simple_tracker.py
import math
import itertools

class CentroidTracker:
    def __init__(self, max_lost=15, dist_thr=80.0):
        self.next_id = 1
        self.tracks = {}  # id -> {"bbox":[x1,y1,x2,y2], "lost":int, "class_name":str, "conf":float}
        self.max_lost = max_lost
        self.dist_thr = dist_thr

    @staticmethod
    def _centroid(b):
        x1, y1, x2, y2 = b
        return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)

    @staticmethod
    def _dist(c1, c2):
        return math.hypot(c1[0]-c2[0], c1[1]-c2[1])

    def update(self, detections):
        # detections: list of dicts with "xyxy", "class_name", "conf"
        det_centroids = [self._centroid(d["xyxy"]) for d in detections]
        track_ids = list(self.tracks.keys())
        track_centroids = [self._centroid(self.tracks[tid]["bbox"]) for tid in track_ids]

        # Greedy matching by nearest neighbor (simple for baseline)
        matches = []
        used_dets = set()
        used_trks = set()
        for ti, tc in enumerate(track_centroids):
            best_j = -1
            best_d = 1e9
            for j, dc in enumerate(det_centroids):
                if j in used_dets: 
                    continue
                d = self._dist(tc, dc)
                if d < best_d:
                    best_d, best_j = d, j
            if best_j >= 0 and best_d <= self.dist_thr:
                matches.append((track_ids[ti], best_j))
                used_trks.add(track_ids[ti])
                used_dets.add(best_j)

        # Update matched
        for tid, j in matches:
            d = detections[j]
            self.tracks[tid]["bbox"] = d["xyxy"]
            self.tracks[tid]["class_name"] = d["class_name"]
            self.tracks[tid]["conf"] = d["conf"]
            self.tracks[tid]["lost"] = 0

        # Add new for unmatched dets
        for j, d in enumerate(detections):
            if j in used_dets: 
                continue
            self.tracks[self.next_id] = {
                "bbox": d["xyxy"],
                "class_name": d["class_name"],
                "conf": d["conf"],
                "lost": 0
            }
            self.next_id += 1

        # Increment lost for unmatched tracks and drop if too large
        to_del = []
        for tid in self.tracks:
            if tid in used_trks:
                continue
            self.tracks[tid]["lost"] += 1
            if self.tracks[tid]["lost"] > self.max_lost:
                to_del.append(tid)
        for tid in to_del:
            del self.tracks[tid]

        # Return a list of tracks with IDs
        out = []
        for tid, data in self.tracks.items():
            out.append({
                "track_id": tid,
                "xyxy": data["bbox"],
                "class_name": data["class_name"],
                "conf": data["conf"],
                "lost": data["lost"]
            })
        return out
