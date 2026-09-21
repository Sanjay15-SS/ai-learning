"""The hand-built agent loop - Week 7. Every lap is logged; four budgets are enforced.

    python3 -m week7.agent "We're moving POST /v2/charges code to v3. What does it look like now?"
    python3 -m week7.agent --budget-demo          # a run that hits a budget and stops cleanly
    python3 -m week7.agent --tool-diff            # writes TOOL_DESCRIPTIONS_DIFF.md
    python3 -m week7.agent "..." --max-iters 3 --max-tokens 20000 --max-cost 0.10 --max-wall 30

Budgets are checked BEFORE every call (would the next lap overrun?) and AFTER every
call (did this one?). Tokens and cost are summed over every lap, because each lap
re-sends the whole message list.
"""
import argparse
import difflib
import json
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional

from src import LOGS, ROOT, llm
from src.contract import CONTRACT
from src.tools import TOOLS_THREE, TOOLS_TWO, run_tool

SYSTEM = ("You answer migration questions about the Ledgerline payments API. You have tools; "
          "the documentation is not in your context, so look things up rather than recalling "
          "them. Before you write code: find the relevant endpoint, read the OpenAPI operation "
          "of every endpoint your code calls in the version you target, and check any v2 "
          "endpoint, parameter, header or event the developer mentions for deprecation. If it "
          "is deprecated, look up the replacement's operation too.\n\n" + CONTRACT)


@dataclass
class Budget:
    max_iters: int = 8
    max_tokens: int = 80_000
    max_cost_usd: float = 0.60
    max_wall_s: float = 180.0

    def check(self, laps: int, usage: llm.Usage, elapsed: float,
              next_input_estimate: int = 0) -> Optional[str]:
        """Name of the first budget that is spent, or None."""
        if laps >= self.max_iters:
            return f"max_iters ({laps}/{self.max_iters} laps)"
        if usage.total_tokens + next_input_estimate >= self.max_tokens:
            return (f"max_tokens ({usage.total_tokens:,} used + ~{next_input_estimate:,} next "
                    f"input >= {self.max_tokens:,})")
        if usage.cost_usd >= self.max_cost_usd:
            return f"max_cost (${usage.cost_usd:.4f} >= ${self.max_cost_usd:.2f})"
        if elapsed >= self.max_wall_s:
            return f"max_wall ({elapsed:.1f}s >= {self.max_wall_s:.0f}s)"
        return None


def run_agent(question: str, budget: Budget = Budget(), tools=TOOLS_THREE,
              log: Callable[[str], None] = print) -> dict:
    t0 = time.perf_counter()
    usage = llm.Usage()
    messages = [{"role": "user", "content": question}]
    steps, laps, next_est = [], 0, 0
    final, status = "", "done"
    log(f"[start] {question}")
    while True:
        stop = budget.check(laps, usage, time.perf_counter() - t0, next_est)
        if stop:
            status = "budget:" + stop.split(" ")[0]
            log(f"[stop] budget fired: {stop}. Terminating cleanly after {laps} laps.")
            break
        remaining_wall = budget.max_wall_s - (time.perf_counter() - t0)
        out_cap = max(256, min(8000, budget.max_tokens - usage.total_tokens - next_est))
        r = llm.create(usage, system=SYSTEM, messages=messages, tools=tools,
                       max_tokens=out_cap, timeout=remaining_wall)
        laps += 1
        calls = [b for b in r.content if getattr(b, "type", "") == "tool_use"]
        log(f"[lap {laps}] stop_reason={r.stop_reason} tool_calls={len(calls)} "
            f"in={r.usage.input_tokens} out={r.usage.output_tokens} | total "
            f"{usage.total_tokens:,} tok ${usage.cost_usd:.4f} {time.perf_counter() - t0:.1f}s")
        if r.stop_reason == "refusal":
            status = "refused"
            break
        if r.stop_reason == "max_tokens":           # a tool call cut off mid-JSON is not run
            final, status = llm.text_of(r), "truncated"
            break
        if r.stop_reason in ("end_turn", "stop_sequence") or not calls:
            final = llm.text_of(r)
            break
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in calls:
            out = run_tool(b.name, dict(b.input))
            steps.append({"lap": laps, "tool": b.name, "input": dict(b.input),
                          "output_chars": len(out)})
            log(f"    -> {b.name}({json.dumps(dict(b.input))}) => {out[:140]}"
                + ("..." if len(out) > 140 else ""))
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        messages.append({"role": "user", "content": results})
        # The next lap re-sends everything: last input + last output + new tool results.
        next_est = (r.usage.input_tokens + r.usage.output_tokens
                    + sum(len(x["content"]) for x in results) // 3)
    latency = time.perf_counter() - t0
    log(f"[end] status={status} laps={laps} tools={len(steps)} tokens={usage.total_tokens:,} "
        f"cost=${usage.cost_usd:.4f} latency={latency:.1f}s")
    return {"system": "agent", "question": question, "answer": final, "status": status,
            "laps": laps, "steps": steps, "latency_s": round(latency, 3), "usage": usage.as_dict()}


def tool_diff() -> None:
    a = json.dumps(TOOLS_TWO, indent=2).splitlines()
    b = json.dumps(TOOLS_THREE, indent=2).splitlines()
    diff = "\n".join(difflib.unified_diff(a, b, "TOOLS_TWO (before)", "TOOLS_THREE (after)",
                                          lineterm=""))
    out = ROOT / "TOOL_DESCRIPTIONS_DIFF.md"
    out.write_text("# Tool description diff - the third tool, and the overlap it removed\n\n"
                   "Before, `search_docs` and `get_openapi_spec` both claimed \"documentation\", "
                   "\"endpoints\" and \"details\", and `api_version` was a free string. After, each "
                   "tool names one job and what it does not do; `api_version` and `method` are "
                   "enums; `check_deprecation` is new and overlaps neither.\n\n```diff\n"
                   + diff + "\n```\n", encoding="utf-8")
    print(f"wrote {out.name}")


BUDGET_DEMO_Q = ("Migrating to v3: our v2 code creates a customer with card_token in one call, "
                 "then lists their cards with GET /v2/customers/{customer_id}/cards and charges "
                 "with POST /v2/charges using source. Rewrite all three steps for v3.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--budget-demo", action="store_true")
    ap.add_argument("--tool-diff", action="store_true")
    ap.add_argument("--two-tools", action="store_true", help="run with the old TOOLS_TWO")
    ap.add_argument("--max-iters", type=int, default=Budget.max_iters)
    ap.add_argument("--max-tokens", type=int, default=Budget.max_tokens)
    ap.add_argument("--max-cost", type=float, default=Budget.max_cost_usd)
    ap.add_argument("--max-wall", type=float, default=Budget.max_wall_s)
    a = ap.parse_args()
    if a.tool_diff:
        return tool_diff()
    budget = Budget(a.max_iters, a.max_tokens, a.max_cost, a.max_wall)
    q = a.question
    if a.budget_demo:
        q, budget = BUDGET_DEMO_Q, Budget(max_iters=2)
    if not q:
        ap.error("give a question, --budget-demo or --tool-diff")

    LOGS.mkdir(exist_ok=True)
    path = LOGS / ("budget_termination.log" if a.budget_demo else "agent_last.log")
    with path.open("w", encoding="utf-8") as fh:
        def log(line):
            print(line)
            fh.write(line + "\n")
        log(f"budget: {budget}")
        res = run_agent(q, budget, TOOLS_TWO if a.two_tools else TOOLS_THREE, log)
        log("\n--- answer ---\n" + (res["answer"] or "(none: " + res["status"] + ")"))
    print(f"\nlog written to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
    sys.exit(0)
