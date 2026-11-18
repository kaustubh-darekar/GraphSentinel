"""Sentinel: the store, policy, recorder and guard wired together."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from graphsentinel.core.config import Settings
from graphsentinel.core.guard import Guard
from graphsentinel.core.policy import Policy
from graphsentinel.core.recorder import Recorder
from graphsentinel.core.store import GraphStore

REPO_ROOT = Path(__file__).resolve().parents[2]


class Sentinel:
    """Everything a guarded agent needs. Create one per process with `Sentinel.open()`."""

    def __init__(self, store: GraphStore, policy: Policy, settings: Settings) -> None:
        self.store = store
        self.policy = policy
        self.settings = settings
        self.recorder = Recorder(store, policy, settings.trusted_destinations)
        self.guard = Guard(store)
        self.guard.warm_up()

    @classmethod
    def open(cls, settings: Settings | None = None, store_path: str | None = None) -> "Sentinel":
        """Open the store (directory mode, or ':memory:') and load the policy."""
        settings = settings or Settings.from_env()
        if store_path is not None:
            settings = replace(settings, store_path=store_path)
        policy_path = Path(settings.policy_path)
        if not policy_path.is_absolute() and not policy_path.exists():
            policy_path = REPO_ROOT / policy_path
        return cls(GraphStore(settings.store_path), Policy.load(policy_path), settings)

    def close(self) -> None:
        """Close the store (checkpoints a directory store)."""
        self.store.close()
