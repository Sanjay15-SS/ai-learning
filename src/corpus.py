"""Load the docs pages, the two OpenAPI specs and the changelog. Search is BM25 over
page text, optionally scoped to one api_version. No network, no embeddings."""
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from . import CORPUS, DOCS_DIR

TOKEN = re.compile(r"[a-z0-9_]+")


@dataclass
class Page:
    page_id: str
    api_version: str
    title: str
    endpoints: List[str]
    body: str


def _parse(path) -> Page:
    raw = path.read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = {}
    for line in front.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    eps = [e.strip() for e in meta.get("endpoints", "").split(",") if e.strip()]
    return Page(meta["page_id"], meta["api_version"], meta["title"], eps, body.strip())


@lru_cache(maxsize=1)
def pages() -> List[Page]:
    return [_parse(p) for p in sorted(DOCS_DIR.glob("*.md"))]


def page(page_id: str) -> Optional[Page]:
    return next((p for p in pages() if p.page_id == page_id), None)


@lru_cache(maxsize=2)
def spec(version: str) -> dict:
    return json.loads((CORPUS / f"openapi_{version}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def changelog() -> List[dict]:
    return json.loads((CORPUS / "changelog.json").read_text(encoding="utf-8"))["entries"]


def _tokens(text: str) -> List[str]:
    return TOKEN.findall(text.lower())


def search(query: str, api_version: Optional[str] = None, k: int = 3) -> List[Page]:
    """BM25 (k1=1.2, b=0.75). api_version=None searches every version - the v1 app."""
    docs = [p for p in pages() if api_version is None or p.api_version == api_version]
    toks = [_tokens(p.title + " " + p.body) for p in docs]
    avg = sum(map(len, toks)) / max(len(toks), 1)
    n = len(docs)
    df: Dict[str, int] = {}
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    scored = []
    for p, t in zip(docs, toks):
        s = 0.0
        for w in set(_tokens(query)):
            f = t.count(w)
            if not f:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(t) / avg))
        scored.append((s, p.page_id, p))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [p for s, _, p in scored[:k] if s > 0]


def spec_paths(version: str) -> Dict[str, List[str]]:
    """{path: [METHOD, ...]} for one version."""
    return {path: sorted(m.upper() for m in ops) for path, ops in spec(version)["paths"].items()}


def full_reference_text() -> str:
    """Every page plus the changelog, for the judge. Stable order so it caches."""
    parts = [f"## [{p.api_version}] {p.title}\n{p.body}" for p in pages()]
    parts.append("## Changelog (v2 -> v3)\n" + "\n".join(
        f"- {e['symbol']} ({e['kind']}): {e['status']} in v3 -> {e['replacement']}. {e['note']}"
        for e in changelog()))
    return "\n\n".join(parts)
