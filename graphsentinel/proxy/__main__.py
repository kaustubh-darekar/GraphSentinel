"""`python -m graphsentinel.proxy --config servers.json [--policy policy.yaml]`"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace

import anyio
from dotenv import load_dotenv

from graphsentinel.core.config import Settings
from graphsentinel.core.sentinel import Sentinel
from graphsentinel.proxy.config import load_servers
from graphsentinel.proxy.server import serve


def main(argv: list[str] | None = None) -> int:
    """Run the MCP proxy over stdio. Logs go to stderr; stdout is the MCP channel."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="graphsentinel: %(message)s")
    load_dotenv()
    ap = argparse.ArgumentParser(prog="graphsentinel proxy", description=__doc__)
    ap.add_argument("--config", required=True, help="servers.json (Claude Desktop mcpServers format)")
    ap.add_argument("--policy", help="policy.yaml (default: GS_POLICY_PATH or ./policy.yaml)")
    ap.add_argument("--store", help="store directory (default: GS_STORE_PATH)")
    ap.add_argument("--ui-port", type=int, default=int(os.environ.get("GS_PROXY_UI_PORT", "8000")),
                    help="serve the web UI from the proxy on this port (default 8000)")
    ap.add_argument("--no-ui", action="store_true", help="do not start the web UI")
    args = ap.parse_args(argv)

    settings = Settings.from_env()
    if args.policy:
        settings = replace(settings, policy_path=os.path.abspath(args.policy))
    sentinel = Sentinel.open(settings, store_path=args.store)
    try:
        anyio.run(lambda: serve(sentinel, load_servers(args.config),
                                ui_port=None if args.no_ui else args.ui_port))
    finally:
        sentinel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
