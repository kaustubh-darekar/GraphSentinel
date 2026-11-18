"""GraphSentinel as an MCP proxy: one MCP server (stdio) in front of real MCP servers.

Every tool call from the client goes through the same guarded path as the demo agent:
record -> link inputs -> check -> run on the real server, ask, or block.
Tools are exposed as `<server>__<tool>`; policy.yaml keys them as `<server>.<tool>`.
Nothing may be printed to stdout: it is the MCP channel.
"""

from __future__ import annotations

import logging
import sys
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import anyio
import mcp_types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from graphsentinel.agent.guarded import Approver, GuardedSession, deny_all
from graphsentinel.core.sentinel import Sentinel
from graphsentinel.proxy.config import ServerSpec

log = logging.getLogger("graphsentinel.proxy")


@dataclass
class Route:
    """Where an exposed tool really lives."""

    server: str
    tool: str
    session: ClientSession

    @property
    def policy_name(self) -> str:
        """The name policy.yaml uses for this tool."""
        return f"{self.server}.{self.tool}"


def exposed_name(server: str, tool: str) -> str:
    """Tool name shown to the client (letters, digits, _ and - only; max 64)."""
    return f"{server}__{tool}"[:64]


def result_text(result: Any) -> str:
    """Flatten a downstream CallToolResult into text for the graph and the client."""
    parts = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        parts.append(text if text is not None else f"[{getattr(item, 'type', 'content')}]")
    text = "\n".join(parts)
    return f"Error: {text}" if getattr(result, "is_error", False) else text


class Proxy:
    """Holds the downstream sessions and turns MCP requests into guarded calls."""

    def __init__(self, sentinel: Sentinel, guarded: GuardedSession) -> None:
        self.sentinel = sentinel
        self.guarded = guarded
        self.routes: dict[str, Route] = {}
        self.tools: list[types.Tool] = []
        self.by_policy: dict[str, Route] = {}
        guarded.run_tool = self._run_downstream

    async def connect(self, stack: AsyncExitStack, servers: list[ServerSpec]) -> None:
        """Start every downstream server and collect its tools."""
        for spec in servers:
            params = StdioServerParameters(command=spec.command, args=spec.args, env=spec.env, cwd=spec.cwd)
            read, write = await stack.enter_async_context(stdio_client(params, errlog=sys.stderr))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listed = await session.list_tools()
            for tool in listed.tools:
                name = exposed_name(spec.name, tool.name)
                route = Route(spec.name, tool.name, session)
                self.routes[name] = route
                self.by_policy[route.policy_name] = route
                self.tools.append(types.Tool(
                    name=name, description=f"[{spec.name}] {tool.description or ''}".strip(),
                    input_schema=tool.input_schema))
            log.info("connected %s (%d tools)", spec.name, len(listed.tools))

    async def on_list_tools(self, _ctx: Any, _params: Any) -> types.ListToolsResult:
        """Every downstream tool, renamed."""
        return types.ListToolsResult(tools=self.tools)

    async def on_call_tool(self, _ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        """Guard the call; run it on the real server only when allowed."""
        route = self.routes.get(params.name)
        if route is None:
            return types.CallToolResult(content=[types.TextContent(text=f"Unknown tool {params.name}")],
                                        is_error=True)
        outcome = await anyio.to_thread.run_sync(self.guarded.call, route.policy_name,
                                                 dict(params.arguments or {}))
        return types.CallToolResult(content=[types.TextContent(text=outcome.text)],
                                    is_error=not outcome.ran)

    def _run_downstream(self, policy_name: str, args: dict[str, Any]) -> str:
        """Runs in the guard's worker thread; hops back to the event loop for the MCP call."""
        route = self.by_policy[policy_name]
        result = anyio.from_thread.run(route.session.call_tool, route.tool, args)
        return result_text(result)


def start_ui(sentinel: Sentinel, port: int) -> Any:
    """Serve the API + web UI from this process (same store), in a background thread."""
    import uvicorn

    from graphsentinel.api.main import create_app

    app = create_app(sentinel)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="graphsentinel-ui", daemon=True)
    thread.start()
    for _ in range(100):  # wait for startup so the runtime exists
        if server.started:
            return app
        if not thread.is_alive():
            break
        threading.Event().wait(0.05)
    log.warning("UI did not start on port %d (is it in use?)", port)
    return None


async def serve(sentinel: Sentinel, servers: list[ServerSpec], *, ui_port: int | None) -> None:
    """Run the proxy over stdio until the client disconnects."""
    app = start_ui(sentinel, ui_port) if ui_port else None
    runtime = getattr(getattr(app, "state", None), "runtime", None)
    title = "MCP proxy: " + ", ".join(s.name for s in servers)
    sid_ref: list[str] = []
    emit = runtime.bus.sink(sid_ref) if runtime else None
    approver: Approver = deny_all
    guarded = GuardedSession.start(sentinel, title, None, mode="proxy",
                                   lineage=sentinel.settings.lineage_mode, emit=emit)
    if runtime is not None:  # the UI can resolve Asks and "Allow once" for this session
        from graphsentinel.api.runtime import Active
        approver = runtime._approver(guarded.session_id)  # noqa: SLF001 (same package family)
        runtime.active[guarded.session_id] = Active(guarded)
    guarded.approver = approver

    proxy = Proxy(sentinel, guarded)
    async with AsyncExitStack() as stack:
        await proxy.connect(stack, servers)
        server = Server("graphsentinel", on_list_tools=proxy.on_list_tools,
                        on_call_tool=proxy.on_call_tool)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
