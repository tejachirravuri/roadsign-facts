"""Drawing detections and the current facts onto a frame."""
from __future__ import annotations

import cv2

COLORS = {
    ("traffic_light", "red"): (0, 0, 255),
    ("traffic_light", "green"): (0, 220, 0),
    ("speed_limit", None): (0, 200, 255),
    ("sign", None): (255, 160, 0),
    ("direction_sign", "autobahn"): (255, 0, 255),
    ("direction_sign", "road"): (0, 220, 255),
}


def _color(d):
    return COLORS.get((d.kind, d.label)) or COLORS.get((d.kind, None), (200, 200, 200))


def draw(image, detections, facts=None):
    out = image.copy()
    scale = max(0.4, out.shape[0] / 720)
    for d in detections:
        x, y, w, h = d.box
        c = _color(d)
        cv2.rectangle(out, (x, y), (x + w, y + h), c, max(1, int(2 * scale)))
        cv2.putText(out, d.label, (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 * scale, c, max(1, int(scale)), cv2.LINE_AA)
    if facts is not None:
        lines = ["%s: %s" % (k, ", ".join(v)) for k, v in facts.snapshot().items()]
        y = int(22 * scale)
        for line in lines:
            cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale,
                        (0, 0, 0), max(2, int(4 * scale)), cv2.LINE_AA)
            cv2.putText(out, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale,
                        (255, 255, 255), max(1, int(1.5 * scale)), cv2.LINE_AA)
            y += int(24 * scale)
    return out
