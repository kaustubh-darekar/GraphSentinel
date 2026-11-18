"""Recorder: writes sessions, calls, data and lineage edges into the graph."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from graphsentinel.core.config import LineageMode, is_trusted, normalize_address
from graphsentinel.core.embedding import Embedder, chunks, clip
from graphsentinel.core.fingerprint import fingerprint
from graphsentinel.core.policy import Policy
from graphsentinel.core.store import GraphStore

if TYPE_CHECKING:
    from graphsentinel.core.guard import Verdict

PREVIEW_CHARS = 280


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def args_text(args: dict[str, Any]) -> str:
    """All string-ish argument values joined into one text, for content matching."""
    parts: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif v is not None:
            parts.append(str(v))

    walk(args)
    return "\n".join(parts)


@dataclass(frozen=True)
class CallRecord:
    """A recorded call: its id, step number within the session, and arguments."""

    id: str
    session: str
    step: int
    tool: str
    args: dict[str, Any]


class Recorder:
    """Writes the agent's activity into the graph, one small query per event."""

    def __init__(self, store: GraphStore, policy: Policy, trusted: frozenset[str]) -> None:
        self.store = store
        self.policy = policy
        self.trusted = frozenset(normalize_address(a) for a in trusted)
        policy.sync(store)

    def start_session(
        self,
        title: str,
        mode: str = "scripted",
        message: str | None = None,
        user: str = "me",
        lineage: LineageMode = "strict",
        scenario: str | None = None,
    ) -> str:
        """Create a :Session (and the :User/:Message that started it). Returns its id."""
        sid = _new_id("s")
        self.store.run("start_session", {
            "id": sid, "title": title, "mode": mode, "at": _now(), "message": message,
            "user": user, "lineage": lineage, "scenario": scenario,
        })
        return sid

    def record_message(self, session: str, role: str, text: str) -> str:
        """A chat message ('user' or 'agent'). Returns its timestamp."""
        at = _now()
        self.store.run("record_message", {"session": session, "role": role, "text": text, "at": at})
        return at

    def record_call(self, session: str, tool: str, args: dict[str, Any]) -> CallRecord:
        """Append a :Call as the next step; also records destinations named in its args."""
        tp = self.policy.tool(tool)
        cid = _new_id("c")
        rows = self.store.run("record_call", {
            "session": session, "id": cid, "tool": tool, "label": tp.label(args),
            "args_json": json.dumps(args, sort_keys=True, default=str), "at": _now(),
        })
        if not rows:
            raise KeyError(f"unknown session {session!r}")
        for address in tp.destinations(args):
            self.record_destination(cid, address)
        return CallRecord(cid, session, rows[0]["step"], tool, args)

    def record_output(self, call: CallRecord | str, text: str,
                      embedder: Embedder | None = None) -> str:
        """Store what a call returned as :Data (preview, size, fingerprint and, when an
        embedder is given, an embedding for vector search). Returns its id."""
        did = _new_id("d")
        self.store.run("record_output", {
            "callId": _cid(call), "id": did, "preview": text[:PREVIEW_CHARS],
            "chars": len(text), "fp": fingerprint(text),
        })
        if embedder is not None and text.strip():
            vec = embedder.embed([clip(text)])[0]
            self.store.run("set_embedding", {"id": did, "embedding": vec, "dims": len(vec),
                                             "embedder": embedder.name})
        return did

    def link_similar(self, call: CallRecord, text: str, embedder: Embedder) -> dict[str, float]:
        """Paraphrase lineage: vector-search each paragraph of `text` against the session's
        Data and add FED_INTO {how:'similar', score} for matches above the embedder's
        threshold (skipping Data already linked by content). Returns {data_id: score}."""
        parts = chunks(text)
        if not parts:
            return {}
        best: dict[str, float] = {}
        for vec in embedder.embed(parts):
            for row in self.store.run("similar_data", {"q": vec, "dims": len(vec),
                                                       "session": call.session}):
                if row["score"] >= embedder.threshold:
                    best[row["id"]] = max(best.get(row["id"], 0.0), float(row["score"]))
        if not best:
            return {}
        rows = [{"id": k, "score": v} for k, v in best.items()]
        linked = self.store.run("link_similar", {"callId": call.id, "rows": rows})
        return {r["id"]: r["score"] for r in linked}

    def link_inputs(
        self, call: CallRecord | str, mode: LineageMode, text: str | None = None
    ) -> list[str]:
        """Add FED_INTO edges into the call; returns the ids of the linked :Data.

        strict:  every Data already in the session's context ('context').
        precise: only Data whose fingerprint overlaps `text` ('content'); `text`
                 defaults to the call's own arguments.
        """
        if mode == "strict":
            rows = self.store.run("link_strict", {"callId": _cid(call)})
        elif mode == "precise":
            if text is None:
                if not isinstance(call, CallRecord):
                    raise ValueError("precise mode needs the CallRecord or explicit text")
                text = args_text(call.args)
            hashes = fingerprint(text)
            if not hashes:
                return []
            rows = self.store.run("link_precise", {"callId": _cid(call), "hashes": hashes})
        else:
            raise ValueError(f"unknown lineage mode {mode!r}")
        return [r["id"] for r in rows]

    def record_destination(self, call: CallRecord | str, address: str) -> bool:
        """Link the call to a :Destination; returns whether the address is trusted."""
        addr = normalize_address(address)
        trusted = is_trusted(addr, self.trusted)
        self.store.run("record_destination", {
            "callId": _cid(call), "dests": [{"address": addr, "trusted": trusted}],
        })
        return trusted

    def record_verdict(self, call: CallRecord | str, verdict: "Verdict") -> None:
        """Persist the guard's decision, reason and path on the :Call."""
        self.store.run("record_verdict", {
            "callId": _cid(call), "decision": verdict.decision,
            "reason": verdict.reason, "path": verdict.path,
        })

    def record_resolution(self, call: CallRecord | str, resolution: str) -> None:
        """How an Ask or Block was resolved: approved | denied | timeout | overridden."""
        self.store.run("record_resolution", {"callId": _cid(call), "resolution": resolution})

    def record_override(self, call: CallRecord | str, by: str, note: str = "") -> None:
        """A human "Allow once" on a blocked call (:Override)-[:OVERRIDES]->(:Call)."""
        self.store.run("record_override", {
            "callId": _cid(call), "by": by, "at": _now(), "note": note,
        })


def _cid(call: CallRecord | str) -> str:
    return call.id if isinstance(call, CallRecord) else call
