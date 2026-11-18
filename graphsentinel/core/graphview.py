"""The node/edge shapes the UI graph uses. One place, so REST, explain and live events agree."""

from __future__ import annotations

from typing import Any

Node = dict[str, Any]
Edge = dict[str, Any]


def tags_of(outside: bool, private: bool, sends_out: bool) -> list[str]:
    """Risk tags in a fixed order."""
    return [t for t, on in (("outside", outside), ("private", private), ("sends_out", sends_out)) if on]


def call_node(id: str, step: int, tool: str, label: str, tags: list[str],
              decision: str | None = None, reason: str | None = None,
              resolution: str | None = None) -> Node:
    """A :Call node."""
    return {"id": id, "kind": "call", "step": step, "tool": tool, "label": label, "tags": tags,
            "decision": decision, "reason": reason, "resolution": resolution}


def call_node_from_row(r: dict[str, Any]) -> Node:
    """A :Call node from a query row with id/step/tool/label/outside/private/sends_out/decision."""
    return call_node(r["id"], r["step"], r["tool"], r["label"] or r["tool"],
                     tags_of(r["outside"], r["private"], r["sends_out"]),
                     r.get("decision"), r.get("reason"), r.get("resolution"))


def data_node(id: str, preview: str, chars: int) -> Node:
    """A :Data node (label is a one-line preview)."""
    first = " ".join(preview.split())
    return {"id": id, "kind": "data", "label": first[:48] + ("..." if len(first) > 48 else ""),
            "preview": preview, "chars": chars}


def dest_id(address: str) -> str:
    """Node id for a :Destination."""
    return f"dest:{address}"


def dest_node(address: str, trusted: bool) -> Node:
    """A :Destination node."""
    return {"id": dest_id(address), "kind": "destination", "label": address, "trusted": trusted}


def edge(source: str, target: str, type_: str, how: str | None = None,
         score: float | None = None) -> Edge:
    """An edge; FED_INTO edges carry `how` ('context' | 'content' | 'similar') and maybe `score`."""
    e: Edge = {"id": f"{type_}:{source}->{target}", "source": source, "target": target, "type": type_}
    if how is not None:
        e["how"] = how
    if score is not None:
        e["score"] = round(float(score), 4)
    return e
