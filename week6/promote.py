"""Turn a real failed trace into a permanent regression case, question verbatim.

    python3 -m week6.promote trc_xxxxxxxxxxxx --mode version_confusion \
        --must /v3/refunds payment_intent [--no-code] [--refusal]

The question is copied byte-for-byte from the trace and the failing answer is stored
on the case, so the case records what it is guarding against.
"""
import argparse
import json

from evals.common import CASES, load_cases, read_jsonl
from week6.traffic import PATH

MODES = ["version_confusion", "deprecated_no_migration", "hallucinated_endpoint",
         "broken_sample", "unanswerable", "conceptual"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_id")
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument("--must", nargs="*", default=[])
    ap.add_argument("--no-code", action="store_true")
    ap.add_argument("--refusal", action="store_true")
    ap.add_argument("--reference", default="")
    a = ap.parse_args()

    t = next((t for t in read_jsonl(PATH) if t["trace_id"] == a.trace_id), None)
    if t is None:
        raise SystemExit(f"no trace {a.trace_id} in {PATH}")
    cases = load_cases()
    if any(c.get("source") == f"trace:{a.trace_id}" for c in cases):
        raise SystemExit("already promoted")
    n = sum(c.get("source", "").startswith("trace:") for c in cases) + 1
    case = {"id": f"R{n:02d}", "mode": a.mode, "question": t["question"],
            "api_version": t["api_version"], "needs_code": not a.no_code,
            "expect_refusal": a.refusal, "must_include": a.must, "reference": a.reference,
            "source": f"trace:{a.trace_id}", "failed_answer": t["answer"],
            "failed_assertions": [k for k, v in t["assertions"].items() if v is False]}
    with CASES.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(case) + "\n")
    print(f"added {case['id']} ({a.mode}) from {a.trace_id}: {t['question']}")


if __name__ == "__main__":
    main()
