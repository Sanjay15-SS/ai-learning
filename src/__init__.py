"""Insurance-claims RAG — Task Set D (Weeks 3-5).

Package-level configuration and the two data records every module shares.
"""
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "endorsements"
RESULTS_PATH = ROOT / "results.md"                # Week 4 deliverable
RESULTS_WEEK3_PATH = ROOT / "results-week3.md"    # Week 3 deliverable, still reproducible
QUESTIONS_PATH = ROOT / "questions.json"          # Week 3 question set
GOLDEN_SET_PATH = ROOT / "golden_set.jsonl"       # Week 4 golden set: 12 adjuster questions + gold chunk_id

EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # MTEB-ranked bi-encoder, 384-dim
TOP_K = 5

# Week 4: which retriever answers a query. "dense" is the Week 3 retriever, unchanged.
# "hybrid" is THE one retrieval change: dense top-25 + BM25 top-25 -> RRF (k=60).
RETRIEVAL_MODE = "hybrid"
CANDIDATES = 25    # depth of each list before fusion
RRF_K = 60         # the standard RRF constant; not tuned

# Strategy 1 - the Week 3 chunker, unchanged.
CHUNK_CHARS = 900
OVERLAP_CHARS = 150

# Strategy 2 - structure-aware: cap on a prose chunk before it splits on paragraphs.
STRUCTURE_MAX_CHARS = 1200

STRATEGIES = ("baseline", "structure_aware")
STRATEGY_LABELS = {
    "baseline": "Naive Chunker",
    "structure_aware": "Structure-Aware Chunker",
}

# Refusal gates. See results.md section 5.1 for the measurement behind both.
COVERAGE_FLOOR = 0.55   # fraction of question terms that must appear in the corpus
SCORE_FLOOR = 0.35      # backstop for a query with no topical neighbour


@dataclass
class Document:
    source_file: str
    form_number: str
    edition_date: str
    policy_line: str
    effective_date: str
    title: str
    text: str

    def meta(self) -> dict:
        d = asdict(self)
        d.pop("text")
        return d


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict = field(default_factory=dict)
