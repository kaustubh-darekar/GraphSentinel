"""Embeddings for paraphrase detection (vector search on the same graph).

An Embedder turns texts into vectors. Scores from Relate's vector index are
(1 + cosine) / 2, so a threshold of 0.85 means cosine >= 0.70.

- LocalEmbedder: deterministic, dependency-free lexical embedder (hashed words and
  word pairs). Needs no key; catches rewordings that keep names and numbers.
- CachedEmbedder: vectors pre-computed into a scenario file (e.g. by OpenAI), so
  scripted mode can replay real embeddings with no key.
- The OpenAI embedder lives in `graphsentinel.agent.embedders` (core has no LLM imports).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from graphsentinel.core.fingerprint import normalize

MAX_EMBED_CHARS = 8000

_STOPWORDS = frozenset("""
a an and are as at be but by for from has have he her his i if in into is it its of on or
our out she so that the their them they this to was we were will with you your who what
which also just than then there these those per plus about over very can may must
""".split())


class Embedder(Protocol):
    """Anything that embeds texts. `threshold` is the minimum index score for a match."""

    name: str
    dims: int
    threshold: float

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text."""
        ...


def text_key(text: str) -> str:
    """Stable key for a text (used by the scenario embedding cache)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def clip(text: str) -> str:
    """The part of a text that gets embedded."""
    return text[:MAX_EMBED_CHARS]


def chunks(text: str, min_words: int = 5) -> list[str]:
    """Paragraphs worth searching for, plus the whole text when it has several."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.split()) >= min_words]
    whole = text.strip()
    out = paras if len(paras) > 1 else []
    if len(whole.split()) >= min_words:
        out.append(whole)
    return list(dict.fromkeys(out))


class LocalEmbedder:
    """Signed feature hashing over content words and word pairs, L2-normalised."""

    def __init__(self, dims: int = 256, threshold: float = 0.70) -> None:
        self.dims = dims
        self.threshold = threshold
        self.name = f"local-hash-{dims}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text."""
        return [self._one(clip(t)) for t in texts]

    def _one(self, text: str) -> list[float]:
        words = [w for w in normalize(text) if w not in _STOPWORDS]
        vec = [0.0] * self.dims
        feats = [(w, 1.0) for w in words] + [(f"{a}_{b}", 0.5) for a, b in zip(words, words[1:])]
        for feat, weight in feats:
            h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "big")
            vec[h % self.dims] += weight if (h >> 63) & 1 else -weight
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class CachedEmbedder:
    """Looks vectors up by text; falls back to another embedder (or fails) on a miss."""

    def __init__(self, name: str, dims: int, threshold: float, vectors: dict[str, list[float]],
                 fallback: Embedder | None = None) -> None:
        self.name = name
        self.dims = dims
        self.threshold = threshold
        self.vectors = vectors
        self.fallback = fallback

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Cached vectors; misses go to the fallback in one batch."""
        out: list[list[float] | None] = [self.vectors.get(text_key(clip(t))) for t in texts]
        missing = [i for i, v in enumerate(out) if v is None]
        if missing:
            if self.fallback is None:
                raise KeyError(f"{len(missing)} text(s) are not in the {self.name} embedding cache; "
                               "regenerate it with `python -m graphsentinel.agent.embed_scenario`")
            for i, v in zip(missing, self.fallback.embed([texts[i] for i in missing])):
                out[i] = v
        return [v for v in out if v is not None]
