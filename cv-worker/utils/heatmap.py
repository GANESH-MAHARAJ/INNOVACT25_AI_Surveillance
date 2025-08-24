# cv-worker/utils/heatmap.py
import numpy as np
import cv2
import time
from typing import List, Tuple, Optional

_PALETTES = {
    "turbo": cv2.COLORMAP_TURBO,
    "magma": cv2.COLORMAP_MAGMA,
    "inferno": cv2.COLORMAP_INFERNO,
    "plasma": cv2.COLORMAP_PLASMA,
    "jet": cv2.COLORMAP_JET,
}

class HeatmapAccumulator:
    """
    Decay-based occupancy heatmap with pretty rendering.
    - add_boxes(): increment regions covered by person bounding boxes
    - step_decay(): fades history over time
    - render(): colorized map (optionally overlaid on base frame)
    """

    def __init__(self, width: int, height: int, decay_per_sec: float = 0.12, blur_ksize: int = 33):
        self.w = int(width)
        self.h = int(height)
        self.decay = float(decay_per_sec)
        self.grid = np.zeros((self.h, self.w), dtype=np.float32)
        self.last_ts = time.time()
        # force odd kernel for Gaussian
        self.blur_ksize = int(blur_ksize) if int(blur_ksize) % 2 == 1 else int(blur_ksize) + 1

    def step_decay(self):
        now = time.time()
        dt = max(0.0, now - self.last_ts)
        self.last_ts = now
        if dt <= 0.0:
            return
        # exponential-ish fade
        self.grid *= max(0.0, 1.0 - self.decay * dt)
        self.grid[self.grid < 1e-7] = 0.0

    def add_boxes(self, boxes_xyxy: List[Tuple[int,int,int,int]], strength: float = 1.0):
        for (x1, y1, x2, y2) in boxes_xyxy:
            x1 = max(0, min(self.w - 1, int(x1)))
            y1 = max(0, min(self.h - 1, int(y1)))
            x2 = max(0, min(self.w - 1, int(x2)))
            y2 = max(0, min(self.h - 1, int(y2)))
            if x2 <= x1 or y2 <= y1:
                continue
            self.grid[y1:y2, x1:x2] += float(strength)

    def _normalize(self, clip_percentile: float = 95.0, gamma: float = 0.6):
        g = self.grid.copy()
        # smooth before scaling for nicer isobands
        if self.blur_ksize > 1:
            g = cv2.GaussianBlur(g, (self.blur_ksize, self.blur_ksize), 0)

        vmax = np.percentile(g[g > 0], clip_percentile) if np.any(g > 0) else 1.0
        if vmax < 1e-6:
            vmax = 1.0
        g = np.clip(g / vmax, 0.0, 1.0)

        # gamma to lift dark areas (more visible early activity)
        g = np.power(g, gamma)
        g8 = (g * 255.0).astype(np.uint8)
        return g8

    def render(
        self,
        base_frame_bgr: Optional[np.ndarray] = None,
        palette: str = "turbo",
        alpha: float = 0.6,
        clip_percentile: float = 90.0,  # a bit more aggressive than 95
        gamma: float = 0.5,             # lift low values more
        draw_grid: bool = False,
    ) -> np.ndarray:
        # --- normalize to 0..255 with blur & gamma ---
        g = self.grid.copy()
        if self.blur_ksize > 1:
            g = cv2.GaussianBlur(g, (self.blur_ksize, self.blur_ksize), 0)
        vmax = np.percentile(g[g > 0], clip_percentile) if np.any(g > 0) else 1.0
        vmax = max(vmax, 1e-6)
        g = np.clip(g / vmax, 0.0, 1.0)
        g = np.power(g, gamma)
        g8 = (g * 255.0).astype(np.uint8)

        # --- colorize ---
        palette_map = {
            "turbo": cv2.COLORMAP_TURBO, "magma": cv2.COLORMAP_MAGMA,
            "inferno": cv2.COLORMAP_INFERNO, "plasma": cv2.COLORMAP_PLASMA,
            "jet": cv2.COLORMAP_JET,
        }
        cmap = palette_map.get(palette.lower(), cv2.COLORMAP_TURBO)
        heat = cv2.applyColorMap(g8, cmap)

        # If no base, just return the heatmap
        if base_frame_bgr is None:
            return heat

        # --- build visibility mask so we only overlay where signal exists ---
        mask = (g8 > 8).astype(np.float32)    # threshold
        mask = cv2.GaussianBlur(mask, (21, 21), 0)  # soften edges
        mask = np.clip(mask, 0.0, 1.0) * alpha
        mask3 = cv2.merge([mask, mask, mask])

        # dim grayscale base a touch so colors pop
        base = cv2.cvtColor(base_frame_bgr, cv2.COLOR_BGR2GRAY)
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
        base = (base * 0.8).astype(np.uint8)

        out = (base * (1.0 - mask3) + heat * mask3).astype(np.uint8)

        if draw_grid:
            step = max(40, min(self.w, self.h) // 12)
            for x in range(0, self.w, step):
                cv2.line(out, (x, 0), (x, self.h), (50, 50, 50), 1, cv2.LINE_AA)
            for y in range(0, self.h, step):
                cv2.line(out, (0, y), (self.w, y), (50, 50, 50), 1, cv2.LINE_AA)
        return out
