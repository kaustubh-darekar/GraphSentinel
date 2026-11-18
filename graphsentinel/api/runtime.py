"""Runtime: runs agent sessions in background threads and holds pending Ask decisions."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from graphsentinel.agent.embedders import live_embedder
from graphsentinel.agent.guarded import GuardedSession
from graphsentinel.agent.runner_live import LiveAgent, live_available
from graphsentinel.agent.runner_scripted import find_scenario, list_scenarios, run_scenario
from graphsentinel.api.events import EventBus
from graphsentinel.core.config import LineageMode
from graphsentinel.core.guard import Verdict
from graphsentinel.core.lineage import session_graph
from graphsentinel.core.recorder import CallRecord
from graphsentinel.core.sentinel import Sentinel


class RuntimeConflict(RuntimeError):
    """The request does not fit the current state (e.g. no pending Ask)."""


@dataclass
class PendingAsk:
    """An Ask waiting for a human."""

    session: str
    done: threading.Event = field(default_factory=threading.Event)
    resolution: str = "timeout"


@dataclass
class Active:
    """A session this process is running (or ran)."""

    guarded: GuardedSession
    live: LiveAgent | None = None
    busy: threading.Lock = field(default_factory=threading.Lock)


class Runtime:
    """Owns the Sentinel, the event bus and the sessions started from the UI."""

    def __init__(self, sentinel: Sentinel, bus: EventBus) -> None:
        self.sentinel = sentinel
        self.bus = bus
        self.lineage: LineageMode = sentinel.settings.lineage_mode
        self.default_mode = os.environ.get("GS_MODE", "scripted").strip().lower()
        self.ask_timeout = float(os.environ.get("GS_ASK_TIMEOUT", "120"))
        self.step_delay = float(os.environ.get("GS_STEP_DELAY", "0.7"))
        self.active: dict[str, Active] = {}
        self.pending: dict[str, PendingAsk] = {}
        self._lock = threading.Lock()

    # ---- config -------------------------------------------------------------------

    def config(self) -> dict[str, Any]:
        """What the UI needs to know about this server."""
        return {"mode": self.default_mode, "lineage": self.lineage,
                "live_available": live_available(),
                "trusted": sorted(self.sentinel.settings.trusted_destinations),
                "store_path": self.sentinel.settings.store_path,
                "ask_timeout": self.ask_timeout}

    def scenarios(self) -> list[dict[str, Any]]:
        """Scenario summaries for the sidebar."""
        return [{"id": s.id, "title": s.title, "description": s.description,
                 "user": s.user, "lineage": s.lineage} for s in list_scenarios()]

    # ---- starting sessions ----------------------------------------------------------

    def start_scenario(self, scenario_id: str, lineage: LineageMode | None = None) -> str:
        """Start replaying a scenario in the background. Returns the session id."""
        sc = find_scenario(scenario_id)
        mode = sc.lineage or lineage or self.lineage
        gs = self._new_session(sc.title, sc.user, "scripted", mode, sc.id)

        def work() -> None:
            run_scenario(self.sentinel, sc, lineage=mode, session=gs,
                         approver=self._approver(gs.session_id), step_delay=self.step_delay)

        self._spawn(gs.session_id, work)
        return gs.session_id

    def start_live(self, message: str, lineage: LineageMode | None = None) -> str:
        """Start a live chat with the model. Returns the session id."""
        if not live_available():
            raise RuntimeConflict("Live mode needs OPENAI_API_KEY and OPENAI_MODEL in .env.")
        title = message if len(message) <= 60 else message[:57] + "..."
        gs = self._new_session(title, message, "live", lineage or self.lineage, None)
        gs.approver = self._approver(gs.session_id)
        if gs.lineage == "precise":
            gs.embedder = live_embedder()
        agent = LiveAgent(gs)
        self.active[gs.session_id].live = agent
        self._spawn(gs.session_id, lambda: agent.send(message, record_user=False))
        return gs.session_id

    def send_message(self, session_id: str, text: str) -> None:
        """A follow-up user message in a live session."""
        act = self.active.get(session_id)
        if act is None or act.live is None:
            raise RuntimeConflict("Only live sessions started in this server accept messages.")
        if act.busy.locked():
            raise RuntimeConflict("The agent is still working on the previous message.")
        self._spawn(session_id, lambda: act.live.send(text))  # type: ignore[union-attr]

    # ---- decisions --------------------------------------------------------------------

    def decide(self, call_id: str, decision: str, by: str = "me", note: str = "") -> dict[str, Any]:
        """Resolve an Ask (allow / deny) or override a Block ("allow_once")."""
        if decision in ("allow", "deny"):
            with self._lock:
                pending = self.pending.get(call_id)
            if pending is None:
                raise RuntimeConflict("This call is not waiting for a decision.")
            pending.resolution = "approved" if decision == "allow" else "denied"
            pending.done.set()
            return {"call_id": call_id, "resolution": pending.resolution}
        if decision == "allow_once":
            sid = self._session_of(call_id)
            gs = self._guarded(sid)
            try:
                out = gs.allow_once(call_id, by=by, note=note)
            except ValueError as exc:
                raise RuntimeConflict(str(exc)) from exc
            return {"call_id": call_id, "resolution": "overridden", "status": out.status}
        raise ValueError("decision must be allow, deny or allow_once")

    def clear_history(self) -> dict[str, int]:
        """Delete every run except ones still working or waiting for a decision."""
        with self._lock:
            keep = {sid for sid in self.active if self._running(sid)}
            keep |= {p.session for p in self.pending.values()}
        rows = self.sentinel.store.run("clear_sessions", {"keep": sorted(keep)})
        self.sentinel.store.run("clear_orphans")
        for sid in [sid for sid in self.active if sid not in keep]:
            del self.active[sid]
        deleted = rows[0]["sessions"] if rows else 0
        self.bus.publish("*", "history_cleared", {"deleted": deleted, "kept": len(keep)})
        return {"deleted": deleted, "kept": len(keep)}

    # ---- reading --------------------------------------------------------------------

    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Session header, chat timeline and graph, as the UI renders them."""
        rows = self.sentinel.store.run("session_timeline", {"session": session_id})
        if not rows:
            raise KeyError(session_id)
        row = rows[0]
        messages = [m for m in row["msgs"] if m.get("text") is not None]
        calls = [{**c, "args": json.loads(c.pop("args_json") or "{}")} for c in row["calls"]]
        items = sorted(messages + calls, key=lambda x: x["at"] or "")
        pending = [cid for cid, p in self.pending.items() if p.session == session_id]
        return {"session": row["session"], "timeline": items, "pending": pending,
                "running": self._running(session_id),
                "live": bool(self.active.get(session_id) and self.active[session_id].live),
                "graph": session_graph(self.sentinel.store, session_id)}

    def sessions(self) -> list[dict[str, Any]]:
        """All sessions in the store, newest first."""
        out = self.sentinel.store.run("list_sessions")
        for s in out:
            s["running"] = self._running(s["id"])
        return out

    # ---- internals ------------------------------------------------------------------

    def _new_session(self, title: str, message: str, mode: str, lineage: LineageMode,
                     scenario: str | None) -> GuardedSession:
        ref: list[str] = []
        gs = GuardedSession.start(self.sentinel, title, message, mode=mode, lineage=lineage,
                                  scenario=scenario, emit=self.bus.sink(ref))
        self.active[gs.session_id] = Active(gs)
        return gs

    def _guarded(self, session_id: str) -> GuardedSession:
        act = self.active.get(session_id)
        if act is not None:
            return act.guarded
        rows = self.sentinel.store.query(
            "MATCH (s:Session {id: $id}) RETURN s.lineage AS lineage", {"id": session_id})
        gs = GuardedSession(self.sentinel, session_id, rows[0]["lineage"] or "strict",
                            emit=self.bus.sink([session_id]), approver=self._approver(session_id))
        self.active[session_id] = Active(gs)
        return gs

    def _session_of(self, call_id: str) -> str:
        rows = self.sentinel.store.query(
            "MATCH (c:Call {id: $id}) RETURN c.session AS s", {"id": call_id})
        if not rows:
            raise KeyError(call_id)
        return rows[0]["s"]

    def _approver(self, session_id: str):  # type: ignore[no-untyped-def]
        def approve(call: CallRecord, _verdict: Verdict) -> str:
            pending = PendingAsk(session_id)
            with self._lock:
                self.pending[call.id] = pending
            try:
                pending.done.wait(self.ask_timeout)
                return pending.resolution
            finally:
                with self._lock:
                    self.pending.pop(call.id, None)
        return approve

    def _spawn(self, session_id: str, fn: Any) -> None:
        act = self.active[session_id]

        def run() -> None:
            with act.busy:
                try:
                    fn()
                except Exception as exc:  # report to the UI instead of dying silently
                    self.bus.publish(session_id, "error", {"message": f"{type(exc).__name__}: {exc}"})
                finally:
                    self.bus.publish(session_id, "session_idle", {"session": session_id})

        threading.Thread(target=run, name=f"session-{session_id}", daemon=True).start()

    def _running(self, session_id: str) -> bool:
        act = self.active.get(session_id)
        return bool(act and act.busy.locked())
