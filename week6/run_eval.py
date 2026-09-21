"""THE ONE COMMAND for Week 6.

    python3 -m week6.run_eval              # app v1 vs app v2, every case, pass rate by mode
    python3 -m week6.run_eval --fresh      # regenerate answers instead of reusing runs/answers_*.jsonl
    python3 -m week6.run_eval --no-judge   # assertions only (free, no API calls if answers exist)

For each app it: answers every case (cached per app), runs the deterministic assertions,
and - only once labels_25.json exists, because the protocol is blind - asks the latest
validated judge for its one binary criterion. A case passes when no applicable assertion
fails AND (if judged) the judge says PASS. Results go to runs/eval_<app>.json.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

from src import RUNS
from src.assistant import answer
from evals.assertions import ASSERTIONS, MOVED_FROM_JUDGE, passed, run_assertions
from evals.common import LABELS, answers_path, load_cases, read_jsonl, write_jsonl
from evals.judge import judge, latest_judge

MODES = ["version_confusion", "deprecated_no_migration", "hallucinated_endpoint",
         "broken_sample", "unanswerable", "conceptual"]
APPS = ("v1", "v2")


def get_answers(app: str, cases: list, fresh: bool) -> dict:
    path = answers_path(app)
    have = {} if fresh else {r["id"]: r for r in read_jsonl(path)}
    todo = [c for c in cases if c["id"] not in have or have[c["id"]]["question"] != c["question"]]
    for i, c in enumerate(todo, 1):
        print(f"  [{app}] answering {i}/{len(todo)} {c['id']}", file=sys.stderr)
        r = answer(c["question"], app=app)
        have[c["id"]] = {"id": c["id"], **r}
        write_jsonl(path, [have[k] for k in sorted(have)])
    return have


def evaluate(app: str, cases: list, answers: dict, use_judge: bool) -> list:
    jv = latest_judge() if use_judge else None
    rows = []
    for c in cases:
        a = answers[c["id"]]["answer"]
        res = run_assertions(c, a)
        row = {"id": c["id"], "mode": c["mode"], "source": c.get("source", "authored"),
               "assertions": res, "assertions_pass": passed(res)}
        if jv:
            row["judge"] = judge(jv, c, a)["verdict"]
        row["pass"] = row["assertions_pass"] and row.get("judge", "PASS") == "PASS"
        rows.append(row)
    (RUNS / f"eval_{app}.json").write_text(json.dumps(
        {"app": app, "judge": jv, "rows": rows}, indent=1), encoding="utf-8")
    return rows


def by_mode(rows: list) -> dict:
    out = defaultdict(lambda: [0, 0])
    for r in rows:
        out[r["mode"]][1] += 1
        out[r["mode"]][0] += r["pass"]
    return out


def pct(p, n):
    return f"{p}/{n} {100 * p / n:3.0f}%" if n else "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--apps", nargs="+", default=list(APPS), choices=APPS)
    args = ap.parse_args()

    cases = load_cases()
    regress = [c for c in cases if c.get("source", "").startswith("trace:")]
    use_judge = not args.no_judge and LABELS.exists()

    results = {}
    for app in args.apps:
        results[app] = evaluate(app, cases, get_answers(app, cases, args.fresh), use_judge)

    print(f"\n{len(cases)} cases ({len(cases) - len(regress)} authored, {len(regress)} regression "
          f"from real traces) · {len(ASSERTIONS)} assertions · "
          f"{1 if use_judge else 0} judged criterion"
          + (f" (judge {latest_judge()})" if use_judge else ""))
    if not use_judge:
        print("judge not run: " + ("--no-judge" if args.no_judge else
              "labels_25.json does not exist yet (blind protocol - label first: python3 -m week6.label)"))
    print(f"moved out of the judge into code: {', '.join(MOVED_FROM_JUDGE)}")
    if len(regress) < 2:
        print(f"WARNING: {len(regress)} regression case(s); the task needs >= 2. "
              f"Run week6/traffic.py, then week6/promote.py <trace_id>.")

    head = f"\n{'mode':<26}" + "".join(f"{'app ' + a:>16}" for a in args.apps)
    if len(args.apps) == 2:
        head += f"{'delta':>9}"
    print(head)
    print("-" * len(head))
    tables = {a: by_mode(results[a]) for a in args.apps}
    for m in MODES + [m for m in tables[args.apps[0]] if m not in MODES]:
        cells = [tables[a].get(m, [0, 0]) for a in args.apps]
        if not cells[0][1]:
            continue
        line = f"{m:<26}" + "".join(f"{pct(*c):>16}" for c in cells)
        if len(cells) == 2:
            line += f"{(cells[1][0] - cells[0][0]) / cells[0][1] * 100:+8.0f}%"
        print(line)
    print("-" * len(head))
    tot = {a: (sum(r["pass"] for r in results[a]), len(results[a])) for a in args.apps}
    line = f"{'ALL':<26}" + "".join(f"{pct(*tot[a]):>16}" for a in args.apps)
    if len(args.apps) == 2:
        line += f"{(tot['v2'][0] - tot['v1'][0]) / tot['v1'][1] * 100:+8.0f}%"
    print(line)

    print("\nassertion failures (app: count)")
    for name, _ in ASSERTIONS:
        print(f"  {name:<22}" + "  ".join(
            f"{a}: {sum(r['assertions'][name] is False for r in results[a]):>2}" for a in args.apps))
    if use_judge:
        print(f"  {'judge FAIL':<22}" + "  ".join(
            f"{a}: {sum(r.get('judge') != 'PASS' for r in results[a]):>2}" for a in args.apps))


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
