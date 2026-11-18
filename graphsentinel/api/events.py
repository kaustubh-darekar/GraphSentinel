"""In-process pub/sub: agent threads publish, WebSocket handlers (asyncio) subscribe."""

from __future__ import annotations

import asyncio
import itertools
import threading
from collections import defaultdict
from typing import Any

Event = dict[str, Any]


class EventBus:
    """Thread-safe fan-out of session events to asyncio queues."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: dict[str, set[asyncio.Queue[Event]]] = defaultdict(set)
        self._lock = threading.Lock()
        self._seq = itertools.count(1)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the server's event loop (called at startup)."""
        self._loop = loop

    def publish(self, session: str, kind: str, data: dict[str, Any]) -> None:
        """Send an event to every subscriber of `session` and of '*'. Safe from any thread."""
        event = {"type": kind, "session": session, "seq": next(self._seq), "data": data}
        with self._lock:
            queues = list(self._subs.get(session, ())) + list(self._subs.get("*", ()))
        if not queues or self._loop is None:
            return
        for q in queues:
            self._loop.call_soon_threadsafe(q.put_nowait, event)

    def subscribe(self, session: str) -> asyncio.Queue[Event]:
        """A queue that receives the session's events ('*' for all sessions)."""
        q: asyncio.Queue[Event] = asyncio.Queue()
        with self._lock:
            self._subs[session].add(q)
        return q

    def unsubscribe(self, session: str, q: asyncio.Queue[Event]) -> None:
        """Stop delivering to `q`."""
        with self._lock:
            self._subs[session].discard(q)
            if not self._subs[session]:
                del self._subs[session]

    def sink(self, session_ref: list[str]) -> Any:
        """An EventSink for GuardedSession. `session_ref[0]` is filled once the id is known."""
        def emit(kind: str, data: dict[str, Any]) -> None:
            sid = data.get("session") if kind == "session_started" else None
            if sid and not session_ref:
                session_ref.append(sid)
            if session_ref:
                self.publish(session_ref[0], kind, data)
        return emit
