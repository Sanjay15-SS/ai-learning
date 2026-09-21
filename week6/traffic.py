"""Run app v1 over desk traffic and trace every answer. Failed traces are where the
regression cases come from.

    python3 -m week6.traffic            # -> traces/traces.jsonl  (refuses to overwrite)
    python3 -m week6.traffic --failed   # list the traces that failed an assertion

Questions are written the way developers actually type them, with no expected answers.
The assertion results stored on each trace are the free, deterministic ones only.
"""
import json
import os
import sys

from src import TRACES
from src.assistant import answer
from src.contract import target_version
from evals.assertions import passed, run_assertions
from evals.common import now, read_jsonl, sha256_text

PATH = TRACES / "traces.jsonl"

DESK = [
 "how do i create a charge in v3",
 "we're moving to v3 - what replaces POST /v2/charges?",
 "refund half of a payment, v3",
 "list cards on a customer (current api)",
 "get customer 2 pages at a time v3",
 "is api_key query param still ok in v3?",
 "webhook signature check v3 python",
 "what header does the v3 webhook signature come in",
 "migrate our v2 refunds code that passes charge=ch_123 to v3",
 "v3: create customer and save their card",
 "how to capture later instead of immediately",
 "what happens if I reuse an idempotency key with a different body",
 "retry strategy for 429 on v3",
 "which errors should I not retry",
 "stay on v2 for now - how do I list a customer's cards?",
 "we're still on v2: paginate customers",
 "delete webhook v3",
 "update customer metadata v3",
 "confirm a payment intent after collecting the card",
 "get a payment intent by id",
 "is there a sandbox for testing",
 "how do I issue a payout",
 "does ledgerline support apple pay",
 "list refunds for pi_123",
 "event name for a successful payment in v3",
 "what does requires_capture mean",
 "how long until an uncaptured payment is cancelled",
 "v3 limit param max value",
 "what's the difference between confirm=true and calling /confirm",
 "we pass source=tok_visa on v3 and get a 400 - why",
]


def main() -> None:
    if "--failed" in sys.argv:
        for t in read_jsonl(PATH):
            if not t["assertions_pass"]:
                bad = [k for k, v in t["assertions"].items() if v is False]
                print(f"{t['trace_id']}  {', '.join(bad):<40} {t['question']}")
        return
    if PATH.exists():
        raise SystemExit(f"{PATH} exists; delete it to re-run the traffic")
    TRACES.mkdir(exist_ok=True)
    with PATH.open("a", encoding="utf-8") as fh:
        for i, q in enumerate(DESK, 1):
            r = answer(q, app="v1")
            pseudo_case = {"id": f"T{i:03d}", "question": q, "api_version": target_version(q),
                           "needs_code": False, "expect_refusal": False, "must_include": []}
            res = run_assertions(pseudo_case, r["answer"])
            t = {"trace_id": "trc_" + sha256_text(f"desk|{q}")[:12], "ts": now(), **r,
                 "api_version": pseudo_case["api_version"], "assertions": res,
                 "assertions_pass": passed(res)}
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"  {i:>2}/{len(DESK)} {'ok  ' if t['assertions_pass'] else 'FAIL'} {q}")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
