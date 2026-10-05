"""Offline checks on the plumbing. A scripted fake stands in for the model, so this
needs no key and spends nothing. It proves the loop, budgets, token summing, workflow
shape, assertions and protocol guards behave - it measures nothing about quality.

    python3 selftest.py
"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

from src import llm
from src.contract import target_version
from src.corpus import pages, search
from src.tools import check_deprecation, get_openapi_spec, match_path, run_tool
from evals import judge as judgemod
from evals.assertions import run_assertions, passed

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail and not cond else ""))


class Fake:
    """Scripted stand-in for anthropic.Anthropic(). `script` is a list of responses;
    the last one repeats forever, which is how a model that never stops looks."""
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.beta = NS(messages=NS(create=self._create))

    def with_options(self, **_):
        return self

    def _create(self, **kw):
        self.calls.append(kw)
        r = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return r


def resp(blocks, stop, inp=1000, out=200):
    return NS(content=blocks, stop_reason=stop, model="claude-opus-5",
              usage=NS(input_tokens=inp, output_tokens=out,
                       cache_creation_input_tokens=0, cache_read_input_tokens=0))


def text(t):
    return NS(type="text", text=t)


def tool(name, inp, i="t1"):
    return NS(type="tool_use", name=name, input=inp, id=i)


GOOD = """API version: v3
Create a payment intent; the v2 `source` parameter is removed and replaced by payment_method.

```python
import requests, uuid
r = requests.post("https://api.ledgerline.example/v3/payment_intents",
                  headers={"Authorization": "Bearer sk_test", "Idempotency-Key": str(uuid.uuid4())},
                  json={"amount": 2500, "currency": "usd", "payment_method": "pm_1", "confirm": True})
```"""
CASE = {"id": "X", "api_version": "v3", "needs_code": True, "expect_refusal": False,
        "must_include": ["/v3/payment_intents", "Idempotency-Key"]}

print("corpus and tools")
check("14 docs pages load", len(pages()) == 14, len(pages()))
check("version-scoped search returns only that version",
      all(p.api_version == "v3" for p in search("create a charge", "v3")))
check("unscoped search can return v2 for a v3 question (the v1 app's weakness)",
      any(p.api_version == "v2" for p in search("charge a card", None)))
check("path with a real id resolves", match_path("/v3/payment_intents/pi_123/capture", "v3")
      == "/v3/payment_intents/{intent_id}/capture")
check("invented path does not resolve", match_path("/v3/payment_intents/{id}/refunds", "v3") is None)
check("spec lookup errors on wrong method", "error" in get_openapi_spec("DELETE", "/v3/refunds", "v3"))
check("spec lookup returns required header",
      "Idempotency-Key" in json.dumps(get_openapi_spec("POST", "/v3/payment_intents", "v3")))
check("deprecation found for an endpoint",
      check_deprecation("POST /v2/charges", "v3")["replacement"] == "POST /v3/payment_intents")
check("deprecation found for a bare path",
      check_deprecation("/v2/customers/{id}/cards", "v3")["status"] == "removed")
check("current symbol is not deprecated",
      check_deprecation("POST /v3/refunds", "v3")["status"] == "not deprecated")
check("tool rejects an api_version outside the enum",
      "error" in json.loads(run_tool("search_docs", {"query": "x", "api_version": "v4"})))
check("unknown tool is an error result, not a crash",
      "error" in json.loads(run_tool("nope", {"api_version": "v3"})))
check("target version: default v3", target_version("how do I refund") == "v3")
check("target version: staying on v2", target_version("we're still on v2: paginate") == "v2")
check("target version: moving to v3", target_version("we are on v2, moving to v3") == "v3")

print("\nassertions")
r = run_assertions(CASE, GOOD)
check("a correct answer passes every assertion", passed(r), r)
check("missing version line fails", run_assertions(CASE, GOOD.replace("API version: v3", ""))["version_stated"] is False)
bad_code = GOOD.replace('"confirm": True})', '"confirm": True')
check("unparseable sample fails", run_assertions(CASE, bad_code)["code_parses"] is False)
check("invented endpoint fails", run_assertions(CASE, GOOD + "\nThen call /v3/payment_intents/{id}/refunds.")["endpoints_exist"] is False)
v2code = GOOD.replace("/v3/payment_intents\",", "/v2/charges\",")
check("v2 path in v3 code fails", run_assertions(CASE, v2code)["no_v2_in_v3_code"] is False)
nonote = "API version: v3\n```python\nrequests.post(u, data={'source': 'tok_visa'})\n```"
check("deprecated symbol without a note fails", run_assertions(CASE, nonote)["deprecations_noted"] is False)
check("deprecated symbol with a note passes", run_assertions(CASE, GOOD)["deprecations_noted"] is True)
refuse_case = {**CASE, "expect_refusal": True, "must_include": [], "needs_code": False}
check("correct refusal passes", run_assertions(refuse_case, "API version: v3\nNot covered in the Ledgerline docs.")["refusal_correct"])
check("a guess where a refusal was due fails", run_assertions(refuse_case, "API version: v3\nUse /v3/payouts.")["refusal_correct"] is False)

print("\nagent loop")
from week7.agent import Budget, run_agent  # noqa: E402
fake = Fake([resp([tool("search_docs", {"query": "charge", "api_version": "v3"})], "tool_use", 1000, 100),
             resp([tool("get_openapi_spec", {"method": "POST", "path": "/v3/payment_intents", "api_version": "v3"}, "t2")], "tool_use", 3000, 100),
             resp([text(GOOD)], "end_turn", 5000, 400)])
llm.set_client(fake)
res = run_agent("charge a card on v3", Budget(), log=lambda s: None)
check("completes a multi-step task", res["status"] == "done" and res["laps"] == 3, res["status"])
check("both tool calls executed", [s["tool"] for s in res["steps"]] == ["search_docs", "get_openapi_spec"])
check("tokens summed over every lap, not just the last",
      res["usage"]["total_tokens"] == 1100 + 3100 + 5400, res["usage"]["total_tokens"])
check("cost summed over every lap",
      abs(res["usage"]["cost_usd"] - ((9000 * 5 + 600 * 25) / 1e6)) < 1e-9, res["usage"]["cost_usd"])
hist = fake.calls[-1]["messages"]
check("each tool result goes back with its matching tool_use_id",
      [hist[2]["content"][0]["tool_use_id"], hist[4]["content"][0]["tool_use_id"]] == ["t1", "t2"])
check("whole history is re-sent each lap", len(fake.calls[2]["messages"]) == 5)
check("refusal fallback requested on every call",
      all(c.get("fallbacks") == "default" for c in fake.calls))

spin = lambda: Fake([resp([tool("search_docs", {"query": "x", "api_version": "v3"})], "tool_use", 1000, 100)])
for label, budget, want in [
        ("max_iters", Budget(max_iters=3), "budget:max_iters"),
        ("max_tokens", Budget(max_tokens=5000), "budget:max_tokens"),
        ("max_cost", Budget(max_cost_usd=0.012), "budget:max_cost"),
        ("max_wall", Budget(max_wall_s=0.0), "budget:max_wall")]:
    llm.set_client(spin())
    lines = []
    res = run_agent("loop forever", budget, log=lines.append)
    check(f"{label} budget stops a model that never stops", res["status"] == want,
          f"{res['status']} after {res['laps']} laps")
    check(f"{label} termination is logged with the budget's name",
          any(l.startswith("[stop] budget fired: " + label) for l in lines))

llm.set_client(Fake([resp([tool("search_docs", {"query": "x", "api_version": "v3"})], "max_tokens")]))
res = run_agent("q", Budget(), log=lambda s: None)
check("a tool call cut off by max_tokens is not executed", res["status"] == "truncated" and not res["steps"])

print("\nworkflow")
from week7.workflow import pick_endpoint, run_workflow  # noqa: E402
fake = Fake([resp([text(GOOD)], "end_turn", 4000, 400)])
llm.set_client(fake)
res = run_workflow("We call POST /v2/charges with source. Give me v3.", log=lambda s: None)
check("exactly one model call, no loop", len(fake.calls) == 1 and res["laps"] == 1)
check("workflow gives the model no tools", "tools" not in fake.calls[0])
check("step 3 result reaches the writer",
      "POST /v3/payment_intents" in fake.calls[0]["messages"][0]["content"])
check("endpoint taken from the question", pick_endpoint("port GET /v2/charges/{charge_id}", {"results": []})
      == ("GET", "/v2/charges/{charge_id}"))
check("same system contract as the agent",
      sys.modules["week7.agent"].SYSTEM.split("Answer format")[1] == sys.modules["week7.workflow"].SYSTEM.split("Answer format")[1])

print("\njudge and blind protocol")
from week6 import judge_eval  # noqa: E402
from evals.common import LABELS  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    judgemod.CACHE = Path(d) / "cache.jsonl"
    llm.set_client(Fake([resp([text("The answer uses v2.\nVERDICT: FAIL")], "end_turn")]))
    j = judgemod.judge("v1", {"id": "E01", "api_version": "v3", "question": "q"}, "a")
    check("judge verdict parsed from the last line", j["verdict"] == "FAIL")
    llm.set_client(Fake([resp([text("VERDICT: PASS")], "end_turn")]))
    j2 = judgemod.judge("v1", {"id": "E01", "api_version": "v3", "question": "q"}, "a")
    check("judge verdict is cached per answer", j2["verdict"] == "FAIL")
    sysblk, user = judgemod.render("v1", {"id": "E01", "api_version": "v3", "question": "QQ"}, "AA")
    check("reference docs sit in the cached system block",
          "cache_control" in sysblk[0] and "Payment intents (v3)" in sysblk[0]["text"])
    check("judge_v1 grades one criterion, not the four moved to code",
          "CORRECT_AND_USABLE" in sysblk[0]["text"] and "1. The Python code sample" not in sysblk[0]["text"])
if not LABELS.exists():
    try:
        judge_eval._labels()
        blocked = False
    except SystemExit:
        blocked = True
    check("judge refuses to run before labels_25.json exists", blocked)

print("\nweek 8 trajectory evals")
from week8.trajectory_eval import validate_tool_args, score_run_trajectory, run_full_week8_eval  # noqa: E402
val_ok, _ = validate_tool_args("get_openapi_spec", {"method": "POST", "path": "/v3/payment_intents", "api_version": "v3"})
check("valid openapi spec path passes argument validation", val_ok)

val_bad, _ = validate_tool_args("get_openapi_spec", {"method": "POST", "path": "/v3/charges", "api_version": "v3"})
check("invented openapi spec path fails argument validation", val_bad is False)

sc = score_run_trajectory("Q01", [{"tool": "check_deprecation", "input": {"symbol": "POST /v2/charges", "api_version": "v3"}},
                                   {"tool": "get_openapi_spec", "input": {"method": "POST", "path": "/v3/payment_intents", "api_version": "v3"}}])
check("expected valid tool sequence passes trajectory eval", sc["pass_trajectory"] is True)

w8_res = run_full_week8_eval()
check("week 8 trajectory eval completes offline", w8_res["baseline"]["gap"] >= 0.0)
check("top failure mode before -> after reduction measured", w8_res["top_mode_before"] >= w8_res["top_mode_after"])

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
if FAIL:
    print("failed: " + ", ".join(FAIL))
    sys.exit(1)

