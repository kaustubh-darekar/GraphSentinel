"""Sandbox files: read-only access to sandbox_data/files and nothing else."""

from __future__ import annotations

from graphsentinel.agent.tools.base import SANDBOX, Tool, schema

ROOT = SANDBOX / "files"


def list_files() -> str:
    """Names of the user's files."""
    return "\n".join(sorted(p.name for p in ROOT.iterdir() if p.is_file()))


def read_file(path: str) -> str:
    """Contents of one file. Paths outside the sandbox are refused."""
    target = (ROOT / path).resolve()
    if ROOT.resolve() not in target.parents or not target.is_file():
        return f"Error: no such file: {path}"
    return target.read_text(encoding="utf-8")


TOOLS = [
    Tool("files.list_files", "List the user's files.", schema({}), list_files),
    Tool("files.read_file", "Read one of the user's files by name.",
         schema({"path": {"type": "string", "description": "File name, e.g. q3_report.md"}}, ["path"]),
         read_file),
]
