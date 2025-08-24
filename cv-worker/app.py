# cv-worker/app.py
from datetime import datetime, timezone
import os, time, threading, queue, yaml
import cv2
import numpy as np
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.background import BackgroundTask
from fastapi.middleware.cors import CORSMiddleware

try:
    cv2.setNumThreads(1)
except Exception:
    pass

from detectors.yolo import YoloDetector
from tracking.simple_tracker import CentroidTracker
from utils.zones import Zones
from utils.bus import EventBus
from features.intrusion import IntrusionDetector
from features.loitering import LoiteringDetector
from features.abandoned import AbandonedDetector
from features.tamper import TamperDetector
from features.fall import FallDetector
from features.violence_proxy import ViolenceProxy
from utils.ringbuffer import RingBuffer
from utils.clipwriter import ClipWriter
from utils.heatmap import HeatmapAccumulator

def iso_utc(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
    if isinstance(ts, str):
        return ts
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

CFG = yaml.safe_load(open("config.yaml", "r", encoding="utf-8"))
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CameraWorker(threading.Thread):
    def __init__(self, cam_id: str, source, yolo_cfg, overlay_cfg, fps_cap=15, zones_cfg=None, api_url="http://localhost:8080", clips_dir="C:/Hackathons/HoneyWell/clips"):
        super().__init__(daemon=True)
        self.id = cam_id
        self.last_frame = None
        self.current_occupancy = 0

        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"[{cam_id}] Could not open camera/video source: {source}")

        tconf = (CFG.get("tamper") or {})
        self.tamper = TamperDetector(
            warmup_frames=tconf.get("warmup_frames", 60),
            persist_frames=tconf.get("persist_frames", 15),
            cooldown_seconds=tconf.get("cooldown_seconds", 10.0),
            blur_drop_ratio=tconf.get("blur_drop_ratio", 0.15),
            abs_blur_floor=tconf.get("abs_blur_floor", 8.0),
            freeze_seconds=tconf.get("freeze_seconds", 60),
            hist_flat_thr=tconf.get("hist_flat_thr", 0.990),
            ema_alpha=tconf.get("ema_alpha", 0.05),
        )
        self.det = YoloDetector(weights=yolo_cfg["weights"], conf=yolo_cfg.get("conf",0.35), iou=yolo_cfg.get("iou",0.45), classes=yolo_cfg.get("classes"))
        self.trk = CentroidTracker(max_lost=15, dist_thr=80.0)
        self.overlay_cfg = overlay_cfg

        self.frame_q = queue.Queue(maxsize=5)
        self.fps_cap = int(fps_cap)
        self._stop = False

        self.zones = Zones(zones_cfg or [])

        self.features = [
            IntrusionDetector(zones_cfg or []),
            LoiteringDetector(zones_cfg or []),
            AbandonedDetector(T_seconds=8, owner_dist=180.0),
            FallDetector(),
            ViolenceProxy()
        ]
        self.bus = EventBus(api_url=api_url)

        # pre-roll buffer; keep post-roll = 0 to avoid stalls
        self.pre_seconds = 7
        self.post_seconds = 0
        self.rbuf = RingBuffer(seconds=self.pre_seconds, fps=self.fps_cap)

        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        self.heatmap = HeatmapAccumulator(width=w, height=h, decay_per_sec=0.15, blur_ksize=35)

        self.writer = ClipWriter(out_dir=clips_dir, fps=self.fps_cap, width=w, height=h)

    def stop(self):
        self._stop = True
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass

    def run(self):
        last = 0.0
        period = 1.0 / max(1, self.fps_cap)

        while not self._stop:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05); continue

            now = time.time()
            if now - last < period:
                time.sleep(max(0, period - (now - last)))
                now = time.time()
            last = now

            # push to pre-roll
            self.rbuf.push(now, frame)

            # tamper feature may emit events
            for ev in self.tamper.step_frame(frame, now, self.id):
                self.bus.post_event(ev)

            # detect + track
            dets = self.det.infer(frame)
            tracks = self.trk.update(dets)

            # occupancy
            self.current_occupancy = sum(
                1 for t in tracks if t.get("class_name","") == "person" or t.get("class_id", -1) in (0,)
            )

            # heatmap
            person_boxes = []
            for t in tracks:
                if t.get("class_name","") == "person" or t.get("class_id", -1) in (0,):
                    x1,y1,x2,y2 = map(int, t["xyxy"])
                    person_boxes.append((x1,y1,x2,y2))
            self.heatmap.step_decay()
            if person_boxes:
                self.heatmap.add_boxes(person_boxes, strength=1.0)

            # features → events
            event_batch = []
            for f in self.features:
                event_batch.extend(f.step(tracks, now, self.id))

            # overlays
            out = frame.copy()
            self.last_frame = out
            if self.overlay_cfg.get("show_zones", True):
                out = self.zones.draw(out)
            for t in tracks:
                x1,y1,x2,y2 = map(int, t["xyxy"])
                cv2.rectangle(out, (x1,y1), (x2,y2), (0,200,255), 2)
                lbl = f'{t["class_name"]}#{t["track_id"]}'
                cv2.putText(out, lbl, (x1, max(20,y1-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)

            if self.frame_q.full():
                try: self.frame_q.get_nowait()
                except: pass
            self.frame_q.put(out)

            # >>> sync clip write + single POST that already includes clip (stable)
            if event_batch:
                pre_frames = self.rbuf.dump()
                post_frames = []
                target = now + self.post_seconds
                while time.time() < target and not self._stop:
                    ok2, fr2 = self.cap.read()
                    if not ok2: break
                    ts2 = time.time()
                    post_frames.append((ts2, fr2))
                    if self.frame_q.full():
                        try: self.frame_q.get_nowait()
                        except: pass
                    self.frame_q.put(fr2)

                for ev in event_batch:
                    eid = ev["event_type"]
                    name = self.writer.write_sync(self.id, eid, pre_frames, post_frames)
                    ev.setdefault("artifacts", {})
                    ev["artifacts"]["clip_mp4"] = f"http://localhost:8080/media/{name}"
                    # ensure ISO time
                    ev["ts_utc"] = iso_utc(ev.get("ts_utc", now))
                    self.bus.post_event(ev)

# ---------- Multi-camera orchestrator ----------
workers: dict[str, CameraWorker] = {}

def start_workers():
    cams = CFG.get("cameras", [])
    if not cams:
        raise RuntimeError("No cameras defined. Add 'cameras:' list in config.yaml.")
    for cam in cams:
        cam_id = cam["id"]
        source = cam["source"]
        fps_cap = cam.get("fps_cap", 15)
        worker = CameraWorker(
            cam_id=cam_id,
            source=source,
            yolo_cfg=CFG["yolo"],
            overlay_cfg=CFG["overlay"],
            fps_cap=fps_cap,
            zones_cfg=CFG.get("zones", []),
            api_url="http://localhost:8080/api",
            clips_dir="C:/Hackathons/HoneyWell/clips"
        )
        workers[cam_id] = worker
        worker.start()
        print(f"[cv] started worker for {cam_id} (source={source})")

def stop_workers():
    for w in workers.values():
        w.stop()
    for w in workers.values():
        try:
            w.join(timeout=2.0)
        except Exception:
            pass

start_workers()

@app.get("/health")
def health():
    return {"ok": True, "cameras": list(workers.keys())}

def mjpeg_generator(cam_id: str):
    w = workers.get(cam_id)
    if not w:
        raise StopIteration
    try:
        while not w._stop:
            frame = w.frame_q.get()
            ret, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                continue
            buf = jpg.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n"
                   b"Content-Length: " + str(len(buf)).encode() + b"\r\n\r\n" +
                   buf + b"\r\n")
    except GeneratorExit:
        return
    except Exception as e:
        print(f"[stream {cam_id}] generator exit:", e)
        return

@app.get("/stream/{cam_id}")
def stream(cam_id: str):
    if cam_id not in workers:
        raise HTTPException(status_code=404, detail="Unknown camera")
    gen = mjpeg_generator(cam_id)
    return StreamingResponse(
        gen,
        media_type="multipart/x-mixed-replace; boundary=frame",
        background=BackgroundTask(lambda: getattr(gen, "close", lambda: None)())
    )

@app.get("/heatmap/{cam_id}")
def heatmap_png(cam_id: str, mode: str = "overlay", palette: str = "turbo", alpha: float = 0.65):
    w = workers.get(cam_id)
    if not w:
        raise HTTPException(status_code=404, detail="Unknown camera")

    base = w.last_frame if (mode == "overlay" and w.last_frame is not None) else None
    img = w.heatmap.render(base_frame_bgr=base, palette=palette, alpha=float(alpha))

    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode heatmap")

    return Response(
        content=buf.tobytes(),
        media_type="image/png",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "Cache-Control": "no-store, max-age=0",
        },
    )

@app.get("/occupancy")
def all_occupancy():
    data = [{"camera_id": cid, "occupancy": w.current_occupancy} for cid, w in workers.items()]
    return {"ok": True, "cameras": data}

@app.get("/occupancy/{cam_id}")
def occupancy_one(cam_id: str):
    w = workers.get(cam_id)
    if not w:
        raise HTTPException(status_code=404, detail="Unknown camera")
    return {"ok": True, "camera_id": cam_id, "occupancy": w.current_occupancy}

@app.on_event("shutdown")
def on_shutdown():
    stop_workers()
