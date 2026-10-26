"""Frame sources.

Three ways of getting frames out of cv2.VideoCapture:

- ``SequentialSource``: read and decode in the calling thread. Simple, but
  the detectors wait while a frame is decoded.
- ``QueuedSource``: a reader thread decodes ahead into a bounded queue. Every
  frame is processed exactly once, decoding overlaps with processing. This is
  the right choice for recorded video.
- ``LatestSource``: a reader thread keeps only the newest frame. The consumer
  always gets the most recent image and older ones are dropped. This is what
  a live camera needs (stale frames are useless), but on a recorded file it
  skips frames, so it has to report how many it dropped. Otherwise a higher
  "FPS" just means less work was done.

OpenCV releases the GIL while decoding, so a plain thread is enough here.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

import cv2
import numpy as np


@dataclass
class Frame:
    index: int            # position in the video (0-based)
    t: float              # video time in seconds
    image: np.ndarray
    read_at: float = 0.0  # perf_counter when the frame was decoded


@dataclass
class SourceStats:
    read: int = 0
    delivered: int = 0
    dropped: int = 0
    decode_s: float = 0.0

    def as_dict(self):
        return {"read": self.read, "delivered": self.delivered,
                "dropped": self.dropped, "decode_s": round(self.decode_s, 3)}


class _Base:
    def __init__(self, path, scale: float = 1.0, max_frames: Optional[int] = None):
        self.path = str(path)
        self.cap = cv2.VideoCapture(self.path)
        if not self.cap.isOpened():
            raise OSError("cannot open video %s" % path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.scale = scale
        self.max_frames = max_frames
        self.stats = SourceStats()
        self._index = 0

    def _grab(self) -> Optional[Frame]:
        if self.max_frames is not None and self._index >= self.max_frames:
            return None
        start = time.perf_counter()
        ok, image = self.cap.read()
        if not ok or image is None:
            return None
        if self.scale != 1.0:
            image = cv2.resize(image, None, fx=self.scale, fy=self.scale,
                               interpolation=cv2.INTER_AREA)
        now = time.perf_counter()
        self.stats.decode_s += now - start
        self.stats.read += 1
        frame = Frame(self._index, self._index / self.fps, image, now)
        self._index += 1
        return frame

    def close(self):
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class SequentialSource(_Base):
    def __iter__(self) -> Iterator[Frame]:
        while True:
            frame = self._grab()
            if frame is None:
                return
            self.stats.delivered += 1
            yield frame


class QueuedSource(_Base):
    def __init__(self, path, scale=1.0, max_frames=None, queue_size: int = 64):
        super().__init__(path, scale, max_frames)
        self._queue: "queue.Queue[Optional[Frame]]" = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            while not self._stop.is_set():
                frame = self._grab()
                self._queue.put(frame)      # blocks while the queue is full
                if frame is None:
                    return
        except Exception:                   # never leave the consumer waiting
            self._queue.put(None)
            raise

    def __iter__(self) -> Iterator[Frame]:
        self._thread.start()
        while True:
            frame = self._queue.get()
            if frame is None:
                return
            self.stats.delivered += 1
            yield frame

    def close(self):
        self._stop.set()
        while not self._queue.empty():     # unblock a waiting producer
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        super().close()


class LatestSource(_Base):
    """Keeps only the newest frame. ``realtime=True`` paces the reader at the
    video frame rate, which is how a camera behaves; without it the reader
    decodes as fast as it can."""

    def __init__(self, path, scale=1.0, max_frames=None, realtime: bool = True):
        super().__init__(path, scale, max_frames)
        self.realtime = realtime
        self._latest: Optional[Frame] = None
        self._done = False
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        start = time.perf_counter()
        while not self._stop.is_set():
            frame = self._grab()
            with self._cond:
                if frame is None:
                    self._done = True
                    self._cond.notify_all()
                    return
                if self._latest is not None:
                    self.stats.dropped += 1
                self._latest = frame
                self._cond.notify_all()
            if self.realtime:
                due = start + (frame.index + 1) / self.fps
                delay = due - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)

    def __iter__(self) -> Iterator[Frame]:
        self._thread.start()
        while True:
            with self._cond:
                while self._latest is None and not self._done:
                    self._cond.wait()
                if self._latest is None and self._done:
                    return
                frame, self._latest = self._latest, None
            self.stats.delivered += 1
            yield frame

    def close(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        super().close()


SOURCES = {"sequential": SequentialSource, "queued": QueuedSource, "latest": LatestSource}


def open_source(kind: str, path, **kwargs):
    try:
        cls = SOURCES[kind]
    except KeyError:
        raise ValueError("unknown source %r (use %s)" % (kind, ", ".join(SOURCES))) from None
    if kind != "queued":
        kwargs.pop("queue_size", None)
    if kind != "latest":
        kwargs.pop("realtime", None)
    return cls(path, **kwargs)
