import time

import numpy as np
import pytest

from conftest import scene
from roadsign.detect.direction import DirectionSignDetector
from roadsign.detect.lights import TrafficLightDetector
from roadsign.detection import Detection, iou, suppress
from roadsign.pipeline import Pipeline
from roadsign.video import LatestSource, QueuedSource, SequentialSource


def numbered_frames(n):
    frames = []
    for i in range(n):
        f = np.zeros((48, 64, 3), np.uint8)
        f[:, :] = (i * 7) % 256   # brightness encodes the index
        frames.append(f)
    return frames


def test_sequential_and_queued_deliver_every_frame(make_video):
    path = make_video(numbered_frames(40))
    seq = [f.index for f in SequentialSource(path)]
    q = QueuedSource(path, queue_size=4)
    queued = [f.index for f in q]
    q.close()
    assert seq == queued == list(range(40))


def test_latest_drops_frames_for_a_slow_consumer(make_video):
    path = make_video(numbered_frames(60), fps=100)
    src = LatestSource(path, realtime=True)
    got = []
    for f in src:
        got.append(f.index)
        time.sleep(0.03)          # consumer slower than 100 fps
    src.close()
    assert got == sorted(got)
    assert src.stats.dropped > 10
    assert src.stats.delivered + src.stats.dropped == src.stats.read


def test_max_frames_and_scale(make_video):
    path = make_video(numbered_frames(20))
    frames = list(SequentialSource(path, scale=0.5, max_frames=5))
    assert len(frames) == 5
    assert frames[0].image.shape[:2] == (24, 32)


@pytest.mark.parametrize("color", ["red", "green"])
def test_traffic_light_on_synthetic_scene(color):
    found = TrafficLightDetector()(scene(light=color))
    assert [d.label for d in found] == [color]


def test_no_light_without_housing():
    img = scene()
    import cv2
    cv2.circle(img, (300, 80), 5, (30, 30, 255), -1)   # red dot on bright sky
    assert TrafficLightDetector()(img) == []


def test_blue_panel_is_autobahn():
    found = DirectionSignDetector()(scene(blue_panel=True))
    assert [d.label for d in found] == ["autobahn"]
    assert DirectionSignDetector()(scene()) == []


def test_suppress_keeps_best():
    a = Detection("x", "1", (0, 0, 10, 10), 0.9)
    b = Detection("x", "1", (1, 1, 10, 10), 0.5)
    c = Detection("x", "1", (50, 50, 10, 10), 0.4)
    assert iou(a.box, b.box) > 0.5
    assert suppress([b, a, c]) == [a, c]


class Fake:
    """Detector that reports a red light on every frame, with a fixed cost."""
    name = "fake"

    def __init__(self, ms=2.0):
        self.ms = ms

    def __call__(self, image):
        time.sleep(self.ms / 1000)
        return [Detection("traffic_light", "red", (0, 0, 5, 5))]


@pytest.mark.parametrize("mode", ["sequential", "threaded", "parallel"])
def test_modes_give_the_same_facts(make_video, mode):
    path = make_video(numbered_frames(30))
    stats, facts = Pipeline([Fake(), DirectionSignDetector()]).run(path, mode)
    assert stats.frames_processed == 30
    assert stats.frames_dropped == 0
    assert [(e.action, e.name, e.value) for e in facts.events] == [("assert", "traffic-light", "red")]
    assert set(stats.detector_ms) == {"fake", "direction_sign"}


class Busy:
    """Detector doing real OpenCV work, which releases the GIL like the real
    detectors (time.sleep is too coarse on Windows to measure overlap)."""

    def __init__(self, name):
        self.name = name
        self.img = np.random.default_rng(0).integers(0, 255, (1200, 1200), np.uint8)

    def __call__(self, image):
        import cv2
        for _ in range(3):
            cv2.GaussianBlur(self.img, (31, 31), 0)
        return []


def test_parallel_overlaps_detectors(make_video):
    import cv2
    cv2.setNumThreads(1)          # keep OpenCV from using all cores inside one call
    path = make_video(numbered_frames(20))
    slow = [Busy("a"), Busy("b")]
    seq, _ = Pipeline(slow).run(path, "sequential")
    par, _ = Pipeline(slow).run(path, "parallel")
    cv2.setNumThreads(-1)
    # two equal detectors: ideal is half the time, allow for a busy machine
    assert np.median(par.frame_ms) < 0.9 * np.median(seq.frame_ms)


def test_unknown_mode(make_video):
    with pytest.raises(ValueError):
        Pipeline([Fake()]).run(make_video(numbered_frames(2)), "turbo")
