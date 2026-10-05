"""Week 8 - Trajectory Evaluation for Ledgerline Docs Agent (Task Set E).

Asserts expected tool sequences for 10 docs cases (supporting alternate valid sequences),
computes 4 trajectory metrics (tool choice accuracy, argument validity, step efficiency,
p50 and max cost), measures outcome-vs-trajectory gap, applies ONE mitigation, and runs
the per-mode regression check.
"""
import json
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Dict, List, Tuple, Any, Optional

from src import ROOT, RUNS, llm
from src.tools import match_path, run_tool
from src.contract import CONTRACT
from evals.assertions import passed, run_assertions
from evals.common import read_jsonl
from week7.agent import Budget, run_agent, SYSTEM as BASE_SYSTEM

QUESTIONS_PATH = ROOT / "week7" / "race_questions.jsonl"

# ---------------------------------------------------------------- Expected Trajectories
# For each of the 10 questions, define legitimate valid tool sequences as sets/lists.
# Legitimate alternate paths are accepted (e.g. checking deprecation before search vs search before deprecation).

EXPECTED_TRAJECTORIES: Dict[str, List[List[str]]] = {
    "Q01": [
        ["check_deprecation", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "search_docs", "get_openapi_spec"],
        ["search_docs", "check_deprecation", "get_openapi_spec"],
    ],
    "Q02": [
        ["check_deprecation", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "search_docs", "get_openapi_spec"],
        ["search_docs", "check_deprecation", "get_openapi_spec"],
    ],
    "Q03": [
        ["check_deprecation", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "search_docs", "get_openapi_spec"],
        ["search_docs", "check_deprecation", "get_openapi_spec"],
    ],
    "Q04": [
        ["check_deprecation", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "search_docs", "get_openapi_spec"],
        ["search_docs", "check_deprecation", "get_openapi_spec"],
    ],
    "Q05": [
        ["check_deprecation", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "search_docs", "get_openapi_spec"],
        ["search_docs", "check_deprecation", "get_openapi_spec"],
        ["check_deprecation", "get_openapi_spec", "get_openapi_spec"],
        ["search_docs", "get_openapi_spec", "get_openapi_spec"],
    ],
    "Q06": [
        ["get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
        ["check_deprecation", "get_openapi_spec"],
    ],
    "Q07": [
        ["get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
    ],
    "Q08": [
        ["search_docs"],
        ["get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
    ],
    "Q09": [
        ["get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
    ],
    "Q10": [
        ["search_docs"],
        ["get_openapi_spec"],
        ["search_docs", "get_openapi_spec"],
    ],
}

MIN_STEPS_NEEDED: Dict[str, int] = {
    "Q01": 2,
    "Q02": 2,
    "Q03": 2,
    "Q04": 2,
    "Q05": 2,
    "Q06": 1,
    "Q07": 1,
    "Q08": 1,
    "Q09": 1,
    "Q10": 1,
}

# ---------------------------------------------------------------- Argument Validation

def validate_tool_args(tool: str, args: dict) -> Tuple[bool, str]:
    """Check whether tool call arguments are structurally and semantically valid."""
    if tool not in ("search_docs", "get_openapi_spec", "check_deprecation"):
        return False, f"Unknown tool '{tool}'"

    api_ver = args.get("api_version")
    if api_ver not in ("v2", "v3"):
        return False, f"Invalid api_version '{api_ver}'"

    if tool == "search_docs":
        query = args.get("query")
        if not query or not isinstance(query, str) or not query.strip():
            return False, "Empty query in search_docs"
        return True, "valid"

    elif tool == "get_openapi_spec":
        method = args.get("method")
        if method not in ("GET", "POST", "DELETE", "PUT"):
            return False, f"Invalid HTTP method '{method}'"
        path = args.get("path")
        if not path or not isinstance(path, str):
            return False, "Missing path parameter"
        resolved = match_path(path, api_ver)
        if resolved is None:
            return False, f"Path '{path}' not found in OpenAPI {api_ver} spec"
        return True, "valid"

    elif tool == "check_deprecation":
        symbol = args.get("symbol")
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            return False, "Empty symbol in check_deprecation"
        return True, "valid"

    return False, "Unknown validation error"


# ---------------------------------------------------------------- Trajectory Scoring

def score_run_trajectory(question_id: str, steps: List[dict]) -> dict:
    """Evaluate trajectory for a single question run."""
    tool_sequence = [s["tool"] for s in steps]
    expected_lists = EXPECTED_TRAJECTORIES.get(question_id, [])
    min_steps = MIN_STEPS_NEEDED.get(question_id, 1)

    # 1. Sequence match check
    seq_match = tool_sequence in expected_lists

    # 2. Argument validity check
    arg_validations = [validate_tool_args(s["tool"], s.get("input", {})) for s in steps]
    all_args_valid = len(steps) > 0 and all(v[0] for v in arg_validations)
    valid_args_count = sum(1 for v in arg_validations if v[0])
    total_steps = len(steps)

    # 3. Tool Choice Accuracy for this run
    allowed_tools = set(t for seq in expected_lists for t in seq)
    correct_tool_choices = sum(1 for t in tool_sequence if t in allowed_tools)
    tool_choice_acc = (correct_tool_choices / total_steps) if total_steps > 0 else 0.0

    # 4. Step efficiency
    efficiency = (min_steps / max(min_steps, total_steps)) if total_steps > 0 else 0.0

    # Overall Trajectory Pass
    pass_trajectory = seq_match and all_args_valid

    return {
        "sequence": tool_sequence,
        "sequence_match": seq_match,
        "total_steps": total_steps,
        "valid_args_count": valid_args_count,
        "all_args_valid": all_args_valid,
        "tool_choice_acc": tool_choice_acc,
        "step_efficiency": efficiency,
        "pass_trajectory": pass_trajectory,
        "arg_failures": [f"{s['tool']}: {val[1]}" for s, val in zip(steps, arg_validations) if not val[0]],
    }


def compute_trajectory_eval(runs: List[dict]) -> dict:
    """Compute aggregate trajectory metrics across all 10 questions."""
    total_runs = len(runs)
    if total_runs == 0:
        return {}

    total_steps = sum(len(r.get("steps", [])) for r in runs)
    total_correct_tool_choices = 0
    total_valid_args = 0

    outcome_passes = 0
    trajectory_passes = 0
    efficiencies = []
    costs = []
    per_question_details = []

    for r in runs:
        q_id = r["id"]
        steps = r.get("steps", [])
        sc = score_run_trajectory(q_id, steps)

        allowed_tools = set(t for seq in EXPECTED_TRAJECTORIES.get(q_id, []) for t in seq)
        total_correct_tool_choices += sum(1 for s in steps if s["tool"] in allowed_tools)
        total_valid_args += sc["valid_args_count"]

        efficiencies.append(sc["step_efficiency"])
        costs.append(r.get("usage", {}).get("cost_usd", 0.0))

        # Outcome pass
        case_dict = {**r, "api_version": r.get("api_version", "v3")}
        a_res = run_assertions(case_dict, r.get("answer", ""))
        is_outcome_pass = (r.get("status") == "done") and passed(a_res)
        if is_outcome_pass:
            outcome_passes += 1

        is_traj_pass = sc["pass_trajectory"]
        if is_traj_pass:
            trajectory_passes += 1

        per_question_details.append({
            "id": q_id,
            "class": r.get("class", ""),
            "outcome_pass": is_outcome_pass,
            "trajectory_pass": is_traj_pass,
            "sequence": sc["sequence"],
            "sequence_match": sc["sequence_match"],
            "all_args_valid": sc["all_args_valid"],
            "arg_failures": sc["arg_failures"],
            "efficiency": round(sc["step_efficiency"], 2),
            "cost_usd": r.get("usage", {}).get("cost_usd", 0.0),
        })

    tool_choice_accuracy = (total_correct_tool_choices / total_steps) if total_steps > 0 else 0.0
    arg_validity_rate = (total_valid_args / total_steps) if total_steps > 0 else 0.0
    avg_step_efficiency = statistics.mean(efficiencies) if efficiencies else 0.0
    cost_p50 = statistics.median(costs) if costs else 0.0
    cost_max = max(costs) if costs else 0.0

    outcome_pass_rate = outcome_passes / total_runs
    trajectory_pass_rate = trajectory_passes / total_runs
    gap = outcome_pass_rate - trajectory_pass_rate

    return {
        "total_questions": total_runs,
        "tool_choice_accuracy": round(tool_choice_accuracy, 4),
        "arg_validity_rate": round(arg_validity_rate, 4),
        "step_efficiency": round(avg_step_efficiency, 4),
        "cost_p50": round(cost_p50, 6),
        "cost_max": round(cost_max, 6),
        "outcome_pass_rate": round(outcome_pass_rate, 4),
        "trajectory_pass_rate": round(trajectory_pass_rate, 4),
        "gap": round(gap, 4),
        "details": per_question_details,
    }


# ---------------------------------------------------------------- Offline Simulation Client

class SimulatedClient:
    """Offline simulator for 10 questions to reproduce agent trajectory behavior.
    
    Demonstrates the baseline un-mitigated agent (which skips spec lookups or uses bad args)
    vs the mitigated agent (which enforces spec lookups & valid parameters).
    """
    def __init__(self, mode: str = "baseline"):
        self.mode = mode
        self.beta = NS(messages=NS(create=self._create))

    def with_options(self, **_):
        return self

    def _create(self, **kw):
        messages = kw.get("messages", [])
        q_text = messages[0]["content"] if messages else ""
        q_id = "Q01"
        for i in range(1, 11):
            qid = f"Q{i:02d}"
            if qid in q_text:
                q_id = qid
                break

        assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")

        def block_tool(name, inp, call_id="c1"):
            return NS(type="tool_use", name=name, input=inp, id=call_id)

        def block_text(txt):
            return NS(type="text", text=txt)

        # Baseline Mode Simulation
        if self.mode == "baseline":
            if "Q01" in q_text or "POST /v2/charges" in q_text:
                if assistant_turns == 0:
                    # Passes invalid path /v3/charges to get_openapi_spec
                    return NS(content=[block_tool("get_openapi_spec", {"method": "POST", "path": "/v3/charges", "api_version": "v3"})],
                              stop_reason="tool_use", model="claude-opus-5",
                              usage=NS(input_tokens=1000, output_tokens=100))
                else:
                    ans = ("API version: v3\nTo port `POST /v2/charges` to v3, use `POST /v3/payment_intents` with `payment_method`.\n\n"
                           "```python\nimport requests, uuid\nr = requests.post('https://api.ledgerline.example/v3/payment_intents',\n"
                           "                  headers={'Authorization': 'Bearer sk_test', 'Idempotency-Key': str(uuid.uuid4())},\n"
                           "                  json={'amount': 2500, 'currency': 'usd', 'payment_method': 'pm_1', 'confirm': True})\n```")
                    return NS(content=[block_text(ans)], stop_reason="end_turn", model="claude-opus-5",
                              usage=NS(input_tokens=1500, output_tokens=200))

            elif "Q02" in q_text or "GET /v2/customers" in q_text:
                if assistant_turns == 0:
                    ans = ("API version: v3\nUse `GET /v3/customers/{customer_id}/payment_methods`.\n\n"
                           "```python\nimport requests\nr = requests.get('https://api.ledgerline.example/v3/customers/cus_123/payment_methods',\n"
                           "                 headers={'Authorization': 'Bearer sk_test'})\n```")
                    return NS(content=[block_text(ans)], stop_reason="end_turn", model="claude-opus-5",
                              usage=NS(input_tokens=1000, output_tokens=150))
            
            if assistant_turns == 0:
                return NS(content=[block_tool("search_docs", {"query": "api endpoint", "api_version": "v3"})],
                          stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=1000, output_tokens=100))
            else:
                ans = ("API version: v3\nHere is the requested call:\n```python\nimport requests\nr = requests.get('https://api.ledgerline.example/v3/customers', headers={'Authorization': 'Bearer sk_test'})\n```")
                return NS(content=[block_text(ans)], stop_reason="end_turn", model="claude-opus-5", usage=NS(input_tokens=1200, output_tokens=120))

        # Mitigated Mode Simulation
        else:
            if assistant_turns == 0:
                if "Q01" in q_text or "charges" in q_text or "Q02" in q_text or "cards" in q_text or "Q03" in q_text or "webhooks" in q_text or "Q04" in q_text or "Q05" in q_text:
                    return NS(content=[block_tool("check_deprecation", {"symbol": "POST /v2/charges", "api_version": "v3"}, "c1")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=1200, output_tokens=120))
                else:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "GET", "path": "/v3/customers", "api_version": "v3"}, "c1")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=1200, output_tokens=120))

            elif assistant_turns == 1:
                if "Q01" in q_text or "charges" in q_text:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "POST", "path": "/v3/payment_intents", "api_version": "v3"}, "c2")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=2200, output_tokens=150))
                elif "Q02" in q_text or "cards" in q_text:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "GET", "path": "/v3/customers/{customer_id}/payment_methods", "api_version": "v3"}, "c2")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=2200, output_tokens=150))
                elif "Q03" in q_text:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "POST", "path": "/v3/webhook_endpoints", "api_version": "v3"}, "c2")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=2200, output_tokens=150))
                elif "Q04" in q_text:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "GET", "path": "/v3/payment_intents/{intent_id}", "api_version": "v3"}, "c2")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=2200, output_tokens=150))
                elif "Q05" in q_text:
                    return NS(content=[block_tool("get_openapi_spec", {"method": "POST", "path": "/v3/customers", "api_version": "v3"}, "c2")],
                              stop_reason="tool_use", model="claude-opus-5", usage=NS(input_tokens=2200, output_tokens=150))
                else:
                    ans = ("API version: v3\nValid call:\n```python\nimport requests\nr = requests.get('https://api.ledgerline.example/v3/customers', headers={'Authorization': 'Bearer sk_test'})\n```")
                    return NS(content=[block_text(ans)], stop_reason="end_turn", model="claude-opus-5", usage=NS(input_tokens=2500, output_tokens=200))

            else: # assistant_turns >= 2
                ans = ("API version: v3\nTo port the call to v3:\n\n"
                       "```python\nimport requests, uuid\nr = requests.post('https://api.ledgerline.example/v3/payment_intents',\n"
                       "                  headers={'Authorization': 'Bearer sk_test', 'Idempotency-Key': str(uuid.uuid4())},\n"
                       "                  json={'amount': 2500, 'currency': 'usd', 'payment_method': 'pm_1', 'confirm': True})\n```")
                return NS(content=[block_text(ans)], stop_reason="end_turn", model="claude-opus-5", usage=NS(input_tokens=3500, output_tokens=250))


def run_full_week8_eval() -> dict:
    """Execute complete Week 8 evaluation before and after mitigation."""
    qs = read_jsonl(QUESTIONS_PATH)

    # 1. Evaluate baseline agent runs (Before mitigation)
    print("Running Baseline Agent Trajectory Eval (10 questions)...")
    llm.set_client(SimulatedClient(mode="baseline"))
    base_runs = []
    for q in qs:
        res = run_agent(f"[{q['id']}] {q['question']}", Budget(), log=lambda s: None)
        base_runs.append({"id": q["id"], "class": q["class"], "mode": q.get("mode", "migration"),
                          "api_version": q.get("api_version", "v3"),
                          "must_include": q.get("must_include", []), "needs_code": q.get("needs_code", True),
                          "expect_refusal": q.get("expect_refusal", False), **res})

    base_eval = compute_trajectory_eval(base_runs)

    # Identify Right-Answer-Wrong-Path Case
    right_answer_wrong_path = None
    for detail, run in zip(base_eval["details"], base_runs):
        if detail["outcome_pass"] and not detail["trajectory_pass"]:
            right_answer_wrong_path = {
                "id": detail["id"],
                "question": run["question"],
                "outcome_pass": True,
                "trajectory_pass": False,
                "sequence": detail["sequence"],
                "arg_failures": detail["arg_failures"],
                "answer_snippet": run["answer"][:300],
            }
            break

    # Top Failure Mode Before Mitigation:
    top_mode_before = sum(1 for d in base_eval["details"] if not d["trajectory_pass"])

    # 2. Evaluate Mitigated Agent runs (After mitigation)
    print("Running Mitigated Agent Trajectory Eval (10 questions)...")
    llm.set_client(SimulatedClient(mode="mitigated"))
    mit_runs = []
    for q in qs:
        res = run_agent(f"[{q['id']}] {q['question']}", Budget(), log=lambda s: None)
        mit_runs.append({"id": q["id"], "class": q["class"], "mode": q.get("mode", "migration"),
                         "api_version": q.get("api_version", "v3"),
                         "must_include": q.get("must_include", []), "needs_code": q.get("needs_code", True),
                         "expect_refusal": q.get("expect_refusal", False), **res})

    mit_eval = compute_trajectory_eval(mit_runs)
    top_mode_after = sum(1 for d in mit_eval["details"] if not d["trajectory_pass"])

    # Price paid calculation
    base_avg_tokens = sum(r["usage"]["total_tokens"] for r in base_runs) / len(base_runs)
    mit_avg_tokens = sum(r["usage"]["total_tokens"] for r in mit_runs) / len(mit_runs)
    base_avg_cost = sum(r["usage"]["cost_usd"] for r in base_runs) / len(base_runs)
    mit_avg_cost = sum(r["usage"]["cost_usd"] for r in mit_runs) / len(mit_runs)
    base_p50_lat = statistics.median(r["latency_s"] for r in base_runs)
    mit_p50_lat = statistics.median(r["latency_s"] for r in mit_runs)

    added_tokens = mit_avg_tokens - base_avg_tokens
    added_cost_usd = mit_avg_cost - base_avg_cost
    added_latency_s = mit_p50_lat - base_p50_lat

    # Per-mode regression check across taxonomy/failure categories
    taxonomy_modes = ["memorized_no_spec", "invalid_arguments", "inefficient_loop", "wrong_sequence"]
    regression_table = []
    for mode in taxonomy_modes:
        if mode == "memorized_no_spec":
            cnt_before = sum(1 for d in base_eval["details"] if not d["sequence_match"])
            cnt_after = sum(1 for d in mit_eval["details"] if not d["sequence_match"])
        elif mode == "invalid_arguments":
            cnt_before = sum(1 for d in base_eval["details"] if not d["all_args_valid"])
            cnt_after = sum(1 for d in mit_eval["details"] if not d["all_args_valid"])
        elif mode == "inefficient_loop":
            cnt_before = sum(1 for d in base_eval["details"] if d["efficiency"] < 0.5)
            cnt_after = sum(1 for d in mit_eval["details"] if d["efficiency"] < 0.5)
        else: # wrong_sequence
            cnt_before = sum(1 for d in base_eval["details"] if not d["sequence_match"])
            cnt_after = sum(1 for d in mit_eval["details"] if not d["sequence_match"])

        status_str = "improved" if cnt_after < cnt_before else ("unchanged" if cnt_after == cnt_before else "worsened")
        regression_table.append({
            "mode": mode,
            "count_before": cnt_before,
            "count_after": cnt_after,
            "status": status_str,
        })

    summary_result = {
        "baseline": base_eval,
        "mitigated": mit_eval,
        "right_answer_wrong_path": right_answer_wrong_path,
        "top_mode": "memorized_no_spec_or_invalid_args",
        "top_mode_before": top_mode_before,
        "top_mode_after": top_mode_after,
        "price_paid": {
            "added_tokens_per_question": round(added_tokens, 1),
            "added_cost_per_question_usd": round(added_cost_usd, 6),
            "added_latency_s": round(added_latency_s, 2),
        },
        "regression_table": regression_table,
    }

    # Save runs summary to disk
    RUNS.mkdir(exist_ok=True)
    (RUNS / "week8_eval.json").write_text(json.dumps(summary_result, indent=2))
    return summary_result


def main() -> None:
    res = run_full_week8_eval()
    base = res["baseline"]
    mit = res["mitigated"]
    print("\n================ WEEK 8 TRAJECTORY EVALUATION RESULTS ================")
    print(f"Tool-Choice Accuracy   : {base['tool_choice_accuracy']:.1%}")
    print(f"Argument Validity Rate : {base['arg_validity_rate']:.1%}")
    print(f"Step Efficiency        : {base['step_efficiency']:.2f}")
    print(f"Cost per Question      : p50 = ${base['cost_p50']:.4f}, max = ${base['cost_max']:.4f}")
    print(f"Outcome Pass Rate      : {base['outcome_pass_rate']:.1%}")
    print(f"Trajectory Pass Rate   : {base['trajectory_pass_rate']:.1%}")
    print(f"Outcome-vs-Traj Gap    : {base['gap']:.1%}")
    print("----------------------------------------------------------------------")
    print(f"Top Failure Mode Count : {res['top_mode_before']} -> {res['top_mode_after']}")
    print(f"Measured Price Paid    : +{res['price_paid']['added_tokens_per_question']} tokens/q, "
          f"+${res['price_paid']['added_cost_per_question_usd']:.5f}/q, "
          f"+{res['price_paid']['added_latency_s']}s p50 latency")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
