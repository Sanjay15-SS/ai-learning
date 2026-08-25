# Code diff — the second chunker and the metadata fields

Submission checklist item: *"Code diff showing the second chunker and the metadata fields."*

```
c06efe3 Task Set D: structure-aware chunker, form metadata on every chunk, policy_line filtering, extractive answering with a forced refusal, 8-question evaluation pipeline
d6a7e04 Week 3 claims-assistant RAG: naive fixed-window chunker, Chroma index, source_file metadata
```

`d6a7e04` is the Week 3 claims-assistant app before this task: one naive fixed-window
chunker, one Chroma collection, `source_file` as the only chunk metadata. Below is
`git diff d6a7e04 c06efe3`.

## Summary

```
 app.py           |  67 +++++++
 questions.json   | 102 +++++++++++
 requirements.txt |   8 +-
 run_pipeline.py  | 536 +++++++++++++++++++++++++++++++++++++++++++++++++++++++
 src/__init__.py  |  36 +++-
 src/chunkers.py  | 171 +++++++++++++++++-
 src/generator.py | 141 +++++++++++++++
 src/indexer.py   | 210 +++++++++++++++++++---
 src/retriever.py |  21 ++-
 9 files changed, 1244 insertions(+), 48 deletions(-)
```

## 1. The metadata fields — `src/indexer.py`, `src/__init__.py`

`Document` gains `form_number`, `edition_date`, `policy_line` and `effective_date`.
`load_document()` parses them from front matter with a regex fallback for PDF and plain
text, and `_validate()` refuses to ingest a document missing any of them — a chunk with
no source_file is a failed ingest, caught at the document. `VectorStore.add()` re-checks
it before anything reaches the index.

```diff
diff --git a/src/__init__.py b/src/__init__.py
index 5779f6b..e62262e 100644
--- a/src/__init__.py
+++ b/src/__init__.py
@@ -1,21 +1,51 @@
-"""Claims-assistant RAG."""
-from dataclasses import dataclass, field
+"""Insurance-claims RAG — Week 3 Practical, Task Set D.
+
+Package-level configuration and the two data records every module shares.
+"""
+from dataclasses import asdict, dataclass, field
 from pathlib import Path
 
 ROOT = Path(__file__).resolve().parent.parent
 DATA_DIR = ROOT / "data" / "endorsements"
+RESULTS_PATH = ROOT / "results.md"
+QUESTIONS_PATH = ROOT / "questions.json"
 
-EMBED_MODEL = "BAAI/bge-small-en-v1.5"
+EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # MTEB-ranked bi-encoder, 384-dim
 TOP_K = 5
+
+# Strategy 1 - the Week 3 chunker, unchanged.
 CHUNK_CHARS = 900
 OVERLAP_CHARS = 150
 
+# Strategy 2 - structure-aware: cap on a prose chunk before it splits on paragraphs.
+STRUCTURE_MAX_CHARS = 1200
+
+STRATEGIES = ("baseline", "structure_aware")
+STRATEGY_LABELS = {
+    "baseline": "Naive Chunker",
+    "structure_aware": "Structure-Aware Chunker",
+}
+
+# Refusal gates. See results.md section 5.1 for the measurement behind both.
+COVERAGE_FLOOR = 0.55   # fraction of question terms that must appear in the corpus
+SCORE_FLOOR = 0.35      # backstop for a query with no topical neighbour
+
 
 @dataclass
 class Document:
     source_file: str
+    form_number: str
+    edition_date: str
+    policy_line: str
+    effective_date: str
+    title: str
     text: str
 
+    def meta(self) -> dict:
+        d = asdict(self)
+        d.pop("text")
+        return d
+
 
 @dataclass
 class Chunk:
diff --git a/src/indexer.py b/src/indexer.py
index 3b04b0e..a6d4077 100644
--- a/src/indexer.py
+++ b/src/indexer.py
@@ -1,23 +1,99 @@
-"""Ingestion: read documents, chunk, embed, index into Chroma."""
+"""Ingestion: read the endorsements, chunk them, embed them, index them.
+
+Requirement 1: every chunk carries source_file, form_number, policy_line and
+edition_date. Metadata originates in load_document(); the chunkers propagate it.
+
+Requirement 6: only the 6 new endorsements are indexed. The base policy wording
+library is not re-indexed and is never read by this pipeline.
+
+The vector database is Chroma, running in-process with an hnswlib HNSW index in
+cosine space. Nothing is written to disk: the index is built fresh each run.
+Metadata filtering is done by the database via `where` clauses, not by us in
+Python afterwards.
+"""
+import re
 from functools import lru_cache
 from pathlib import Path
-from typing import List, Optional, Sequence
+from typing import Dict, List, Optional, Sequence
 
 import numpy as np
 
-from . import CHUNK_CHARS, Chunk, DATA_DIR, Document, EMBED_MODEL, OVERLAP_CHARS
-from .chunkers import chunk_document
+from . import (CHUNK_CHARS, Chunk, DATA_DIR, Document, EMBED_MODEL, OVERLAP_CHARS,
+               STRATEGIES, STRUCTURE_MAX_CHARS)
+from .chunkers import baseline_chunks, structure_aware_chunks
 
+# --------------------------------------------------------------------------
+# Loading + form metadata
+# --------------------------------------------------------------------------
 
-def load_document(path: Path) -> Document:
-    if path.suffix.lower() == ".pdf":
+FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
+FORM_RE = re.compile(r"\b([A-Z]{2}-\d{4})\b\s*\(\s*ed\.?\s*(\d{2}-\d{2})\s*\)", re.I)
+LINE_RE = re.compile(r"Policy\s+Line:\s*([A-Z]{2}-\d)", re.I)
+EFF_RE = re.compile(r"Effective:\s*([A-Za-z0-9 ,\-/]+)")
+
+
+def _parse_front_matter(raw: str) -> dict:
+    m = FRONT_MATTER_RE.match(raw)
+    if not m:
+        return {}
+    out = {}
+    for line in m.group(1).splitlines():
+        if ":" in line:
+            k, v = line.split(":", 1)
+            out[k.strip()] = v.strip().strip('"').strip("'")
+    return out
+
+
+def _read_pdf(path: Path) -> str:
+    try:
         from pypdf import PdfReader
+    except ImportError as exc:                       # pypdf is optional
+        raise RuntimeError(
+            f"{path.name} is a PDF but pypdf is not installed. Run: pip install pypdf") from exc
+
+    reader = PdfReader(str(path))
+    return "\n".join((page.extract_text() or "") for page in reader.pages)
 
-        reader = PdfReader(str(path))
-        raw = "\n".join((page.extract_text() or "") for page in reader.pages)
+
+def _validate(doc: Document) -> None:
+    """A chunk with no source_file is a failed ingest - catch it at the document."""
+    missing = [f for f in ("source_file", "form_number", "policy_line", "edition_date")
+               if not getattr(doc, f)]
+    if missing:
+        raise ValueError(f"{doc.source_file or '<unknown file>'}: missing metadata {missing}")
+
+
+def load_document(path: Path) -> Document:
+    if path.suffix.lower() == ".pdf":
+        raw, fm = _read_pdf(path), {}
     else:
         raw = path.read_text(encoding="utf-8")
-    return Document(source_file=path.name, text=raw.strip())
+        fm = _parse_front_matter(raw)
+        raw = FRONT_MATTER_RE.sub("", raw, count=1)
+
+    form, edition = fm.get("form_number"), fm.get("edition_date")
+    if not form or not edition:
+        m = FORM_RE.search(raw)
+        form = form or (m.group(1).upper() if m else None)
+        edition = edition or (m.group(2) if m else None)
+
+    line = fm.get("policy_line")
+    if not line:
+        m = LINE_RE.search(raw)
+        line = m.group(1).upper() if m else None
+
+    effective = fm.get("effective_date")
+    if not effective:
+        m = EFF_RE.search(raw)
+        effective = m.group(1).strip() if m else ""
+
+    title = fm.get("title") or (raw.strip().splitlines() or [""])[0].lstrip("# ").strip()
+
+    doc = Document(source_file=path.name, form_number=form or "", edition_date=edition or "",
+                   policy_line=line or "", effective_date=effective or "",
+                   title=title, text=raw.strip())
+    _validate(doc)
+    return doc
 
 
 def load_documents(data_dir: Path = DATA_DIR) -> List[Document]:
@@ -28,6 +104,12 @@ def load_documents(data_dir: Path = DATA_DIR) -> List[Document]:
     return [load_document(p) for p in paths]
 
 
+# --------------------------------------------------------------------------
+# Embeddings - ONE model across both strategies
+# --------------------------------------------------------------------------
+# Changing the chunker and the embedding model in the same run would teach you
+# nothing about which one moved the number, so this is fixed for every run.
+
 @lru_cache(maxsize=1)
 def _embedder():
     from fastembed import TextEmbedding
@@ -46,13 +128,20 @@ def embed_passages(texts: List[str]) -> np.ndarray:
 
 
 def embed_query(text: str) -> np.ndarray:
+    """BGE applies its retrieval instruction prefix to queries here."""
     return _normalize(np.asarray(list(_embedder().query_embed([text])), dtype=np.float32))[0]
 
 
+# --------------------------------------------------------------------------
+# Vector database - Chroma, in-memory, HNSW
+# --------------------------------------------------------------------------
+
 _CLIENT = None
+_LIST_KEYS = ("exclusion_codes",)   # Chroma metadata must be scalars; these round-trip as lists
 
 
 def _shared_client():
+    """One in-memory Chroma instance per process, shared by both collections."""
     global _CLIENT
     if _CLIENT is None:
         import chromadb
@@ -61,6 +150,24 @@ def _shared_client():
     return _CLIENT
 
 
+def _flatten(meta: dict) -> dict:
+    out = {}
+    for k, v in meta.items():
+        if v is None:
+            continue
+        out[k] = ",".join(str(x) for x in v) if isinstance(v, (list, tuple)) else (
+            v if isinstance(v, (str, int, float, bool)) else str(v))
+    return out
+
+
+def _restore(meta: dict) -> dict:
+    out = dict(meta)
+    for k in _LIST_KEYS:
+        raw = out.get(k)
+        out[k] = [p for p in raw.split(",") if p] if isinstance(raw, str) else (raw or [])
+    return out
+
+
 class SearchHit:
     __slots__ = ("score", "chunk", "rank")
 
@@ -68,13 +175,17 @@ class SearchHit:
         self.score, self.chunk, self.rank = score, chunk, rank
 
     def to_dict(self) -> dict:
+        m = self.chunk.metadata
         return {"rank": self.rank, "score": round(self.score, 4),
-                "chunk_id": self.chunk.chunk_id,
-                "source_file": self.chunk.metadata.get("source_file"),
-                "text": self.chunk.text}
+                "chunk_id": self.chunk.chunk_id, "form_number": m.get("form_number"),
+                "policy_line": m.get("policy_line"), "edition_date": m.get("edition_date"),
+                "clause": m.get("clause"), "source_file": m.get("source_file"),
+                "exclusion_codes": m.get("exclusion_codes", []), "text": self.chunk.text}
 
 
 class VectorStore:
+    """One Chroma collection per chunking strategy."""
+
     def __init__(self, name: str):
         self.name = name
         self._collection = None
@@ -91,53 +202,96 @@ class VectorStore:
             self._collection = client.create_collection(
                 name=self.name, metadata={"hnsw:space": "cosine"})
         else:
-            self._collection = client.get_collection(self.name)
+            try:
+                self._collection = client.get_collection(self.name)
+            except Exception as exc:
+                raise FileNotFoundError(
+                    f"collection '{self.name}' not built in this process - the index is "
+                    f"in-memory, so ingest() must run first") from exc
         return self._collection
 
     def add(self, chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
+        if len(chunks) != vectors.shape[0]:
+            raise ValueError("chunk/vector count mismatch")
+        missing = [c.chunk_id for c in chunks if not c.metadata.get("source_file")]
+        if missing:
+            raise ValueError(f"failed ingest - chunks with no source_file: {missing[:5]}")
         self._get(create=True).add(
             ids=[c.chunk_id for c in chunks],
             embeddings=[v.tolist() for v in vectors],
             documents=[c.text for c in chunks],
-            metadatas=[dict(c.metadata) for c in chunks])
+            metadatas=[_flatten(c.metadata) for c in chunks])
 
     def get(self, chunk_id: str) -> Optional[Chunk]:
         res = self._get().get(ids=[chunk_id], include=["documents", "metadatas"])
         if not res["ids"]:
             return None
-        return Chunk(res["ids"][0], res["documents"][0], dict(res["metadatas"][0]))
+        return Chunk(res["ids"][0], res["documents"][0], _restore(res["metadatas"][0]))
 
-    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[SearchHit]:
+    @staticmethod
+    def _where(filters: Optional[Dict[str, object]]):
+        """Translate a plain dict into a Chroma `where` clause."""
+        if not filters:
+            return None
+        clauses = [{k: {"$in": list(v)}} if isinstance(v, (list, tuple, set)) else {k: {"$eq": v}}
+                   for k, v in filters.items()]
+        return clauses[0] if len(clauses) == 1 else {"$and": clauses}
+
+    def search(self, query_vec: np.ndarray, top_k: int = 5,
+               filters: Optional[Dict[str, object]] = None) -> List[SearchHit]:
         coll = self._get()
         res = coll.query(query_embeddings=[query_vec.tolist()],
                          n_results=min(top_k, max(1, coll.count())),
+                         where=self._where(filters),        # filtering happens in the DB
                          include=["documents", "metadatas", "distances"])
         if not res["ids"] or not res["ids"][0]:
             return []
-        return [SearchHit(1.0 - float(d), Chunk(i, doc, dict(m)), rank)
+        return [SearchHit(1.0 - float(d), Chunk(i, doc, _restore(m)), rank)
                 for rank, (i, doc, m, d) in enumerate(
                     zip(res["ids"][0], res["documents"][0],
                         res["metadatas"][0], res["distances"][0]), start=1)]
 
     def __len__(self) -> int:
-        return self._get().count()
-
+        try:
+            return self._get().count()
+        except FileNotFoundError:
+            return 0
 
-INDEX_NAME = "policy"
 
+# --------------------------------------------------------------------------
+# Ingest
+# --------------------------------------------------------------------------
 
-@lru_cache(maxsize=2)
-def get_store() -> VectorStore:
-    return VectorStore(INDEX_NAME)
+@lru_cache(maxsize=4)
+def get_store(strategy: str) -> VectorStore:
+    if strategy not in STRATEGIES:
+        raise ValueError(f"unknown strategy '{strategy}'; expected one of {STRATEGIES}")
+    return VectorStore(strategy)
 
 
-def ingest(data_dir: Path = DATA_DIR, verbose: bool = True) -> dict:
+def ingest(strategy: str, data_dir: Path = DATA_DIR, verbose: bool = True) -> dict:
+    """Chunk, embed and index the endorsement drop under one chunking strategy."""
     docs = load_documents(data_dir)
+
     chunks: List[Chunk] = []
     for doc in docs:
-        chunks += chunk_document(doc, CHUNK_CHARS, OVERLAP_CHARS)
-    VectorStore(INDEX_NAME).add(chunks, embed_passages([c.text for c in chunks]))
+        if strategy == "baseline":
+            chunks += baseline_chunks(doc, CHUNK_CHARS, OVERLAP_CHARS)
+        else:
+            chunks += structure_aware_chunks(doc, STRUCTURE_MAX_CHARS)
+
+    store = VectorStore(strategy)
+    store.add(chunks, embed_passages([c.text for c in chunks]))
     get_store.cache_clear()
+
+    per_form: Dict[str, int] = {}
+    for c in chunks:
+        per_form[c.metadata["form_number"]] = per_form.get(c.metadata["form_number"], 0) + 1
+
     if verbose:
-        print(f"Ingested {len(chunks)} chunks from {len(docs)} files.")
-    return {"chunks": len(chunks), "documents": len(docs)}
+        rel = data_dir.relative_to(data_dir.parent.parent) if data_dir.is_absolute() else data_dir
+        print(f"Ingested {len(chunks)} chunks from {len(docs)} files in {rel}. "
+              f"Total indexed chunks: {len(chunks)}.")
+
+    return {"chunks": len(chunks), "documents": len(docs), "per_form": per_form,
+            "table_row_chunks": sum(1 for c in chunks if c.metadata.get("kind") == "table_row")}
```

## 2. The second chunker — `src/chunkers.py`

`_base_meta()` stamps the requirement-1 metadata on every chunk from *either* strategy.
`structure_aware_chunks()` splits on clause headers and emits one chunk per table row,
each carrying `_context_header()` — form number, edition, policy line, clause — plus the
table's own header row, so an exclusion row is never separated from what scopes it.

```diff
diff --git a/src/chunkers.py b/src/chunkers.py
index 6b2609f..24cc122 100644
--- a/src/chunkers.py
+++ b/src/chunkers.py
@@ -1,10 +1,57 @@
-"""Chunking: fixed-width character windows with overlap."""
-from typing import List
+"""Two chunking strategies over the same 6 endorsements, same embedding model.
+
+Strategy 1 (baseline)         - the Week 3 chunker: fixed-width character windows with overlap.
+                    Structure-blind, so an exclusion row can be cut away from its
+                    table header and from the form number that scopes it.
+
+Strategy 2 (structure_aware)  - splits on form/clause headers, and emits ONE CHUNK PER
+                    EXCLUSION ROW, each carrying the form number, edition date,
+                    policy line, clause title and the table's header row. An
+                    exclusion row is never separated from its table header or its
+                    form number.
+"""
+import re
+from typing import List, Optional
 
 from . import Chunk, Document
 
+CLAUSE_RE = re.compile(r"^##\s+(.*)$", re.M)
+CLAUSE_ID_RE = re.compile(r"(Clause\s+\d+)", re.I)
+EXCL_CODE_RE = re.compile(r"\b(E-\d{2})\b")
+TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
+TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
+
+
+def _base_meta(doc: Document, strategy: str) -> dict:
+    """Requirement 1 metadata, stamped on every chunk from either strategy."""
+    return {
+        "source_file": doc.source_file,
+        "form_number": doc.form_number,
+        "policy_line": doc.policy_line,
+        "edition_date": doc.edition_date,
+        "effective_date": doc.effective_date,
+        "title": doc.title,
+        "strategy": strategy,
+    }
+
+
+# --------------------------------------------------------------------------
+# Strategy A - baseline (structure-blind fixed windows)
+# --------------------------------------------------------------------------
+
+def _clause_at(text: str, pos: int) -> str:
+    """Best-effort: the clause heading most recently preceding this offset."""
+    last = ""
+    for m in CLAUSE_RE.finditer(text):
+        if m.start() > pos:
+            break
+        last = m.group(1).strip()
+    cid = CLAUSE_ID_RE.search(last)
+    return cid.group(1).title() if cid else (last or "Header")
+
 
-def chunk_document(doc: Document, size: int, overlap: int) -> List[Chunk]:
+def baseline_chunks(doc: Document, size: int, overlap: int,
+                    strategy: str = "baseline") -> List[Chunk]:
     text = doc.text
     step = max(1, size - overlap)
     chunks: List[Chunk] = []
@@ -13,13 +60,123 @@ def chunk_document(doc: Document, size: int, overlap: int) -> List[Chunk]:
         if not piece.strip():
             continue
         idx = len(chunks)
-        meta = {
-            "source_file": doc.source_file,
+        meta = _base_meta(doc, strategy)
+        meta.update({
+            "clause": _clause_at(text, start),
+            "exclusion_codes": sorted(set(EXCL_CODE_RE.findall(piece))),
             "chunk_index": idx,
             "char_start": start,
             "char_end": min(start + size, len(text)),
-        }
-        chunks.append(Chunk(f"{doc.source_file}::{idx:03d}", piece.strip(), meta))
+        })
+        chunks.append(Chunk(f"{strategy}::{doc.form_number}::{idx:03d}", piece.strip(), meta))
         if start + size >= len(text):
             break
     return chunks
+
+
+# --------------------------------------------------------------------------
+# Strategy B - structure-aware (header/clause split, one chunk per exclusion row)
+# --------------------------------------------------------------------------
+
+def _split_sections(text: str):
+    """Yield (heading, body) pairs. Text before the first '##' is the Header section."""
+    matches = list(CLAUSE_RE.finditer(text))
+    if not matches:
+        return [("Header", text)]
+    out = [("Header", text[: matches[0].start()].strip())]
+    for i, m in enumerate(matches):
+        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
+        out.append((m.group(1).strip(), text[m.end():end].strip()))
+    return [(h, b) for h, b in out if b]
+
+
+def _split_table(body: str):
+    """Return (prose_lines, tables) where each table is (header_line, [row_lines])."""
+    prose, tables = [], []
+    cur_header, cur_rows, in_table = None, [], False
+    for line in body.splitlines():
+        if TABLE_ROW_RE.match(line):
+            if TABLE_SEP_RE.match(line):
+                in_table = True
+                continue
+            if not in_table and cur_header is None:
+                cur_header = line.strip()
+            elif in_table:
+                cur_rows.append(line.strip())
+            else:
+                cur_header = line.strip()
+        else:
+            if cur_header is not None:
+                tables.append((cur_header, cur_rows))
+                cur_header, cur_rows, in_table = None, [], False
+            prose.append(line)
+    if cur_header is not None:
+        tables.append((cur_header, cur_rows))
+    return prose, tables
+
+
+def _context_header(doc: Document, clause: str) -> str:
+    """The provenance stamp that travels with every structure-aware chunk."""
+    return (f"Form {doc.form_number} (ed. {doc.edition_date}) — {doc.title} — "
+            f"Policy Line {doc.policy_line} — {clause}")
+
+
+def _paragraph_pack(paragraphs, max_chars: int):
+    out, cur = [], ""
+    for p in paragraphs:
+        if cur and len(cur) + len(p) + 2 > max_chars:
+            out.append(cur)
+            cur = p
+        else:
+            cur = f"{cur}\n\n{p}" if cur else p
+    if cur:
+        out.append(cur)
+    return out
+
+
+def structure_aware_chunks(doc: Document, max_chars: int,
+                           strategy: str = "structure_aware") -> List[Chunk]:
+    chunks: List[Chunk] = []
+
+    def add(text: str, clause: str, kind: str,
+            code: Optional[str] = None, table_header: Optional[str] = None):
+        idx = len(chunks)
+        meta = _base_meta(doc, strategy)
+        cid = CLAUSE_ID_RE.search(clause)
+        meta.update({
+            "clause": cid.group(1).title() if cid else clause,
+            "clause_heading": clause,
+            "kind": kind,
+            "exclusion_codes": [code] if code else sorted(set(EXCL_CODE_RE.findall(text))),
+            "table_header": table_header,
+            "chunk_index": idx,
+        })
+        chunks.append(Chunk(f"{strategy}::{doc.form_number}::{idx:03d}", text.strip(), meta))
+
+    for clause, body in _split_sections(doc.text):
+        prose_lines, tables = _split_table(body)
+        header = _context_header(doc, clause)
+
+        prose = "\n".join(prose_lines).strip()
+        if prose:
+            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
+            for packed in _paragraph_pack(paragraphs, max_chars):
+                add(f"{header}\n\n{packed}", clause, "prose")
+
+        # One chunk per table row. The row always ships with the form number,
+        # the clause it sits under, and the table's own header row.
+        for table_header, rows in tables:
+            for row in rows:
+                code_m = EXCL_CODE_RE.search(row)
+                add(f"{header}\n\n{table_header}\n{row}", clause, "table_row",
+                    code_m.group(1) if code_m else None, table_header)
+
+    return chunks
+
+
+def chunk_document(doc: Document, strategy: str, **kw) -> List[Chunk]:
+    if strategy == "baseline":
+        return baseline_chunks(doc, kw["size"], kw["overlap"])
+    if strategy == "structure_aware":
+        return structure_aware_chunks(doc, kw["max_chars"])
+    raise ValueError(f"unknown strategy {strategy}")
```

## 3. Metadata filtering in the vector DB — `src/retriever.py`

`search()` takes `filters`, and `VectorStore._where()` (in `indexer.py`, above) turns
it into a Chroma `where` clause, so `policy_line` filtering runs inside the database
during search rather than being post-filtered in Python.

```diff
diff --git a/src/retriever.py b/src/retriever.py
index 8fa6bde..3ccaaa2 100644
--- a/src/retriever.py
+++ b/src/retriever.py
@@ -1,13 +1,22 @@
-"""Dense retrieval: top-K over the index."""
-from typing import List, Optional
+"""Dense retrieval: top-K over a chunking strategy, with optional metadata filtering.
 
-from . import Chunk, TOP_K
+The filter is passed straight through to the vector database as a `where` clause,
+so filtering happens during search rather than being applied to results afterwards.
+"""
+from typing import Dict, List, Optional
+
+from . import STRATEGIES, TOP_K, Chunk
 from .indexer import SearchHit, embed_query, get_store
 
 
-def search(question: str, top_k: int = TOP_K) -> List[SearchHit]:
-    return get_store().search(embed_query(question), top_k=top_k)
+def search(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
+           filters: Optional[Dict[str, object]] = None) -> List[SearchHit]:
+    return get_store(strategy).search(embed_query(question), top_k=top_k, filters=filters)
 
 
 def get_chunk(chunk_id: str) -> Optional[Chunk]:
-    return get_store().get(chunk_id)
+    """Resolve a citation's chunk_id back to the exact indexed chunk."""
+    strategy = chunk_id.split("::", 1)[0]
+    if strategy not in STRATEGIES:
+        return None
+    return get_store(strategy).get(chunk_id)
```

## 4. Grounded answering with a forced refusal — `src/generator.py` (new)

No model and no "use your best judgement" clause. The refusal is a gate in code, and the
answer is quoted verbatim from the cited chunk, so it cannot state anything the cited
chunk does not.

```diff
diff --git a/src/generator.py b/src/generator.py
new file mode 100644
index 0000000..7d7a680
--- /dev/null
+++ b/src/generator.py
@@ -0,0 +1,141 @@
+"""Grounded answering with a FORCED refusal - no model, no API key.
+
+The task's common-mistakes list forbids a grounding step that says "use your best
+judgement": an invented coverage answer is a bad-faith exposure. Here the refusal
+is not a suggestion to a model, it is a gate in code, and the answer text is
+QUOTED from the cited chunk rather than written, so it cannot drift from source.
+
+Two gates, both measured (see results.md section 5.1):
+
+  1. Term coverage. The content words of the question are checked against the
+     whole indexed corpus. A question whose distinctive terms do not appear
+     anywhere ("reserve-setting threshold", "CLM-2024-88431") is refused before
+     retrieval is even consulted. Measured margin on this corpus: worst
+     in-corpus 0.62 vs best out-of-corpus 0.50.
+
+  2. Retrieval score floor - a backstop for a query with no topical neighbour.
+
+Cosine similarity alone CANNOT gate this: out-of-corpus questions score 0.69-0.71
+while a legitimate question scores 0.7174. That is why gate 1 is lexical.
+"""
+import re
+from functools import lru_cache
+from typing import Dict, List, Optional, Tuple
+
+from . import COVERAGE_FLOOR, DATA_DIR, SCORE_FLOOR, TOP_K
+from .indexer import SearchHit
+from .retriever import search
+
+# Question words and generic verbs carry no evidence about whether the corpus
+# covers a topic, so they are excluded from the coverage test.
+STOPWORDS = set("""
+what is the a an of for to in on does do how much many under and or with any this
+that are was were be been which who whose when where its it his her their our your
+my we you i not no if then than as at by from can could should would will shall
+must may might have has had there here about into over per each all some more most
+""".split())
+
+CONTENT_TERM_RE = re.compile(r"[a-z0-9][a-z0-9\-]{3,}")
+
+REFUSAL_TEXT = ("I could not find this in the indexed endorsements, so I cannot answer it. "
+                "Answering would mean inventing a coverage position.")
+
+
+@lru_cache(maxsize=1)
+def _corpus_text() -> str:
+    parts = []
+    for p in sorted(DATA_DIR.iterdir()):
+        if p.suffix.lower() in {".md", ".txt"}:
+            parts.append(p.read_text(encoding="utf-8"))
+    return " ".join(parts).lower()
+
+
+def content_terms(question: str) -> List[str]:
+    return [t for t in CONTENT_TERM_RE.findall(question.lower()) if t not in STOPWORDS]
+
+
+def term_coverage(question: str) -> Tuple[float, List[str]]:
+    """Fraction of the question's content terms that appear anywhere in the corpus."""
+    terms = content_terms(question)
+    if not terms:
+        return 0.0, []
+    corpus = _corpus_text()
+    missing = [t for t in terms if t not in corpus]
+    return 1.0 - len(missing) / len(terms), missing
+
+
+def _best_span(chunk_text: str, question: str, kind: str = "") -> str:
+    """The part of the cited chunk that answers, quoted verbatim.
+
+    The answer is quoted, never composed, so it cannot say anything the cited
+    chunk does not say. For a table-row chunk the column header is quoted with
+    the row, otherwise a bare row of figures is unreadable on its own.
+    """
+    lines = [ln.strip() for ln in chunk_text.splitlines() if ln.strip()]
+    body = [ln for ln in lines if not ln.startswith("Form ")] or lines
+
+    if kind == "table_row" and len(body) >= 2:
+        return "\n".join(body[-2:])          # column header + the row itself
+
+    terms = set(content_terms(question))
+    best, best_score = body[0], -1
+    for ln in body:
+        low = ln.lower()
+        score = sum(1 for t in terms if t in low)
+        if score > best_score:
+            best, best_score = ln, score
+    return best
+
+
+def _refusal(question: str, strategy: str, hits: List[SearchHit], gate: str,
+             reason: str) -> dict:
+    return {
+        "question": question, "strategy": strategy, "refused": True,
+        "answer": REFUSAL_TEXT, "reason": reason, "citations": [],
+        "retrieved": [h.to_dict() for h in hits], "gate": gate,
+        "top_score": round(hits[0].score, 4) if hits else 0.0,
+    }
+
+
+def answer(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
+           filters: Optional[Dict[str, object]] = None) -> dict:
+    coverage, missing = term_coverage(question)
+    hits = search(question, strategy=strategy, top_k=top_k, filters=filters)
+
+    # Gate 1 - the corpus does not contain the vocabulary this question is about.
+    if coverage < COVERAGE_FLOOR:
+        return _refusal(
+            question, strategy, hits, "term_coverage",
+            f"Only {coverage:.0%} of the question's content terms appear anywhere in the "
+            f"indexed endorsements (floor {COVERAGE_FLOOR:.0%}). Absent entirely: "
+            f"{', '.join(missing)}. Refused without composing an answer.")
+
+    # Gate 2 - backstop: nothing retrieved is even topically close.
+    if not hits or hits[0].score < SCORE_FLOOR:
+        top = hits[0].score if hits else 0.0
+        return _refusal(
+            question, strategy, hits, "score_floor",
+            f"No indexed chunk scored above the {SCORE_FLOOR} retrieval floor "
+            f"(best was {top:.4f}).")
+
+    # Grounded answer, quoted verbatim from the top chunk.
+    top = hits[0]
+    m = top.chunk.metadata
+    quote = _best_span(top.chunk.text, question, m.get("kind", ""))
+    return {
+        "question": question, "strategy": strategy, "refused": False,
+        "answer": (f"{quote}\n\n(Per {m.get('form_number')} ed. {m.get('edition_date')}, "
+                   f"{m.get('clause')}, policy line {m.get('policy_line')}.)"),
+        "reason": (f"Answered from the highest-scoring chunk. Term coverage {coverage:.0%}; "
+                   f"retrieval score {top.score:.4f}."),
+        "citations": [{
+            "chunk_id": top.chunk.chunk_id,
+            "form_number": m.get("form_number"),
+            "clause": m.get("clause"),
+            "source_file": m.get("source_file"),
+            "quote": quote,
+        }],
+        "retrieved": [h.to_dict() for h in hits],
+        "gate": "extractive", "top_score": round(top.score, 4),
+        "coverage": round(coverage, 3),
+    }
```

## 5. The 8 questions as data — `questions.json` (new)

```diff
diff --git a/questions.json b/questions.json
new file mode 100644
index 0000000..0ee2c18
--- /dev/null
+++ b/questions.json
@@ -0,0 +1,102 @@
+{
+  "_comment": "The 8 known-answer questions were written from the endorsements BEFORE any search was run. A chunk counts as correct only if its text carries BOTH `marker` (the identifier asked about) and `answer_marker` (the span that answers) - so a chunk holding the exclusion code without its rule, or the rule without the code, is not a hit.",
+  "questions": [
+    {
+      "qid": "Q1",
+      "question": "Does exclusion E-17 apply to water damage from a burst supply line under HO-0304?",
+      "gold_form": "HO-0304",
+      "gold_clause": "Clause 3",
+      "marker": "E-17",
+      "answer_marker": "burst supply line",
+      "known_answer": "No. E-17 excludes seepage lasting 14 days or more, but carries an express exception for a sudden and accidental discharge including a burst supply line, provided the loss is reported within 30 days.",
+      "from_table": true
+    },
+    {
+      "qid": "Q2",
+      "question": "The dwelling was left vacant and the pipes froze. Is that loss excluded under HO-0304?",
+      "gold_form": "HO-0304",
+      "gold_clause": "Clause 3",
+      "marker": "E-18",
+      "answer_marker": "maintain heat",
+      "known_answer": "Excluded under E-18, unless the insured used reasonable care to maintain heat, or shut off the water supply and drained the system.",
+      "from_table": true
+    },
+    {
+      "qid": "Q3",
+      "question": "Is granule loss on a shingle roof covered, or is it treated as cosmetic damage?",
+      "gold_form": "HO-0455",
+      "gold_clause": "Clause 3",
+      "marker": "E-21",
+      "answer_marker": "water-shedding",
+      "known_answer": "Excluded under E-21 as cosmetic damage that does not compromise the water-shedding function, unless the Cosmetic Damage Buy-Back is shown in the Declarations.",
+      "from_table": true
+    },
+    {
+      "qid": "Q4",
+      "question": "Can the insured run a small home office and keep coverage under the home business exclusion?",
+      "gold_form": "HO-2199",
+      "gold_clause": "Clause 2",
+      "marker": "E-33",
+      "answer_marker": "$10,000",
+      "known_answer": "Yes. E-33 excludes business losses but excepts an incidental office occupancy with no employees and no customer visits where annual gross receipts do not exceed $10,000.",
+      "from_table": true
+    },
+    {
+      "qid": "Q5",
+      "question": "What percentage of replacement cost is paid for a 12-year-old asphalt shingle roof?",
+      "gold_form": "HO-0455",
+      "gold_clause": "Clause 2",
+      "marker": "60%",
+      "answer_marker": "11 to 15 years",
+      "known_answer": "60% - the 11 to 15 year band of the HO-0455 Payment Schedule.",
+      "from_table": true
+    },
+    {
+      "qid": "Q6",
+      "question": "What is the water damage deductible per occurrence under the limited water damage endorsement?",
+      "gold_form": "HO-0304",
+      "gold_clause": "Clause 1",
+      "marker": "$2,500",
+      "answer_marker": "Water Damage Deductible",
+      "known_answer": "$2,500 per occurrence, reduced to $1,000 where a licensed plumber's inspection report dated within 12 months of the loss is produced.",
+      "from_table": true
+    },
+    {
+      "qid": "Q7",
+      "question": "How much ordinance or law coverage does the increased-amount endorsement provide?",
+      "gold_form": "HO-0612",
+      "gold_clause": "Clause 1",
+      "marker": "25%",
+      "answer_marker": "Coverage A",
+      "known_answer": "25% of the Coverage A limit, up from 10% in the base wording, as additional insurance.",
+      "from_table": false
+    },
+    {
+      "qid": "Q8",
+      "question": "How is 'sudden and accidental' defined for the purposes of these endorsements?",
+      "gold_form": "HO-0788",
+      "gold_clause": "Clause 2",
+      "marker": "unexpected and unintended",
+      "answer_marker": "identifiable point in time",
+      "known_answer": "An event both unexpected and unintended from the insured's standpoint that begins at an identifiable point in time; a slow weep or drip is not sudden and accidental even if it later worsens abruptly.",
+      "from_table": false
+    }
+  ],
+  "unanswerable": [
+    "What is the reserve-setting threshold for claim CLM-2024-88431?",
+    "Who is the assigned adjuster for policy HO-99213, and what is their direct phone number?",
+    "What is the current reinsurance attachment point for our homeowners book this treaty year?"
+  ],
+  "answerable": [
+    "Q1",
+    "Q6",
+    "Q7"
+  ],
+  "filter_demo": {
+    "query": "Does the seepage exclusion apply to water escaping from a burst supply line, and how many days does it take to trigger?",
+    "field": "policy_line",
+    "value": "HO-3"
+  },
+  "bonus_question": "A supply line under the kitchen sink burst while the family was away for three weeks. The water ran the entire time and was only found when they got home. Is the loss covered under HO-0304?",
+  "_answerable_note": "Q1/Q6/Q7 are the three run through generation: each retrieves its gold chunk at rank 1. Q5 is deliberately NOT used here - see results.md section 7, where its failure is diagnosed rather than hidden."
+}
\ No newline at end of file
```
