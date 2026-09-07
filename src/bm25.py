"""BM25 over the indexed chunks - the lexical half of the Week 4 hybrid retriever.

Why it exists: a bi-encoder maps "E-17" and "E-33" to nearly the same point, and
"ed. 03-24" to nothing in particular. BM25 treats them as what they are - exact
tokens that either occur in a chunk or do not. The tokenizer keeps hyphenated
identifiers whole ("e-17", "ho-0304", "03-24") instead of splitting them into
"e", "17", "ho", "0304" and losing the code.

Plain numpy, no dependency; the 99-chunk index is a 99 x |vocab| matrix.
"""
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import Chunk

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1, self.b = k1, b
        docs = [tokenize(c.text) for c in self.chunks]
        self.doc_len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if len(docs) else 0.0
        self.vocab: Dict[str, int] = {}
        for d in docs:
            for t in d:
                if t not in self.vocab:
                    self.vocab[t] = len(self.vocab)
        tf = np.zeros((len(docs), len(self.vocab)), dtype=np.float32)
        for i, d in enumerate(docs):
            for t, n in Counter(d).items():
                tf[i, self.vocab[t]] = n
        df = (tf > 0).sum(axis=0)
        n_docs = len(docs)
        # Lucene-style idf: ln(1 + (N - df + 0.5) / (df + 0.5)), never negative.
        self.idf = np.log1p((n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
        denom = tf + self.k1 * (1.0 - self.b + self.b * self.doc_len[:, None] / max(self.avgdl, 1e-9))
        self.weights = (tf * (self.k1 + 1.0)) / np.where(denom == 0, 1.0, denom)   # per-term BM25 weight

    def scores(self, query: str) -> np.ndarray:
        ids = [self.vocab[t] for t in tokenize(query) if t in self.vocab]
        if not ids:
            return np.zeros(len(self.chunks), dtype=np.float32)
        return (self.weights[:, ids] * self.idf[ids]).sum(axis=1)

    def search(self, query: str, top_k: int = 25,
               allowed: Optional[np.ndarray] = None) -> List[Tuple[int, float]]:
        """(chunk index, bm25 score) for the top_k chunks with a non-zero score.
        `allowed` is a boolean mask - the metadata filter, applied before ranking."""
        s = self.scores(query)
        if allowed is not None:
            s = np.where(allowed, s, 0.0)
        order = np.argsort(-s, kind="stable")[:top_k]
        return [(int(i), float(s[i])) for i in order if s[i] > 0]
