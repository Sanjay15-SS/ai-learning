"""Retrieval: top-K over a chunking strategy, with optional metadata filtering.

Week 3 ("dense"): embed the question, HNSW cosine search in Chroma, filter as a
DB-side `where` clause. Unchanged, still available as mode="dense".

Week 4 ("hybrid") - THE one retrieval change of Task Set D:
    dense top-25  +  BM25 top-25  ->  Reciprocal Rank Fusion (k=60)  ->  top-K
RRF fuses RANKS, never scores: a cosine of 0.78 and a BM25 score of 9.4 are not on
the same scale and never were. Each list votes 1/(k + rank) for every chunk it
holds; a chunk that both retrievers rank highly wins, and a chunk that only BM25
can find (an exclusion code, a form edition) is no longer invisible.

`search_explain()` is the data behind the inspection view: every candidate the
retriever considered, with the rank each stage gave it.
"""
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import CANDIDATES, RETRIEVAL_MODE, RRF_K, STRATEGIES, TOP_K, Chunk
from .bm25 import BM25Index
from .indexer import SearchHit, embed_query, get_registry, get_store

MODES = ("dense", "hybrid")


class Candidate:
    """One chunk in the inspection view, with the rank and score every stage gave it.

    `stages` maps a stage name ("dense", "bm25", "rrf") to (rank, score); a stage
    that never surfaced the chunk is absent. `final_rank`/`final_score` are the
    retriever's verdict - what the answer step actually sees.
    """
    __slots__ = ("chunk", "stages", "final_rank", "final_score")

    def __init__(self, chunk: Chunk):
        self.chunk = chunk
        self.stages: Dict[str, Tuple[int, float]] = {}
        self.final_rank: Optional[int] = None
        self.final_score: float = 0.0

    def rank_in(self, stage: str) -> Optional[int]:
        r = self.stages.get(stage)
        return r[0] if r else None


# --------------------------------------------------------------------------
# Stage 1a - dense (Week 3, unchanged)
# --------------------------------------------------------------------------

def _dense(question: str, strategy: str, n: int,
           filters: Optional[Dict[str, object]]) -> List[SearchHit]:
    return get_store(strategy).search(embed_query(question), top_k=n, filters=filters)


# --------------------------------------------------------------------------
# Stage 1b - BM25 (Week 4)
# --------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _bm25(strategy: str) -> BM25Index:
    return BM25Index(get_registry(strategy).chunks)


def _allowed_mask(strategy: str, filters: Optional[Dict[str, object]]) -> Optional[np.ndarray]:
    """The same metadata filter the DB applies to the dense list, applied to BM25."""
    if not filters:
        return None
    chunks = get_registry(strategy).chunks
    mask = np.ones(len(chunks), dtype=bool)
    for k, v in filters.items():
        wanted = set(v) if isinstance(v, (list, tuple, set)) else {v}
        mask &= np.array([c.metadata.get(k) in wanted for c in chunks])
    return mask


def _lexical(question: str, strategy: str, n: int,
             filters: Optional[Dict[str, object]]) -> List[Tuple[Chunk, float]]:
    reg = get_registry(strategy)
    return [(reg.chunks[i], s) for i, s in
            _bm25(strategy).search(question, top_k=n, allowed=_allowed_mask(strategy, filters))]


# --------------------------------------------------------------------------
# Stage 2 - Reciprocal Rank Fusion
# --------------------------------------------------------------------------

def _fuse(question: str, strategy: str, filters: Optional[Dict[str, object]],
          candidates: int, k: int = RRF_K) -> List[Candidate]:
    by_id: Dict[str, Candidate] = {}

    def cand(chunk: Chunk) -> Candidate:
        if chunk.chunk_id not in by_id:
            by_id[chunk.chunk_id] = Candidate(chunk)
        return by_id[chunk.chunk_id]

    for h in _dense(question, strategy, candidates, filters):
        cand(h.chunk).stages["dense"] = (h.rank, h.score)
    for rank, (chunk, score) in enumerate(_lexical(question, strategy, candidates, filters), 1):
        cand(chunk).stages["bm25"] = (rank, score)

    fused = []
    for c in by_id.values():
        rrf = sum(1.0 / (k + r) for r, _ in c.stages.values())
        fused.append((rrf, c))
    # Ties broken by dense rank so the order is deterministic.
    fused.sort(key=lambda t: (-t[0], t[1].rank_in("dense") or 10 ** 6))
    for i, (rrf, c) in enumerate(fused, 1):
        c.stages["rrf"] = (i, rrf)
        c.final_rank, c.final_score = i, rrf
    return [c for _, c in fused]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def search_explain(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
                   filters: Optional[Dict[str, object]] = None, mode: str = RETRIEVAL_MODE,
                   candidates: int = CANDIDATES) -> List[Candidate]:
    """The inspection view: every candidate the retriever considered, in final order."""
    if mode == "dense":
        out = []
        for h in _dense(question, strategy, candidates, filters):
            c = Candidate(h.chunk)
            c.stages["dense"] = (h.rank, h.score)
            c.final_rank, c.final_score = h.rank, h.score
            out.append(c)
        return out
    if mode == "hybrid":
        return _fuse(question, strategy, filters, candidates)
    raise ValueError(f"unknown retrieval mode '{mode}'; expected one of {MODES}")


def search(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
           filters: Optional[Dict[str, object]] = None,
           mode: str = RETRIEVAL_MODE) -> List[SearchHit]:
    if mode == "dense":
        return _dense(question, strategy, top_k, filters)
    if mode == "hybrid":
        return [SearchHit(c.final_score, c.chunk, c.final_rank,
                          cosine=(c.stages["dense"][1] if "dense" in c.stages else None))
                for c in _fuse(question, strategy, filters, CANDIDATES)[:top_k]]
    raise ValueError(f"unknown retrieval mode '{mode}'; expected one of {MODES}")


def get_chunk(chunk_id: str) -> Optional[Chunk]:
    """Resolve a citation's chunk_id back to the exact indexed chunk."""
    strategy = chunk_id.split("::", 1)[0]
    if strategy not in STRATEGIES:
        return None
    return get_store(strategy).get(chunk_id)
