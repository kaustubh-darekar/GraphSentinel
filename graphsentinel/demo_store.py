"""Build the committed demo store: every scenario replayed (scripted, no key) into stores/demo/.

    python -m graphsentinel.demo_store        (or: make demo-store)

Then exports a single-file copy with `relate clone stores/demo stores/demo.rl`
when the Relate CLI is installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from graphsentinel.agent.runner_scripted import list_scenarios, run_scenario
from graphsentinel.agent.tools import outbox
from graphsentinel.core.config import Settings
from graphsentinel.core.sentinel import REPO_ROOT, Sentinel

DEMO_DIR = REPO_ROOT / "stores" / "demo"
DEMO_RL = REPO_ROOT / "stores" / "demo.rl"


def relate_cli() -> str | None:
    """Path to the `relate` CLI, if installed."""
    found = shutil.which("relate")
    if found:
        return found
    win = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "relate" / "relate.exe"
    return str(win) if win.exists() else None


def build(directory: Path = DEMO_DIR) -> list[tuple[str, str, str]]:
    """Replay every scenario into a fresh store. Returns (scenario, lineage, verdict) rows."""
    if directory.exists():
        shutil.rmtree(directory)
    os.environ["GS_EMBEDDER"] = os.environ.get("GS_EMBEDDER", "auto")
    os.environ.pop("OPENAI_API_KEY", None)  # the demo store is reproducible without a key
    sentinel = Sentinel.open(Settings(store_path=str(directory)))
    rows: list[tuple[str, str, str]] = []
    try:
        runs = [(sc, sc.lineage or "strict") for sc in list_scenarios()]
        # Show the difference precise lineage makes on the poisoned email as well.
        runs += [(sc, "precise") for sc in list_scenarios() if sc.id == "01_poisoned_email"]
        for sc, lineage in runs:
            result = run_scenario(sentinel, sc, lineage=lineage)
            last = result.outcomes[-1].verdict.decision if result.outcomes else "-"
            rows.append((sc.id, result.lineage, last))
            if not result.ok:
                raise SystemExit(f"{sc.id} ({lineage}) did not give the expected verdicts")
        outbox.clear()
    finally:
        sentinel.close()
    (directory / ".gitkeep").unlink(missing_ok=True)
    return rows


def export_rl(directory: Path = DEMO_DIR, target: Path = DEMO_RL) -> bool:
    """Single-file copy via `relate clone`. Returns False when the CLI is missing."""
    cli = relate_cli()
    if cli is None:
        return False
    if target.exists():
        target.unlink() if target.is_file() else shutil.rmtree(target)
    subprocess.run([cli, "clone", str(directory), str(target)], check=True,
                   env={**os.environ, "RELATE_TELEMETRY": "off"})
    return True


def main() -> int:
    """Entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for scenario, lineage, decision in build():
        print(f"  {scenario:<26} {lineage:<8} last send: {decision}")
    print(f"Demo store written to {DEMO_DIR.relative_to(REPO_ROOT)}/")
    if export_rl():
        print(f"Single-file copy: {DEMO_RL.relative_to(REPO_ROOT)}")
    else:
        print("Relate CLI not found; skipped the .rl export (install it to create stores/demo.rl).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
