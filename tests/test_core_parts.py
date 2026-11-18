"""Smaller pieces of core: fingerprints, policy, store threading."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from graphsentinel.core import GraphStore, Policy
from graphsentinel.core.fingerprint import fingerprint, normalize, overlap, shingles, stable_hash
from tests.conftest import ROOT


def test_normalize_lowercases_and_strips_punctuation() -> None:
    assert normalize("Hello, World! It's 95,000.") == ["hello", "world", "it", "s", "95", "000"]


def test_shingles_are_eight_words() -> None:
    s = shingles(" ".join(f"w{i}" for i in range(10)))
    assert len(s) == 3 and s[0] == "w0 w1 w2 w3 w4 w5 w6 w7"
    assert shingles("just three words") == ["just three words"]
    assert shingles("  ...  ") == []


def test_hashes_are_stable_32_bit() -> None:
    assert stable_hash("abc") == stable_hash("abc")
    assert 0 <= stable_hash("abc") < 2**32
    assert stable_hash("abc") != stable_hash("abd")


def test_copied_text_overlaps_and_unrelated_text_does_not() -> None:
    secret = "Alex Kim Engineer 128000 Sam Patel Designer 104000 Jordan Lee Manager"
    leak = "FYI the numbers are: " + secret.upper() + " thanks"
    assert overlap(fingerprint(secret), fingerprint(leak))
    assert not overlap(fingerprint(secret), fingerprint("the weather is nice today in the park"))


def test_policy_sync_sets_labels(store: GraphStore) -> None:
    Policy.load(ROOT / "policy.yaml").sync(store)
    rows = store.query("MATCH (t:Tool)-[:PART_OF]->(s:Server) "
                       "RETURN t.name AS name, labels(t) AS labels, s.name AS server")
    by = {r["name"]: r for r in rows}
    assert set(by["email.read_inbox"]["labels"]) == {"Tool", "Outside", "Private"}
    assert set(by["email.send_email"]["labels"]) == {"Tool", "SendsOut"}
    assert by["calc.calculate"]["labels"] == ["Tool"]
    assert by["web.fetch_url"]["server"] == "web"


def test_policy_resync_removes_stale_labels(store: GraphStore) -> None:
    Policy.from_dict({"tools": {"x.y": {"tags": ["outside"]}}}).sync(store)
    Policy.from_dict({"tools": {"x.y": {"tags": ["private"]}}}).sync(store)
    labels = store.query("MATCH (t:Tool {name: 'x.y'}) RETURN labels(t) AS l")[0]["l"]
    assert set(labels) == {"Tool", "Private"}


def test_policy_rejects_unknown_tags() -> None:
    with pytest.raises(ValueError):
        Policy.from_dict({"tools": {"x.y": {"tags": ["lethal"]}}})


def test_store_is_usable_from_any_thread(store: GraphStore) -> None:
    results: list[int] = []

    def worker(n: int) -> None:
        store.query("CREATE (:Probe {n: $n})", {"n": n})
        results.append(n)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.query("MATCH (p:Probe) RETURN count(p) AS n")[0]["n"] == 8


def test_schema_is_idempotent_and_directory_store_persists(tmp_path: Path) -> None:
    path = tmp_path / "db"
    with GraphStore(path) as s:
        s.query("CREATE (:Session {id: 's1'})")
    with GraphStore(path) as s:  # schema runs again on reopen
        assert s.query("MATCH (x:Session) RETURN x.id AS id") == [{"id": "s1"}]
    assert path.is_dir()


def test_transaction_rolls_back_on_error(store: GraphStore) -> None:
    store.query("CREATE (:Session {id: 'dup'})")
    with pytest.raises(Exception):
        store.transaction([
            ("CREATE (:Probe {n: 1})", None),
            ("CREATE (:Session {id: 'dup'})", None),  # violates the unique constraint
        ])
    assert store.query("MATCH (p:Probe) RETURN count(p) AS n")[0]["n"] == 0
