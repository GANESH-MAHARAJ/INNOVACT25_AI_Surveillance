# cv-worker/detectors/yolo.py
from ultralytics import YOLO
import numpy as np

class YoloDetector:
    def __init__(self, weights: str, conf: float = 0.35, iou: float = 0.45, classes=None, imgsz: int = 640):
        self.model = YOLO(weights)
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self._class_filter = None
        # map class names -> indices (case-insensitive)
        names = self.model.names if isinstance(self.model.names, dict) else {i: n for i, n in enumerate(self.model.names)}
        if classes:
            name_to_idx = {v.lower(): k for k, v in names.items()}
            self._class_filter = [name_to_idx[c.lower()] for c in classes if c.lower() in name_to_idx]

    def infer(self, frame_bgr):
        # BGR -> RGB for ultralytics
        results = self.model.predict(
            source=frame_bgr[..., ::-1],
            conf=self.conf,
            iou=self.iou,
            classes=self._class_filter,
            imgsz=self.imgsz,
            verbose=False
        )
        dets = []
        if not results:
            return dets
        r0 = results[0]
        if r0.boxes is None:
            return dets
        boxes = r0.boxes.xyxy.cpu().numpy()
        confs = r0.boxes.conf.cpu().numpy()
        clss  = r0.boxes.cls.cpu().numpy().astype(int)
        names = r0.names if isinstance(r0.names, dict) else {i: n for i, n in enumerate(r0.names)}
        for (x1, y1, x2, y2), cf, ci in zip(boxes, confs, clss):
            dets.append({
                "xyxy": [float(x1), float(y1), float(x2), float(y2)],
                "conf": float(cf),
                "class_id": int(ci),
                "class_name": names[int(ci)]
            })
        return dets
