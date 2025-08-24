from collections import deque
from typing import Deque, Tuple
import numpy as np

# Stores (ts_float, frame_bgr)
class RingBuffer:
    def __init__(self, seconds: float, fps: int):
        self.capacity = max(1, int(seconds * fps))
        self.buf: Deque[Tuple[float, np.ndarray]] = deque(maxlen=self.capacity)

    def push(self, ts, frame):
        self.buf.append((ts, frame))

    # return a copy (list) to avoid mutation while writing file
    def dump(self):
        return list(self.buf)
