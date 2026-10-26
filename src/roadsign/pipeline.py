"""Running all detectors on a video and producing facts.

Modes:

- ``sequential``  decode, then run the detectors one after the other, all in
                  the main thread (how the original scripts worked)
- ``threaded``    a reader thread decodes ahead into a queue, the detectors
                  run one after the other in the main thread
- ``parallel``    reader thread plus all detectors on the same frame at the
                  same time in a thread pool (OpenCV releases the GIL)
- ``live``        like parallel, but the reader runs at the video frame rate
                  and keeps only the newest frame, like a camera. Frames the
                  detectors cannot keep up with are dropped and counted.

Every mode processes the frames it gets in order and feeds the fact base.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from .facts import FactBase, FactConfig, FactEvent
from .video import open_source

MODES = {
    "sequential": ("sequential", False),
    "threaded": ("queued", False),
    "parallel": ("queued", True),
    "live": ("latest", True),
}


@dataclass
class RunStats:
    video: str
    mode: str
    scale: float
    frames_in_video: int
    frames_read: int = 0
    frames_processed: int = 0
    frames_dropped: int = 0
    wall_s: float = 0.0
    cpu_percent: Optional[float] = None
    detector_ms: Dict[str, List[float]] = field(default_factory=dict)
    frame_ms: List[float] = field(default_factory=list)
    latency_ms: List[float] = field(default_factory=list)
    detections: Dict[str, int] = field(default_factory=dict)
    facts: int = 0

    @property
    def fps(self):
        return self.frames_processed / self.wall_s if self.wall_s else 0.0

    def summary(self) -> dict:
        def stat(values):
            if not values:
                return {"mean": None, "p95": None}
            a = np.asarray(values)
            return {"mean": round(float(a.mean()), 2), "p95": round(float(np.percentile(a, 95)), 2)}
        return {
            "video": self.video, "mode": self.mode, "scale": self.scale,
            "frames_in_video": self.frames_in_video, "frames_read": self.frames_read,
            "frames_processed": self.frames_processed, "frames_dropped": self.frames_dropped,
            "wall_s": round(self.wall_s, 2), "processed_fps": round(self.fps, 2),
            "cpu_percent": self.cpu_percent,
            "frame_ms": stat(self.frame_ms), "latency_ms": stat(self.latency_ms),
            "detector_ms": {k: stat(v) for k, v in self.detector_ms.items()},
            "detections": self.detections, "facts": self.facts,
        }


class Pipeline:
    def __init__(self, detectors: list, fact_cfg: FactConfig = FactConfig()):
        self.detectors = detectors
        self.fact_cfg = fact_cfg

    def run(self, video, mode: str = "parallel", scale: float = 1.0,
            max_frames: Optional[int] = None,
            on_frame: Optional[Callable] = None, on_event: Optional[Callable] = None):
        """Returns (RunStats, FactBase). ``on_frame(frame, detections, events)``
        is called for every processed frame, ``on_event(event)`` for every fact
        change."""
        try:
            source_kind, parallel = MODES[mode]
        except KeyError:
            raise ValueError("unknown mode %r (use %s)" % (mode, ", ".join(MODES))) from None
        facts = FactBase(self.fact_cfg)
        source = open_source(source_kind, video, scale=scale, max_frames=max_frames)
        stats = RunStats(Path(str(video)).name, mode, scale, source.frame_count,
                         detector_ms={d.name: [] for d in self.detectors})
        pool = ThreadPoolExecutor(max_workers=len(self.detectors)) if parallel else None

        def timed(det, image):
            t0 = time.perf_counter()
            result = det(image)
            return det.name, result, (time.perf_counter() - t0) * 1000

        proc = _process_handle()
        cpu0 = _cpu_times(proc)
        start = time.perf_counter()
        try:
            for frame in source:
                t0 = time.perf_counter()
                if pool:
                    results = list(pool.map(lambda d: timed(d, frame.image), self.detectors))
                else:
                    results = [timed(d, frame.image) for d in self.detectors]
                detections = []
                for name, found, ms in results:
                    stats.detector_ms[name].append(ms)
                    detections.extend(found)
                    for d in found:
                        stats.detections[d.kind] = stats.detections.get(d.kind, 0) + 1
                events = facts.update(frame.index, frame.t, detections)
                done = time.perf_counter()
                stats.frame_ms.append((done - t0) * 1000)
                stats.latency_ms.append((done - frame.read_at) * 1000)
                stats.frames_processed += 1
                if on_event:
                    for ev in events:
                        on_event(ev)
                if on_frame:
                    on_frame(frame, detections, events, facts)
        finally:
            stats.wall_s = time.perf_counter() - start
            cpu1 = _cpu_times(proc)
            if cpu0 is not None and cpu1 is not None and stats.wall_s > 0:
                stats.cpu_percent = round(100 * (cpu1 - cpu0) / stats.wall_s, 1)
            stats.frames_read = source.stats.read
            stats.frames_dropped = source.stats.dropped
            stats.facts = len(facts.events)
            source.close()
            if pool:
                pool.shutdown()
        return stats, facts


def _process_handle():
    try:
        import psutil
        return psutil.Process()
    except ImportError:
        return None


def _cpu_times(proc):
    if proc is None:
        return None
    t = proc.cpu_times()
    return t.user + t.system


def default_detectors(model_path):
    from .classifier import SignClassifier
    from .detect.direction import DirectionSignDetector
    from .detect.lights import TrafficLightDetector
    from .detect.signs import SignDetector
    return [TrafficLightDetector(), SignDetector(SignClassifier.load(model_path)),
            DirectionSignDetector()]
