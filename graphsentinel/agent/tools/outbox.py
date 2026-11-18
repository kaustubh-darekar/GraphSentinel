"""Where the sandbox "Sends out" tools put things. Nothing leaves the process."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_sent: list[dict[str, Any]] = []


def deliver(kind: str, **fields: Any) -> None:
    """Record a sent email or message."""
    with _lock:
        _sent.append({"kind": kind, **fields})


def sent() -> list[dict[str, Any]]:
    """Everything delivered so far (used by tests to prove blocked sends never ran)."""
    with _lock:
        return list(_sent)


def clear() -> None:
    """Empty the outbox."""
    with _lock:
        _sent.clear()
