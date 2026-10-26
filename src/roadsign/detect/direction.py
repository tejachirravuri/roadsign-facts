"""Direction signs and road type.

In Germany direction and guide signs on the Autobahn are blue, those on
federal and other roads yellow (or white in towns). A large, saturated,
roughly rectangular blue or yellow panel with light text on it in the upper
part of the frame is reported as ``direction_sign`` with label ``autobahn``
or ``road``. Over several frames this becomes the road type fact.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from ..detection import Detection, circularity, suppress


@dataclass
class DirectionConfig:
    roi_bottom: float = 0.6
    min_area_frac: float = 0.006
    max_circularity: float = 0.85     # round blue signs are mandatory signs, not panels
    min_rectangularity: float = 0.65
    aspect: tuple = (0.6, 6.0)
    text_frac: tuple = (0.01, 0.45)   # share of light / dark text pixels inside


# (hue range, saturation thresholds tried in turn, value minimum, text colour).
# A strict saturation keeps a pale sky from merging with the panel, a looser
# one catches panels in flat light.
PANELS = {
    "autobahn": ((100, 125), (130, 100), 70, "light"),
    "road": ((18, 32), (130,), 130, "dark"),
}


class DirectionSignDetector:
    name = "direction_sign"

    def __init__(self, cfg: DirectionConfig = DirectionConfig()):
        self.cfg = cfg

    def __call__(self, image) -> List[Detection]:
        cfg = self.cfg
        H, W = image.shape[:2]
        roi = image[: int(H * cfg.roi_bottom)]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        kernel = np.ones((5, 5), np.uint8)
        out = []
        for label, (hue, sats, v_min, text) in PANELS.items():
            for s_min in sats:
                lo, hi = (hue[0], s_min, v_min), (hue[1], 255, 255)
                out.extend(self._panels(hsv, grey, lo, hi, text, label, H, W, kernel))
        return suppress(out)

    def _panels(self, hsv, grey, lo, hi, text, label, H, W, kernel):
        cfg = self.cfg
        mask = cv2.inRange(hsv, lo, hi)
        # close over the text so the panel is one region
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < cfg.min_area_frac * H * W:
                continue
            (cx, cy), (rw, rh), _ = cv2.minAreaRect(c)
            if rw * rh <= 0 or area / (rw * rh) < cfg.min_rectangularity:
                continue
            if circularity(cv2.convexHull(c)) > cfg.max_circularity:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if not cfg.aspect[0] <= w / max(h, 1) <= cfg.aspect[1]:
                continue
            inside = grey[y:y + h, x:x + w]
            # filled outline: large blocks of lettering stay holes in the mask
            filled = np.zeros((h, w), np.uint8)
            cv2.drawContours(filled, [c - np.array([x, y])], -1, 255, -1)
            panel = filled > 0
            raw = cv2.inRange(hsv[y:y + h, x:x + w], lo, hi) > 0
            holes = panel & ~raw
            sat = hsv[y:y + h, x:x + w, 1]
            if text == "light":
                # white lettering: unsaturated and clearly brighter than dark
                # (compression softens it, so no fixed high threshold)
                share = float((holes & (sat < 90) & (inside > 110)).mean())
            else:
                share = float((holes & (inside < 90)).mean())
            if not cfg.text_frac[0] <= share <= cfg.text_frac[1]:
                continue
            score = min(1.0, area / (0.02 * H * W))
            out.append(Detection(self.name, label, (x, y, w, h), score,
                                 {"text_share": round(share, 3)}))
        return out
