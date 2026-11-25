"""The closed failure->test loop, the demo script's Part 1, and the hand-labelling CLI."""
import json
import subprocess

from . import HERE, RUNS
from .evaluate import CASES, LABELS, REGRESSIONS, assertions, load_cases
from .obs import read_log, full_trace

LOOP_TRACE = "trc12_d54345f79f9e"      # the trace that started it: v2.4 caller, v3 client.search()


def promote(trace_id: str, template_case: str) -> dict:
    """Copy the question WORD FOR WORD from a real failed trace into a permanent regression case.
    Expectations come from the template case of the same kind."""
    rec = full_trace(trace_id)["request"]
    if rec is None:
        src = RUNS / "found_redactor_corrupts_code.jsonl"
        rec = next((json.loads(l) for l in src.read_text().splitlines()
                    if json.loads(l)["trace_id"] == trace_id), None)
    if rec is None:
        raise SystemExit(f"no trace {trace_id}")
    tpl = next(c for c in load_cases(include_regressions=False) if c["id"] == template_case)
    existing = [json.loads(l) for l in REGRESSIONS.read_text().splitlines()] if REGRESSIONS.exists() else []
    if any(c.get("source") == f"trace:{trace_id}" for c in existing):
        return next(c for c in existing if c.get("source") == f"trace:{trace_id}")
    case = {"id": f"R{len(existing) + 1:02d}", "cat": tpl["cat"], "question": rec["question"],
            "expect": tpl["expect"], "gold": tpl["gold"], "tools": tpl["tools"],
            "source": f"trace:{trace_id}",
            "why": "v2.4 caller was handed a v3 client.search(cursor=) snippet; it imports cleanly "
                   "and fails at runtime on 2.4."}
    with REGRESSIONS.open("a") as fh:
        fh.write(json.dumps(case) + "\n")
    return case


def closed_loop():
    """Live: promote the failure, run the case with the guard OFF (red), then ON (green)."""
    from . import engine
    case = promote(LOOP_TRACE, "C01")
    print(f"\n== closed loop: {case['id']} <- {case['source']}\n   {case['question']}")
    result = {"case": case, "runs": []}
    try:
        for label, guards in (("guard OFF (code_check disabled)", {"code_check": False}),
                              ("guard ON  (parse + symbol table + one repair)", {"code_check": True})):
            rec = engine.answer(case["question"], None, mode="after", case_id=case["id"], guards=guards)
            a = assertions(case, rec, read_log())
            ok = all(a.values())
            print(f"   {label}: {'GREEN' if ok else 'RED'}   trace={rec['trace_id']}   "
                  f"failed={[k for k, v in a.items() if not v]}")
            if not ok:
                print("     " + "; ".join(rec["code_check"]["errors"]))
            result["runs"].append({"label": label, "result": "GREEN" if ok else "RED",
                                   "trace_id": rec["trace_id"],
                                   "failed": [k for k, v in a.items() if not v],
                                   "code_errors": rec["code_check"]["errors"]})
    finally:
        engine.close_session()
        (RUNS / "loop.json").write_text(json.dumps(result, indent=1))


def demo():
    from . import engine
    qs = [("I'm on 2.4 - how do I paginate through all entries for an account?", None),
          ("How do I call client.query() in 3.0?", None)]
    try:
        for q, v in qs:
            r = engine.answer(q, v, mode="after", case_id="demo")
            print(f"\n### {q}\ntrace_id={r['trace_id']}  version={r['version']['version']} "
                  f"(resolved from {r['version']['source']}, before retrieval)  "
                  f"cost=${r['total_cost_usd']:.5f}  latency={r['total_latency_s']}s\n")
            print(r["answer"])
    finally:
        engine.close_session()


def label():
    rows = [json.loads(l) for l in (RUNS / "eval_after.jsonl").read_text().splitlines()]
    cases = {c["id"]: c for c in load_cases()}
    lab = json.loads(LABELS.read_text()) if LABELS.exists() else {"labels": {}}
    who = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
    for r in rows:
        if r["case_id"] in lab["labels"]:
            continue
        c = cases[r["case_id"]]
        print("=" * 80, f"\n{r['case_id']}  caller on {c['expect']['version']}\nQ: {c['question']}\n\n{r['answer']}\n")
        v = ""
        while v not in ("p", "f", "q"):
            v = input("correct and usable for that version? [p]ass/[f]ail/[q]uit: ").strip().lower()
        if v == "q":
            break
        lab["labels"][r["case_id"]] = "PASS" if v == "p" else "FAIL"
        lab["labeler"] = who
        LABELS.write_text(json.dumps(lab, indent=1))
