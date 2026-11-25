"""Week 3-4 RAG retrieval, re-pointed at the SDK corpus.

- Structure-aware chunking (the Week-4 chunker): one chunk per `##` section, code fences never
  split. Known limit: a section longer than a screen is still one chunk.
- BM25 over chunk text.
- THE VERSION FILTER IS METADATA, ENFORCED HERE IN CODE: a chunk whose `sdk_version` does not
  cover the caller's version is removed BEFORE scoring. The model never sees it.
- Stack Overflow handling (`so_mode`):
    drop   - not indexed
    raw    - indexed and shown to the model like any page (v1 code leaks in)
    bridge - indexed for MATCHING only; a SO hit is swapped for its linked doc page in the
             caller's version. SO phrasing helps recall, SO code never reaches the model.
"""
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional

from . import CORPUS
from . import sdk_spec as S

TOKEN = re.compile(r"[a-z0-9_]+")


@dataclass
class Chunk:
    chunk_id: str
    page_id: str
    source: str            # docs | migration | changelog | sample | stackoverflow | issue
    sdk_version: str       # "2.x" | "3.0" | "2.4" | "all" | "1.x"
    title: str
    url: str
    text: str
    linked_doc: Optional[str] = None
    tokens: list = field(default_factory=list, repr=False)

    @property
    def version_label(self) -> str:
        return {"2.x": "v2.x", "3.0": "v3.0", "all": "v2.x+v3.0", "1.x": "v1 (dead)"}.get(
            self.sdk_version, "v" + self.sdk_version)


def covers(chunk_version: str, caller: str) -> bool:
    """Does a chunk tagged `chunk_version` apply to a caller on `caller`?"""
    if chunk_version == "all":
        return True
    cmaj, cmin = S.V(caller)
    if chunk_version.endswith(".x"):
        return int(chunk_version[0]) == cmaj
    tmaj, tmin = S.V(chunk_version)
    return tmaj == cmaj and tmin <= cmin


def _front(raw: str):
    _, front, body = raw.split("---", 2)
    meta = {}
    for line in front.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, body.strip()


def _sections(body: str) -> List[str]:
    """Split on `## ` headings, but never inside a ``` fence."""
    out, cur, fence = [], [], False
    for line in body.splitlines():
        if line.startswith("```"):
            fence = not fence
        if line.startswith("## ") and not fence and cur:
            out.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return [s.strip() for s in out if s.strip()]


def _tok(text: str) -> List[str]:
    return TOKEN.findall(text.lower())


@lru_cache(maxsize=1)
def all_chunks() -> List[Chunk]:
    out: List[Chunk] = []
    pages = sorted((CORPUS / "docs").rglob("*.md")) + [CORPUS / "migration.md", CORPUS / "CHANGELOG.md"]
    for p in pages:
        meta, body = _front(p.read_text(encoding="utf-8"))
        for i, sec in enumerate(_sections(body)):
            out.append(Chunk(f"{meta['page_id']}#{i}", meta["page_id"], meta["source"],
                             meta["sdk_version"], meta["title"], meta["url"], sec))
    for line in (CORPUS / "samples.jsonl").read_text(encoding="utf-8").splitlines():
        s = json.loads(line)
        ver, topic = s["sdk_version"], s["topic"]
        out.append(Chunk(s["id"], s["id"], "sample", ver, f"Sample: {topic} ({ver})",
                         f"https://github.com/ledgerline/samples/blob/main/{s['id']}.py",
                         f"```python\n{s['code']}\n```"))
    for line in (CORPUS / "stackoverflow.jsonl").read_text(encoding="utf-8").splitlines():
        s = json.loads(line)
        out.append(Chunk(s["id"], s["id"], "stackoverflow", s["sdk_version"], s["title"], s["url"],
                         f"{s['title']}\n{s['body']}", linked_doc=s["linked_doc"]))
    for line in (CORPUS / "issues.jsonl").read_text(encoding="utf-8").splitlines():
        s = json.loads(line)
        out.append(Chunk(s["id"], s["id"], "issue", s["sdk_version"], f"{s['id']}: {s['title']}",
                         f"https://github.com/ledgerline/ledgerline-python/issues/{s['id'][3:]}",
                         f"{s['title']}\n{s['body']}"))
    for c in out:
        c.tokens = _tok(c.title + " " + c.text)
    return out


@dataclass
class RetrieverConfig:
    version_filter: bool = True
    so_mode: str = "bridge"         # drop | raw | bridge
    k: int = 4
    include_samples: bool = True


def _bm25(query: str, docs: List[Chunk], k: int) -> List[tuple]:
    if not docs:
        return []
    avg = sum(len(d.tokens) for d in docs) / len(docs)
    df = {}
    for d in docs:
        for w in set(d.tokens):
            df[w] = df.get(w, 0) + 1
    n, q = len(docs), set(_tok(query))
    scored = []
    for d in docs:
        s = 0.0
        for w in q:
            f = d.tokens.count(w)
            if f:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(d.tokens) / avg))
        if s > 0:
            scored.append((s, d))
    scored.sort(key=lambda x: (-x[0], x[1].chunk_id))
    return scored


def search(query: str, version: Optional[str], cfg: RetrieverConfig = RetrieverConfig()) -> List[Chunk]:
    pool = []
    for c in all_chunks():
        if c.source == "sample" and not cfg.include_samples:
            continue
        if c.source == "stackoverflow":
            if cfg.so_mode == "drop":
                continue
            if cfg.so_mode == "raw" or not cfg.version_filter:
                pool.append(c)          # SO shown as-is (raw) - the poison path
                continue
            pool.append(c)              # bridge: kept for matching, swapped below
            continue
        if cfg.version_filter and version and not covers(c.sdk_version, version):
            continue                    # <- the filter. Metadata, not words.
        pool.append(c)
    ranked = _bm25(query, pool, k=len(pool))
    out, seen = [], set()
    major = str(S.V(version)[0]) if version else "3"
    for _, c in ranked:
        if c.source == "stackoverflow" and cfg.so_mode == "bridge" and cfg.version_filter:
            target = f"v{major}/{c.linked_doc}"
            doc = next((d for d in all_chunks() if d.page_id == target), None)
            if doc is None:
                continue
            c = doc
        if c.chunk_id in seen:
            continue
        seen.add(c.chunk_id)
        out.append(c)
        if len(out) >= cfg.k:
            break
    return out


def page_chunks(page_id: str) -> List[Chunk]:
    return [c for c in all_chunks() if c.page_id == page_id]
