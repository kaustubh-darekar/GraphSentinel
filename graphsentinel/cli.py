"""The `graphsentinel` command: `graphsentinel run ...`, `graphsentinel proxy ...`, `graphsentinel demo-store`."""

from __future__ import annotations

import sys


def main() -> int:
    """Dispatch to a subcommand."""
    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("--help", [])
    if cmd == "run":
        from graphsentinel.run import main as run_main
        return run_main(rest)
    if cmd == "proxy":
        from graphsentinel.proxy.__main__ import main as proxy_main
        return proxy_main(rest)
    if cmd == "demo-store":
        from graphsentinel.demo_store import main as demo_main
        return demo_main()
    print("usage: graphsentinel {run|proxy|demo-store} [options]\n"
          "  run         replay scenarios or chat live (python -m graphsentinel.run --help)\n"
          "  proxy       guard real MCP servers for Claude Desktop (--config servers.json)\n"
          "  demo-store  rebuild stores/demo from the scenarios")
    return 0 if cmd in ("-h", "--help") else 2


if __name__ == "__main__":
    raise SystemExit(main())
