"""The proxy's server list, in the same shape as Claude Desktop's `mcpServers` config."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServerSpec:
    """How to start one downstream MCP server (stdio)."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None


def load_servers(path: str | Path) -> list[ServerSpec]:
    """Read `{"mcpServers": {name: {command, args, env, cwd}}}` (a bare mapping also works)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    servers = data.get("mcpServers", data)
    out = []
    for name, spec in servers.items():
        if "." in name or "__" in name:
            raise ValueError(f"server name {name!r} must not contain '.' or '__'")
        out.append(ServerSpec(name, spec["command"], list(spec.get("args", [])),
                              spec.get("env"), spec.get("cwd")))
    return out
