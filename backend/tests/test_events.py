from __future__ import annotations

from app.core.events import EventEmitter, ListSink, now_ms
from app.models.schemas import EventType


async def test_emitter_assigns_monotonic_seq_from_zero():
    sink = ListSink()
    emitter = EventEmitter("run-1", sink)
    await emitter.emit(EventType.status, {"stage": "planning"})
    await emitter.emit(EventType.done, {"ok": True})
    assert [e.seq for e in sink.events] == [0, 1]
    assert sink.events[0].run_id == "run-1"
    assert sink.events[0].type == EventType.status
    assert isinstance(sink.events[0].ts, int)


def test_now_ms_is_positive_int():
    value = now_ms()
    assert isinstance(value, int)
    assert value > 0
