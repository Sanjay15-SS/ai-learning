"""Lay traces out for reading. Computes nothing.

    python3 show.py --sample                 # the seeded 20, in full
    python3 show.py --trace trc_xxxx         # one trace
    python3 show.py --file traces/demo.jsonl --all

This is a viewer. It does not label, count, group or judge - every number in
taxonomy.md came from reading this output, not from a script that produced it.
"""
import argparse
from pathlib import Path

from sample import SEED, draw
from trace import read_traces

TRACES = Path(__file__).resolve().parent / "traces" / "traces.jsonl"
RULE = "-" * 78


def show(t: dict, n=None) -> None:
    head = f"[{n}] " if n else ""
    print(f"{head}{t['trace_id']}   {t['run']}/{t['qid']}   {t['latency_ms']} ms")
    print(f"Q: {t['question']}")
    g = t["gates"]
    print(f"gates: coverage {g['coverage']} (floor {g['coverage_floor']})"
          + (f"  missing {g['missing_terms']}" if g["missing_terms"] else "")
          + (f"  best_cosine {g['best_cosine']}" if g["best_cosine"] is not None else ""))
    print("retrieved:")
    for r in sorted(t["retrieval"], key=lambda r: r["rank"]):
        codes = ",".join(r["exclusion_codes"]) or r["clause"]
        print(f"  {r['rank']}. {r['score']:.4f}  {r['form_number']}@{r['edition_date']} "
              f"{codes:<12s} {r['chunk_id']}")
    o = t["outcome"]
    print(f"outcome: {'REFUSED' if o['refused'] else 'ANSWERED'}  gate={o['gate']}  "
          f"cited={o['citation'] or '-'}")
    for line in (o["answer"] or "").strip().splitlines():
        print(f"  | {line}")
    print(f"redaction: {t['redaction']['total']} removed {t['redaction']['counts'] or ''}")
    print(RULE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(TRACES))
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--trace")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    traces = read_traces(Path(args.file))
    if args.trace:
        picked = [t for t in traces if t["trace_id"] == args.trace]
    elif args.sample:
        picked = draw(traces, args.seed, args.n)
    elif args.all:
        picked = traces
    else:
        raise SystemExit("give --sample, --all, or --trace <id>")

    print(RULE)
    for i, t in enumerate(picked, 1):
        show(t, i)


if __name__ == "__main__":
    main()
