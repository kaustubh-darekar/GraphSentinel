"""Choosing an embedder, and the OpenAI one (kept out of core)."""

from __future__ import annotations

import os
from typing import Any

from graphsentinel.core.embedding import CachedEmbedder, Embedder, LocalEmbedder, clip

DEFAULT_DIMS = 256


class OpenAIEmbedder:
    """OpenAI embeddings (model from OPENAI_EMBED_MODEL), shortened to `dims` when supported."""

    def __init__(self, model: str, dims: int = DEFAULT_DIMS, threshold: float | None = None) -> None:
        from openai import OpenAI  # lazy: scripted mode never needs it

        self.client = OpenAI()
        self.model = model
        self.dims = dims
        self.threshold = threshold if threshold is not None else _env_threshold(0.85)
        self.name = f"openai:{model}:{dims}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        if not texts:
            return []
        kwargs: dict[str, Any] = {"model": self.model, "input": [clip(t) for t in texts]}
        if self.model.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.dims
        resp = self.client.embeddings.create(**kwargs)
        vecs = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        self.dims = len(vecs[0])
        return vecs


def _env_threshold(default: float) -> float:
    raw = os.environ.get("GS_SIMILARITY_THRESHOLD")
    return float(raw) if raw else default


def openai_embedder_available() -> bool:
    """True when OPENAI_API_KEY and OPENAI_EMBED_MODEL are set."""
    return bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_EMBED_MODEL"))


def local_embedder() -> LocalEmbedder:
    """The keyless embedder (threshold overridable with GS_LOCAL_SIMILARITY_THRESHOLD)."""
    raw = os.environ.get("GS_LOCAL_SIMILARITY_THRESHOLD")
    return LocalEmbedder(threshold=float(raw) if raw else 0.70)


def live_embedder() -> Embedder | None:
    """Embedder for live sessions. GS_EMBEDDER = auto (default) | openai | local | off."""
    choice = os.environ.get("GS_EMBEDDER", "auto").strip().lower()
    if choice == "off":
        return None
    if choice in ("auto", "openai") and openai_embedder_available():
        return OpenAIEmbedder(os.environ["OPENAI_EMBED_MODEL"])
    if choice == "openai":
        raise RuntimeError("GS_EMBEDDER=openai needs OPENAI_API_KEY and OPENAI_EMBED_MODEL")
    return local_embedder()


def scripted_embedder(cache: dict[str, Any] | None) -> Embedder | None:
    """Embedder for scenario replays: the scenario's stored vectors if it has them, else local."""
    if os.environ.get("GS_EMBEDDER", "auto").strip().lower() == "off":
        return None
    if not cache:
        return local_embedder()
    return CachedEmbedder(
        name=f"cached:{cache['model']}:{cache['dims']}",
        dims=int(cache["dims"]),
        threshold=_env_threshold(float(cache.get("threshold", 0.85))),
        vectors={k: [float(x) for x in v] for k, v in cache["vectors"].items()},
    )
