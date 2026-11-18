"""Tool definition shared by every sandbox tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SANDBOX = Path(__file__).resolve().parents[1] / "sandbox_data"


@dataclass(frozen=True)
class Tool:
    """A callable tool with an OpenAI-style JSON schema for its arguments."""

    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., str]

    def run(self, args: dict[str, Any]) -> str:
        """Call the tool; argument errors come back as text the agent can read."""
        try:
            return self.fn(**args)
        except TypeError as exc:
            return f"Error: bad arguments for {self.name}: {exc}"


def schema(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """JSON schema for an object with the given properties."""
    return {"type": "object", "properties": props, "required": required or [],
            "additionalProperties": False}
