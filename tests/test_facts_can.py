import pytest

from roadsign.can import Comprehension, VirtualBus, decode, encode
from roadsign.detection import Detection
from roadsign.facts import FactBase, FactConfig, FactEvent


def det(kind, label):
    return Detection(kind, label, (0, 0, 10, 10))


def feed(fb, sequence, fps=25):
    events = []
    for i, dets in enumerate(sequence):
        events += fb.update(i, i / fps, dets)
    return events


def test_single_frame_is_not_a_fact():
    fb = FactBase(FactConfig(window=12, min_hits=4))
    events = feed(fb, [[det("speed_limit", "50")]] + [[]] * 20)
    assert events == []


def test_speed_limit_holds_until_replaced():
    fb = FactBase(FactConfig(window=12, min_hits=4))
    seq = [[det("speed_limit", "50")]] * 6 + [[]] * 200 + [[det("speed_limit", "70")]] * 6
    events = feed(fb, seq)
    assert [(e.action, e.value) for e in events] == [("assert", "50"), ("retract", "50"), ("assert", "70")]
    assert fb.snapshot() == {"speed-limit": ["70"]}
    # the 50 limit was still valid during the 200 empty frames
    assert events[1].frame >= 206


def test_traffic_light_is_retracted_when_gone():
    fb = FactBase(FactConfig(window=12, min_hits=4, light_hold_s=1.0))
    events = feed(fb, [[det("traffic_light", "red")]] * 10 + [[]] * 40)
    assert [(e.action, e.value) for e in events] == [("assert", "red"), ("retract", "red")]
    assert 1.0 < events[1].t - 9 / 25 < 1.2


def test_flicker_between_values_needs_enough_hits():
    fb = FactBase(FactConfig(window=12, min_hits=4))
    seq = [[det("traffic_light", "red")] if i % 3 else [det("traffic_light", "green")] for i in range(12)]
    feed(fb, seq)
    assert fb.snapshot()["traffic-light"] == ["green", "red"]


def test_clips_and_deffacts():
    fb = FactBase(FactConfig(window=4, min_hits=2))
    feed(fb, [[det("speed_limit", "80"), det("direction_sign", "autobahn")]] * 3)
    assert '(speed-limit 80)' in fb.deffacts()
    assert '(road-type "autobahn")' in fb.deffacts()
    assert fb.events[0].clips() in ('(assert (speed-limit 80))', '(assert (road-type "autobahn"))')


@pytest.mark.parametrize("name,value", [
    ("speed-limit", "120"), ("traffic-light", "red"), ("traffic-light", "green"),
    ("road-type", "autobahn"), ("road-type", "road"), ("sign", "yield"), ("sign", "priority road"),
])
def test_can_roundtrip(name, value):
    for action in ("assert", "retract"):
        ev = FactEvent(12.345, 7, action, name, value)
        frame = encode(ev)
        assert len(frame.data) == 8
        back = decode(frame)
        assert (back.action, back.name, back.value) == (action, name, value)
        assert back.t == pytest.approx(12.345, abs=1e-3)


def test_priorities_and_candump():
    speed = encode(FactEvent(1.0, 0, "assert", "speed-limit", "50"))
    light = encode(FactEvent(1.0, 0, "assert", "traffic-light", "red"))
    assert speed.arbitration_id < light.arbitration_id
    line = speed.candump("can0")
    assert " can0 110#0132020" in line


def test_bus_to_comprehension():
    bus = VirtualBus()
    for ev in [FactEvent(0.5, 1, "assert", "speed-limit", "50"),
               FactEvent(0.6, 2, "assert", "traffic-light", "red"),
               FactEvent(2.0, 50, "retract", "traffic-light", "red")]:
        bus.send(encode(ev))
    rx = Comprehension()
    rx.drain(bus)
    assert rx.facts == {"speed-limit": {"50"}, "traffic-light": set()}
    assert len(rx.events) == 3
