"""Paraphrase detection with vector search on the same graph."""

from __future__ import annotations

from typing import Iterator

import pytest

from graphsentinel.agent.guarded import GuardedSession
from graphsentinel.agent.runner_scripted import find_scenario, run_scenario
from graphsentinel.agent.tools import outbox
from graphsentinel.core.config import Settings
from graphsentinel.core.embedding import CachedEmbedder, LocalEmbedder, chunks
from graphsentinel.core.sentinel import Sentinel


@pytest.fixture
def sentinel(monkeypatch: pytest.MonkeyPatch) -> Iterator[Sentinel]:
    for var in ("OPENAI_API_KEY", "OPENAI_EMBED_MODEL", "GS_EMBEDDER", "GS_SIMILARITY_THRESHOLD"):
        monkeypatch.delenv(var, raising=False)  # prove scripted mode needs no key
    outbox.clear()
    s = Sentinel.open(Settings(store_path=":memory:"))
    yield s
    s.close()


def similar_edges(sentinel: Sentinel, call_id: str) -> list[dict]:
    return sentinel.store.query(
        "MATCH (src:Call)-[:PRODUCED]->(d:Data)-[f:FED_INTO {how: 'similar'}]->(c:Call {id: $id}) "
        "RETURN src.tool AS tool, src.label AS label, f.score AS score", {"id": call_id})


def test_scenario_05_is_blocked_only_because_of_the_similar_edge(sentinel: Sentinel) -> None:
    sc = find_scenario("05_paraphrased_leak")
    assert sc.lineage == "precise" and sc.embeddings, "scenario 05 ships pre-computed vectors"
    result = run_scenario(sentinel, sc)
    send = result.outcomes[-1]
    assert send.verdict.decision == "block"
    edges = similar_edges(sentinel, send.call.id)
    assert [e["label"] for e in edges] == ["salaries.xlsx"]
    assert edges[0]["score"] >= sc.embeddings["threshold"]
    # the Private source reaches the send only through that similar edge
    private = [s for s in send.verdict.private if s.label == "salaries.xlsx"]
    assert private and len(private[0].chain) == 3
    assert outbox.sent() == []


def test_without_vectors_the_same_scenario_only_asks(sentinel: Sentinel,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GS_EMBEDDER", "off")
    result = run_scenario(sentinel, find_scenario("05_paraphrased_leak"))
    assert result.outcomes[-1].verdict.decision == "ask"
    assert similar_edges(sentinel, result.outcomes[-1].call.id) == []


def test_the_local_embedder_also_catches_the_reworded_salaries(sentinel: Sentinel) -> None:
    sc = find_scenario("05_paraphrased_leak")
    result = run_scenario(sentinel, sc, embedder=LocalEmbedder())
    send = result.outcomes[-1]
    assert send.verdict.decision == "block"
    assert [e["label"] for e in similar_edges(sentinel, send.call.id)] == ["salaries.xlsx"]


def test_unrelated_text_gets_no_similar_edge(sentinel: Sentinel) -> None:
    gs = GuardedSession.start(sentinel, "t", None, mode="scripted", lineage="precise")
    gs.embedder = LocalEmbedder()
    gs.call("email.read_inbox", {"unread_only": True})
    gs.call("files.read_file", {"path": "salaries.xlsx"})
    out = gs.call("email.send_email", {
        "to": "friend@elsewhere.test", "subject": "Thursday",
        "body": "Thanks, the meeting has moved to Thursday at three in the afternoon. See you there."})
    assert similar_edges(sentinel, out.call.id) == []
    assert out.verdict.decision == "allow"


def test_strict_sessions_do_not_embed(sentinel: Sentinel) -> None:
    run_scenario(sentinel, find_scenario("01_poisoned_email"), lineage="strict")
    rows = sentinel.store.query("MATCH (d:Data) WHERE d.embedding IS NOT NULL RETURN count(d) AS n")
    assert rows == [{"n": 0}]


def test_cached_embedder_misses_are_explicit() -> None:
    emb = CachedEmbedder("cached:x", 3, 0.85, {})
    with pytest.raises(KeyError, match="embed_scenario"):
        emb.embed(["hello"])
    with_fallback = CachedEmbedder("cached:x", 256, 0.85, {}, fallback=LocalEmbedder())
    assert len(with_fallback.embed(["hello world"])[0]) == 256


def test_local_embedder_is_deterministic_and_normalised() -> None:
    a, b = LocalEmbedder().embed(["Alex Kim earns 128000", "Alex Kim earns 128000"])
    assert a == b and abs(sum(x * x for x in a) - 1.0) < 1e-9


def test_chunks_split_paragraphs() -> None:
    text = "First paragraph has enough words in it.\n\nSecond paragraph also has enough words here."
    parts = chunks(text)
    assert parts[:2] == ["First paragraph has enough words in it.",
                         "Second paragraph also has enough words here."]
    assert parts[-1] == text
    assert chunks("too short") == []
