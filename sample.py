"""The seeded random draw.

    python3 sample.py                      # the 20 to read, seed 20250907
    python3 sample.py --seed N --n K
    python3 sample.py --replay-pick        # one trace, drawn with a second seed

Trace ids are sorted before sampling, so the order lines happen to sit in the file
cannot affect which 20 come out. The same seed gives the same 20 on any machine.

The replay trace is drawn with its own seed rather than chosen after the reading, so
it cannot be the one that happened to replay well.
"""
import argparse
import random
from pathlib import Path

from trace import read_traces

TRACES = Path(__file__).resolve().parent / "traces" / "traces.jsonl"
SEED = 20250907


def draw(traces, seed: int, n: int):
    ids = sorted(t["trace_id"] for t in traces)
    rng = random.Random(seed)
    picked = set(rng.sample(ids, min(n, len(ids))))
    return [t for t in sorted(traces, key=lambda t: t["trace_id"]) if t["trace_id"] in picked]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--replay-pick", action="store_true",
                    help="draw the single trace to replay, with seed+1")
    ap.add_argument("--file", default=str(TRACES))
    args = ap.parse_args()

    traces = read_traces(Path(args.file))
    if args.replay_pick:
        one = draw(traces, args.seed + 1, 1)[0]
        print(one["trace_id"])
        print(f"  {one['qid']}  {one['question']}")
        return

    picked = draw(traces, args.seed, args.n)
    print(f"population {len(traces)}, seed {args.seed}, n {args.n}\n")
    print(f"{'#':>3}  {'trace_id':<18} {'qid':<5} question")
    for i, t in enumerate(picked, 1):
        q = t["question"] if len(t["question"]) <= 78 else t["question"][:75] + "..."
        print(f"{i:>3}  {t['trace_id']:<18} {t['qid']:<5} {q}")


if __name__ == "__main__":
    main()
