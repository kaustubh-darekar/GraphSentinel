"""The guard: decides Allow / Ask / Block for a call by walking its lineage.

For a call to a :SendsOut tool:
- Block if its lineage includes an Outside call AND a Private call AND a destination
  is not trusted (the risky three in one session).
- Ask if the lineage includes Outside or Private (but not both) and a destination
  is not trusted.
- Allow otherwise, including Private data going to a trusted destination.
Non-sending calls are always allowed. A human :Override turns a call into Allow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from graphsentinel.core.store import GraphStore

Decision = Literal["allow", "ask", "block"]


@dataclass(frozen=True)
class Source:
    """An Outside or Private call in the lineage, with the chain that links it to the send."""

    call_id: str
    step: int
    tool: str
    label: str
    outside: bool
    private: bool
    chain: list[str]  # alternating call/data ids, from the source call to the checked call


@dataclass(frozen=True)
class Verdict:
    """The guard's answer for one call."""

    decision: Decision
    reason: str
    path: list[str] = field(default_factory=list)  # chains (call/data ids) joined end to end
    sources: list[Source] = field(default_factory=list)
    untrusted: list[str] = field(default_factory=list)  # destinations that are not trusted

    @property
    def outside(self) -> list[Source]:
        """Outside sources in the lineage."""
        return [s for s in self.sources if s.outside]

    @property
    def private(self) -> list[Source]:
        """Private sources in the lineage."""
        return [s for s in self.sources if s.private]

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly form for the API."""
        return asdict(self)


class Guard:
    """Runs the lineage check against the graph. Read-only: record the verdict separately."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def warm_up(self) -> None:
        """Plan the guard's queries once, so the first real check is as fast as the rest."""
        for name in ("guard_context", "guard_lineage"):
            self.store.run(name, {"callId": "warm-up"})

    def check(self, call_id: str) -> Verdict:
        """Decide Allow / Ask / Block for `call_id`."""
        ctx = self.store.run("guard_context", {"callId": call_id})
        if not ctx:
            raise KeyError(f"unknown call {call_id!r}")
        row = ctx[0]
        if not row["sends_out"]:
            return Verdict("allow", "Not a Sends out call.")
        if row["overrides"]:
            return Verdict("allow", f"Allowed once by {row['overrides'][0]}.")

        dests = [d for d in row["dests"] if d.get("address") is not None]
        untrusted = [d["address"] for d in dests if not d["trusted"]]
        if dests and not untrusted:
            return Verdict("allow", "Destination is trusted.")
        if not dests:
            untrusted = ["an unknown destination"]

        sources = [_source(r) for r in self.store.run("guard_lineage", {"callId": call_id})]
        outside = [s for s in sources if s.outside]
        private = [s for s in sources if s.private]
        path = _merge_chains([s.chain for s in _pick(outside, private)])
        where = ", ".join(untrusted)

        if outside and private:
            # Name pure-Private sources (salaries.xlsx) rather than repeating an Outside
            # source that is also Private (the inbox), unless that is all there is.
            only_private = [s for s in private if not s.outside]
            if only_private:
                reason = (f"Blocked: data from Outside ({_names(outside)}) and Private "
                          f"({_names(only_private)}) was about to go to {where}.")
            else:  # one source is both, e.g. an inbox full of outside emails
                reason = (f"Blocked: data from Outside and Private ({_names(outside)}) "
                          f"was about to go to {where}.")
            return Verdict("block", reason, path, sources, untrusted)
        if outside or private:
            kind, srcs = ("Outside", outside) if outside else ("Private", private)
            reason = f"Ask: data from {kind} ({_names(srcs)}) is about to go to {where}."
            return Verdict("ask", reason, path, sources, untrusted)
        return Verdict("allow", "No Outside or Private data in the lineage.", [], [], untrusted)


def _source(r: dict[str, Any]) -> Source:
    return Source(r["src"], r["step"], r["tool"], r["label"] or r["tool"],
                  bool(r["outside"]), bool(r["private"]), list(r["path"]))


def _pick(outside: list[Source], private: list[Source]) -> list[Source]:
    """The sources whose chains make up `Verdict.path`: the first Outside source, plus
    the first Private source that is a different call (falling back to any Private)."""
    picked = outside[:1]
    others = [s for s in private if not picked or s.call_id != picked[0].call_id]
    picked += others[:1] if others else ([] if picked else private[:1])
    return picked


def _names(sources: list[Source]) -> str:
    seen: list[str] = []
    for s in sources:
        if s.label not in seen:
            seen.append(s.label)
    return ", ".join(seen)


def _merge_chains(chains: list[list[str]]) -> list[str]:
    """Chains joined end to end. Each consecutive pair inside a chain is a real edge; the
    seam between chains is (checked call, next source call), which is never an edge."""
    return [i for chain in chains for i in chain]
