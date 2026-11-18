"""REST + WebSocket API against an in-memory store."""

from __future__ import annotations

import time
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from graphsentinel.agent.tools import outbox
from graphsentinel.api.cypher import ReadOnlyError, check_read_only
from graphsentinel.api.main import create_app
from graphsentinel.core.config import Settings
from graphsentinel.core.sentinel import Sentinel


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GS_STEP_DELAY", "0")
    monkeypatch.setenv("GS_ASK_TIMEOUT", "5")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    outbox.clear()
    sentinel = Sentinel.open(Settings(store_path=":memory:"))
    with TestClient(create_app(sentinel)) as c:
        yield c
    sentinel.close()


def wait_until(client: TestClient, sid: str, pred: Any, timeout: float = 10) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = client.get(f"/api/sessions/{sid}").json()
        if pred(snap):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting on session {sid}")


def calls(snap: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in snap["timeline"] if i["kind"] == "call"]


def test_config_and_scenarios(client: TestClient) -> None:
    cfg = client.get("/api/config").json()
    assert cfg["live_available"] is False and cfg["lineage"] in ("strict", "precise")
    assert client.put("/api/config", json={"lineage": "precise"}).json()["lineage"] == "precise"
    ids = [s["id"] for s in client.get("/api/scenarios").json()]
    assert "01_poisoned_email" in ids


def test_scenario_01_blocks_and_explains(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"scenario": "01_poisoned_email",
                                             "lineage": "strict"}).json()["id"]
    snap = wait_until(client, sid, lambda s: not s["running"] and len(calls(s)) == 3)
    send = calls(snap)[-1]
    assert send["decision"] == "block" and send["path"]
    assert "salaries.xlsx" in send["reason"]
    kinds = {n["kind"] for n in snap["graph"]["nodes"]}
    assert kinds == {"call", "data", "destination"}

    ex = client.get(f"/api/calls/{send['id']}/explain").json()
    assert set(send["path"]) <= {n["id"] for n in ex["nodes"]}
    assert client.get("/api/sessions").json()[0]["blocks"] == 1


def test_websocket_streams_snapshot_then_events(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"scenario": "03_safe_report"}).json()["id"]
    seen: list[str] = []
    with client.websocket_connect(f"/api/sessions/{sid}/events") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        while "session_idle" not in seen:
            seen.append(ws.receive_json()["type"])
    snap = wait_until(client, sid, lambda s: not s["running"])
    assert calls(snap)[-1]["decision"] == "allow"
    assert len(outbox.sent()) == 1


def test_ask_waits_for_the_ui_then_allow(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"scenario": "04_ask_then_override"}).json()["id"]
    snap = wait_until(client, sid, lambda s: s["pending"])
    call_id = snap["pending"][0]
    assert client.post(f"/api/calls/{call_id}/decision", json={"decision": "allow"}).status_code == 200
    snap = wait_until(client, sid, lambda s: not s["running"] and not s["pending"])
    assert calls(snap)[-1]["resolution"] == "approved"
    assert len(outbox.sent()) == 1
    # a second decision is a conflict
    assert client.post(f"/api/calls/{call_id}/decision", json={"decision": "deny"}).status_code == 409


def test_allow_once_overrides_a_block(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"scenario": "01_poisoned_email",
                                             "lineage": "strict"}).json()["id"]
    snap = wait_until(client, sid, lambda s: not s["running"] and len(calls(s)) == 3)
    call_id = calls(snap)[-1]["id"]
    r = client.post(f"/api/calls/{call_id}/decision", json={"decision": "allow_once"})
    assert r.json()["status"] == "ran" and len(outbox.sent()) == 1
    snap = client.get(f"/api/sessions/{sid}").json()
    assert calls(snap)[-1]["resolution"] == "overridden"


def test_live_mode_without_key_is_a_clear_409(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"message": "hello"})
    assert r.status_code == 409 and "OPENAI_API_KEY" in r.json()["detail"]


def test_cypher_console_is_read_only(client: TestClient) -> None:
    client.post("/api/sessions", json={"scenario": "03_safe_report"})
    time.sleep(0.5)
    ok = client.post("/api/cypher", json={"query": "MATCH (t:Tool) RETURN t.name AS name, t ORDER BY name"})
    assert ok.status_code == 200 and ok.json()["columns"] == ["name", "t"]
    assert ok.json()["rows"][0]["t"]["_node"]
    for q in ("CREATE (:X)", "MATCH (n) DETACH DELETE n", "MATCH (n) SET n.x = 1",
              "merge (x:Y)", "DROP INDEX call_session"):
        assert client.post("/api/cypher", json={"query": q}).status_code == 403, q
    bad = client.post("/api/cypher", json={"query": "MATCH (n RETURN n"})
    assert bad.status_code == 400


def test_read_only_filter_ignores_strings_and_comments() -> None:
    check_read_only("MATCH (c:Call) WHERE c.reason CONTAINS 'SET' RETURN c // DELETE")
    check_read_only("MATCH (n) RETURN n.created_at AS createdAt, n.dataset AS d")
    with pytest.raises(ReadOnlyError):
        check_read_only("MATCH (n) WITH n CALL { CREATE (:X) } RETURN n")


def test_store_read_always_rolls_back(client: TestClient) -> None:
    store = client.app.state.runtime.sentinel.store
    store.read("CREATE (:Sneaky)")  # bypasses the keyword filter on purpose
    assert store.query("MATCH (s:Sneaky) RETURN count(s) AS n") == [{"n": 0}]


def test_clear_history_deletes_finished_runs_but_keeps_tools(client: TestClient) -> None:
    for sc in ("01_poisoned_email", "03_safe_report"):
        sid = client.post("/api/sessions", json={"scenario": sc}).json()["id"]
        wait_until(client, sid, lambda s: not s["running"])
    assert len(client.get("/api/sessions").json()) == 2
    assert client.delete("/api/sessions").json() == {"deleted": 2, "kept": 0}
    assert client.get("/api/sessions").json() == []
    rows = client.post("/api/cypher", json={"query": "MATCH (n) RETURN labels(n)[0] AS l, count(*) AS n"}).json()["rows"]
    labels = {r["l"] for r in rows}
    assert {"Tool", "Server"} <= labels and not labels & {"Session", "Call", "Data", "Message", "Destination"}
    assert client.delete("/api/sessions").json() == {"deleted": 0, "kept": 0}


def test_clear_history_keeps_a_run_waiting_for_a_decision(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"scenario": "04_ask_then_override"}).json()["id"]
    snap = wait_until(client, sid, lambda s: s["pending"])
    assert client.delete("/api/sessions").json() == {"deleted": 0, "kept": 1}
    client.post(f"/api/calls/{snap['pending'][0]}/decision", json={"decision": "deny"})
    wait_until(client, sid, lambda s: not s["running"])
