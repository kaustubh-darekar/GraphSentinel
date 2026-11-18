"""The guarded call path, the scenarios and the sandbox tools."""

from __future__ import annotations

from typing import Any, Iterator

import pytest

from graphsentinel.agent.guarded import GuardedSession
from graphsentinel.agent.runner_scripted import find_scenario, list_scenarios, run_scenario
from graphsentinel.agent.tools import outbox
from graphsentinel.core.config import Settings
from graphsentinel.core.sentinel import Sentinel


@pytest.fixture
def sentinel() -> Iterator[Sentinel]:
    s = Sentinel.open(Settings(store_path=":memory:"))
    outbox.clear()
    yield s
    s.close()


@pytest.mark.parametrize("scenario_id, decision, delivered", [
    ("01_poisoned_email", "block", 0),
    ("02_poisoned_webpage", "block", 0),
    ("03_safe_report", "allow", 1),
    ("04_ask_then_override", "ask", 1),  # the scripted user allows it
])
def test_scenarios_give_expected_verdicts(sentinel: Sentinel, scenario_id: str,
                                          decision: str, delivered: int) -> None:
    result = run_scenario(sentinel, find_scenario(scenario_id), lineage="strict")
    assert result.ok, [(c.step, c.expected, c.actual) for c in result.checks]
    assert result.outcomes[-1].verdict.decision == decision
    assert len(outbox.sent()) == delivered


def test_every_scenario_parses_and_has_an_expectation() -> None:
    scenarios = list_scenarios()
    assert [s.id for s in scenarios][:5] == [
        "01_poisoned_email", "02_poisoned_webpage", "03_safe_report",
        "04_ask_then_override", "05_paraphrased_leak"]
    for s in scenarios:
        assert any("expect" in step for step in s.steps), s.id
        assert "#" not in s.user or "#sales" in s.user or "#partners" in s.user


def test_block_refusal_reaches_the_agent_and_events_fire(sentinel: Sentinel) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    result = run_scenario(sentinel, find_scenario("01_poisoned_email"), lineage="strict",
                          emit=lambda k, d: events.append((k, d)))
    send = result.outcomes[-1]
    assert send.status == "blocked" and "blocked" in send.text.lower()
    kinds = [k for k, _ in events]
    for k in ("session_started", "user_message", "call_recorded", "graph_delta",
              "verdict", "call_result", "agent_message", "session_finished"):
        assert k in kinds, k
    verdict = next(d for k, d in events if k == "verdict" and d["decision"] == "block")
    assert verdict["path"] and verdict["check_ms"] >= 0


def test_ask_denied_by_default_never_runs(sentinel: Sentinel) -> None:
    gs = GuardedSession.start(sentinel, "t", "post news", mode="scripted", lineage="strict")
    gs.call("web.fetch_url", {"url": "https://news.industry.test/today"})
    out = gs.call("slack.post_message", {"channel": "#partners-external", "text": "news"})
    assert out.verdict.decision == "ask" and out.status == "denied"
    assert outbox.sent() == []
    row = sentinel.store.query("MATCH (c:Call {id: $id}) RETURN c.resolution AS r", {"id": out.call.id})
    assert row == [{"r": "denied"}]


def test_ask_timeout_is_a_deny(sentinel: Sentinel) -> None:
    gs = GuardedSession.start(sentinel, "t", None, mode="scripted", lineage="strict",
                              approver=lambda _c, _v: "timeout")
    gs.call("web.fetch_url", {"url": "https://news.industry.test/today"})
    out = gs.call("slack.post_message", {"channel": "#partners-external", "text": "news"})
    assert out.status == "timeout" and outbox.sent() == []


def test_allow_once_runs_a_blocked_call_and_records_the_override(sentinel: Sentinel) -> None:
    result = run_scenario(sentinel, find_scenario("01_poisoned_email"), lineage="strict")
    blocked = result.outcomes[-1]
    gs = GuardedSession(sentinel, result.session_id, "strict")
    out = gs.allow_once(blocked.call.id, by="me", note="I checked it")
    assert out.ran and len(outbox.sent()) == 1
    row = sentinel.store.query(
        "MATCH (o:Override)-[:OVERRIDES]->(c:Call {id: $id}) "
        "RETURN o.by AS by, c.decision AS d, c.resolution AS r", {"id": blocked.call.id})
    assert row == [{"by": "me", "d": "block", "r": "overridden"}]
    with pytest.raises(ValueError):
        gs.allow_once(blocked.call.id)


def test_unknown_tool_is_recorded_and_returns_an_error(sentinel: Sentinel) -> None:
    gs = GuardedSession.start(sentinel, "t", None, mode="scripted", lineage="strict")
    out = gs.call("shell.exec", {"cmd": "ls"})
    assert out.ran and out.text.startswith("Error: unknown tool")


def test_sandbox_files_cannot_escape() -> None:
    from graphsentinel.agent.tools import get
    assert get("files.read_file").run({"path": "../inbox.json"}).startswith("Error")
    assert get("files.read_file").run({"path": "../../../pyproject.toml"}).startswith("Error")
    assert "salaries.xlsx" in get("files.list_files").run({})


def test_cli_runs_a_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    from graphsentinel.run import main
    assert main(["01_poisoned_email", "--lineage", "strict"]) == 0
    out = capsys.readouterr().out
    assert "BLOCK" in out and "PASS" in out and "Outside (inbox)" in out
