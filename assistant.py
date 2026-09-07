"""The Week 4 answering logic, with a trace written around it.

Nothing in the answering path is changed here. `src.generator.answer()` is called
exactly as `app.py` calls it, on the shipped retrieval mode, and this module only
records what went in and what came out. That is the constraint the week is under:
a taxonomy is only about the app it was read from, so the app must not move while
it is being read.

What the trace records that the answer object does not: the corpus fingerprint, the
policy version, the wall-clock latency, and the gate readings for the gate that did
NOT fire, so a refusal can be told apart from a near-refusal after the fact.
"""
import time
from typing import Optional

from prompts import policy_record
from src import CANDIDATES, COVERAGE_FLOOR, RETRIEVAL_MODE, RRF_K, SCORE_FLOOR
from src.generator import answer, term_coverage
from trace import corpus_fingerprint, now, trace_id

STRATEGY = "structure_aware"
TOP_K = 3


def _retrieval_row(h: dict) -> dict:
    return {"rank": h["rank"], "chunk_id": h["chunk_id"], "score": h["score"],
            "form_number": h["form_number"], "edition_date": h["edition_date"],
            "policy_line": h["policy_line"], "clause": h["clause"],
            "exclusion_codes": h.get("exclusion_codes", [])}


def run_question(qid: str, question: str, run: str,
                 mode: str = RETRIEVAL_MODE, top_k: int = TOP_K,
                 corpus: Optional[dict] = None) -> dict:
    t0 = time.perf_counter()
    res = answer(question, strategy=STRATEGY, top_k=top_k, mode=mode)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    coverage, missing = term_coverage(question)
    hits = res["retrieved"]
    # The dense cosine behind gate 2, recorded whether or not that gate fired.
    best_cosine = max((h["score"] for h in hits), default=0.0) if mode == "dense" else None

    return {
        "schema": 1,
        "trace_id": trace_id(run, qid, question),
        "ts": now(),
        "run": run,
        "qid": qid,
        "question": question,
        "app": {"strategy": STRATEGY, "mode": mode, "top_k": top_k,
                "candidates": CANDIDATES, "rrf_k": RRF_K},
        "policy": policy_record(),
        "corpus": corpus or corpus_fingerprint(STRATEGY),
        "retrieval": [_retrieval_row(h) for h in hits],
        "gates": {"coverage": round(coverage, 3), "coverage_floor": COVERAGE_FLOOR,
                  "missing_terms": missing, "score_floor": SCORE_FLOOR,
                  "best_cosine": best_cosine},
        "outcome": {"refused": res["refused"], "gate": res["gate"],
                    "citation": res["citations"][0]["chunk_id"] if res["citations"] else None,
                    "quote": res["citations"][0]["quote"] if res["citations"] else None,
                    "answer": res["answer"], "reason": res["reason"]},
        "latency_ms": round(latency_ms, 2),
    }
