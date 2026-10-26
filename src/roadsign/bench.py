"""Benchmark of pipeline modes and frame sizes.

The numbers that matter for a camera in a car:

- processed fps: frames that went through all detectors per second of wall
  time. Comparing modes on a recorded video is only fair if all of them
  process the same frames, so ``frames_processed`` is reported next to it.
- dropped frames: only the live mode drops; it shows how much of the scene
  the detectors miss at a given camera frame rate.
- latency: time from a frame being decoded to its facts being updated.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .pipeline import Pipeline, default_detectors


def run_bench(videos, modes, scales, model_path, max_frames: Optional[int] = None,
              repeat: int = 1, opencv_threads: Optional[int] = None) -> List[dict]:
    import cv2
    if opencv_threads is not None:
        cv2.setNumThreads(opencv_threads)
    pipeline = Pipeline(default_detectors(model_path))
    rows = []
    for video in videos:
        for scale in scales:
            for mode in modes:
                for rep in range(repeat):
                    stats, facts = pipeline.run(video, mode, scale, max_frames)
                    s = stats.summary()
                    row = {
                        "video": s["video"], "mode": mode, "scale": scale, "repeat": rep,
                        "opencv_threads": opencv_threads if opencv_threads is not None else cv2.getNumThreads(),
                        "frames_in_video": s["frames_in_video"], "frames_read": s["frames_read"],
                        "frames_processed": s["frames_processed"], "frames_dropped": s["frames_dropped"],
                        "wall_s": s["wall_s"], "processed_fps": s["processed_fps"],
                        "cpu_percent": s["cpu_percent"],
                        "frame_ms_mean": s["frame_ms"]["mean"], "frame_ms_p95": s["frame_ms"]["p95"],
                        "latency_ms_mean": s["latency_ms"]["mean"], "latency_ms_p95": s["latency_ms"]["p95"],
                        "facts": s["facts"],
                    }
                    for name, st in s["detector_ms"].items():
                        row["%s_ms" % name] = st["mean"]
                    rows.append(row)
    return rows
