"""Dense retrieval: top-K over a chunking strategy, with optional metadata filtering.

The filter is passed straight through to the vector database as a `where` clause,
so filtering happens during search rather than being applied to results afterwards.
"""
from typing import Dict, List, Optional

from . import STRATEGIES, TOP_K, Chunk
from .indexer import SearchHit, embed_query, get_store


def search(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
           filters: Optional[Dict[str, object]] = None) -> List[SearchHit]:
    return get_store(strategy).search(embed_query(question), top_k=top_k, filters=filters)


def get_chunk(chunk_id: str) -> Optional[Chunk]:
    """Resolve a citation's chunk_id back to the exact indexed chunk."""
    strategy = chunk_id.split("::", 1)[0]
    if strategy not in STRATEGIES:
        return None
    return get_store(strategy).get(chunk_id)
