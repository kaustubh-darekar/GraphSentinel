"""GraphStore: the only code that touches `relate`.

A Relate connection is thread-affine: it only works on the thread that opened it.
GraphStore owns one worker thread that opens the connection and runs every query
from a queue, so any thread (FastAPI's pool, the agent loop, tests) can submit work.
"""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable

import relate

from graphsentinel.core.queries import load as load_query
from graphsentinel.core.queries import split_statements

Rows = list[dict[str, Any]]
Statement = tuple[str, dict[str, Any] | None]

_SCHEMA_PATH = Path(__file__).with_name("schema.cypher")
_STOP = object()


class GraphStore:
    """A Relate database served by a dedicated worker thread.

    `path` is a directory (storage mode: directory) or ":memory:" for tests.
    """

    def __init__(self, path: str | Path = ":memory:", *, read_only: bool = False) -> None:
        self.path = str(path)
        self.read_only = read_only
        if self.path != ":memory:" and not read_only:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._jobs: queue.Queue[Any] = queue.Queue()
        self._ready: Future[None] = Future()
        self._thread = threading.Thread(target=self._run, name="graphstore", daemon=True)
        self._thread.start()
        self._ready.result()  # re-raises if the open or the schema failed
        if not read_only:
            self.run_script(_SCHEMA_PATH.read_text(encoding="utf-8"))

    # ---- public API -------------------------------------------------------

    def submit(self, query: str, params: dict[str, Any] | None = None) -> Future[Rows]:
        """Queue one Cypher statement; the Future resolves to a list of row dicts."""
        return self._call(lambda conn: _execute(conn, query, params))

    def query(self, query: str, params: dict[str, Any] | None = None) -> Rows:
        """Run one statement and block until its rows are available."""
        return self.submit(query, params).result()

    def run(self, name: str, params: dict[str, Any] | None = None) -> Rows:
        """Run a named query from `core/queries/<name>.cypher`."""
        return self.query(load_query(name), params)

    def transaction(self, statements: list[Statement]) -> list[Rows]:
        """Run several statements in one transaction (one fsync instead of many)."""
        return self._call(lambda conn: _transaction(conn, statements)).result()

    def read(self, query: str, params: dict[str, Any] | None = None) -> Rows:
        """Run a statement inside a transaction that is always rolled back (nothing persists)."""
        return self._call(lambda conn: _rolled_back(conn, query, params)).result()

    def run_script(self, script: str) -> None:
        """Run a `;`-separated script of statements, each on its own (used for schema)."""
        for stmt in split_statements(script):
            self.query(stmt)

    def close(self) -> None:
        """Close the connection on its owning thread and stop the worker."""
        if self._thread.is_alive():
            self._jobs.put(_STOP)
            self._thread.join()

    def __enter__(self) -> "GraphStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- worker thread ----------------------------------------------------

    def _call(self, fn: Callable[[Any], Any]) -> Future[Any]:
        if not self._thread.is_alive():
            raise RuntimeError("GraphStore is closed")
        fut: Future[Any] = Future()
        self._jobs.put((fn, fut))
        return fut

    def _run(self) -> None:
        try:
            conn = relate.connect(self.path, read_only=self.read_only)
        except BaseException as exc:  # surface open errors to the constructor
            self._ready.set_exception(exc)
            return
        self._ready.set_result(None)
        try:
            while (job := self._jobs.get()) is not _STOP:
                fn, fut = job
                if not fut.set_running_or_notify_cancel():
                    continue
                try:
                    fut.set_result(fn(conn))
                except BaseException as exc:
                    fut.set_exception(exc)
        finally:
            conn.close()


def _execute(conn: Any, query: str, params: dict[str, Any] | None) -> Rows:
    return [dict(row) for row in conn.execute(query, params or {})]


def _rolled_back(conn: Any, query: str, params: dict[str, Any] | None) -> Rows:
    conn.autocommit = False
    try:
        return _execute(conn, query, params)
    finally:
        conn.rollback()
        conn.autocommit = True


def _transaction(conn: Any, statements: list[Statement]) -> list[Rows]:
    conn.autocommit = False
    try:
        out = [_execute(conn, q, p) for q, p in statements]
        conn.commit()
        return out
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True
