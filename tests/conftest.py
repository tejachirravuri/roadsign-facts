import cv2
import numpy as np
import pytest


def scene(light=None, speed_sign=False, blue_panel=False, size=(360, 640)):
    """Synthetic road frame: grey sky, darker road, optional objects."""
    H, W = size
    img = np.full((H, W, 3), (200, 190, 180), np.uint8)
    img[int(H * 0.6):] = (90, 90, 90)
    if light:
        x, y = 300, 60
        cv2.rectangle(img, (x, y), (x + 16, y + 44), (25, 25, 25), -1)   # housing
        cy = y + 8 if light == "red" else y + 36
        color = (30, 30, 255) if light == "red" else (170, 255, 40)
        cv2.circle(img, (x + 8, cy), 5, color, -1)
    if speed_sign:
        cv2.circle(img, (500, 120), 22, (255, 255, 255), -1)
        cv2.circle(img, (500, 120), 22, (30, 30, 220), 5)
    if blue_panel:
        cv2.rectangle(img, (60, 30), (260, 110), (170, 70, 10), -1)
        for i in range(3):
            cv2.putText(img, "Kassel 7", (75, 55 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 2)
    return img


@pytest.fixture
def make_video(tmp_path):
    def _make(frames, name="clip.avi", fps=25):
        path = tmp_path / name
        h, w = frames[0].shape[:2]
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
        for f in frames:
            writer.write(f)
        writer.release()
        return path
    return _make
