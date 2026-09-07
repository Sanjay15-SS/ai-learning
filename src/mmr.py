"""Maximal Marginal Relevance over an already-fused candidate list - Week 4 bonus.

MMR is not a retriever. It reorders what the retriever already found, trading a
little relevance for less redundancy:

    score(c) = lambda * rel(c)  -  (1 - lambda) * max cos(c, already selected)

`lambda = 1.0` selects in plain retriever order, so it is the control the sweep is
measured against. Relevance is the fused rank turned into a 0-1 score, because an
RRF value and a cosine are not on the same scale; similarity between two chunks is
the cosine of their passage vectors, read from the ingest registry.

On this corpus the redundancy is three editions of the same clause, so diversity is
reported as distinct table rows and distinct editions in the top-3, not just cosine.
"""
from typing import Dict, List, Sequence

import numpy as np

from .indexer import get_registry


def _vectors(candidates: Sequence, strategy: str) -> np.ndarray:
    reg = get_registry(strategy)
    return np.stack([reg.vectors[reg.index_of[c.chunk.chunk_id]] for c in candidates])


def mmr_order(candidates: Sequence, strategy: str, lam: float = 0.7, k: int = 3) -> List:
    """The top-k of `candidates` reordered by MMR. lam=1.0 keeps the input order."""
    cands = list(candidates)
    if not cands:
        return []
    k = min(k, len(cands))
    if lam >= 1.0:
        return cands[:k]

    vecs = _vectors(cands, strategy)                       # already L2-normalised
    # Relevance from the fused rank: 1.0 for rank 1, decaying to 0 at the end of the list.
    rel = np.array([1.0 - i / len(cands) for i in range(len(cands))], dtype=np.float32)

    chosen: List[int] = [0]                                # rank 1 is always taken first
    while len(chosen) < k:
        sim_to_chosen = (vecs @ vecs[chosen].T).max(axis=1)
        score = lam * rel - (1.0 - lam) * sim_to_chosen
        score[chosen] = -np.inf
        chosen.append(int(np.argmax(score)))
    return [cands[i] for i in chosen]


def top3_diversity(top: Sequence, strategy: str) -> Dict[str, float]:
    """How redundant the selected top-3 actually is.

    mean_pairwise_cos   - lower is more diverse
    distinct_rows       - distinct (form, clause, exclusion code) rows out of 3
    distinct_editions   - distinct (form, edition) pairs out of 3
    """
    sel = list(top)
    if not sel:
        return {"mean_pairwise_cos": 0.0, "distinct_rows": 0, "distinct_editions": 0}

    vecs = _vectors(sel, strategy)
    sims = [float(vecs[i] @ vecs[j]) for i in range(len(sel)) for j in range(i + 1, len(sel))]

    rows, editions = set(), set()
    for c in sel:
        m = c.chunk.metadata
        codes = tuple(m.get("exclusion_codes") or ())
        rows.add((m.get("form_number"), m.get("clause"), codes))
        editions.add((m.get("form_number"), m.get("edition_date")))

    return {"mean_pairwise_cos": round(sum(sims) / len(sims), 4) if sims else 0.0,
            "distinct_rows": len(rows), "distinct_editions": len(editions)}
