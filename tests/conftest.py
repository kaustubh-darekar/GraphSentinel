"""Shared pytest fixtures: an in-memory store with the repo policy loaded."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest

from graphsentinel.core import CallRecord, Guard, GraphStore, Policy, Recorder
from graphsentinel.core.config import DEFAULT_TRUSTED, LineageMode

ROOT = Path(__file__).resolve().parents[1]


class Agent:
    """Tiny test driver: records a call the way the guarded wrapper does."""

    def __init__(self, store: GraphStore, mode: LineageMode = "strict") -> None:
        self.store = store
        self.mode = mode
        self.rec = Recorder(store, Policy.load(ROOT / "policy.yaml"), frozenset(DEFAULT_TRUSTED))
        self.guard = Guard(store)
        self.session = self.rec.start_session("test", message="do the thing")

    def call(self, tool: str, output: str | None = None, **args: Any) -> CallRecord:
        """record -> link inputs -> (output). Returns the call."""
        c = self.rec.record_call(self.session, tool, args)
        self.rec.link_inputs(c, self.mode)
        if output is not None:
            self.rec.record_output(c, output)
        return c


@pytest.fixture
def store() -> Iterator[GraphStore]:
    s = GraphStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def agent(store: GraphStore) -> Agent:
    return Agent(store, "strict")


@pytest.fixture
def precise_agent(store: GraphStore) -> Agent:
    return Agent(store, "precise")
