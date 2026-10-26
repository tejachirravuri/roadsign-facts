"""Common detection record and colour helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import cv2
import numpy as np


@dataclass
class Detection:
    kind: str                          # traffic_light | speed_limit | sign | direction_sign
    label: str                         # red/green, "50", class name, autobahn/road
    box: Tuple[int, int, int, int]     # x, y, w, h in frame pixels
    score: float = 1.0
    extra: dict = field(default_factory=dict)

    def as_dict(self):
        return {"kind": self.kind, "label": self.label, "box": list(map(int, self.box)),
                "score": round(float(self.score), 3), **self.extra}


def hsv(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)


def red_mask(hsv_image, s_min=90, v_min=70, hue_low_max=10):
    """Red wraps around hue 0, so two ranges are combined."""
    low = cv2.inRange(hsv_image, (0, s_min, v_min), (hue_low_max, 255, 255))
    high = cv2.inRange(hsv_image, (165, s_min, v_min), (180, 255, 255))
    return cv2.bitwise_or(low, high)


def circularity(contour) -> float:
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter <= 0:
        return 0.0
    return float(4 * np.pi * area / (perimeter * perimeter))


def clip_box(x, y, w, h, shape):
    H, W = shape[:2]
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(W, int(x + w)), min(H, int(y + h))
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def suppress(detections, threshold=0.3):
    """Greedy non-maximum suppression by score."""
    kept = []
    for d in sorted(detections, key=lambda d: -d.score):
        if all(iou(d.box, k.box) < threshold for k in kept):
            kept.append(d)
    return kept
