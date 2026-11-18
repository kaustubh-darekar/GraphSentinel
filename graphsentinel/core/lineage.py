"""Lineage explain and session graphs, shaped for the UI."""

from __future__ import annotations

from typing import Any

from graphsentinel.core.graphview import (
    Edge, Node, call_node_from_row, data_node, dest_node, dest_id, edge,
)
from graphsentinel.core.store import GraphStore


def explain(store: GraphStore, call_id: str) -> dict[str, Any]:
    """Return `{call_id, nodes, edges, path}` for every call and data item upstream of `call_id`.

    Nodes have `kind` 'call' | 'data' | 'destination'; edges have `type`
    'PRODUCED' | 'FED_INTO' | 'SENT_TO' (FED_INTO also carries `how`).
    `path` is the guard's stored path (empty until a verdict is recorded).
    """
    ancestors = store.run("lineage_ancestors", {"callId": call_id})
    call_ids = [call_id] + (ancestors[0]["ids"] if ancestors else [])
    calls = store.run("lineage_calls", {"callIds": call_ids})
    target = next((c for c in calls if c["id"] == call_id), None)
    if target is None:
        raise KeyError(f"unknown call {call_id!r}")
    nodes, edges = _subgraph(store, calls, call_ids)
    return {"call_id": call_id, "nodes": nodes, "edges": edges, "path": target["path"] or []}


def session_graph(store: GraphStore, session_id: str) -> dict[str, Any]:
    """Every call, data item and destination of one session."""
    rows = store.run("session_call_ids", {"session": session_id})
    call_ids = rows[0]["ids"] if rows else []
    calls = store.run("lineage_calls", {"callIds": call_ids}) if call_ids else []
    nodes, edges = _subgraph(store, calls, call_ids, include_unused_data=True)
    return {"session": session_id, "nodes": nodes, "edges": edges}


def _subgraph(store: GraphStore, calls: list[dict[str, Any]], call_ids: list[str],
              include_unused_data: bool = False) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    seen: set[str] = set()

    def add(node: Node) -> None:
        if node["id"] not in seen:
            seen.add(node["id"])
            nodes.append(node)

    for c in calls:
        add(call_node_from_row(c))
        for d in c["destinations"]:
            add(dest_node(d["address"], d["trusted"]))
            edges.append(edge(c["id"], dest_id(d["address"]), "SENT_TO"))

    if not call_ids:
        return nodes, edges
    query = "session_edges" if include_unused_data else "lineage_edges"
    for e in store.run(query, {"callIds": call_ids}):
        if e["data"] not in seen:
            add(data_node(e["data"], e["preview"], e["chars"]))
            edges.append(edge(e["from_call"], e["data"], "PRODUCED"))
        if e["to_call"] is not None:
            edges.append(edge(e["data"], e["to_call"], "FED_INTO", e["how"], e.get("score")))
    return nodes, edges
