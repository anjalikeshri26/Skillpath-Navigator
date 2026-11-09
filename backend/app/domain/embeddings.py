"""Lightweight lexical retrieval (TF-IDF over unigrams + bigrams, cosine similarity).

This is deliberately *not* a neural embedding model. It needs no downloads and no paid API, and it is
good enough to rank a small, curated catalogue and to catch near-duplicate quiz questions. The public
surface (`TfidfIndex.search`, `TfidfIndex.nearest`) is small so it can be replaced by a sentence-embedding
model plus pgvector later without touching callers.
"""
import math
from collections import Counter

from .text import features


def _l2_normalise(vec: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    return {k: v / norm for k, v in vec.items()} if norm else {}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class TfidfIndex:
    def __init__(self, documents: dict[str, str]):
        self._doc_features = {doc_id: features(text) for doc_id, text in documents.items()}
        n = len(self._doc_features)
        df: Counter = Counter()
        for feats in self._doc_features.values():
            df.update(set(feats))
        self._idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}
        # Terms never seen in the corpus are treated as rare, which keeps unknown query words informative.
        self._default_idf = math.log(1 + n) + 1.0
        self._vectors = {doc_id: self._vectorise_features(f) for doc_id, f in self._doc_features.items()}

    def _vectorise_features(self, feats: list[str]) -> dict[str, float]:
        counts = Counter(feats)
        vec = {t: (1.0 + math.log(c)) * self._idf.get(t, self._default_idf) for t, c in counts.items()}
        return _l2_normalise(vec)

    def vectorise(self, text: str) -> dict[str, float]:
        return self._vectorise_features(features(text))

    def search(self, query: str, k: int = 5, *, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        q = self.vectorise(query)
        scored = [
            (doc_id, cosine(q, vec))
            for doc_id, vec in self._vectors.items()
            if allowed is None or doc_id in allowed
        ]
        scored = [(d, s) for d, s in scored if s > 0]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    def nearest(self, text: str) -> tuple[str, float] | None:
        hits = self.search(text, k=1)
        return hits[0] if hits else None
