"""Traffic light state from colour blobs.

A lit lamp is a small, bright, saturated and roughly round blob. What tells
it apart from tail lights, red/white barriers, posters, flags or leaves is
the housing around it: dark and unsaturated below a red lamp (yellow and
green are off) or above a green one, and dark at the sides. Only the upper
part of the frame is searched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from ..detection import Detection, circularity, clip_box, hsv, red_mask, suppress


@dataclass
class LightConfig:
    roi_bottom: float = 0.65          # search above this fraction of the height
    min_area_frac: float = 6e-6       # blob area relative to frame area
    max_area_frac: float = 1.5e-3
    min_circularity: float = 0.45
    v_min: int = 170
    housing_max_v: float = 110.0      # mean brightness of the housing
    housing_max_s: float = 100.0      # housing is black or grey, not coloured
    side_max_v: float = 140.0         # beside the lamp is housing too
    housing_cells: float = 2.0        # housing length in lamp diameters
    min_contrast: float = 75.0        # lamp brighter than its housing by this much
    max_ring_share: float = 0.3       # same colour around the lamp: car body, roof, poster


GREEN_LOW, GREEN_HIGH = (55, 70, 0), (100, 255, 255)


def mask_any_brightness(hsv_image, label):
    """Lamp colour at any brightness, to see whether the surroundings share it."""
    if label == "red":
        # red to orange: a red lamp is never set in an orange wall or roof
        return red_mask(hsv_image, s_min=110, v_min=40, hue_low_max=22)
    # saturated green only: a pale blue sky would otherwise count as green
    return cv2.inRange(hsv_image, (60, 120, 40), (95, 255, 255))


class TrafficLightDetector:
    name = "traffic_light"

    def __init__(self, cfg: LightConfig = LightConfig()):
        self.cfg = cfg

    def _blobs(self, mask, area_min, area_max):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if not area_min <= area <= area_max:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if not 0.55 <= w / max(h, 1) <= 1.8:
                continue
            if circularity(c) < self.cfg.min_circularity:
                continue
            yield x, y, w, h

    def _housing(self, hsv_image, box, below: bool):
        """Mean value and saturation of the housing below / above the lamp,
        and the brightness of the strips left and right of it."""
        v, s = hsv_image[:, :, 2], hsv_image[:, :, 1]
        x, y, w, h = box
        d = max(w, h)
        length = int(round(self.cfg.housing_cells * d))
        if below:
            region = clip_box(x - 0.25 * d, y + h + 0.2 * d, w + 0.5 * d, length, v.shape)
        else:
            region = clip_box(x - 0.25 * d, y - 0.2 * d - length, w + 0.5 * d, length, v.shape)
        rx, ry, rw, rh = region
        if rw < 2 or rh < max(2, length // 2):
            return None
        side = max(1, int(round(0.35 * d)))
        sides = []
        for sx in (x - side - 1, x + w + 1):
            bx = clip_box(sx, y, side, h, v.shape)
            if bx[2] and bx[3]:
                sides.append(v[bx[1]:bx[1] + bx[3], bx[0]:bx[0] + bx[2]].mean())
        side_v = float(max(sides)) if sides else 255.0
        return (float(v[ry:ry + rh, rx:rx + rw].mean()),
                float(s[ry:ry + rh, rx:rx + rw].mean()), side_v)

    @staticmethod
    def _ring_share(colour, box):
        """Share of lamp coloured pixels in a ring around the lamp, leaving
        out the glow right next to it."""
        x, y, w, h = box
        d = max(w, h)
        rx, ry, rw, rh = clip_box(x - d, y - d, w + 2 * d, h + 2 * d, colour.shape)
        ring = colour[ry:ry + rh, rx:rx + rw] > 0
        inner = np.zeros_like(ring)
        g = int(round(0.4 * d))
        inner[max(0, y - ry - g):y - ry + h + g, max(0, x - rx - g):x - rx + w + g] = True
        outside = ~inner
        return float(ring[outside].mean()) if outside.any() else 0.0

    def __call__(self, image) -> List[Detection]:
        cfg = self.cfg
        H, W = image.shape[:2]
        roi = image[: int(H * cfg.roi_bottom)]
        h = hsv(roi)
        v = h[:, :, 2]
        bright = v >= cfg.v_min
        area_min = max(3.0, cfg.min_area_frac * H * W)
        area_max = cfg.max_area_frac * H * W
        kernel = np.ones((3, 3), np.uint8)

        out = []
        for label, mask, below in (
                # narrow red hue: orange fences and amber lamps are hue 10-25
                ("red", red_mask(h, s_min=110, v_min=cfg.v_min, hue_low_max=7), True),
                ("green", cv2.inRange(h, GREEN_LOW, GREEN_HIGH) & (bright * 255).astype(np.uint8), False)):
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            colour = mask_any_brightness(h, label)
            for box in self._blobs(mask, area_min, area_max):
                housing = self._housing(h, box, below)
                if housing is None:
                    continue
                dark, sat, side = housing
                if dark > cfg.housing_max_v or sat > cfg.housing_max_s or side > cfg.side_max_v:
                    continue
                x, y, w, hh = box
                lamp_v = float(v[y:y + hh, x:x + w].mean())
                if lamp_v - dark < cfg.min_contrast:
                    continue
                if self._ring_share(colour, box) > cfg.max_ring_share:
                    continue
                score = min(1.0, (lamp_v - dark) / 150.0)
                out.append(Detection(self.name, label, box, score))
        return suppress(out)
