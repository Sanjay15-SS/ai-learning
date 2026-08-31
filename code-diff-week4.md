# Code diff — the ONE retrieval change

Submission checklist item: *"Code diff showing exactly one retrieval change."*

The change is **`RETRIEVAL_MODE = "dense"` → `"hybrid"`** — dense top-25 + BM25 top-25,
fused with Reciprocal Rank Fusion at k=60. Everything else in the retrieval path is
untouched: same `structure_aware` chunker, same `BAAI/bge-small-en-v1.5` embeddings, same
Chroma HNSW index, same top-3, same 12 questions. No reranker was added in the same run —
results.md §5 has the evidence that ruled it out.

`before/` is the tree at the moment `baseline_record.json` was frozen at 9/12.

## The switch — `src/__init__.py`

```diff
@@ -7,7 +7,8 @@
 
 ROOT = Path(__file__).resolve().parent.parent
 DATA_DIR = ROOT / "data" / "endorsements"
-RESULTS_PATH = ROOT / "results.md"
+RESULTS_PATH = ROOT / "results.md"                 # Week 4 deliverable
+RESULTS_WEEK3_PATH = ROOT / "results-week3.md"    # Week 3 deliverable, still reproducible
 QUESTIONS_PATH = ROOT / "questions.json"          # Week 3 question set
 GOLDEN_SET_PATH = ROOT / "golden_set.jsonl"       # Week 4 golden set: 12 adjuster questions + gold chunk_id
 
@@ -15,7 +16,10 @@
 TOP_K = 5
 
 # Week 4: which retriever answers a query. "dense" is the Week 3 retriever, unchanged.
-RETRIEVAL_MODE = "dense"
+# "hybrid" is THE one retrieval change: dense top-25 + BM25 top-25 -> RRF (k=60).
+RETRIEVAL_MODE = "hybrid"
+CANDIDATES = 25    # depth of each list before fusion
+RRF_K = 60         # the standard RRF constant; not tuned
 
 # Strategy 1 - the Week 3 chunker, unchanged.
 CHUNK_CHARS = 900
```

## 1. BM25 — `src/bm25.py` (new file)

A bi-encoder maps `E-17` and `E-33` to nearly the same point, and `ed. 03-24` to nothing in
particular. BM25 treats them as exact tokens. The tokenizer keeps hyphenated identifiers
whole — `e-17`, `ho-0304`, `03-24` — instead of splitting them into `e`/`17` and losing the
code. Plain numpy, no new dependency. Cross-checked against an independently written
Lucene-idf implementation: agrees to 5e-05 on every golden-set query.

```diff
@@ -0,0 +1,64 @@
+"""BM25 over the indexed chunks - the lexical half of the Week 4 hybrid retriever.
+
+Why it exists: a bi-encoder maps "E-17" and "E-33" to nearly the same point, and
+"ed. 03-24" to nothing in particular. BM25 treats them as what they are - exact
+tokens that either occur in a chunk or do not. The tokenizer keeps hyphenated
+identifiers whole ("e-17", "ho-0304", "03-24") instead of splitting them into
+"e", "17", "ho", "0304" and losing the code.
+
+Plain numpy, no dependency; the 99-chunk index is a 99 x |vocab| matrix.
+"""
+import math
+import re
+from collections import Counter
+from typing import Dict, List, Optional, Sequence, Tuple
+
+import numpy as np
+
+from . import Chunk
+
+TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
+
+
+def tokenize(text: str) -> List[str]:
+    return TOKEN_RE.findall(text.lower())
+
+
+class BM25Index:
+    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75):
+        self.chunks = list(chunks)
+        self.k1, self.b = k1, b
+        docs = [tokenize(c.text) for c in self.chunks]
+        self.doc_len = np.array([len(d) for d in docs], dtype=np.float32)
+        self.avgdl = float(self.doc_len.mean()) if len(docs) else 0.0
+        self.vocab: Dict[str, int] = {}
+        for d in docs:
+            for t in d:
+                if t not in self.vocab:
+                    self.vocab[t] = len(self.vocab)
+        tf = np.zeros((len(docs), len(self.vocab)), dtype=np.float32)
+        for i, d in enumerate(docs):
+            for t, n in Counter(d).items():
+                tf[i, self.vocab[t]] = n
+        df = (tf > 0).sum(axis=0)
+        n_docs = len(docs)
+        # Lucene-style idf: ln(1 + (N - df + 0.5) / (df + 0.5)), never negative.
+        self.idf = np.log1p((n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
+        denom = tf + self.k1 * (1.0 - self.b + self.b * self.doc_len[:, None] / max(self.avgdl, 1e-9))
+        self.weights = (tf * (self.k1 + 1.0)) / np.where(denom == 0, 1.0, denom)   # per-term BM25 weight
+
+    def scores(self, query: str) -> np.ndarray:
+        ids = [self.vocab[t] for t in tokenize(query) if t in self.vocab]
+        if not ids:
+            return np.zeros(len(self.chunks), dtype=np.float32)
+        return (self.weights[:, ids] * self.idf[ids]).sum(axis=1)
+
+    def search(self, query: str, top_k: int = 25,
+               allowed: Optional[np.ndarray] = None) -> List[Tuple[int, float]]:
+        """(chunk index, bm25 score) for the top_k chunks with a non-zero score.
+        `allowed` is a boolean mask - the metadata filter, applied before ranking."""
+        s = self.scores(query)
+        if allowed is not None:
+            s = np.where(allowed, s, 0.0)
+        order = np.argsort(-s, kind="stable")[:top_k]
+        return [(int(i), float(s[i])) for i in order if s[i] > 0]
```

## 2. Fusion — `src/retriever.py`

RRF fuses **ranks**, never scores: a cosine of 0.69 and a BM25 score of 6.17 are not on the
same scale, so each list votes `1/(60 + rank)` and the votes are summed. The metadata filter
is applied to the BM25 side too (`_allowed_mask`), so `--policy-line HO-3` still means the
same thing in both halves of the hybrid.

```diff
@@ -1,26 +1,36 @@
 """Retrieval: top-K over a chunking strategy, with optional metadata filtering.
 
-Week 3: dense only - embed the question, HNSW cosine search in Chroma, filter as a
-DB-side `where` clause.
+Week 3 ("dense"): embed the question, HNSW cosine search in Chroma, filter as a
+DB-side `where` clause. Unchanged, still available as mode="dense".
 
-Week 4 adds `search_explain()`, the data behind the inspection view: for one
-question it returns the top-N candidates with the rank each retrieval stage gave
-them, so a miss can be labelled from evidence rather than from the answer text.
+Week 4 ("hybrid") - THE one retrieval change of Task Set D:
+    dense top-25  +  BM25 top-25  ->  Reciprocal Rank Fusion (k=60)  ->  top-K
+RRF fuses RANKS, never scores: a cosine of 0.78 and a BM25 score of 9.4 are not on
+the same scale and never were. Each list votes 1/(k + rank) for every chunk it
+holds; a chunk that both retrievers rank highly wins, and a chunk that only BM25
+can find (an exclusion code, a form edition) is no longer invisible.
+
+`search_explain()` is the data behind the inspection view: every candidate the
+retriever considered, with the rank each stage gave it.
 """
+from functools import lru_cache
 from typing import Dict, List, Optional, Tuple
 
-from . import RETRIEVAL_MODE, STRATEGIES, TOP_K, Chunk
-from .indexer import SearchHit, embed_query, get_store
+import numpy as np
 
-MODES = ("dense",)
+from . import CANDIDATES, RETRIEVAL_MODE, RRF_K, STRATEGIES, TOP_K, Chunk
+from .bm25 import BM25Index
+from .indexer import SearchHit, embed_query, get_registry, get_store
 
+MODES = ("dense", "hybrid")
 
+
 class Candidate:
     """One chunk in the inspection view, with the rank and score every stage gave it.
 
-    `stages` maps a stage name ("dense", ...) to (rank, score); a stage that never
-    surfaced the chunk is absent. `final_rank`/`final_score` are the retriever's
-    verdict - what the answer step actually sees.
+    `stages` maps a stage name ("dense", "bm25", "rrf") to (rank, score); a stage
+    that never surfaced the chunk is absent. `final_rank`/`final_score` are the
+    retriever's verdict - what the answer step actually sees.
     """
     __slots__ = ("chunk", "stages", "final_rank", "final_score")
 
@@ -35,24 +45,92 @@
         return r[0] if r else None
 
 
+# --------------------------------------------------------------------------
+# Stage 1a - dense (Week 3, unchanged)
+# --------------------------------------------------------------------------
+
 def _dense(question: str, strategy: str, n: int,
            filters: Optional[Dict[str, object]]) -> List[SearchHit]:
     return get_store(strategy).search(embed_query(question), top_k=n, filters=filters)
 
 
+# --------------------------------------------------------------------------
+# Stage 1b - BM25 (Week 4)
+# --------------------------------------------------------------------------
+
+@lru_cache(maxsize=4)
+def _bm25(strategy: str) -> BM25Index:
+    return BM25Index(get_registry(strategy).chunks)
+
+
+def _allowed_mask(strategy: str, filters: Optional[Dict[str, object]]) -> Optional[np.ndarray]:
+    """The same metadata filter the DB applies to the dense list, applied to BM25."""
+    if not filters:
+        return None
+    chunks = get_registry(strategy).chunks
+    mask = np.ones(len(chunks), dtype=bool)
+    for k, v in filters.items():
+        wanted = set(v) if isinstance(v, (list, tuple, set)) else {v}
+        mask &= np.array([c.metadata.get(k) in wanted for c in chunks])
+    return mask
+
+
+def _lexical(question: str, strategy: str, n: int,
+             filters: Optional[Dict[str, object]]) -> List[Tuple[Chunk, float]]:
+    reg = get_registry(strategy)
+    return [(reg.chunks[i], s) for i, s in
+            _bm25(strategy).search(question, top_k=n, allowed=_allowed_mask(strategy, filters))]
+
+
+# --------------------------------------------------------------------------
+# Stage 2 - Reciprocal Rank Fusion
+# --------------------------------------------------------------------------
+
+def _fuse(question: str, strategy: str, filters: Optional[Dict[str, object]],
+          candidates: int, k: int = RRF_K) -> List[Candidate]:
+    by_id: Dict[str, Candidate] = {}
+
+    def cand(chunk: Chunk) -> Candidate:
+        if chunk.chunk_id not in by_id:
+            by_id[chunk.chunk_id] = Candidate(chunk)
+        return by_id[chunk.chunk_id]
+
+    for h in _dense(question, strategy, candidates, filters):
+        cand(h.chunk).stages["dense"] = (h.rank, h.score)
+    for rank, (chunk, score) in enumerate(_lexical(question, strategy, candidates, filters), 1):
+        cand(chunk).stages["bm25"] = (rank, score)
+
+    fused = []
+    for c in by_id.values():
+        rrf = sum(1.0 / (k + r) for r, _ in c.stages.values())
+        fused.append((rrf, c))
+    # Ties broken by dense rank so the order is deterministic.
+    fused.sort(key=lambda t: (-t[0], t[1].rank_in("dense") or 10 ** 6))
+    for i, (rrf, c) in enumerate(fused, 1):
+        c.stages["rrf"] = (i, rrf)
+        c.final_rank, c.final_score = i, rrf
+    return [c for _, c in fused]
+
+
+# --------------------------------------------------------------------------
+# Public API
+# --------------------------------------------------------------------------
+
 def search_explain(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
                    filters: Optional[Dict[str, object]] = None, mode: str = RETRIEVAL_MODE,
-                   candidates: int = 25) -> List[Candidate]:
+                   candidates: int = CANDIDATES) -> List[Candidate]:
     """The inspection view: every candidate the retriever considered, in final order."""
-    if mode not in MODES:
-        raise ValueError(f"unknown retrieval mode '{mode}'; expected one of {MODES}")
-    out = []
-    for h in _dense(question, strategy, candidates, filters):
-        c = Candidate(h.chunk)
-        c.stages["dense"] = (h.rank, h.score)
-        c.final_rank, c.final_score = h.rank, h.score
-        out.append(c)
-    return out
+    if mode == "dense":
+        out = []
+        for h in _dense(question, strategy, candidates, filters):
+            c = Candidate(h.chunk)
+            c.stages["dense"] = (h.rank, h.score)
+            c.final_rank, c.final_score = h.rank, h.score
+            out.append(c)
+        return out
+    if mode == "hybrid":
+        return _fuse(question, strategy, filters, candidates)
+    raise ValueError(f"unknown retrieval mode '{mode}'; expected one of {MODES}")
 
 
 def search(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
@@ -60,6 +138,10 @@
            mode: str = RETRIEVAL_MODE) -> List[SearchHit]:
     if mode == "dense":
         return _dense(question, strategy, top_k, filters)
+    if mode == "hybrid":
+        return [SearchHit(c.final_score, c.chunk, c.final_rank,
+                          cosine=(c.stages["dense"][1] if "dense" in c.stages else None))
+                for c in _fuse(question, strategy, filters, CANDIDATES)[:top_k]]
     raise ValueError(f"unknown retrieval mode '{mode}'; expected one of {MODES}")
 
 
```

## 3. The one gate that had to follow — `src/generator.py`, `SearchHit`

`SCORE_FLOOR` is a **cosine** floor (0.35). Under fusion `hit.score` becomes an RRF score of
about 0.03, which would trip that floor on every query and refuse everything. `SearchHit` now
carries `cosine` alongside `score`, and the gate reads the cosine. This is not a second
retrieval change — it keeps the refusal gate measuring the same quantity it measured before,
which is what makes the two runs comparable at all.

```diff
@@ -111,13 +111,14 @@
             f"indexed endorsements (floor {COVERAGE_FLOOR:.0%}). Absent entirely: "
             f"{', '.join(missing)}. Refused without composing an answer.")
 
-    # Gate 2 - backstop: nothing retrieved is even topically close.
-    if not hits or hits[0].score < SCORE_FLOOR:
-        top = hits[0].score if hits else 0.0
+    # Gate 2 - backstop: nothing retrieved is even topically close. The floor is a
+    # cosine, so it reads the cosine - an RRF score (~0.03) is on another scale.
+    best_cos = max((h.cosine for h in hits if h.cosine is not None), default=0.0)
+    if not hits or best_cos < SCORE_FLOOR:
         return _refusal(
             question, strategy, hits, "score_floor",
-            f"No indexed chunk scored above the {SCORE_FLOOR} retrieval floor "
-            f"(best was {top:.4f}).")
+            f"No indexed chunk scored above the {SCORE_FLOOR} cosine floor "
+            f"(best was {best_cos:.4f}).")
 
     # Grounded answer, quoted verbatim from the top chunk.
     top = hits[0]
@@ -169,10 +169,14 @@
 
 
 class SearchHit:
-    __slots__ = ("score", "chunk", "rank")
-
-    def __init__(self, score: float, chunk: Chunk, rank: int):
+    """`score` is whatever the retriever ranked by (cosine for dense, RRF for hybrid);
+    `cosine` is always the dense similarity when the chunk has one, so a gate that
+    means "is anything topically close?" can keep reading a cosine."""
+    __slots__ = ("score", "chunk", "rank", "cosine")
+
+    def __init__(self, score: float, chunk: Chunk, rank: int, cosine: Optional[float] = None):
         self.score, self.chunk, self.rank = score, chunk, rank
+        self.cosine = score if cosine is None else cosine
 
     def to_dict(self) -> dict:
         m = self.chunk.metadata
```
