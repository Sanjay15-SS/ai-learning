"""Week 6 eval suite + Week 5 taxonomy + Week 8 trajectory eval, run against the INTEGRATED
system (engine.answer, MCP hop included). Assertions first; the judge only scores what an
assertion cannot.

    python3 -m capstone eval [--mode before|after|both] [--ids C01,C02] [--no-judge]
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from src import llm

from . import HERE, RUNS, codecheck, engine, retriever, sdk_spec as S
from .obs import read_log

CASES = HERE / "evals" / "cases.jsonl"
REGRESSIONS = HERE / "evals" / "regressions.jsonl"
LABELS = HERE / "evals" / "labels.json"
JUDGE_CACHE = RUNS / "judge_cache.jsonl"
DEAD = re.compile(r"\bledgerline\.connect\(|\bconn\.find\(|fetch_more\(")
SOURCES = re.compile(r"\nSources:\n(.*)\Z", re.S)


def load_cases(ids=None, include_regressions=True):
    cases = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    if include_regressions and REGRESSIONS.exists():
        cases += [json.loads(l) for l in REGRESSIONS.read_text().splitlines() if l.strip()]
    if ids:
        cases = [c for c in cases if c["id"] in ids]
    return cases


# ------------------------------------------------------------------ assertions (free, deterministic)

def assertions(case: dict, rec: dict, log_lines=None) -> dict:
    e, ans = case["expect"], rec["answer"]
    ver = e["version"]
    low = ans.lower()
    a = {}
    a["version_resolved"] = rec["version"]["version"] == ver and (
        not e.get("assumed") or rec["version"]["assumed"])
    m = SOURCES.search(ans)
    cites = rec.get("citations", [])
    a["cites_version"] = bool(m) and bool(cites) and all(
        c["source"] != "stackoverflow" and retriever.covers(c["version"], ver) for c in cites) \
        and all(re.search(r"\(v[0-9]", line) for line in m.group(1).splitlines() if line.strip())
    chk = codecheck.check_answer(ans, ver)
    a["code_runs_in_version"] = chk["ok"]                  # vacuously true with no code
    if e.get("code"):
        a["code_present"] = chk["n_blocks"] > 0
    if e.get("deprecation"):
        sym = e["deprecation"]
        dep = S.status(sym, ver)
        a["deprecation_surfaced"] = (sym.split(".")[-1] in ans and "deprecat" in low
                                     and str(dep.get("removed") or "") in ans)
    if e.get("removed"):
        short = e["removed"].split(".")[-1]
        a["removed_said_plainly"] = short in ans and any(
            p in low for p in ("no longer exists", "does not exist", "not part of", "doesn't exist"))
    for w in e.get("must_mention", []):
        a[f"mentions:{w}"] = w.lower() in low
    if e.get("deprecation_or_new"):
        a["uses_current_api"] = any(w in ans for w in e["deprecation_or_new"])
    a["no_dead_api"] = not DEAD.search(ans)
    if e.get("secrets"):
        raw = json.dumps([l for l in (log_lines or []) if l.get("trace_id") == rec["trace_id"]])
        a["secrets_not_logged"] = not any(s in raw for s in e["secrets"])
        a["secrets_not_in_answer"] = not any(s in ans for s in e["secrets"])
    return a


def looks_like_code(case, rec) -> bool:
    """The old bar: a code block that parses. No symbol table."""
    blocks = codecheck.code_blocks(rec["answer"])
    if not case["expect"].get("code") or not blocks:
        return True
    return all(codecheck.check(b, "3.0")["parses"] for b in blocks)


# ------------------------------------------------------------------ judge (one binary criterion)

JUDGE = """You grade an answer from an SDK documentation assistant.
The developer is on ledgerline SDK {version}. Reference (ground truth for {version}):
{reference}

Question: {question}

Answer:
{answer}

PASS only if ALL hold: the answer actually addresses the question; everything it claims about
{version} agrees with the reference; it does not recommend a method that does not exist in
{version}. Otherwise FAIL. Reply with one line: VERDICT: PASS or VERDICT: FAIL"""


def _reference(case):
    ver = case["expect"]["version"]
    pages = set(case.get("gold") or []) | {"migration"}
    txt = "\n\n".join(c.text for c in retriever.all_chunks() if c.page_id in pages)
    syms = "\n".join(f"- {s}: " + (("exists" + (f", DEPRECATED since {st['deprecated']}, removed {st['removed']}"
                                                 if st['state'] == 'deprecated' else ""))
                                   if st["exists"] else f"does NOT exist in {ver}")
                     for s in S.SYMBOLS for st in [S.status(s, ver)])
    return txt[:3500] + "\n\nSymbol table for " + ver + ":\n" + syms


def judge(case, rec) -> dict:
    key = hashlib.sha256((case["id"] + rec["answer"]).encode()).hexdigest()[:16]
    cache = {}
    if JUDGE_CACHE.exists():
        for l in JUDGE_CACHE.read_text().splitlines():
            r = json.loads(l)
            cache[r["key"]] = r
    if key in cache:
        return cache[key]
    u = llm.Usage()
    r = llm.create(u, system="You are a strict grader.", max_tokens=20, messages=[{"role": "user",
                   "content": JUDGE.format(version=case["expect"]["version"], reference=_reference(case),
                                           question=case["question"], answer=rec["answer"])}])
    txt = llm.text_of(r)
    v = "PASS" if re.search(r"VERDICT:\s*PASS", txt, re.I) else "FAIL"
    out = {"key": key, "case_id": case["id"], "verdict": v, "raw": txt[:200], "cost_usd": u.cost_usd}
    JUDGE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with JUDGE_CACHE.open("a") as fh:
        fh.write(json.dumps(out) + "\n")
    return out


# ------------------------------------------------------------------ run

# 12 cases, every category represented - fits in ~1 h on an 8 GB M1. The full 30 resume later.
SUBSET = ["C01", "C04", "C06", "C07", "C11", "C13", "C14", "C18", "C22", "C24", "C28", "C30"]


def row_from_rec(c, rec, mode, use_judge, log_lines=None):
    a = assertions(c, rec, log_lines if log_lines is not None else read_log())
    row = {"case_id": c["id"], "cat": c["cat"], "mode": mode, "trace_id": rec["trace_id"],
           "assertions": a, "assert_pass": all(a.values()),
           "looks_like_code_pass": all(v for k, v in a.items() if k not in
                                       ("code_runs_in_version",)) and looks_like_code(c, rec),
           "answer": rec["answer"], "tools_called": rec["tools_called"],
           "events": rec["events"], "cost_usd": rec["total_cost_usd"],
           "latency_s": rec["total_latency_s"], "version": rec["version"],
           "has_code": rec["code_check"]["n_blocks"] > 0}
    if use_judge:
        row["judge"] = judge(c, rec)["verdict"]
    return row


def run(mode="after", ids=None, use_judge=True, out=None, guards=None, include_regressions=True,
        fresh=False):
    """Appends one row per case as it finishes and SKIPS cases already in the file, so an
    interrupted run resumes where it stopped. A case already answered in the trace log
    (same mode, no guard override) is re-scored from its trace instead of re-asking the model."""
    cases = load_cases(ids, include_regressions)
    out = Path(out or RUNS / f"eval_{mode}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    if fresh and out.exists():
        out.unlink()
    done = {json.loads(l)["case_id"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    logged = {}
    if guards is None and mode == "before":   # after-mode code changed since the smoke runs
        for r in read_log():
            if r.get("kind") == "request" and r.get("mode") == mode and r.get("case_id") \
                    and r.get("guards", {}).get("code_check") == (mode == "after"):
                logged[r["case_id"]] = r
    rows = []
    try:
        for c in cases:
            if c["id"] in done:
                continue
            rec = logged.get(c["id"]) or engine.answer(c["question"], c.get("sdk_version"), mode=mode,
                                                       case_id=c["id"], guards=guards)
            row = row_from_rec(c, rec, mode, use_judge)
            with out.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            rows.append(row)
            a = row["assertions"]
            print(f"  {c['id']:<4} {mode:<6} {'PASS' if row['assert_pass'] else 'FAIL'}  "
                  f"judge={row.get('judge', '-'):<4} {rec['trace_id']}  "
                  f"{[k for k, v in a.items() if not v]}", flush=True)
    finally:
        engine.close_session()
    return rows


def load_rows(mode):
    p = RUNS / f"eval_{mode}.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


# ------------------------------------------------------------------ metrics

def summarize(rows) -> dict:
    n = len(rows)
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r["assert_pass"])
    code_rows = [r for r in rows if r["has_code"]]
    wrong = [r for r in code_rows if not r["assertions"]["code_runs_in_version"]]
    return {"n": n, "assert_pass_rate": round(sum(r["assert_pass"] for r in rows) / max(n, 1), 3),
            "pass_by_category": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_cat.items())},
            "answers_with_code": len(code_rows),
            "wrong_version_code_rate": round(len(wrong) / max(len(code_rows), 1), 3),
            "wrong_version_code": f"{len(wrong)}/{len(code_rows)}",
            "looks_like_code_pass": sum(r["looks_like_code_pass"] for r in rows),
            "symbol_checked_pass": sum(r["assert_pass"] for r in rows),
            "red_once_looks_like_code_stops_counting": sum(
                1 for r in rows if r["looks_like_code_pass"] and not r["assertions"]["code_runs_in_version"]),
            "judge_pass_rate": (round(sum(r.get("judge") == "PASS" for r in rows) / n, 3)
                                if n and "judge" in rows[0] else None),
            "mean_cost_usd": round(sum(r["cost_usd"] for r in rows) / max(n, 1), 6),
            "mean_latency_s": round(sum(r["latency_s"] for r in rows) / max(n, 1), 2),
            "p95_latency_s": sorted(r["latency_s"] for r in rows)[int(0.95 * (n - 1))] if n else None}


def judge_agreement(rows) -> dict:
    if not LABELS.exists():
        return {"status": "no labels yet - run: python3 -m capstone label"}
    lab = json.loads(LABELS.read_text())
    pairs = [(lab["labels"][r["case_id"]], r["judge"]) for r in rows
             if r["case_id"] in lab["labels"] and "judge" in r]
    if not pairs:
        return {"status": "labels do not match this run"}
    agree = sum(a == b for a, b in pairs)
    tp = sum(a == b == "FAIL" for a, b in pairs)
    return {"n": len(pairs), "agreement": round(agree / len(pairs), 3), "labeler": lab.get("labeler"),
            "human_fail_caught_by_judge": f"{tp}/{sum(a == 'FAIL' for a, _ in pairs)}",
            "disagreements": [r["case_id"] for r in rows if r["case_id"] in lab["labels"]
                              and lab["labels"][r["case_id"]] != r.get("judge")]}


SEVERITY = {"wrong_version_code": "critical", "removed_method_invented": "critical",
            "deprecation_not_surfaced": "high", "uncited_or_wrong_version_citation": "medium",
            "version_misresolved": "critical", "version_dropped_at_mcp_hop": "high",
            "guard_withheld_needed_code": "medium", "redactor_corrupts_code": "high",
            "secret_leak": "critical", "dead_api_from_stackoverflow": "critical",
            "missing_content": "medium"}


def classify(row) -> list:
    a, modes = row["assertions"], []
    if not a.get("version_resolved", True):
        modes.append("version_misresolved")
    if not a.get("code_runs_in_version", True):
        modes.append("wrong_version_code")
    if a.get("removed_said_plainly") is False:
        modes.append("removed_method_invented")
    if a.get("deprecation_surfaced") is False:
        modes.append("deprecation_not_surfaced")
    if a.get("cites_version") is False:
        modes.append("uncited_or_wrong_version_citation")
    if a.get("no_dead_api") is False:
        modes.append("dead_api_from_stackoverflow")
    if a.get("secrets_not_logged") is False or a.get("secrets_not_in_answer") is False:
        modes.append("secret_leak")
    if a.get("code_present") is False and any(e["event"] == "code_withheld" for e in row["events"]):
        modes.append("guard_withheld_needed_code")
    if any(k.startswith("mentions:") and not v for k, v in a.items()) or a.get("code_present") is False \
            and "guard_withheld_needed_code" not in modes or a.get("uses_current_api") is False:
        modes.append("missing_content")
    return modes


def taxonomy(rows) -> list:
    n = len(rows)
    cnt, ex = Counter(), {}
    for r in rows:
        for m in classify(r):
            cnt[m] += 1
            ex.setdefault(m, r["trace_id"])
        # integration-created: the agent passed a different sdk_version over MCP than resolved
        if any(e["event"] == "tool_version_mismatch" for e in r["events"]):
            cnt["version_dropped_at_mcp_hop"] += 1
            ex.setdefault("version_dropped_at_mcp_hop", r["trace_id"])
    return [{"mode": m, "count": c, "freq_pct": round(100 * c / n, 1), "severity": SEVERITY.get(m, "medium"),
             "trace_id": ex[m]} for m, c in cnt.most_common()]


def trajectory(rows) -> dict:
    """Tool choice: did the agent call at least one of the case's expected tools, and did every
    version-scoped call carry the caller's version (as the agent ASKED, before pinning)?"""
    cases = {c["id"]: c for c in load_cases()}
    out = []
    for r in rows:
        c = cases.get(r["case_id"])
        if not c or not c.get("tools"):
            continue
        called = [t["tool"] for t in r["tools_called"]]
        right_tool = any(t in c["tools"] for t in called)
        right_args = all(t["asked_version"] == r["version"]["version"]
                         for t in r["tools_called"] if t["asked_version"] is not None or
                         t["tool"] in ("search_sdk_docs", "symbol_exists", "check_code"))
        traj_ok = right_tool and right_args
        out.append({"case_id": r["case_id"], "called": called, "expected_any_of": c["tools"],
                    "tool_choice_ok": right_tool, "version_arg_ok": right_args,
                    "trajectory_ok": traj_ok, "outcome_ok": r["assert_pass"]})
    n = len(out)
    if not n:
        return {"n": 0}
    tca = sum(o["tool_choice_ok"] for o in out) / n
    traj = sum(o["trajectory_ok"] for o in out) / n
    outc = sum(o["outcome_ok"] for o in out) / n
    return {"n": n, "tool_choice_accuracy": round(tca, 3), "trajectory_pass": round(traj, 3),
            "outcome_pass": round(outc, 3), "outcome_minus_trajectory_gap": round(outc - traj, 3),
            "outcome_ok_but_trajectory_wrong": [o["case_id"] for o in out if o["outcome_ok"] and not o["trajectory_ok"]],
            "trajectory_ok_but_outcome_wrong": [o["case_id"] for o in out if o["trajectory_ok"] and not o["outcome_ok"]],
            "no_tool_called": sum(1 for o in out if not o["called"]), "rows": out}


def so_ablation() -> dict:
    """Retrieval hit@4 on the gold pages with Stack Overflow dropped / raw / bridged. No LLM."""
    cases = [c for c in load_cases(include_regressions=False) if c.get("gold")]
    out = {}
    for name, cfg in {"drop": retriever.RetrieverConfig(so_mode="drop"),
                      "raw_unfiltered (before)": retriever.RetrieverConfig(version_filter=False, so_mode="raw"),
                      "bridge (after)": retriever.RetrieverConfig(so_mode="bridge")}.items():
        hits, so_shown, wrong_ver = 0, 0, 0
        for c in cases:
            got = retriever.search(c["question"], c["expect"]["version"], cfg)
            hits += any(g.page_id in c["gold"] for g in got)
            so_shown += any(g.source == "stackoverflow" for g in got)
            wrong_ver += any(not retriever.covers(g.sdk_version, c["expect"]["version"]) for g in got)
        out[name] = {"hit_at_4": f"{hits}/{len(cases)}", "hit_rate": round(hits / len(cases), 3),
                     "cases_with_SO_text_in_context": so_shown,
                     "cases_with_wrong_version_chunk": wrong_ver}
    return out
