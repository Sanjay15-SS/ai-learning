"""Ingestion: read the endorsements, chunk them, embed them, index them.

Requirement 1: every chunk carries source_file, form_number, policy_line and
edition_date. Metadata originates in load_document(); the chunkers propagate it.

Requirement 6: only the 6 new endorsements are indexed. The base policy wording
library is not re-indexed and is never read by this pipeline.

The vector database is Chroma, running in-process with an hnswlib HNSW index in
cosine space. Nothing is written to disk: the index is built fresh each run.
Metadata filtering is done by the database via `where` clauses, not by us in
Python afterwards.
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import (CHUNK_CHARS, Chunk, DATA_DIR, Document, EMBED_MODEL, OVERLAP_CHARS,
               STRATEGIES, STRUCTURE_MAX_CHARS)
from .chunkers import baseline_chunks, structure_aware_chunks

# --------------------------------------------------------------------------
# Loading + form metadata
# --------------------------------------------------------------------------

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
FORM_RE = re.compile(r"\b([A-Z]{2}-\d{4})\b\s*\(\s*ed\.?\s*(\d{2}-\d{2})\s*\)", re.I)
LINE_RE = re.compile(r"Policy\s+Line:\s*([A-Z]{2}-\d)", re.I)
EFF_RE = re.compile(r"Effective:\s*([A-Za-z0-9 ,\-/]+)")


def _parse_front_matter(raw: str) -> dict:
    m = FRONT_MATTER_RE.match(raw)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:                       # pypdf is optional
        raise RuntimeError(
            f"{path.name} is a PDF but pypdf is not installed. Run: pip install pypdf") from exc

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _validate(doc: Document) -> None:
    """A chunk with no source_file is a failed ingest - catch it at the document."""
    missing = [f for f in ("source_file", "form_number", "policy_line", "edition_date")
               if not getattr(doc, f)]
    if missing:
        raise ValueError(f"{doc.source_file or '<unknown file>'}: missing metadata {missing}")


def load_document(path: Path) -> Document:
    if path.suffix.lower() == ".pdf":
        raw, fm = _read_pdf(path), {}
    else:
        raw = path.read_text(encoding="utf-8")
        fm = _parse_front_matter(raw)
        raw = FRONT_MATTER_RE.sub("", raw, count=1)

    form, edition = fm.get("form_number"), fm.get("edition_date")
    if not form or not edition:
        m = FORM_RE.search(raw)
        form = form or (m.group(1).upper() if m else None)
        edition = edition or (m.group(2) if m else None)

    line = fm.get("policy_line")
    if not line:
        m = LINE_RE.search(raw)
        line = m.group(1).upper() if m else None

    effective = fm.get("effective_date")
    if not effective:
        m = EFF_RE.search(raw)
        effective = m.group(1).strip() if m else ""

    title = fm.get("title") or (raw.strip().splitlines() or [""])[0].lstrip("# ").strip()

    doc = Document(source_file=path.name, form_number=form or "", edition_date=edition or "",
                   policy_line=line or "", effective_date=effective or "",
                   title=title, text=raw.strip())
    _validate(doc)
    return doc


def load_documents(data_dir: Path = DATA_DIR) -> List[Document]:
    paths = sorted(p for p in data_dir.iterdir()
                   if p.suffix.lower() in {".md", ".txt", ".pdf"} and not p.name.startswith("."))
    if not paths:
        raise FileNotFoundError(f"no documents found in {data_dir}")
    return [load_document(p) for p in paths]


# --------------------------------------------------------------------------
# Embeddings - ONE model across both strategies
# --------------------------------------------------------------------------
# Changing the chunker and the embedding model in the same run would teach you
# nothing about which one moved the number, so this is fixed for every run.

@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBED_MODEL)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def embed_passages(texts: List[str]) -> np.ndarray:
    return _normalize(np.asarray(list(_embedder().embed(texts)), dtype=np.float32))


def embed_query(text: str) -> np.ndarray:
    """BGE applies its retrieval instruction prefix to queries here."""
    return _normalize(np.asarray(list(_embedder().query_embed([text])), dtype=np.float32))[0]


# --------------------------------------------------------------------------
# Vector database - Chroma, in-memory, HNSW
# --------------------------------------------------------------------------

_CLIENT = None
_LIST_KEYS = ("exclusion_codes",)   # Chroma metadata must be scalars; these round-trip as lists


def _shared_client():
    """One in-memory Chroma instance per process, shared by both collections."""
    global _CLIENT
    if _CLIENT is None:
        import chromadb

        _CLIENT = chromadb.EphemeralClient()
    return _CLIENT


def _flatten(meta: dict) -> dict:
    out = {}
    for k, v in meta.items():
        if v is None:
            continue
        out[k] = ",".join(str(x) for x in v) if isinstance(v, (list, tuple)) else (
            v if isinstance(v, (str, int, float, bool)) else str(v))
    return out


def _restore(meta: dict) -> dict:
    out = dict(meta)
    for k in _LIST_KEYS:
        raw = out.get(k)
        out[k] = [p for p in raw.split(",") if p] if isinstance(raw, str) else (raw or [])
    return out


class SearchHit:
    __slots__ = ("score", "chunk", "rank")

    def __init__(self, score: float, chunk: Chunk, rank: int):
        self.score, self.chunk, self.rank = score, chunk, rank

    def to_dict(self) -> dict:
        m = self.chunk.metadata
        return {"rank": self.rank, "score": round(self.score, 4),
                "chunk_id": self.chunk.chunk_id, "form_number": m.get("form_number"),
                "policy_line": m.get("policy_line"), "edition_date": m.get("edition_date"),
                "clause": m.get("clause"), "source_file": m.get("source_file"),
                "exclusion_codes": m.get("exclusion_codes", []), "text": self.chunk.text}


class VectorStore:
    """One Chroma collection per chunking strategy."""

    def __init__(self, name: str):
        self.name = name
        self._collection = None

    def _get(self, create: bool = False):
        if self._collection is not None:
            return self._collection
        client = _shared_client()
        if create:
            try:
                client.delete_collection(self.name)
            except Exception:
                pass
            self._collection = client.create_collection(
                name=self.name, metadata={"hnsw:space": "cosine"})
        else:
            try:
                self._collection = client.get_collection(self.name)
            except Exception as exc:
                raise FileNotFoundError(
                    f"collection '{self.name}' not built in this process - the index is "
                    f"in-memory, so ingest() must run first") from exc
        return self._collection

    def add(self, chunks: Sequence[Chunk], vectors: np.ndarray) -> None:
        if len(chunks) != vectors.shape[0]:
            raise ValueError("chunk/vector count mismatch")
        missing = [c.chunk_id for c in chunks if not c.metadata.get("source_file")]
        if missing:
            raise ValueError(f"failed ingest - chunks with no source_file: {missing[:5]}")
        self._get(create=True).add(
            ids=[c.chunk_id for c in chunks],
            embeddings=[v.tolist() for v in vectors],
            documents=[c.text for c in chunks],
            metadatas=[_flatten(c.metadata) for c in chunks])

    def get(self, chunk_id: str) -> Optional[Chunk]:
        res = self._get().get(ids=[chunk_id], include=["documents", "metadatas"])
        if not res["ids"]:
            return None
        return Chunk(res["ids"][0], res["documents"][0], _restore(res["metadatas"][0]))

    @staticmethod
    def _where(filters: Optional[Dict[str, object]]):
        """Translate a plain dict into a Chroma `where` clause."""
        if not filters:
            return None
        clauses = [{k: {"$in": list(v)}} if isinstance(v, (list, tuple, set)) else {k: {"$eq": v}}
                   for k, v in filters.items()]
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def search(self, query_vec: np.ndarray, top_k: int = 5,
               filters: Optional[Dict[str, object]] = None) -> List[SearchHit]:
        coll = self._get()
        res = coll.query(query_embeddings=[query_vec.tolist()],
                         n_results=min(top_k, max(1, coll.count())),
                         where=self._where(filters),        # filtering happens in the DB
                         include=["documents", "metadatas", "distances"])
        if not res["ids"] or not res["ids"][0]:
            return []
        return [SearchHit(1.0 - float(d), Chunk(i, doc, _restore(m)), rank)
                for rank, (i, doc, m, d) in enumerate(
                    zip(res["ids"][0], res["documents"][0],
                        res["metadatas"][0], res["distances"][0]), start=1)]

    def __len__(self) -> int:
        try:
            return self._get().count()
        except FileNotFoundError:
            return 0


# --------------------------------------------------------------------------
# Ingest
# --------------------------------------------------------------------------

@lru_cache(maxsize=4)
def get_store(strategy: str) -> VectorStore:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'; expected one of {STRATEGIES}")
    return VectorStore(strategy)


def ingest(strategy: str, data_dir: Path = DATA_DIR, verbose: bool = True) -> dict:
    """Chunk, embed and index the endorsement drop under one chunking strategy."""
    docs = load_documents(data_dir)

    chunks: List[Chunk] = []
    for doc in docs:
        if strategy == "baseline":
            chunks += baseline_chunks(doc, CHUNK_CHARS, OVERLAP_CHARS)
        else:
            chunks += structure_aware_chunks(doc, STRUCTURE_MAX_CHARS)

    store = VectorStore(strategy)
    store.add(chunks, embed_passages([c.text for c in chunks]))
    get_store.cache_clear()

    per_form: Dict[str, int] = {}
    for c in chunks:
        per_form[c.metadata["form_number"]] = per_form.get(c.metadata["form_number"], 0) + 1

    if verbose:
        rel = data_dir.relative_to(data_dir.parent.parent) if data_dir.is_absolute() else data_dir
        print(f"Ingested {len(chunks)} chunks from {len(docs)} files in {rel}. "
              f"Total indexed chunks: {len(chunks)}.")

    return {"chunks": len(chunks), "documents": len(docs), "per_form": per_form,
            "table_row_chunks": sum(1 for c in chunks if c.metadata.get("kind") == "table_row")}
