"""The guarded call path shared by every runner (scripted, live, API, proxy).

record call -> link inputs -> check -> Allow: run the tool
                                    -> Ask: wait for a human decision (default deny)
                                    -> Block: refuse, explain the path
Every step is written to the graph and published as an event for the UI.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal

from graphsentinel.agent import tools
from graphsentinel.core.config import LineageMode, is_trusted
from graphsentinel.core.embedding import Embedder
from graphsentinel.core.graphview import call_node, data_node, dest_node, dest_id, edge
from graphsentinel.core.guard import Verdict
from graphsentinel.core.recorder import CallRecord, args_text
from graphsentinel.core.sentinel import Sentinel

EventSink = Callable[[str, dict[str, Any]], None]
# Called for an Ask. Returns "approved" | "denied" | "timeout".
Approver = Callable[[CallRecord, Verdict], str]
RunTool = Callable[[str, dict[str, Any]], str]
Status = Literal["ran", "blocked", "denied", "timeout"]


@dataclass
class Outcome:
    """What happened to one tool call."""

    call: CallRecord
    verdict: Verdict
    status: Status
    text: str  # what the agent sees: the tool output, or a refusal message
    check_ms: float

    @property
    def ran(self) -> bool:
        """True when the tool actually executed."""
        return self.status == "ran"


def deny_all(_call: CallRecord, _verdict: Verdict) -> str:
    """Default Ask handler when nobody is watching: deny."""
    return "denied"


def run_sandbox_tool(name: str, args: dict[str, Any]) -> str:
    """Run a tool from the sandbox registry."""
    try:
        tool = tools.get(name)
    except KeyError:
        return f"Error: unknown tool {name}"
    return tool.run(args)


class GuardedSession:
    """One agent session whose every tool call goes through the guard."""

    def __init__(
        self,
        sentinel: Sentinel,
        session_id: str,
        lineage: LineageMode,
        emit: EventSink | None = None,
        approver: Approver | None = None,
        run_tool: RunTool = run_sandbox_tool,
        embedder: Embedder | None = None,
    ) -> None:
        self.sentinel = sentinel
        self.session_id = session_id
        self.lineage = lineage
        self.emit: EventSink = emit or (lambda _t, _d: None)
        self.approver = approver or deny_all
        self.run_tool = run_tool
        self.embedder = embedder

    @property
    def vectors_on(self) -> bool:
        """Paraphrase detection runs in precise sessions that have an embedder."""
        return self.lineage == "precise" and self.embedder is not None

    @classmethod
    def start(cls, sentinel: Sentinel, title: str, message: str | None, *, mode: str,
              lineage: LineageMode, scenario: str | None = None,
              emit: EventSink | None = None, approver: Approver | None = None,
              run_tool: RunTool = run_sandbox_tool) -> "GuardedSession":
        """Create a new :Session and return a guarded session bound to it."""
        sid = sentinel.recorder.start_session(title, mode=mode, message=message,
                                              lineage=lineage, scenario=scenario)
        gs = cls(sentinel, sid, lineage, emit, approver, run_tool)
        gs.emit("session_started", {"session": sid, "title": title, "mode": mode,
                                    "lineage": lineage, "scenario": scenario})
        if message is not None:
            gs.emit("user_message", {"text": message})
        return gs

    # ---- chat ---------------------------------------------------------------

    def say(self, text: str) -> None:
        """Record and publish something the agent said to the user."""
        at = self.sentinel.recorder.record_message(self.session_id, "agent", text)
        self.emit("agent_message", {"text": text, "at": at})

    def user(self, text: str) -> None:
        """Record and publish a follow-up user message."""
        at = self.sentinel.recorder.record_message(self.session_id, "user", text)
        self.emit("user_message", {"text": text, "at": at})

    # ---- the guarded call -------------------------------------------------------

    def call(self, tool: str, args: dict[str, Any]) -> Outcome:
        """Record, check and (maybe) run one tool call."""
        rec = self.sentinel.recorder
        call = rec.record_call(self.session_id, tool, args)
        self._publish_call(call)
        linked = rec.link_inputs(call, self.lineage)
        self._publish_links(call, linked)
        if self.vectors_on and self.sentinel.policy.tool(call.tool).sends_out:
            try:
                similar = rec.link_similar(call, args_text(call.args), self.embedder)  # type: ignore[arg-type]
                self._publish_links(call, list(similar), how="similar", scores=similar)
            except Exception as exc:  # the content lineage still applies; report and go on
                self.emit("error", {"message": f"Paraphrase check failed: {type(exc).__name__}: {exc}"})

        t0 = time.perf_counter()
        verdict = self.sentinel.guard.check(call.id)
        check_ms = (time.perf_counter() - t0) * 1000
        rec.record_verdict(call, verdict)
        self.emit("verdict", {"call_id": call.id, "step": call.step, "check_ms": round(check_ms, 2),
                              **verdict.to_dict()})

        if verdict.decision == "allow":
            return self._execute(call, verdict, check_ms)
        if verdict.decision == "ask":
            self.emit("ask_pending", {"call_id": call.id, "reason": verdict.reason})
            resolution = self.approver(call, verdict)
            rec.record_resolution(call, resolution)
            self.emit("resolution", {"call_id": call.id, "resolution": resolution})
            if resolution == "approved":
                return self._execute(call, verdict, check_ms)
            status: Status = "timeout" if resolution == "timeout" else "denied"
            text = (f"GraphSentinel held this call for approval and the user did not allow it "
                    f"({resolution}). {verdict.reason} Nothing was sent.")
            return self._refused(call, verdict, status, text, check_ms)
        text = (f"GraphSentinel blocked this call. {verdict.reason} Nothing was sent. "
                "Tell the user what happened instead of retrying.")
        return self._refused(call, verdict, "blocked", text, check_ms)

    def allow_once(self, call_id: str, by: str = "me", note: str = "") -> Outcome:
        """Human "Allow once" on a blocked (or denied) call: record an :Override and run it."""
        rows = self.sentinel.store.run("call_for_rerun", {"callId": call_id})
        if not rows:
            raise KeyError(f"unknown call {call_id!r}")
        row = rows[0]
        if row["ran"]:
            raise ValueError("this call already ran")
        rec = self.sentinel.recorder
        rec.record_override(call_id, by=by, note=note)
        call = CallRecord(call_id, self.session_id, row["step"], row["tool"],
                          json.loads(row["args_json"]))
        verdict = self.sentinel.guard.check(call_id)
        rec.record_resolution(call_id, "overridden")
        self.emit("resolution", {"call_id": call_id, "resolution": "overridden", "by": by})
        return self._execute(call, verdict, 0.0)

    # ---- helpers ----------------------------------------------------------------

    def _execute(self, call: CallRecord, verdict: Verdict, check_ms: float) -> Outcome:
        output = self.run_tool(call.tool, call.args)
        data_id = self.sentinel.recorder.record_output(
            call, output, self.embedder if self.vectors_on else None)
        node = data_node(data_id, output[:280], len(output))
        self.emit("graph_delta", {"nodes": [node], "edges": [edge(call.id, data_id, "PRODUCED")]})
        self.emit("call_result", {"call_id": call.id, "status": "ran", "output": output[:2000],
                                  "chars": len(output)})
        return Outcome(call, verdict, "ran", output, check_ms)

    def _refused(self, call: CallRecord, verdict: Verdict, status: Status, text: str,
                 check_ms: float) -> Outcome:
        self.emit("call_result", {"call_id": call.id, "status": status, "output": text})
        return Outcome(call, verdict, status, text, check_ms)

    def _publish_call(self, call: CallRecord) -> None:
        tp = self.sentinel.policy.tool(call.tool)
        tags = [t for t, on in (("outside", tp.outside), ("private", tp.private),
                                ("sends_out", tp.sends_out)) if on]
        node = call_node(call.id, call.step, call.tool, tp.label(call.args), tags)
        trusted = self.sentinel.recorder.trusted
        dests = [d.strip().lower() for d in tp.destinations(call.args)]
        nodes = [node] + [dest_node(d, is_trusted(d, trusted)) for d in dests]
        edges = [edge(call.id, dest_id(d), "SENT_TO") for d in dests]
        self.emit("call_recorded", {"call_id": call.id, "step": call.step, "tool": call.tool,
                                    "args": call.args, "node": node})
        self.emit("graph_delta", {"nodes": nodes, "edges": edges})

    def _publish_links(self, call: CallRecord, linked: list[str],
                       how: str | None = None, scores: dict[str, float] | None = None) -> None:
        if not linked:
            return
        how = how or ("context" if self.lineage == "strict" else "content")
        edges = [edge(d, call.id, "FED_INTO", how, (scores or {}).get(d)) for d in linked]
        self.emit("graph_delta", {"nodes": [], "edges": edges})
