"""Fill the trace files.

    python3 run_traffic.py          # 117 desk questions -> traces/traces.jsonl
    python3 run_traffic.py demo     # 10 review questions -> traces/demo.jsonl

Refuses to overwrite an existing trace file. Traces are the evidence this week is
read from; silently replacing them with a second run under different code is how a
taxonomy stops describing anything. Delete the file if you mean it.
"""
import os
import sys
from pathlib import Path

from assistant import STRATEGY, run_question
from questions import DEMO_SET, DESK_SET
from src.indexer import ingest
from trace import TraceWriter, corpus_fingerprint

TRACE_DIR = Path(__file__).resolve().parent / "traces"
RUNS = {"desk": (DESK_SET, "traces.jsonl"), "demo": (DEMO_SET, "demo.jsonl")}


def main() -> None:
    run = sys.argv[1] if len(sys.argv) > 1 else "desk"
    if run not in RUNS:
        raise SystemExit(f"unknown run '{run}'; expected one of {sorted(RUNS)}")
    qs, filename = RUNS[run]

    TRACE_DIR.mkdir(exist_ok=True)
    path = TRACE_DIR / filename
    if path.exists():
        raise SystemExit(
            f"{path} already exists with {sum(1 for _ in path.open())} traces. "
            f"Delete it if you intend to re-run this traffic.")

    print(f"ingesting {STRATEGY} ...")
    report = ingest(STRATEGY, verbose=False)
    corpus = corpus_fingerprint(STRATEGY)
    print(f"corpus {corpus['sha']}, {report['chunks']} chunks")

    writer = TraceWriter(path, run)
    refused = 0
    for i, (qid, question) in enumerate(qs, 1):
        rec = run_question(qid, question, run, corpus=corpus)
        clean = writer.write(rec)
        refused += clean["outcome"]["refused"]
        print(f"  {i:>3}/{len(qs)}  {qid}  {clean['outcome']['gate']:<14s} "
              f"{clean['outcome']['citation'] or '-'}")

    print(f"\nwrote {writer.written} traces to {path}")
    print(f"refusals: {refused}/{writer.written}")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)          # Chroma and the ONNX session race at interpreter teardown
