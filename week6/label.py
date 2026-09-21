"""Hand-label the 25 authored cases BLIND, before the judge has ever run.

    python3 -m week6.label

Shows each app-v1 answer with the question and the developer's version - never an
assertion result and never a judge verdict - and asks the single binary criterion the
judge will be asked: CORRECT_AND_USABLE, PASS or FAIL. Progress is saved after every
answer, so you can stop and resume.

Refuses to start if any judge output exists. When the 25th label is in, it writes
labels_25.json with the sha256 of the answers file it labelled. Commit it before
running the judge:  git add labels_25.json && git commit -m "labels: 25 blind hand labels"
"""
import json
import sys

from src import RUNS
from evals.common import LABELS, answers_path, load_cases, now, read_jsonl, sha256_file
from evals.judge import CACHE

PARTIAL = RUNS / "labels_partial.json"
CRITERION = ("CORRECT_AND_USABLE - using only the Ledgerline docs as ground truth, does the "
             "answer correctly resolve the question for the developer's API version, so they "
             "could act on it without another lookup? (A correct 'not covered' passes; a "
             "guess fails.)")


def main() -> None:
    if LABELS.exists():
        raise SystemExit(f"{LABELS.name} already exists and is final. Delete it only if you "
                         "mean to throw the labels away.")
    if CACHE.exists() or list(RUNS.glob("agreement_*.json")):
        raise SystemExit("A judge has already run. Labels written now would not be blind.")
    ans_path = answers_path("v1")
    answers = {r["id"]: r for r in read_jsonl(ans_path)}
    cases = [c for c in load_cases() if c.get("source", "authored") == "authored"][:25]
    missing = [c["id"] for c in cases if c["id"] not in answers]
    if missing:
        raise SystemExit(f"no app-v1 answers for {missing}. Run: python3 -m week6.run_eval --no-judge")

    state = json.loads(PARTIAL.read_text()) if PARTIAL.exists() else {
        "answers_file": ans_path.name, "answers_sha256": sha256_file(ans_path),
        "criterion": CRITERION, "started_at": now(), "labels": {}}
    if state["answers_sha256"] != sha256_file(ans_path):
        raise SystemExit("answers_v1.jsonl changed since labelling started; the labels would "
                         "not describe these answers. Delete runs/labels_partial.json to restart.")

    print(CRITERION + "\n")
    for i, c in enumerate(cases, 1):
        if c["id"] in state["labels"]:
            continue
        print("=" * 78)
        print(f"[{i}/25] {c['id']}   developer is on {c['api_version']}")
        print(f"Q: {c['question']}\n")
        print(answers[c["id"]]["answer"])
        print("-" * 78)
        while True:
            v = input("PASS or FAIL? [p/f] (q to stop) > ").strip().lower()
            if v in ("p", "f", "q"):
                break
        if v == "q":
            print(f"saved {len(state['labels'])}/25 - run again to continue")
            return
        note = input("one-line reason (optional) > ").strip()
        state["labels"][c["id"]] = {"label": "PASS" if v == "p" else "FAIL", "note": note,
                                    "labelled_at": now()}
        PARTIAL.write_text(json.dumps(state, indent=1))

    state["finalized_at"] = now()
    LABELS.write_text(json.dumps(state, indent=1))
    PARTIAL.unlink()
    n = sum(v["label"] == "PASS" for v in state["labels"].values())
    print(f"\nwrote {LABELS.name}: 25 labels, {n} PASS / {25 - n} FAIL, "
          f"finalized {state['finalized_at']}")
    print('now commit it:  git add labels_25.json && git commit -m "labels: 25 blind hand labels"')


if __name__ == "__main__":
    main()
    sys.exit(0)
