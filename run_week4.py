"""Week 4 - Task Set D: label the failures, then buy back hit-rate@3 with ONE change.

    python run_week4.py            # measures every retrieval mode in src.retriever.MODES,
                                   # writes results.md + eval_record.json
    python run_week4.py --freeze   # write baseline_record.json (dense) - run BEFORE any change

Same 12 golden questions, same index, same embedding model, same top-3 in every run.
The only variable between the "before" and "after" columns is the retrieval mode.
"""
import argparse
import json
import statistics
import time
from datetime import datetime, timezone

from src import EMBED_MODEL, GOLDEN_SET_PATH, ROOT, STRATEGIES
from src.indexer import get_registry, ingest
from src.inspect_view import inspect, load_golden, render
from src.mmr import mmr_order, top3_diversity
from src.retriever import CANDIDATES, MODES, search, search_explain

STRATEGY = "structure_aware"
TOP_K = 3
LATENCY_REPS = 7
BASELINE_RECORD = ROOT / "baseline_record.json"
EVAL_RECORD = ROOT / "eval_record.json"
PROBES = ROOT / "probes.jsonl"


def p50_p95(samples):
    s = sorted(samples)
    return statistics.median(s), s[int(round(0.95 * (len(s) - 1)))]


def measure_latency(questions, mode):
    """Wall-clock per search() call, question embedding included. Warm-up first."""
    for q in questions[:3]:
        search(q, strategy=STRATEGY, top_k=TOP_K, mode=mode)
    samples = []
    for _ in range(LATENCY_REPS):
        for q in questions:
            t0 = time.perf_counter()
            search(q, strategy=STRATEGY, top_k=TOP_K, mode=mode)
            samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def evaluate(golden, mode):
    rows = []
    for g in golden:
        v = inspect(g["question"], g["gold_chunk_id"], strategy=STRATEGY, mode=mode, top_k=TOP_K)
        rows.append({"qid": g["qid"], "hit": v["hit"], "gold_rank": v["gold_rank"],
                     "label": v["label"], "cause": v["cause"], "coverage": v["coverage"],
                     "missing_terms": v["missing_terms"],
                     "evidence": v["evidence"], "answer_ok": v["answer_ok"],
                     "cited": v["cited"], "top_ids": v["top_ids"],
                     "stages": {c.chunk.chunk_id: c.stages for c in v["candidates"]},
                     "view": render(v, show=5)})
    return rows


def summarise(rows):
    return {"hits": sum(r["hit"] for r in rows), "n": len(rows),
            "answer_ok": sum(r["answer_ok"] for r in rows),
            "labels": {lab: sum(1 for r in rows if r["label"] == lab)
                       for lab in ("PASS", "R", "G", "NIC")},
            "causes": {c: sum(1 for r in rows if r["cause"] == c)
                       for c in ("PASS", "R", "G-rank", "G-refuse", "NIC")}}


MMR_LAMBDAS = (1.0, 0.9, 0.8, 0.7, 0.5, 0.3)


def mmr_sweep(golden, mode="hybrid"):
    """Bonus: MMR over the fused candidates. lambda=1.0 is plain RRF order (the
    control). Reported: hit-rate@3 AND how diverse the top-3 became."""
    base = {g["qid"]: search_explain(g["question"], strategy=STRATEGY, mode=mode,
                                     candidates=CANDIDATES) for g in golden}
    out = {"lambdas": [], "per_question": {}}
    for lam in MMR_LAMBDAS:
        hits, divs, rows = 0, [], {}
        for g in golden:
            top = mmr_order(base[g["qid"]], STRATEGY, lam, 3)
            hit = g["gold_chunk_id"] in [c.chunk.chunk_id for c in top]
            hits += hit
            d = top3_diversity(top, STRATEGY)
            divs.append(d)
            rows[g["qid"]] = {"hit": hit, "top_ids": [c.chunk.chunk_id for c in top], **d}
        out["lambdas"].append({
            "lambda": lam, "hits": hits, "n": len(golden),
            "mean_pairwise_cos": sum(d["mean_pairwise_cos"] for d in divs) / len(divs),
            "mean_distinct_rows": sum(d["distinct_rows"] for d in divs) / len(divs),
            "mean_distinct_editions": sum(d["distinct_editions"] for d in divs) / len(divs)})
        out["per_question"][lam] = rows
        print(f"  MMR lambda={lam:<4} hit-rate@3 = {hits}/{len(golden)}  "
              f"mean pairwise cos(top-3) = {out['lambdas'][-1]['mean_pairwise_cos']:.3f}  "
              f"distinct rows = {out['lambdas'][-1]['mean_distinct_rows']:.2f}/3")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true",
                    help="write baseline_record.json from the dense retriever and exit")
    args = ap.parse_args()

    golden = load_golden()
    questions = [g["question"] for g in golden]
    print(f"golden set: {len(golden)} questions from {GOLDEN_SET_PATH.name}")
    print(f"embedding: {EMBED_MODEL}; ingesting {STRATEGY} ...")
    report = ingest(STRATEGY)

    record = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "embed_model": EMBED_MODEL, "chunks": report["chunks"], "top_k": TOP_K,
              "latency_reps": LATENCY_REPS, "modes": {}}

    modes = ["dense"] if args.freeze else list(MODES)
    for mode in modes:
        print(f"\n=== mode: {mode} ===")
        rows = evaluate(golden, mode)
        summ = summarise(rows)
        lat = measure_latency(questions, mode)
        p50, p95 = p50_p95(lat)
        record["modes"][mode] = {"rows": rows, "summary": summ,
                                 "latency_ms": {"p50": p50, "p95": p95,
                                                "samples": len(lat)}}
        print(f"hit-rate@3 = {summ['hits']}/{summ['n']}   answer_ok = {summ['answer_ok']}/{summ['n']}   "
              f"p50 = {p50:.1f} ms  p95 = {p95:.1f} ms")
        print(f"  labels {summ['labels']}  ->  causes {summ['causes']}")
        for r in rows:
            print(f"  {r['qid']}  {'HIT ' if r['hit'] else 'MISS'}  rank={str(r['gold_rank']):>4s}  "
                  f"{r['cause']:<9s} {r['evidence'][:88]}")

    if args.freeze:
        dense = record["modes"]["dense"]
        frozen = {"frozen_at": record["generated"], "mode": "dense", "top_k": TOP_K,
                  "chunks": report["chunks"], "hit_rate_at_3": f"{dense['summary']['hits']}/{dense['summary']['n']}",
                  "p50_ms": round(dense["latency_ms"]["p50"], 2),
                  "per_question": {r["qid"]: {"hit": r["hit"], "gold_rank": r["gold_rank"], "label": r["label"]}
                                   for r in dense["rows"]}}
        BASELINE_RECORD.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
        print(f"\nbaseline written to {BASELINE_RECORD.name}: hit-rate@3 {frozen['hit_rate_at_3']}, "
              f"p50 {frozen['p50_ms']} ms")
        return

    print("\n=== bonus: MMR over the fused candidate list ===")
    # Not-in-corpus probe (not counted in hit-rate; demonstrates the NIC label).
    probes = [json.loads(l) for l in PROBES.read_text(encoding="utf-8").splitlines() if l.strip()]
    record["probes"] = []
    for p in probes:
        v = inspect(p["question"], p["gold_chunk_id"], strategy=STRATEGY, mode=modes[0], top_k=TOP_K)
        record["probes"].append({"qid": p["qid"], "question": p["question"], "note": p["note"],
                                 "label": v["label"], "evidence": v["evidence"], "view": render(v, show=3)})

    # Bonus - MMR over the FUSED candidate list. Tuned once, on this grid, then stopped.
    record["mmr"] = mmr_sweep(golden)

    if BASELINE_RECORD.exists():
        record["baseline_record"] = json.loads(BASELINE_RECORD.read_text(encoding="utf-8"))

    EVAL_RECORD.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote {EVAL_RECORD.name}")

    from write_results import write_results   # noqa: E402  (report writer, separate file)
    write_results(record, golden)


if __name__ == "__main__":
    main()
