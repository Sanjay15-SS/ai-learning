"""Ask the endorsement corpus a single question.

    python app.py "Does E-17 apply to a burst supply line under HO-0304?"
    python app.py "..." --strategy baseline
    python app.py "..." --policy-line HO-3
    python app.py --chunk structure_aware::HO-0304@03-24::010

run_pipeline.py is the graded deliverable; this is for poking at the index by hand.
"""
import argparse

from src import RETRIEVAL_MODE, STRATEGIES, TOP_K
from src.generator import answer
from src.indexer import ingest
from src.retriever import get_chunk


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask the indexed endorsements a question.")
    ap.add_argument("question", nargs="?", help="the question to ask")
    ap.add_argument("--strategy", default="structure_aware", choices=list(STRATEGIES))
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--mode", default=RETRIEVAL_MODE, help="retriever: dense (Week 3) or hybrid (Week 4: BM25 + RRF)")
    ap.add_argument("--policy-line", default=None, help="metadata filter, e.g. HO-3")
    ap.add_argument("--chunk", metavar="CHUNK_ID",
                    help="resolve a chunk_id back to its indexed text and exit")
    args = ap.parse_args()

    if not args.question and not args.chunk:
        ap.error("give a question, or --chunk CHUNK_ID")

    # The index is in-memory, so it is built fresh for this process.
    print(f"Indexing endorsements ({args.strategy})...")
    ingest(args.strategy, verbose=False)
    if args.chunk and args.chunk.split("::", 1)[0] != args.strategy:
        ingest(args.chunk.split("::", 1)[0], verbose=False)

    if args.chunk:
        chunk = get_chunk(args.chunk)
        if chunk is None:
            raise SystemExit(f"no chunk '{args.chunk}'")
        m = chunk.metadata
        print(f"\n{chunk.chunk_id}")
        print(f"{m.get('source_file')} | {m.get('form_number')} ed.{m.get('edition_date')} | "
              f"{m.get('policy_line')} | {m.get('clause')}")
        print("-" * 70)
        print(chunk.text)
        return

    filters = {"policy_line": args.policy_line} if args.policy_line else None
    res = answer(args.question, strategy=args.strategy, top_k=args.top_k, filters=filters,
                 mode=args.mode)

    print("\n" + ("REFUSED" if res["refused"] else "ANSWER") +
          f"   (mode={args.mode}, gate={res['gate']}, top_score={res['top_score']})\n")
    print(res["answer"])
    if res["reason"]:
        print(f"\nreason: {res['reason']}")
    for c in res["citations"]:
        print(f"\nsource: {c['form_number']} {c['clause']}  [{c['chunk_id']}]")

    print(f"\nTop {len(res['retrieved'])} retrieved:")
    for r in res["retrieved"]:
        print(f"  {r['rank']}. {r['score']:.4f}  {r['form_number']} ({r['policy_line']})  "
              f"{r['clause']}")


if __name__ == "__main__":
    main()
