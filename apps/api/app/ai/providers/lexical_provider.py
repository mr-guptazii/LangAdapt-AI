"""A real (not random) embedding provider with no API key or heavy ML
dependency required — a signed hashing-trick bag-of-words vector, the same
family of technique as scikit-learn's HashingVectorizer.

This exists because MockEmbeddingProvider (mock_provider.py) seeds a random
vector from a hash of the whole text: two near-identical sentences get
unrelated vectors, so cosine-similarity memory retrieval was pure noise
regardless of environment, including production (no code path ever branched
away from it). This provider instead hashes each TOKEN to a dimension and
accumulates a signed count, so texts sharing vocabulary land closer together
under cosine similarity — genuinely content-sensitive, unlike the mock.

It is deliberately NOT presented as a deep semantic embedding: it has no
notion of synonyms or paraphrase (e.g. "car" and "automobile" won't be
recognized as related). That would require a real embedding model API (none
configured) or a local neural model (too heavy for this app's memory-
constrained deployment, which has already hit OOM issues from a much lighter
dependency). Word-overlap similarity is a real, legitimate, well-documented
lower bound on semantic embedding — an honest middle ground between random
noise and a full neural embedding, not a fabrication.
"""
import hashlib
import re

import numpy as np

from app.ai.providers.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingLexicalEmbeddingProvider(EmbeddingProvider):
    name = "hashing_lexical"

    def __init__(self, dim: int = 384):
        self.dim = dim

    async def embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float64)
        tokens = _TOKEN_RE.findall(text.lower())
        for tok in tokens:
            digest = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
            idx = digest % self.dim
            # Signed hashing (feature-hashing trick): the sign bit is derived
            # from a different part of the same hash, so collisions between two
            # different tokens landing on the same dimension partially cancel
            # instead of always constructively adding — reduces systematic bias
            # from hash collisions at this dimensionality.
            sign = 1.0 if (digest // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            # Empty or punctuation-only text — return a valid zero vector
            # rather than raising; callers treat "no embedding signal" as
            # legitimately dissimilar to everything, which is correct here.
            return [0.0] * self.dim
        return (vec / norm).tolist()
