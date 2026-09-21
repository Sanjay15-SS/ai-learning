"""The same task as a fixed workflow - Week 7. Hard-coded steps, no loop.

    python3 -m week7.workflow "We're moving POST /v2/charges code to v3. What does it look like now?"

  step 1  search_docs(question, target version)
  step 2  get_openapi_spec(the endpoint named in the question, else the top page's first)
  step 3  check_deprecation(that endpoint)
  step 4  one model call writes the answer from the three results

Same tool implementations as the agent, same model, same system contract, same output
format. What it cannot do is decide to take a fourth look: if step 3 says the endpoint
is deprecated, the replacement's spec is never fetched. That is the point of the race.
"""
import json
import re
import sys
import time

from src import llm
from src.contract import CONTRACT, target_version
from src.tools import check_deprecation, get_openapi_spec, search_docs

SYSTEM = ("You answer migration questions about the Ledgerline payments API. The results of "
          "three lookups are supplied with the question; use only them.\n\n" + CONTRACT)

ENDPOINT = re.compile(r"\b(GET|POST|DELETE)\s+(/v[23]/[A-Za-z0-9_{}\-/]+)")


def pick_endpoint(question: str, step1: dict):
    m = ENDPOINT.search(question)
    if m:
        return m.group(1), m.group(2)
    for page in step1["results"]:
        if page["endpoints"]:
            method, path = page["endpoints"][0].split(" ", 1)
            return method, path
    return None, None


def run_workflow(question: str, log=print) -> dict:
    t0 = time.perf_counter()
    usage = llm.Usage()
    version = target_version(question)
    log(f"[start] {question}")

    s1 = search_docs(question, version)
    log(f"  step 1 search_docs({version}) -> {[p['page_id'] for p in s1['results']]}")
    method, path = pick_endpoint(question, s1)
    if path:
        s2 = get_openapi_spec(method, path, path.split("/")[1])
        s3 = check_deprecation(f"{method} {path}", version)
    else:
        s2 = {"error": "no endpoint found in the question or the top pages"}
        s3 = {"error": "no endpoint to check"}
    log(f"  step 2 get_openapi_spec({method} {path}) -> {'error' if 'error' in s2 else 'ok'}")
    log(f"  step 3 check_deprecation({method} {path}) -> {s3.get('status')}")

    lookups = (f"<search_docs>\n{json.dumps(s1)}\n</search_docs>\n"
               f"<get_openapi_spec>\n{json.dumps(s2)}\n</get_openapi_spec>\n"
               f"<check_deprecation>\n{json.dumps(s3)}\n</check_deprecation>")
    r = llm.create(usage, system=SYSTEM, max_tokens=8000, messages=[{"role": "user", "content":
        f"{lookups}\n\nDeveloper question: {question}"}])
    status = {"refusal": "refused", "max_tokens": "truncated"}.get(r.stop_reason, "done")
    latency = time.perf_counter() - t0
    log(f"  step 4 write -> {r.stop_reason}")
    log(f"[end] status={status} tokens={usage.total_tokens:,} cost=${usage.cost_usd:.4f} "
        f"latency={latency:.1f}s")
    return {"system": "workflow", "question": question, "answer": llm.text_of(r),
            "status": status, "laps": 1, "steps": [
                {"tool": "search_docs"}, {"tool": "get_openapi_spec", "path": path},
                {"tool": "check_deprecation", "path": path}],
            "latency_s": round(latency, 3), "usage": usage.as_dict()}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 -m week7.workflow "question"')
    res = run_workflow(sys.argv[1])
    print("\n--- answer ---\n" + res["answer"])
