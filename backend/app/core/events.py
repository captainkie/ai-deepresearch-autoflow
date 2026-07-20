"""Typed event emission for the engine.

The engine talks to the outside world only through a ``Sink`` — an async
callable that receives :class:`Event`s. ``ListSink`` collects them (tests, CLI);
the API milestone adds sinks that persist to SQLite and fan out over SSE.
``EventEmitter`` stamps each event with a monotonic ``seq`` (from 0) and ``ts``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from app.models.schemas import Event, EventType

Sink = Callable[[Event], Awaitable[None]]


def now_ms() -> int:
    return int(time.time() * 1000)


class ListSink:
    """A sink that appends every event to an in-memory list."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def __call__(self, event: Event) -> None:
        self.events.append(event)


class EventEmitter:
    def __init__(self, run_id: str, sink: Sink) -> None:
        self.run_id = run_id
        self._sink = sink
        self._seq = 0

    async def emit(self, event_type: EventType, data: dict) -> Event:
        # Assign + increment synchronously (no await between) so concurrent
        # sections never share a seq under asyncio's single-threaded scheduler.
        seq = self._seq
        self._seq += 1
        event = Event(
            seq=seq,
            run_id=self.run_id,
            ts=now_ms(),
            type=event_type,
            data=data,
        )
        await self._sink(event)
        return event
