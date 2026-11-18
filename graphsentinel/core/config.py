"""Runtime settings read from environment variables (see `.env.example`).

`core` never loads `.env` itself; entry points (CLI, API) call `dotenv.load_dotenv()` first.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from typing import Literal

LineageMode = Literal["strict", "precise"]

DEFAULT_TRUSTED = ("*@acme.test", "#internal*")


def normalize_address(address: str) -> str:
    """Canonical form used to compare destinations: trimmed and lowercased."""
    return address.strip().lower()


def is_trusted(address: str, trusted: frozenset[str]) -> bool:
    """Whether `address` matches a trusted entry. Entries may use wildcards:
    `*@acme.test` (a whole domain), `#internal*` (channels by prefix)."""
    addr = normalize_address(address)
    return any(fnmatch.fnmatchcase(addr, pattern) for pattern in trusted)


@dataclass(frozen=True)
class Settings:
    """GraphSentinel settings. Build from env with `Settings.from_env()`."""

    store_path: str = "./stores/graphsentinel"
    lineage_mode: LineageMode = "strict"
    trusted_destinations: frozenset[str] = field(
        default_factory=lambda: frozenset(DEFAULT_TRUSTED)
    )
    policy_path: str = "policy.yaml"

    @classmethod
    def from_env(cls) -> "Settings":
        """Read GS_* variables, falling back to the defaults above."""
        raw = os.environ.get("GS_TRUSTED_DESTINATIONS")
        trusted = DEFAULT_TRUSTED if raw is None else raw.split(",")
        mode = os.environ.get("GS_LINEAGE_MODE", "strict").strip().lower()
        if mode not in ("strict", "precise"):
            raise ValueError(f"GS_LINEAGE_MODE must be strict or precise, got {mode!r}")
        return cls(
            store_path=os.environ.get("GS_STORE_PATH", cls.store_path),
            lineage_mode=mode,  # type: ignore[arg-type]
            trusted_destinations=frozenset(normalize_address(a) for a in trusted if a.strip()),
            policy_path=os.environ.get("GS_POLICY_PATH", cls.policy_path),
        )
