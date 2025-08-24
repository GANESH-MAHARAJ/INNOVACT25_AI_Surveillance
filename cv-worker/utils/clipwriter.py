# cv-worker/utils/clipwriter.py
import os
import shutil
import subprocess
import tempfile
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Callable

import numpy as np

try:
    import cv2
except Exception as e:
    raise RuntimeError("OpenCV (cv2) is required. pip install opencv-python") from e

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception as e:
    raise RuntimeError("imageio-ffmpeg is required. pip install imageio-ffmpeg") from e

FrameT = Tuple[float, np.ndarray]  # (ts_float, frame_bgr)

class ClipWriter(threading.Thread):
    """
    Robust clip writer (Windows-friendly):
      1) Normalize frames to (width,height) BGR uint8
      2) Write PNG sequence to a temp folder
      3) ffmpeg -> H.264 (yuv420p, faststart) MP4
         IMPORTANT: we force muxer with -f mp4 so writing to *.mp4.tmp works.
      4) Atomic move to final path
    """
    def __init__(self, out_dir="C:/Hackathons/HoneyWell/clips", fps=15, width=640, height=480):
        super().__init__(daemon=True)
        self.q: "queue.Queue[dict]" = queue.Queue(maxsize=256)
        self.out_dir = os.path.normpath(out_dir)
        self.fps = int(fps)
        self.width = int(width)
        self.height = int(height)
        os.makedirs(self.out_dir, exist_ok=True)
        print(f"[ClipWriter] ffmpeg: {FFMPEG_EXE}")
        

    def make_name(self, camera_id: str, event_id: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe = lambda s: "".join(ch for ch in str(s) if ch.isalnum() or ch in ("-", "_"))
        return f"{ts}_{safe(camera_id)}_{safe(event_id)}.mp4"

    # ------------------ synchronous writer ------------------
    def write_sync(
        self,
        camera_id: str,
        event_id: str,
        frames: List[FrameT],
        post_frames: Optional[List[FrameT]] = None,
        name: Optional[str] = None,
    ) -> str:
        if not name:
            name = self.make_name(camera_id, event_id)
        out_path = Path(self.out_dir) / name
        all_frames = (frames or []) + (post_frames or [])
        if not all_frames:
            raise RuntimeError("No frames to write")

        # 1) PNG sequence in temp dir
        tmpdir = Path(tempfile.mkdtemp(prefix="clip_"))
        try:
            count = 0
            for _, f in all_frames:
                if f is None:
                    continue
                if not isinstance(f, np.ndarray):
                    raise RuntimeError("Frame is not a numpy array")
                if f.dtype != np.uint8:
                    f = f.astype(np.uint8)
                h, w = f.shape[:2]
                if (w, h) != (self.width, self.height):
                    f = cv2.resize(f, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
                png_path = tmpdir / f"{count:06d}.png"
                if not cv2.imwrite(str(png_path), f):
                    raise RuntimeError(f"Failed to write PNG {png_path}")
                count += 1
            if count == 0:
                raise RuntimeError("No valid frames after normalization")

            # 2) ffmpeg: image2 -> H.264 yuv420p + faststart
            input_pattern = (tmpdir / "%06d.png").as_posix()
            tmp_mp4 = (out_path.as_posix() + ".tmp")

            cmd = [
                FFMPEG_EXE,
                "-y",
                "-f", "image2",
                "-framerate", str(self.fps),
                "-i", input_pattern,
                "-an",
                "-vcodec", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
                "-movflags", "+faststart",
                "-r", str(self.fps),
                "-f", "mp4",
                tmp_mp4
            ]
            print("[ClipWriter] encode cmd:", " ".join(cmd))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                sample_list = "\n".join([p.name for p in sorted(tmpdir.glob('*.png'))[:5]])
                raise RuntimeError(
                    "ffmpeg failed.\n"
                    f"  returncode: {proc.returncode}\n"
                    f"  stderr head: {proc.stderr[:600]}\n"
                    f"  tmpdir: {tmpdir}\n"
                    f"  first files:\n{sample_list}"
                )

            # 3) Atomic move to final .mp4
            if out_path.exists():
                out_path.unlink()
            Path(tmp_mp4).replace(out_path)

            sz = out_path.stat().st_size
            print("[ClipWriter] wrote", str(out_path), "size", sz, "bytes")
            if sz < 100 * 1024:
                raise RuntimeError(f"Encoded file too small: {sz} bytes")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return name

    # ------------------ optional queue API ------------------
    def enqueue(self, camera_id: str, event_id: str, frames: List[FrameT], post_frames: Optional[List[FrameT]] = None, name: Optional[str] = None,on_done: Optional[Callable[[str, str], None]] = None) -> str:
        if not name:
            name = self.make_name(camera_id, event_id)
        self.q.put({"camera_id": camera_id, "event_id": event_id, "frames": frames, "post_frames": post_frames or [], "name": name,"on_done": on_done})
        return name

    def run(self):
        while True:
            job = self.q.get()
            try:
                self.write_sync(job["camera_id"], job["event_id"], job.get("frames", []), job.get("post_frames", []), name=job.get("name"))
            except Exception as e:
                print("[ClipWriter] error:", e)

    # (helper unused in this sync flow)
    def _encode_job(self, job: dict) -> str:
        name = job["name"]
        out_path = Path(self.out_dir) / name
        frames = (job.get("frames") or []) + (job.get("post_frames") or [])
        if not frames:
            raise RuntimeError("No frames to write")

        tmpdir = Path(tempfile.mkdtemp(prefix="clip_"))
        try:
            for i, (_, f) in enumerate(frames):
                if f is None: continue
                if f.dtype != np.uint8:
                    f = f.astype(np.uint8)
                h, w = f.shape[:2]
                if (w, h) != (self.width, self.height):
                    f = cv2.resize(f, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
                cv2.imwrite(str(tmpdir / f"{i:06d}.png"), f)

            input_pattern = (tmpdir / "%06d.png").as_posix()
            tmp_mp4 = (out_path.as_posix() + ".tmp")

            cmd = [
                FFMPEG_EXE, "-y",
                "-f", "image2", "-framerate", str(self.fps), "-i", input_pattern,
                "-an", "-vcodec", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-movflags", "+faststart",
                "-r", str(self.fps), "-f", "mp4", tmp_mp4
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {proc.stderr[:400]}")

            if out_path.exists(): out_path.unlink()
            Path(tmp_mp4).replace(out_path)
            return str(out_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
