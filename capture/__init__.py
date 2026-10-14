"""Acquisition adapters producing BGR frames regardless of source."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
import math
import cv2
import numpy as np


@dataclass
class Frame:
    image: np.ndarray
    source: str
    index: int = 0
    timestamp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    capture_monotonic: float | None = None


def load_image(path: str | Path) -> Frame:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return Frame(image, str(path))


def video_frames(path: str | Path, interval: float = 1.0,
                 limit: int | None = None) -> Iterator[Frame]:
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Video interval must be positive and finite")
    if limit is not None and limit < 1:
        raise ValueError("Frame limit must be positive")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError(f"Cannot read video: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video has no valid frame rate")
        index, emitted = 0, 0
        next_sample = 0.0
        previous_timestamp = -1.0
        while limit is None or emitted < limit:
            ok = cap.grab()
            if not ok:
                break
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            method = 'video_position'
            if not math.isfinite(timestamp) or timestamp < 0 or (index > 0 and timestamp <= previous_timestamp):
                timestamp = max(index / fps, previous_timestamp + 1 / fps)
                method = 'frame_rate_fallback'
            previous_timestamp = timestamp
            if timestamp + 1e-8 >= next_sample:
                ok, image = cap.retrieve()
                if not ok:
                    break
                yield Frame(image, str(path), index, timestamp,
                            {"fps": fps, "timestamp_method": method})
                emitted += 1
                next_sample = (math.floor((timestamp+1e-8) / interval)+1)*interval
            index += 1
    finally:
        cap.release()
