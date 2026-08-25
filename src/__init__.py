"""Insurance-claims RAG — Week 3 Practical, Task Set D.

Package-level configuration and the two data records every module shares.
"""
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "endorsements"
RESULTS_PATH = ROOT / "results.md"
QUESTIONS_PATH = ROOT / "questions.json"

EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # MTEB-ranked bi-encoder, 384-dim
TOP_K = 5

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
