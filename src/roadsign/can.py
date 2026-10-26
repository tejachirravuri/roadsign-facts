"""Facts as CAN messages.

In the project setup each Raspberry Pi runs image processing algorithms and
sends its results over CAN (PiCAN2 boards) to the comprehension level, which
builds the facts file for the expert system. This module defines that
message format and two transports:

- ``VirtualBus``: in-process, thread safe, used for tests and for running
  everything on one machine
- ``PythonCanBus``: wraps python-can, e.g. ``socketcan`` on ``can0`` with a
  PiCAN2, or python-can's own ``virtual`` interface

Message layout (classic CAN, 8 data bytes, little endian):

    byte 0     action      1 = assert, 0 = retract
    byte 1     value code  speed in km/h, light 1 red / 2 green,
                           road 1 autobahn / 2 road, sign: GTSRB class id
    byte 2     source      1 lights, 2 signs, 3 direction signs
    byte 3     reserved
    bytes 4-7  video time in ms (uint32)

Arbitration ids: 0x110 speed-limit, 0x120 traffic-light, 0x130 road-type,
0x140 sign. Lower ids win arbitration, so speed limits have priority.
"""
from __future__ import annotations

import queue
import struct
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .classifier import NAMES
from .facts import FactEvent

IDS = {"speed-limit": 0x110, "traffic-light": 0x120, "road-type": 0x130, "sign": 0x140}
NAMES_BY_ID = {v: k for k, v in IDS.items()}
SOURCE = {"speed-limit": 2, "traffic-light": 1, "road-type": 3, "sign": 2}
LIGHTS = {"red": 1, "green": 2}
ROADS = {"autobahn": 1, "road": 2}
PAYLOAD = struct.Struct("<BBBBI")


@dataclass
class CanFrame:
    arbitration_id: int
    data: bytes
    timestamp: float = 0.0

    def candump(self, channel="vcan0") -> str:
        return "(%.6f) %s %03X#%s" % (self.timestamp, channel, self.arbitration_id,
                                      self.data.hex().upper())


def _value_code(name, value) -> int:
    if name == "speed-limit":
        return int(value)
    if name == "traffic-light":
        return LIGHTS[value]
    if name == "road-type":
        return ROADS[value]
    return NAMES.index(value)


def _value_from_code(name, code) -> str:
    if name == "speed-limit":
        return str(code)
    if name == "traffic-light":
        return {v: k for k, v in LIGHTS.items()}[code]
    if name == "road-type":
        return {v: k for k, v in ROADS.items()}[code]
    return NAMES[code]


def encode(ev: FactEvent) -> CanFrame:
    data = PAYLOAD.pack(1 if ev.action == "assert" else 0, _value_code(ev.name, ev.value),
                        SOURCE[ev.name], 0, int(round(ev.t * 1000)) & 0xFFFFFFFF)
    return CanFrame(IDS[ev.name], data, time.time())


def decode(frame: CanFrame) -> FactEvent:
    name = NAMES_BY_ID[frame.arbitration_id]
    action, code, _, _, t_ms = PAYLOAD.unpack(bytes(frame.data))
    return FactEvent(t_ms / 1000.0, -1, "assert" if action else "retract", name,
                     _value_from_code(name, code))


class VirtualBus:
    def __init__(self):
        self._q: "queue.Queue[CanFrame]" = queue.Queue()
        self.log: List[CanFrame] = []

    def send(self, frame: CanFrame):
        self.log.append(frame)
        self._q.put(frame)

    def recv(self, timeout: Optional[float] = None) -> Optional[CanFrame]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def shutdown(self):
        pass


class PythonCanBus:
    """python-can transport (``pip install python-can``)."""

    def __init__(self, interface="socketcan", channel="can0", **kwargs):
        import can
        self._can = can
        self.bus = can.Bus(interface=interface, channel=channel, **kwargs)
        self.log: List[CanFrame] = []

    def send(self, frame: CanFrame):
        self.log.append(frame)
        self.bus.send(self._can.Message(arbitration_id=frame.arbitration_id,
                                        data=frame.data, is_extended_id=False))

    def recv(self, timeout: Optional[float] = None) -> Optional[CanFrame]:
        msg = self.bus.recv(timeout)
        if msg is None:
            return None
        return CanFrame(msg.arbitration_id, bytes(msg.data), msg.timestamp)

    def shutdown(self):
        self.bus.shutdown()


class Comprehension:
    """Receiving side: decodes frames and keeps the current fact set."""

    def __init__(self):
        self.facts = {}
        self.events: List[FactEvent] = []

    def handle(self, frame: CanFrame) -> FactEvent:
        ev = decode(frame)
        self.events.append(ev)
        values = self.facts.setdefault(ev.name, set())
        if ev.action == "assert":
            values.add(ev.value)
        else:
            values.discard(ev.value)
        return ev

    def drain(self, bus, timeout=0.0):
        while True:
            frame = bus.recv(timeout)
            if frame is None:
                return
            self.handle(frame)
