"""Named Cypher queries. Every query lives in `<name>.cypher` next to this file."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def load(name: str) -> str:
    """Return the text of `queries/<name>.cypher`, with `//` comment lines removed."""
    text = (_DIR / f"{name}.cypher").read_text(encoding="utf-8")
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//")).strip()


def split_statements(script: str) -> list[str]:
    """Split a `;`-separated script into statements, dropping comments and blanks."""
    lines = [ln for ln in script.splitlines() if not ln.lstrip().startswith("//")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
