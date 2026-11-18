"""Read-only Cypher for the console: keyword filter, rollback, and JSON-safe results."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import relate

from graphsentinel.core.store import GraphStore

WRITE_KEYWORDS = ("CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "DROP", "LOAD",
                  "FOREACH", "CALL")
_STRINGS = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`")
_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
# Map keys (`{set: 1}`), labels/types (`:Call`, `: Call`), properties (`n.set`) and
# parameters (`$set`) are replaced before scanning for keywords.
_MAP_KEYS = re.compile(r"([{,]\s*)\w+(\s*:)")
_NAMES = re.compile(r"[:.$]\s*\w+")
_WRITES = re.compile(r"\b(" + "|".join(WRITE_KEYWORDS) + r")\b", re.I)
MAX_ROWS = 500


class ReadOnlyError(ValueError):
    """The query contains a write keyword."""


def check_read_only(query: str) -> None:
    """Reject queries that contain any write keyword outside strings and comments."""
    bare = _STRINGS.sub("''", _COMMENTS.sub(" ", query))
    bare = _NAMES.sub(" _", _MAP_KEYS.sub(r"\1_\2", bare))
    m = _WRITES.search(bare)
    if m:
        raise ReadOnlyError(f"The console is read-only: {m.group(1).upper()} is not allowed.")


def run_read_only(store: GraphStore, query: str,
                  params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run `query` in a transaction that is always rolled back. Returns columns and rows."""
    check_read_only(query)
    rows = store.read(query, params)
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    columns = list(rows[0].keys()) if rows else []
    return {"columns": columns, "rows": [{k: jsonable(v) for k, v in r.items()} for r in rows],
            "truncated": truncated}


def jsonable(v: Any) -> Any:
    """Convert Relate values (nodes, paths, vectors, temporals) to plain JSON."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, relate.Node):
        return {"_node": list(v.labels), **{k: jsonable(x) for k, x in _props(v).items()}}
    if isinstance(v, relate.Relationship):
        return {"_rel": v.type, **{k: jsonable(x) for k, x in _props(v).items()}}
    if isinstance(v, relate.Path):
        return {"_path": [jsonable(n) for n in v.nodes]}
    if isinstance(v, relate.Vector):
        vals = list(v.values)
        return f"vector[{v.dimension}]({', '.join(f'{x:.3f}' for x in vals[:4])}{', ...' if len(vals) > 4 else ''})"
    if isinstance(v, relate.Temporal):
        return v.text
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return str(v)


def _props(entity: Any) -> dict[str, Any]:
    props = dict(entity.properties)
    if "embedding" in props:
        props["embedding"] = "<vector>"
    if "fp" in props and isinstance(props["fp"], list):
        props["fp"] = f"<{len(props['fp'])} hashes>"
    return props
