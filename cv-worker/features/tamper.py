# cv-worker/features/tamper.py
import cv2, numpy as np, time
from datetime import datetime

class TamperDetector:
    def __init__(
        self,
        warmup_frames=60,
        persist_frames=15,
        cooldown_seconds=10.0,
        blur_drop_ratio=0.15,
        abs_blur_floor=8.0,
        freeze_seconds=60,
        hist_flat_thr=0.990,
        ema_alpha=0.05,              # smoothing for baseline
    ):
        # thresholds
        self.warmup_frames   = int(warmup_frames)
        self.persist_frames  = int(persist_frames)
        self.cooldown_seconds= float(cooldown_seconds)
        self.blur_drop_ratio = float(blur_drop_ratio)
        self.abs_blur_floor  = float(abs_blur_floor)
        self.freeze_seconds  = float(freeze_seconds)
        self.hist_flat_thr   = float(hist_flat_thr)
        self.ema_alpha       = float(ema_alpha)

        # state
        self._frame_count = 0
        self._lap_baseline = None
        self._below_cnt = 0
        self._last_alert_ts = 0.0

        self._last_hash = None
        self._freeze_since = None

    def _iso(self, ts: float) -> str:
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def step_frame(self, frame, ts, camera_id):
        events = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- Laplacian variance (sharpness proxy) ---
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        self._frame_count += 1

        # Build/Update EMA baseline
        if self._lap_baseline is None:
            self._lap_baseline = lap_var
        else:
            self._lap_baseline = (
                self.ema_alpha * lap_var + (1.0 - self.ema_alpha) * self._lap_baseline
            )

        # Only evaluate blur after warmup
        blur_suspicious = False
        if self._frame_count > self.warmup_frames:
            # condition: either extremely low absolute sharpness, OR big drop vs baseline
            drop_cond = lap_var < self.blur_drop_ratio * max(1e-3, self._lap_baseline)
            abs_cond  = lap_var < self.abs_blur_floor
            blur_suspicious = drop_cond or abs_cond

            if blur_suspicious:
                self._below_cnt += 1
            else:
                self._below_cnt = 0

            can_alert = (time.time() - self._last_alert_ts) >= self.cooldown_seconds
            if self._below_cnt >= self.persist_frames and can_alert:
                events.append({
                    "ts_utc": self._iso(ts),
                    "camera_id": camera_id,
                    "event_type": "camera_tamper",
                    "severity": "high",
                    "metrics": {
                        "laplacian_var": round(lap_var, 2),
                        "lap_baseline": round(self._lap_baseline, 2),
                        "below_frames": int(self._below_cnt),
                        "drop_ratio": round(lap_var / max(1e-3, self._lap_baseline), 3)
                    },
                    "explanation": (
                        f"Sharpness drop: var={lap_var:.1f} "
                        f"(baseline {self._lap_baseline:.1f}, "
                        f"ratio {lap_var/max(1e-3,self._lap_baseline):.2f}); "
                        f"persist {self._below_cnt} frames"
                    )
                })
                self._below_cnt = 0
                self._last_alert_ts = time.time()

        # --- Freeze detection (debounced) ---
        # Simple hash = mean intensity bucketed by 1
        h = int(gray.mean())
        if self._last_hash is not None and h == self._last_hash:
            if self._freeze_since is None:
                self._freeze_since = ts
            elif (ts - self._freeze_since) >= self.freeze_seconds:
                if (time.time() - self._last_alert_ts) >= self.cooldown_seconds:
                    events.append({
                        "ts_utc": self._iso(ts),
                        "camera_id": camera_id,
                        "event_type": "camera_tamper",
                        "severity": "high",
                        "metrics": {"frozen_sec": round(ts - self._freeze_since, 2)},
                        "explanation": f"Frozen frame for {round(ts - self._freeze_since,1)}s"
                    })
                    self._last_alert_ts = time.time()
                self._freeze_since = ts + 9999  # avoid refire immediately
        else:
            self._freeze_since = None
        self._last_hash = h

        # --- Histogram flatness (covered lens only) ---
        hist = cv2.calcHist([gray],[0],None,[16],[0,256]).flatten()
        hist = hist / (hist.sum() + 1e-6)
        if hist.max() >= self.hist_flat_thr:
            if (time.time() - self._last_alert_ts) >= self.cooldown_seconds:
                events.append({
                    "ts_utc": self._iso(ts),
                    "camera_id": camera_id,
                    "event_type": "camera_tamper",
                    "severity": "high",
                    "metrics": {"hist_max_bin": float(hist.max())},
                    "explanation": f"Histogram dominance (covered/near-dark); max bin={hist.max():.3f}"
                })
                self._last_alert_ts = time.time()

        return events
