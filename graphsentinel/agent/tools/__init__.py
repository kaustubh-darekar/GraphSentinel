"""Fake sandbox tools. They never touch the network or files outside sandbox_data/."""

from __future__ import annotations

from graphsentinel.agent.tools import calc, email, files, slack, web
from graphsentinel.agent.tools.base import Tool

REGISTRY: dict[str, Tool] = {t.name: t for m in (email, files, web, slack, calc) for t in m.TOOLS}


def get(name: str) -> Tool:
    """Look up a tool by name (raises KeyError for unknown tools)."""
    return REGISTRY[name]
