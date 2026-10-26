"""Turning per-frame detections into facts for an expert system.

Single frames are noisy, so a fact is only asserted when its value was seen
in at least ``min_hits`` of the last ``window`` frames. How long it stays
depends on its meaning:

- ``speed-limit``: valid until a different limit is seen (like on the road)
- ``traffic-light``: retracted when not seen for ``light_hold_s``
- ``road-type``: autobahn / road from the colour of direction signs, valid
  until the other kind is seen
- ``sign``: any other sign, retracted after ``sign_hold_s``

Every change is an event (assert or retract) with the video time, which can
be written as JSON lines, as CLIPS ``assert`` commands or sent as CAN frames.
"""
from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Tuple


@dataclass
class FactConfig:
    window: int = 12
    min_hits: int = 4
    light_hold_s: float = 1.5
    sign_hold_s: float = 2.0


@dataclass
class FactEvent:
    t: float
    frame: int
    action: str           # assert | retract
    name: str             # speed-limit | traffic-light | road-type | sign
    value: str

    def as_dict(self):
        return asdict(self)

    def clips(self) -> str:
        value = self.value if self.value.replace(".", "").isdigit() else '"%s"' % self.value
        if self.action == "assert":
            return "(assert (%s %s))" % (self.name, value)
        return "(retract-fact %s %s)" % (self.name, value)


KIND_TO_FACT = {
    "speed_limit": "speed-limit",
    "traffic_light": "traffic-light",
    "direction_sign": "road-type",
    "sign": "sign",
}
STICKY = {"speed-limit", "road-type"}


class FactBase:
    def __init__(self, cfg: FactConfig = FactConfig()):
        self.cfg = cfg
        self.history: Dict[str, Deque[Tuple[str, ...]]] = {
            name: deque(maxlen=cfg.window) for name in KIND_TO_FACT.values()}
        self.current: Dict[str, set] = {name: set() for name in KIND_TO_FACT.values()}
        self.last_seen: Dict[Tuple[str, str], float] = {}
        self.events: List[FactEvent] = []

    def _emit(self, t, frame, action, name, value, out):
        ev = FactEvent(round(t, 3), frame, action, name, value)
        self.events.append(ev)
        out.append(ev)

    def update(self, frame: int, t: float, detections: Iterable) -> List[FactEvent]:
        seen: Dict[str, set] = {name: set() for name in self.history}
        for d in detections:
            name = KIND_TO_FACT.get(d.kind)
            if name:
                seen[name].add(d.label)
        out: List[FactEvent] = []
        for name, values in seen.items():
            self.history[name].append(tuple(sorted(values)))
            counts = Counter(v for vals in self.history[name] for v in vals)
            confirmed = {v for v, n in counts.items() if n >= self.cfg.min_hits}
            for v in values & confirmed:
                self.last_seen[(name, v)] = t

            if name in STICKY:
                if not confirmed:
                    continue
                # the value seen most often in the window replaces the old one
                best = max(confirmed, key=lambda v: (counts[v], v))
                if best not in self.current[name]:
                    for old in sorted(self.current[name]):
                        self._emit(t, frame, "retract", name, old, out)
                    self.current[name] = {best}
                    self._emit(t, frame, "assert", name, best, out)
                continue

            hold = self.cfg.light_hold_s if name == "traffic-light" else self.cfg.sign_hold_s
            for v in sorted(confirmed - self.current[name]):
                if v in values:
                    self.current[name].add(v)
                    self._emit(t, frame, "assert", name, v, out)
            for v in sorted(self.current[name]):
                if t - self.last_seen.get((name, v), t) > hold:
                    self.current[name].discard(v)
                    self._emit(t, frame, "retract", name, v, out)
        return out

    def snapshot(self) -> Dict[str, List[str]]:
        return {name: sorted(values) for name, values in self.current.items() if values}

    def deffacts(self, title: str = "camera") -> str:
        lines = ["(deffacts %s" % title]
        for name, values in self.snapshot().items():
            for v in values:
                lines.append("   (%s %s)" % (name, v if v.isdigit() else '"%s"' % v))
        lines.append(")")
        return "\n".join(lines) + "\n"


def write_jsonl(path, events: Iterable[FactEvent]):
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.as_dict()) + "\n")


def write_clips(path, events: Iterable[FactEvent]):
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write("; t=%.2fs frame %d\n%s\n" % (ev.t, ev.frame, ev.clips()))
