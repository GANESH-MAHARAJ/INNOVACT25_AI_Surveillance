import cv2
from .geometry import point_in_poly

class Zones:
    def __init__(self, zone_cfgs):
        self.zones = zone_cfgs or []

    def where(self, x, y):
        hits = []
        for z in self.zones:
            if point_in_poly(x, y, z["polygon"]):
                hits.append(z)
        return hits

    def draw(self, frame, color=(60, 60, 200)):
        out = frame
        for z in self.zones:
            pts = z["polygon"]
            for i in range(len(pts)):
                x1,y1 = map(int, pts[i])
                x2,y2 = map(int, pts[(i+1)%len(pts)])
                cv2.line(out, (x1,y1), (x2,y2), color, 2)
            cv2.putText(out, z["name"], tuple(map(int, pts[0])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        return out
