"""Rebuild one answer from its trace alone.

    python3 replay.py trc_xxxxxxxxxxxx

Replay reaches into nothing live. It takes the chunk ids off the trace and resolves
them against the pinned corpus, takes the policy by its recorded version id, and
takes the retrieval order off the trace rather than running the retriever again.
The question is never re-embedded and the index is never searched.

It refuses to run at all if the corpus fingerprint or the policy sha has moved since
the trace was written, because a replay under changed rules proves nothing about the
run it claims to reproduce.

What this tests: whether a trace holds enough to reconstruct the determination and
the citation without the app. If a field is missing, this is where it shows up.
"""
import sys
from pathlib import Path

from prompts import POLICY_ID, policy_sha
from src import COVERAGE_FLOOR, SCORE_FLOOR
from src.generator import REFUSAL_TEXT, _best_span, term_coverage
from src.indexer import get_registry, ingest
from trace import corpus_fingerprint, find_trace

TRACE_DIR = Path(__file__).resolve().parent / "traces"


def load(tid: str) -> dict:
    for name in ("traces.jsonl", "demo.jsonl"):
        p = TRACE_DIR / name
        if p.exists():
            t = find_trace(p, tid)
            if t:
                return t
    raise SystemExit(f"no trace {tid} in {TRACE_DIR}")


def rebuild(t: dict, chunks_by_id: dict) -> dict:
    """The answering policy, applied to the trace's own recorded retrieval."""
    gates = t["gates"]
    coverage = gates["coverage"]
    if coverage < gates["coverage_floor"]:
        return {"refused": True, "gate": "term_coverage", "citation": None,
                "quote": None, "answer": REFUSAL_TEXT}

    best_cos = gates.get("best_cosine")
    if best_cos is not None and best_cos < gates["score_floor"]:
        return {"refused": True, "gate": "score_floor", "citation": None,
                "quote": None, "answer": REFUSAL_TEXT}

    rows = sorted(t["retrieval"], key=lambda r: r["rank"])
    if not rows:
        return {"refused": True, "gate": "score_floor", "citation": None,
                "quote": None, "answer": REFUSAL_TEXT}

    top = rows[0]
    chunk = chunks_by_id[top["chunk_id"]]
    quote = _best_span(chunk.text, t["question"], chunk.metadata.get("kind", ""))
    m = chunk.metadata
    return {"refused": False, "gate": "extractive", "citation": chunk.chunk_id,
            "quote": quote,
            "answer": (f"{quote}\n\n(Per {m.get('form_number')} ed. {m.get('edition_date')}, "
                       f"{m.get('clause')}, policy line {m.get('policy_line')}.)")}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 replay.py <trace_id>")
    t = load(sys.argv[1])

    ingest(t["corpus"]["strategy"], verbose=False)
    live_corpus = corpus_fingerprint(t["corpus"]["strategy"])
    if live_corpus["sha"] != t["corpus"]["sha"]:
        raise SystemExit(
            f"corpus has moved since this trace was written "
            f"({t['corpus']['sha']} -> {live_corpus['sha']}). Replay would prove nothing.")
    if t["policy"]["sha"] != policy_sha() or t["policy"]["id"] != POLICY_ID:
        raise SystemExit(
            f"policy has moved since this trace was written "
            f"({t['policy']['id']}/{t['policy']['sha']} -> {POLICY_ID}/{policy_sha()}).")

    chunks = {c.chunk_id: c for c in get_registry(t["corpus"]["strategy"]).chunks}
    new = rebuild(t, chunks)
    old = t["outcome"]

    print(f"trace     {t['trace_id']}  ({t['run']} / {t['qid']})")
    print(f"question  {t['question']}")
    print(f"corpus    {t['corpus']['sha']}, {t['corpus']['chunks']} chunks - matched")
    print(f"policy    {t['policy']['id']}, sha {t['policy']['sha']} - matched")
    print(f"retriever {t['app']['mode']} / k={t['app']['top_k']} - taken from the trace, not re-run")
    print("\nretrieved (from the trace):")
    for r in sorted(t["retrieval"], key=lambda r: r["rank"]):
        print(f"  {r['rank']}. {r['score']:.4f}  {r['chunk_id']}")

    print("\nORIGINAL\n" + (old["answer"] or "").strip())
    print("\nREPLAYED\n" + (new["answer"] or "").strip())

    checks = [("refused", old["refused"], new["refused"]),
              ("gate", old["gate"], new["gate"]),
              ("citation", old["citation"], new["citation"]),
              ("quote", old["quote"], new["quote"]),
              ("answer text", old["answer"], new["answer"])]
    print("\nfield-by-field:")
    ok = True
    for name, a, b in checks:
        same = a == b
        ok &= same
        print(f"  {'same' if same else 'DIFFERS':<8} {name}")
    print("\nbyte-identical replay" if ok else "\nreplay diverged")


if __name__ == "__main__":
    main()
