"""REST and WebSocket routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from graphsentinel.api.cypher import ReadOnlyError, run_read_only
from graphsentinel.api.runtime import Runtime, RuntimeConflict
from graphsentinel.core.lineage import explain

router = APIRouter(prefix="/api")


def rt(request: Request) -> Runtime:
    """The app's Runtime."""
    return request.app.state.runtime


class NewSession(BaseModel):
    """Start a scenario replay, or a live chat from free text."""

    scenario: str | None = None
    message: str | None = None
    lineage: Literal["strict", "precise"] | None = None


class NewMessage(BaseModel):
    """A follow-up message in a live session."""

    text: str = Field(min_length=1)


class Decision(BaseModel):
    """allow / deny resolve an Ask; allow_once overrides a Block."""

    decision: Literal["allow", "deny", "allow_once"]
    by: str = "me"
    note: str = ""


class CypherQuery(BaseModel):
    """A read-only query for the console."""

    query: str = Field(min_length=1)
    params: dict[str, Any] | None = None


class ConfigPatch(BaseModel):
    """Settings the UI can change."""

    lineage: Literal["strict", "precise"]


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/config")
def get_config(request: Request) -> dict[str, Any]:
    """Mode, lineage mode, whether live mode is available, trusted destinations."""
    return rt(request).config()


@router.put("/config")
def put_config(body: ConfigPatch, request: Request) -> dict[str, Any]:
    """Switch strict / precise lineage for new sessions."""
    rt(request).lineage = body.lineage
    return rt(request).config()


@router.get("/scenarios")
def get_scenarios(request: Request) -> list[dict[str, Any]]:
    """Scenarios available for replay."""
    return rt(request).scenarios()


@router.get("/sessions")
def get_sessions(request: Request) -> list[dict[str, Any]]:
    """Every session in the store, newest first."""
    return rt(request).sessions()


@router.delete("/sessions")
def clear_sessions(request: Request) -> dict[str, int]:
    """Clear history: delete every run that is not still working."""
    return rt(request).clear_history()


@router.post("/sessions", status_code=201)
def post_session(body: NewSession, request: Request) -> dict[str, str]:
    """Start a scenario (scripted) or a live chat."""
    r = rt(request)
    try:
        if body.scenario:
            return {"id": r.start_scenario(body.scenario, body.lineage)}
        if body.message:
            return {"id": r.start_live(body.message, body.lineage)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    raise HTTPException(422, "Give a scenario or a message.")


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request) -> dict[str, Any]:
    """Header, chat timeline and graph of one session."""
    try:
        return rt(request).snapshot(session_id)
    except KeyError as exc:
        raise HTTPException(404, "No such session.") from exc


@router.get("/sessions/{session_id}/graph")
def get_session_graph(session_id: str, request: Request) -> dict[str, Any]:
    """The session's graph only."""
    return get_session(session_id, request)["graph"]


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str, request: Request) -> JSONResponse:
    """Download the session as JSON."""
    snap = get_session(session_id, request)
    return JSONResponse(snap, headers={
        "Content-Disposition": f'attachment; filename="graphsentinel-{session_id}.json"'})


@router.post("/sessions/{session_id}/messages", status_code=202)
def post_message(session_id: str, body: NewMessage, request: Request) -> dict[str, str]:
    """Send a follow-up message to a live session."""
    try:
        rt(request).send_message(session_id, body.text)
    except RuntimeConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "accepted"}


@router.get("/calls/{call_id}/explain")
def get_explain(call_id: str, request: Request) -> dict[str, Any]:
    """The lineage subgraph behind one call."""
    try:
        return explain(rt(request).sentinel.store, call_id)
    except KeyError as exc:
        raise HTTPException(404, "No such call.") from exc


@router.post("/calls/{call_id}/decision")
def post_decision(call_id: str, body: Decision, request: Request) -> dict[str, Any]:
    """Allow or deny an Ask, or "Allow once" a Block."""
    try:
        return rt(request).decide(call_id, body.decision, body.by, body.note)
    except KeyError as exc:
        raise HTTPException(404, "No such call.") from exc
    except RuntimeConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/cypher")
def post_cypher(body: CypherQuery, request: Request) -> dict[str, Any]:
    """Run a read-only Cypher query against the live graph."""
    try:
        return run_read_only(rt(request).sentinel.store, body.query, body.params)
    except ReadOnlyError as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:  # Cypher syntax and runtime errors go back to the console
        raise HTTPException(400, f"{type(exc).__name__}: {exc}") from exc


@router.websocket("/sessions/{session_id}/events")
async def session_events(ws: WebSocket, session_id: str) -> None:
    """A snapshot first, then every event of the session as it happens."""
    r: Runtime = ws.app.state.runtime
    await ws.accept()
    queue = r.bus.subscribe(session_id)
    try:
        try:
            snap = await run_in_threadpool(r.snapshot, session_id)
        except KeyError:
            await ws.send_json({"type": "error", "data": {"message": "No such session."}})
            await ws.close()
            return
        await ws.send_json({"type": "snapshot", "session": session_id, "data": snap})
        while True:
            await ws.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        r.bus.unsubscribe(session_id, queue)


@router.websocket("/events")
async def all_events(ws: WebSocket) -> None:
    """Every event of every session (used by the sidebar to refresh the session list)."""
    r: Runtime = ws.app.state.runtime
    await ws.accept()
    queue = r.bus.subscribe("*")
    try:
        while True:
            event = await queue.get()
            if event["type"] in ("session_started", "verdict", "session_idle", "session_finished",
                                 "history_cleared"):
                await ws.send_json({"type": event["type"], "session": event["session"]})
    except WebSocketDisconnect:
        pass
    finally:
        r.bus.unsubscribe("*", queue)
