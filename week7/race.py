"""Agent vs workflow over the same 10 questions - Week 7.

    python3 -m week7.race                  # both systems -> race.csv + the 8-number table
    python3 -m week7.race --only agent     # one side (rows merge into race_runs.jsonl)

Pass = every applicable deterministic assertion passes (the same code as the Week 6
eval: version stated, code parses, endpoints exist in the spec, no v2 path in v3 code,
deprecations noted, required facts present) and the run finished (not budget-stopped).
Tokens are summed over every call; cost is priced per call from its own usage.
"""
import argparse
import csv
import json
import os
import statistics
import sys

from week7.agent import Budget, run_agent
from src import ROOT, RUNS
from evals.assertions import passed, run_assertions
from evals.common import read_jsonl
from week7.workflow import run_workflow

QUESTIONS = ROOT / "week7" / "race_questions.jsonl"
RUNS_FILE = RUNS / "race_runs.jsonl"
CSV = ROOT / "race.csv"


def score(q: dict, res: dict) -> dict:
    a = run_assertions(q, res["answer"])
    return {"assertions": a, "pass": res["status"] == "done" and passed(a)}


def summarise(rows: list) -> dict:
    n = len(rows)
    return {"n": n, "pass_rate": sum(r["pass"] for r in rows) / n,
            "p50_latency_s": statistics.median(r["latency_s"] for r in rows),
            "total_tokens": sum(r["usage"]["total_tokens"] for r in rows),
            "cost_per_question_usd": sum(r["usage"]["cost_usd"] for r in rows) / n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["agent", "workflow"])
    a = ap.parse_args()
    qs = read_jsonl(QUESTIONS)
    systems = [a.only] if a.only else ["agent", "workflow"]

    rows = [r for r in read_jsonl(RUNS_FILE) if r["system"] not in systems]
    for sysname in systems:
        for q in qs:
            print(f"\n===== {sysname} {q['id']} ({q['class']})")
            res = run_agent(q["question"], Budget()) if sysname == "agent" \
                else run_workflow(q["question"])
            rows.append({"id": q["id"], "class": q["class"], **res, **score(q, res)})
    RUNS.mkdir(exist_ok=True)
    RUNS_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows))

    with CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "id", "class", "pass", "status", "laps", "tool_calls",
                    "latency_s", "total_tokens", "cost_usd", "failed_assertions"])
        for r in sorted(rows, key=lambda r: (r["system"], r["id"])):
            w.writerow([r["system"], r["id"], r["class"], int(r["pass"]), r["status"], r["laps"],
                        len(r["steps"]), r["latency_s"], r["usage"]["total_tokens"],
                        round(r["usage"]["cost_usd"], 6),
                        ";".join(k for k, v in r["assertions"].items() if v is False)])
        w.writerow([])
        w.writerow(["system", "pass_rate", "p50_latency_s", "total_tokens", "cost_per_question_usd"])
        for s in ("agent", "workflow"):
            sr = [r for r in rows if r["system"] == s]
            if sr:
                m = summarise(sr)
                w.writerow([s, round(m["pass_rate"], 3), round(m["p50_latency_s"], 2),
                            m["total_tokens"], round(m["cost_per_question_usd"], 5)])

    print(f"\n{'system':<10}{'pass rate':>12}{'p50 latency':>14}{'total tokens':>15}{'cost/question':>15}")
    for s in ("agent", "workflow"):
        sr = [r for r in rows if r["system"] == s]
        if not sr:
            continue
        m = summarise(sr)
        print(f"{s:<10}{m['pass_rate']:>11.0%} {m['p50_latency_s']:>12.1f}s "
              f"{m['total_tokens']:>14,} {m['cost_per_question_usd']:>14.4f}$")
    print("\nby question class (pass):")
    for cls in sorted({q["class"] for q in qs}):
        print(f"  {cls:<38}" + "  ".join(
            f"{s}: {sum(r['pass'] for r in rows if r['system'] == s and r['class'] == cls)}/"
            f"{sum(1 for r in rows if r['system'] == s and r['class'] == cls)}"
            for s in ("agent", "workflow")))
    print(f"\nwrote {CSV.name}")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
