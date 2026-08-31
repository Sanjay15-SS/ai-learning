"""Inspection view for one question - the thing you open BEFORE labelling a failure.

    python inspect_query.py "does exclusion E-17 apply under form HO-0304 ed. 03-24"
    python inspect_query.py --qid G01                # a golden-set question, with its gold chunk_id
    python inspect_query.py --qid G01 --mode dense
    python inspect_query.py "..." --gold structure_aware::HO-0304@03-24::010
"""
import argparse
import os
import sys

from src import RETRIEVAL_MODE
from src.indexer import ingest
from src.inspect_view import inspect, load_golden, render


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--qid", help="golden_set.jsonl qid, e.g. G01")
    ap.add_argument("--gold", help="chunk_id you know is correct")
    ap.add_argument("--mode", default=RETRIEVAL_MODE)
    ap.add_argument("--show", type=int, default=5, help="candidates to print")
    args = ap.parse_args()

    q, gold = args.question, args.gold
    if args.qid:
        row = next((r for r in load_golden() if r["qid"] == args.qid), None)
        if row is None:
            raise SystemExit(f"no qid {args.qid} in golden_set.jsonl")
        q, gold = row["question"], row["gold_chunk_id"]
    if not q:
        ap.error("give a question or --qid")

    ingest("structure_aware", verbose=False)
    print(render(inspect(q, gold, mode=args.mode), show=args.show))


if __name__ == "__main__":
    main()
    # Chroma's in-memory client and the ONNX session race each other at interpreter
    # teardown and print a recursive_mutex error after the output is already complete.
    # The work is done here; exit without running their atexit hooks.
    sys.stdout.flush()
    os._exit(0)
