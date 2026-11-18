"""Text fingerprints for content matching (precise lineage mode).

A fingerprint is the set of stable 32-bit hashes of every 8-word shingle in the
normalised text. Two texts share data when their fingerprints overlap.
"""

from __future__ import annotations

import hashlib
import re

SHINGLE_WORDS = 8
_NON_WORD = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize(text: str) -> list[str]:
    """Lowercase, replace punctuation with spaces, and split into words."""
    return _NON_WORD.sub(" ", text.lower()).split()


def shingles(text: str, k: int = SHINGLE_WORDS) -> list[str]:
    """All k-word windows of the text. Texts shorter than k words give one shingle."""
    words = normalize(text)
    if not words:
        return []
    if len(words) < k:
        return [" ".join(words)]
    return [" ".join(words[i : i + k]) for i in range(len(words) - k + 1)]


def stable_hash(s: str) -> int:
    """32-bit hash that is identical across processes and platforms (unlike `hash()`)."""
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=4).digest(), "big")


def fingerprint(text: str, k: int = SHINGLE_WORDS) -> list[int]:
    """Sorted, de-duplicated shingle hashes of `text`."""
    return sorted({stable_hash(s) for s in shingles(text, k)})


def overlap(a: list[int], b: list[int]) -> set[int]:
    """Hashes present in both fingerprints."""
    return set(a) & set(b)
