"""Validate the judge against the 25 blind hand labels.

    python3 -m week6.judge_eval run v1                      # agreement_before
    (write prediction.txt: one sentence, what v2 will fix)
    python3 -m week6.judge_eval build-v2 E03 E11            # two of v1's OWN disagreements -> few-shot
    python3 -m week6.judge_eval run v2                      # agreement_after
    python3 -m week6.judge_eval report                      # before -> after, held-out, disagreements

Every ordering rule of the protocol is checked here rather than trusted:
  * labels_25.json must exist, be final, and describe the exact answers being judged;
  * the judge run must start after the labels were finalized (and after their git commit,
    when the folder is a git repo);
  * judge_v2 can only be built from disagreements that judge_v1 actually produced, and only
    once prediction.txt exists and is newer than the v1 run.
"""
import json
import os
import sys
from datetime import datetime, timezone

from src import EVALS, RUNS
from evals.common import (LABELS, PREDICTION, answers_path, git_commit_of, load_cases, now,
                          read_jsonl, sha256_file)
from evals.judge import judge, judge_path


def _labels() -> dict:
    if not LABELS.exists():
        raise SystemExit("labels_25.json does not exist. Label first: python3 -m week6.label")
    lab = json.loads(LABELS.read_text())
    if len(lab["labels"]) != 25 or "finalized_at" not in lab:
        raise SystemExit("labels_25.json is not a finished set of 25 labels")
    if lab["answers_sha256"] != sha256_file(answers_path("v1")):
        raise SystemExit("runs/answers_v1.jsonl changed after labelling - the labels do not "
                         "describe these answers")
    return lab


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def run(version: str) -> None:
    lab = _labels()
    started = now()
    if _ts(lab["finalized_at"]) >= _ts(started):
        raise SystemExit("judge would start before the labels were finalized")
    commit = git_commit_of(LABELS)
    if commit and _ts(commit[1]) > _ts(started):
        raise SystemExit("labels_25.json was committed after this run started")
    if not judge_path(version).exists():
        raise SystemExit(f"{judge_path(version).name} does not exist")

    cases = {c["id"]: c for c in load_cases()}
    answers = {r["id"]: r for r in read_jsonl(answers_path("v1"))}
    rows = []
    for i, (cid, h) in enumerate(sorted(lab["labels"].items()), 1):
        print(f"  judge {version} {i}/25 {cid}", file=sys.stderr)
        j = judge(version, cases[cid], answers[cid]["answer"])
        rows.append({"id": cid, "mode": cases[cid]["mode"], "human": h["label"],
                     "judge": j["verdict"], "agree": j["verdict"] == h["label"],
                     "human_note": h["note"], "judge_rationale": j["rationale"]})
    agree = sum(r["agree"] for r in rows)
    out = {"judge": version, "judge_sha256": sha256_file(judge_path(version)),
           "labels_sha256": sha256_file(LABELS), "labels_finalized_at": lab["finalized_at"],
           "labels_git_commit": commit[0] if commit else None,
           "started_at": started, "finished_at": now(),
           "agreement": round(agree / len(rows), 4), "agree": agree, "n": len(rows),
           "confusion": {f"human {h} / judge {j}": sum(r["human"] == h and r["judge"] == j
                                                       for r in rows)
                         for h in ("PASS", "FAIL") for j in ("PASS", "FAIL")},
           "rows": rows}
    (RUNS / f"agreement_{version}.json").write_text(json.dumps(out, indent=1))
    print(f"\njudge {version}: agreement {agree}/{len(rows)} = {100 * agree / len(rows):.0f}%")
    for k, v in out["confusion"].items():
        print(f"  {k:<28} {v}")
    print("\ndisagreements:")
    for r in rows:
        if not r["agree"]:
            print(f"  {r['id']} ({r['mode']}): human {r['human']}, judge {r['judge']}"
                  + (f" - human note: {r['human_note']}" if r["human_note"] else ""))


def build_v2(ids: list) -> None:
    if len(ids) != 2:
        raise SystemExit("give exactly two case ids")
    v1_path = RUNS / "agreement_v1.json"
    if not v1_path.exists():
        raise SystemExit("run judge v1 first")
    v1 = json.loads(v1_path.read_text())
    if not PREDICTION.exists() or not PREDICTION.read_text().strip():
        raise SystemExit("write prediction.txt first - one sentence on what the iteration "
                         "will fix. It must exist BEFORE judge_v2 is built.")
    if os.path.getmtime(PREDICTION) < os.path.getmtime(v1_path):
        raise SystemExit("prediction.txt is older than the v1 judge run; it should be written "
                         "after reading v1's disagreements and before iterating")
    if judge_path("v2").exists():
        raise SystemExit("judge_v2.txt already exists")
    rows = {r["id"]: r for r in v1["rows"]}
    bad = [i for i in ids if i not in rows or rows[i]["agree"]]
    if bad:
        raise SystemExit(f"{bad} are not disagreements of judge v1")

    cases = {c["id"]: c for c in load_cases()}
    answers = {r["id"]: r for r in read_jsonl(answers_path("v1"))}
    ex = ["\nTwo graded examples. In each, a previous grader got the verdict wrong; the "
          "verdict shown is the correct one.\n"]
    for n, i in enumerate(ids, 1):
        r = rows[i]
        why = r["human_note"] or "(no reason recorded)"
        ex.append(f"<example {n}>\nDeveloper on: {cases[i]['api_version']}\n"
                  f"Question: {cases[i]['question']}\nAnswer:\n{answers[i]['answer']}\n"
                  f"Correct verdict: {r['human']} - {why}\n</example {n}>\n")
    v1_text = judge_path("v1").read_text()
    judge_path("v2").write_text(v1_text.replace("<<EXAMPLES>>", "\n".join(ex)))
    (RUNS / "judge_v2_examples.json").write_text(json.dumps(
        {"examples": ids, "prediction_sha256": sha256_file(PREDICTION), "built_at": now()},
        indent=1))
    print(f"wrote {judge_path('v2').name} with examples {ids}. diff:  "
          f"diff evals/judge_v1.txt evals/judge_v2.txt")


def report() -> None:
    a = {v: json.loads((RUNS / f"agreement_{v}.json").read_text())
         for v in ("v1", "v2") if (RUNS / f"agreement_{v}.json").exists()}
    if "v1" not in a:
        raise SystemExit("no judge runs yet")
    ex = json.loads((RUNS / "judge_v2_examples.json").read_text())["examples"] \
        if (RUNS / "judge_v2_examples.json").exists() else []
    print(f"agreement_before (judge v1): {a['v1']['agree']}/25 = {a['v1']['agreement']:.0%}")
    if "v2" in a:
        print(f"agreement_after  (judge v2): {a['v2']['agree']}/25 = {a['v2']['agreement']:.0%}")
        held = [r for r in a["v2"]["rows"] if r["id"] not in ex]
        h1 = [r for r in a["v1"]["rows"] if r["id"] not in ex]
        print(f"held-out (the 23 not used as examples): v1 {sum(r['agree'] for r in h1)}/23 "
              f"-> v2 {sum(r['agree'] for r in held)}/23")
        flips = [(r1["id"], r1["agree"], r2["agree"])
                 for r1, r2 in zip(a["v1"]["rows"], a["v2"]["rows"]) if r1["agree"] != r2["agree"]]
        print("changed between v1 and v2: " + (", ".join(
            f"{i} {'fixed' if not x and y else 'BROKE'}" for i, x, y in flips) or "none"))
    if PREDICTION.exists():
        print(f"\nprediction.txt: {PREDICTION.read_text().strip()}")
    summary = {v: {"agree": x["agree"], "n": x["n"], "agreement": x["agreement"]}
               for v, x in a.items()}
    (RUNS / "agreement_summary.json").write_text(json.dumps(summary, indent=1))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "run" and len(sys.argv) == 3 and sys.argv[2] in ("v1", "v2"):
        run(sys.argv[2])
    elif cmd == "build-v2":
        build_v2(sys.argv[2:])
    elif cmd == "report":
        report()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
