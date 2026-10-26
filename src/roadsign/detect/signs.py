"""Traffic signs: colour candidates, shape filter, HOG/SVM classification.

Candidates are regions with a red border (prohibition and warning signs) or
a blue disc (mandatory signs). Each candidate is cropped with a small margin
and classified into the 43 GTSRB classes or 'background'. Speed limits are
reported as kind ``speed_limit`` with the number as label, everything else
as kind ``sign``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from ..classifier import BACKGROUND, NAMES, SPEED, SignClassifier
from ..detection import Detection, circularity, clip_box, hsv, red_mask, suppress


@dataclass
class SignConfig:
    roi_bottom: float = 0.75
    min_size_frac: float = 0.025      # of the frame height
    max_size_frac: float = 0.35
    min_margin: float = 0.4           # SVM decision margin to accept a class
    max_candidates: int = 40
    max_solid: float = 0.7            # red share inside the hull for non-round shapes
    blue_min_circularity: float = 0.84  # blue signs must be discs (a square is 0.785)
    blue_max_fill: float = 0.88       # a disc fills ~0.79 of its box, a square sign ~1


# What the inside of a sign of each class looks like. Most prohibition and
# warning signs are white inside a red border; checking this rejects red
# cars, lamps and posters that the classifier happens to like.
INTERIOR = {}
INTERIOR.update({c: "white" for c in list(range(0, 12)) + [13, 15, 16] + list(range(18, 32))})
INTERIOR.update({c: "white" for c in (6, 32, 41, 42)})       # end of ... signs
INTERIOR.update({12: "yellow", 14: "red", 17: "red"})
INTERIOR.update({c: "blue" for c in range(33, 41)})


def interior_matches(image, box, cls) -> bool:
    kind = INTERIOR.get(cls)
    if kind is None:
        return True
    x, y, w, h = box
    # central part, a bit lower for triangles pointing up
    cx0, cx1 = x + int(0.3 * w), x + int(0.7 * w)
    cy0, cy1 = y + int(0.35 * h), y + int(0.75 * h)
    if cx1 <= cx0 or cy1 <= cy0:
        return False
    patch = cv2.cvtColor(image[cy0:cy1, cx0:cx1], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(int)
    hue, sat, val = patch[:, 0], patch[:, 1], patch[:, 2]
    if kind == "white":
        # white with black or grey symbols: few saturated pixels, some bright ones
        return (sat < 80).mean() > 0.6 and (val > 120).mean() > 0.3
    if kind == "yellow":
        return ((hue >= 15) & (hue <= 35) & (sat > 90)).mean() > 0.3
    if kind == "blue":
        return ((hue >= 95) & (hue <= 130) & (sat > 90)).mean() > 0.3
    return (((hue <= 10) | (hue >= 165)) & (sat > 90)).mean() > 0.3


class SignDetector:
    name = "sign"

    def __init__(self, classifier: SignClassifier, cfg: SignConfig = SignConfig()):
        self.clf = classifier
        self.cfg = cfg

    def candidates(self, image):
        cfg = self.cfg
        H, W = image.shape[:2]
        roi = image[: int(H * cfg.roi_bottom)]
        h = hsv(roi)
        min_size = max(10, int(cfg.min_size_frac * H))
        max_size = int(cfg.max_size_frac * H)
        kernel = np.ones((3, 3), np.uint8)

        red = cv2.morphologyEx(red_mask(h, s_min=80, v_min=50), cv2.MORPH_CLOSE, kernel)
        blue = cv2.morphologyEx(cv2.inRange(h, (100, 120, 50), (125, 255, 255)), cv2.MORPH_OPEN, kernel)
        boxes = []
        for mask, need_round in ((red, False), (blue, True)):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                x, y, w, hh = cv2.boundingRect(c)
                if not (min_size <= w <= max_size and min_size <= hh <= max_size):
                    continue
                if not 0.7 <= w / hh <= 1.4:
                    continue
                hull = cv2.convexHull(c)
                fill = cv2.contourArea(hull) / float(w * hh)
                round_ = circularity(hull)
                if need_round and (round_ < cfg.blue_min_circularity or fill > cfg.blue_max_fill):
                    continue
                # discs fill ~0.78 of their box, triangles ~0.5
                if not (round_ > 0.6 or 0.4 < fill < 0.65):
                    continue
                if not need_round:
                    # sign borders are hollow; a solid red region must be
                    # round (stop, no entry), otherwise it is e.g. a stripe
                    # of a red/white warning beacon
                    hull_mask = np.zeros((hh, w), np.uint8)
                    cv2.drawContours(hull_mask, [hull - np.array([x, y])], -1, 255, -1)
                    inside = hull_mask > 0
                    solid = float((mask[y:y + hh, x:x + w][inside] > 0).mean()) if inside.any() else 1.0
                    if solid > cfg.max_solid and round_ < 0.8:
                        continue
                boxes.append((x, y, w, hh))
        boxes.sort(key=lambda b: -b[2] * b[3])
        return boxes[: cfg.max_candidates]

    def __call__(self, image) -> List[Detection]:
        boxes = self.candidates(image)
        if not boxes:
            return []
        crops, kept = [], []
        for x, y, w, h in boxes:
            m = 0.12
            bx = clip_box(x - m * w, y - m * h, w * (1 + 2 * m), h * (1 + 2 * m), image.shape)
            crop = image[bx[1]:bx[1] + bx[3], bx[0]:bx[0] + bx[2]]
            if crop.size:
                crops.append(crop)
                kept.append((x, y, w, h))
        classes, margins = self.clf.predict(crops)
        out = []
        for box, cls, margin in zip(kept, classes, margins):
            cls = int(cls)
            if cls == BACKGROUND or margin < self.cfg.min_margin:
                continue
            if not interior_matches(image, box, cls):
                continue
            if cls in SPEED:
                out.append(Detection("speed_limit", str(SPEED[cls]), box, float(margin),
                                     {"class_id": cls}))
            else:
                out.append(Detection("sign", NAMES[cls], box, float(margin), {"class_id": cls}))
        return suppress(out)
