"""CLI: replay scenarios (or chat live) and print a coloured timeline.

    python -m graphsentinel.run scenarios/01_poisoned_email.yaml
    python -m graphsentinel.run --all
    python -m graphsentinel.run --live "Summarise my unread emails."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from typing import Any

from dotenv import load_dotenv

from graphsentinel.core.sentinel import Sentinel

COLORS = {"block": "31", "ask": "33", "allow": "32", "dim": "2", "bold": "1",
          "outside": "33", "private": "35", "sends_out": "31", "cyan": "36"}


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def c(text: str, color: str) -> str:
    """Wrap text in an ANSI colour when printing to a terminal."""
    return f"\x1b[{COLORS[color]}m{text}\x1b[0m" if _USE_COLOR else text


_USE_COLOR = False


class TimelinePrinter:
    """Turns guarded-session events into terminal lines."""

    def __init__(self, sentinel: Sentinel) -> None:
        self.policy = sentinel.policy

    def __call__(self, kind: str, data: dict[str, Any]) -> None:
        handler = getattr(self, f"on_{kind}", None)
        if handler:
            handler(data)

    def on_session_started(self, d: dict[str, Any]) -> None:
        print(c(f"\n== {d['title']}", "bold") + c(f"  ({d['lineage']} lineage, session {d['session']})", "dim"))

    def on_user_message(self, d: dict[str, Any]) -> None:
        print(c("  user   ", "cyan") + d["text"])

    def on_agent_message(self, d: dict[str, Any]) -> None:
        lines = textwrap.dedent(d["text"]).strip().splitlines() or [""]
        print(c("  agent  ", "dim") + lines[0])
        for ln in lines[1:]:
            print("         " + ln)

    def on_call_recorded(self, d: dict[str, Any]) -> None:
        tp = self.policy.tool(d["tool"])
        tags = " ".join(c(t.replace("_", " "), t) for t, on in
                        (("outside", tp.outside), ("private", tp.private), ("sends_out", tp.sends_out)) if on)
        args = json.dumps(d["args"], ensure_ascii=False)
        args = args if len(args) <= 70 else args[:67] + "..."
        print(f"  {d['step']:>2}. {c(d['tool'], 'bold')} {c(args, 'dim')} {tags}")

    def on_verdict(self, d: dict[str, Any]) -> None:
        decision = d["decision"]
        if decision == "allow" and d["reason"] == "Not a Sends out call.":
            print(c(f"      allow  ({d['check_ms']:.2f} ms)", "dim"))
            return
        print("      " + c(decision.upper(), decision) + c(f"  ({d['check_ms']:.2f} ms)  ", "dim") + d["reason"])
        if decision != "allow" and d["path"]:
            print(c("      path: " + " -> ".join(d["path"]), "dim"))

    def on_resolution(self, d: dict[str, Any]) -> None:
        print(c(f"      user decision: {d['resolution']}", "cyan"))


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a non-zero exit code when an expectation fails."""
    global _USE_COLOR
    load_dotenv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if os.name == "nt":
        os.system("")  # enables ANSI colours in the Windows console
    _USE_COLOR = _use_color()

    ap = argparse.ArgumentParser(prog="python -m graphsentinel.run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*", help="scenario files or ids (e.g. 01_poisoned_email)")
    ap.add_argument("--all", action="store_true", help="run every scenario in scenarios/")
    ap.add_argument("--live", metavar="MESSAGE", help="chat with the live OpenAI agent instead")
    ap.add_argument("--lineage", choices=["strict", "precise"], help="override GS_LINEAGE_MODE")
    ap.add_argument("--store", default=":memory:",
                    help="store directory (default: in-memory; the API's store is GS_STORE_PATH)")
    args = ap.parse_args(argv)

    from graphsentinel.agent.runner_scripted import find_scenario, list_scenarios, run_scenario

    sentinel = Sentinel.open(store_path=args.store)
    printer = TimelinePrinter(sentinel)
    try:
        if args.live:
            return _live(sentinel, printer, args.live, args.lineage)
        scenarios = list_scenarios() if args.all else [find_scenario(s) for s in args.scenarios]
        if not scenarios:
            ap.error("give a scenario, --all, or --live MESSAGE")
        failures = 0
        for sc in scenarios:
            result = run_scenario(sentinel, sc, lineage=args.lineage, emit=printer)
            for chk in result.checks:
                mark = c("PASS", "allow") if chk.ok else c("FAIL", "block")
                print(f"  {mark} step {chk.step} {chk.tool}: expected {chk.expected}, got {chk.actual}")
                failures += not chk.ok
        return 1 if failures else 0
    finally:
        sentinel.close()


def _live(sentinel: Sentinel, printer: TimelinePrinter, message: str, lineage: str | None) -> int:
    from graphsentinel.agent.runner_live import LiveAgent, LiveConfigError

    def ask_in_terminal(_call: Any, verdict: Any) -> str:
        if not sys.stdin.isatty():
            return "denied"
        answer = input(c(f"      {verdict.reason} Allow? [y/N] ", "ask"))
        return "approved" if answer.strip().lower() in ("y", "yes") else "denied"

    try:
        agent = LiveAgent.start(sentinel, message, lineage=lineage or sentinel.settings.lineage_mode,
                                emit=printer, approver=ask_in_terminal)
    except LiveConfigError as exc:
        print(c(f"Live mode is not configured: {exc}", "block"))
        return 2
    agent.send(message, record_user=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
