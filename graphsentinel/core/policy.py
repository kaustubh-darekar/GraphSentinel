"""Tool risk policy: which tools read Outside content, read Private data, or Send out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from graphsentinel.core.store import GraphStore

TAGS = ("outside", "private", "sends_out")


@dataclass(frozen=True)
class ToolPolicy:
    """Risk tags and argument hints for one tool."""

    name: str
    server: str
    outside: bool = False
    private: bool = False
    sends_out: bool = False
    destination_args: tuple[str, ...] = ()
    label_arg: str | None = None
    static_label: str | None = None

    def label(self, args: dict[str, Any]) -> str:
        """Short human label for a call: the `label_arg` value, else `label`, else the tool name."""
        value = args.get(self.label_arg) if self.label_arg else None
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        if value not in (None, ""):
            return str(value)
        return self.static_label or self.name

    def destinations(self, args: dict[str, Any]) -> list[str]:
        """Every destination address found in the call's arguments."""
        out: list[str] = []
        for key in self.destination_args:
            value = args.get(key)
            if isinstance(value, str):
                out += [v for v in (p.strip() for p in value.split(",")) if v]
            elif isinstance(value, list):
                out += [str(v).strip() for v in value if str(v).strip()]
        return out


class Policy:
    """All tool policies, loaded from `policy.yaml`."""

    def __init__(self, tools: dict[str, ToolPolicy]) -> None:
        self.tools = tools

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        """Parse a policy file."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Policy":
        """Build a policy from the parsed YAML structure."""
        tools: dict[str, ToolPolicy] = {}
        for name, spec in (data.get("tools") or {}).items():
            spec = spec or {}
            tags = set(spec.get("tags") or [])
            unknown = tags - set(TAGS)
            if unknown:
                raise ValueError(f"{name}: unknown tags {sorted(unknown)}")
            tools[name] = ToolPolicy(
                name=name,
                server=spec.get("server") or name.split(".", 1)[0],
                outside="outside" in tags,
                private="private" in tags,
                sends_out="sends_out" in tags,
                destination_args=tuple(spec.get("destination_args") or ()),
                label_arg=spec.get("label_arg"),
                static_label=spec.get("label"),
            )
        return cls(tools)

    def tool(self, name: str) -> ToolPolicy:
        """Policy for `name`; unknown tools are untagged."""
        return self.tools.get(name) or ToolPolicy(name=name, server=name.split(".", 1)[0])

    def sync(self, store: GraphStore) -> None:
        """MERGE every :Tool and :Server node and set its Outside/Private/SendsOut labels."""
        rows = [
            {"name": t.name, "server": t.server, "outside": t.outside,
             "private": t.private, "sends_out": t.sends_out}
            for t in self.tools.values()
        ]
        if rows:
            store.run("sync_policy", {"rows": rows})
