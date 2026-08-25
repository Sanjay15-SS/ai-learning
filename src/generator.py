"""Grounded answering with a FORCED refusal - no model, no API key.

The task's common-mistakes list forbids a grounding step that says "use your best
judgement": an invented coverage answer is a bad-faith exposure. Here the refusal
is not a suggestion to a model, it is a gate in code, and the answer text is
QUOTED from the cited chunk rather than written, so it cannot drift from source.

Two gates, both measured (see results.md section 5.1):

  1. Term coverage. The content words of the question are checked against the
     whole indexed corpus. A question whose distinctive terms do not appear
     anywhere ("reserve-setting threshold", "CLM-2024-88431") is refused before
     retrieval is even consulted. Measured margin on this corpus: worst
     in-corpus 0.62 vs best out-of-corpus 0.50.

  2. Retrieval score floor - a backstop for a query with no topical neighbour.

Cosine similarity alone CANNOT gate this: out-of-corpus questions score 0.69-0.71
while a legitimate question scores 0.7174. That is why gate 1 is lexical.
"""
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from . import COVERAGE_FLOOR, DATA_DIR, SCORE_FLOOR, TOP_K
from .indexer import SearchHit
from .retriever import search

# Question words and generic verbs carry no evidence about whether the corpus
# covers a topic, so they are excluded from the coverage test.
STOPWORDS = set("""
what is the a an of for to in on does do how much many under and or with any this
that are was were be been which who whose when where its it his her their our your
my we you i not no if then than as at by from can could should would will shall
must may might have has had there here about into over per each all some more most
""".split())

CONTENT_TERM_RE = re.compile(r"[a-z0-9][a-z0-9\-]{3,}")

REFUSAL_TEXT = ("I could not find this in the indexed endorsements, so I cannot answer it. "
                "Answering would mean inventing a coverage position.")


@lru_cache(maxsize=1)
def _corpus_text() -> str:
    parts = []
    for p in sorted(DATA_DIR.iterdir()):
        if p.suffix.lower() in {".md", ".txt"}:
            parts.append(p.read_text(encoding="utf-8"))
    return " ".join(parts).lower()


def content_terms(question: str) -> List[str]:
    return [t for t in CONTENT_TERM_RE.findall(question.lower()) if t not in STOPWORDS]


def term_coverage(question: str) -> Tuple[float, List[str]]:
    """Fraction of the question's content terms that appear anywhere in the corpus."""
    terms = content_terms(question)
    if not terms:
        return 0.0, []
    corpus = _corpus_text()
    missing = [t for t in terms if t not in corpus]
    return 1.0 - len(missing) / len(terms), missing


def _best_span(chunk_text: str, question: str, kind: str = "") -> str:
    """The part of the cited chunk that answers, quoted verbatim.

    The answer is quoted, never composed, so it cannot say anything the cited
    chunk does not say. For a table-row chunk the column header is quoted with
    the row, otherwise a bare row of figures is unreadable on its own.
    """
    lines = [ln.strip() for ln in chunk_text.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.startswith("Form ")] or lines

    if kind == "table_row" and len(body) >= 2:
        return "\n".join(body[-2:])          # column header + the row itself

    terms = set(content_terms(question))
    best, best_score = body[0], -1
    for ln in body:
        low = ln.lower()
        score = sum(1 for t in terms if t in low)
        if score > best_score:
            best, best_score = ln, score
    return best


def _refusal(question: str, strategy: str, hits: List[SearchHit], gate: str,
             reason: str) -> dict:
    return {
        "question": question, "strategy": strategy, "refused": True,
        "answer": REFUSAL_TEXT, "reason": reason, "citations": [],
        "retrieved": [h.to_dict() for h in hits], "gate": gate,
        "top_score": round(hits[0].score, 4) if hits else 0.0,
    }


def answer(question: str, strategy: str = "structure_aware", top_k: int = TOP_K,
           filters: Optional[Dict[str, object]] = None) -> dict:
    coverage, missing = term_coverage(question)
    hits = search(question, strategy=strategy, top_k=top_k, filters=filters)

    # Gate 1 - the corpus does not contain the vocabulary this question is about.
    if coverage < COVERAGE_FLOOR:
        return _refusal(
            question, strategy, hits, "term_coverage",
            f"Only {coverage:.0%} of the question's content terms appear anywhere in the "
            f"indexed endorsements (floor {COVERAGE_FLOOR:.0%}). Absent entirely: "
            f"{', '.join(missing)}. Refused without composing an answer.")

    # Gate 2 - backstop: nothing retrieved is even topically close.
    if not hits or hits[0].score < SCORE_FLOOR:
        top = hits[0].score if hits else 0.0
        return _refusal(
            question, strategy, hits, "score_floor",
            f"No indexed chunk scored above the {SCORE_FLOOR} retrieval floor "
            f"(best was {top:.4f}).")

    # Grounded answer, quoted verbatim from the top chunk.
    top = hits[0]
    m = top.chunk.metadata
    quote = _best_span(top.chunk.text, question, m.get("kind", ""))
    return {
        "question": question, "strategy": strategy, "refused": False,
        "answer": (f"{quote}\n\n(Per {m.get('form_number')} ed. {m.get('edition_date')}, "
                   f"{m.get('clause')}, policy line {m.get('policy_line')}.)"),
        "reason": (f"Answered from the highest-scoring chunk. Term coverage {coverage:.0%}; "
                   f"retrieval score {top.score:.4f}."),
        "citations": [{
            "chunk_id": top.chunk.chunk_id,
            "form_number": m.get("form_number"),
            "clause": m.get("clause"),
            "source_file": m.get("source_file"),
            "quote": quote,
        }],
        "retrieved": [h.to_dict() for h in hits],
        "gate": "extractive", "top_score": round(top.score, 4),
        "coverage": round(coverage, 3),
    }
