# Task Set E — Ledgerline docs assistant (Weeks 6 and 7)

A docs assistant for a fictional payments API ("Ledgerline") with a **v2** and a **v3**,
so that "a v2 endpoint recommended to a v3 user" is a failure that can actually happen.

- Week 6: validate the docs-answer judge before trusting its number.
- Week 7: race the docs agent against a fixed workflow.

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate                   # every command below assumes the venv
python3 selftest.py                         # 50 offline checks with a scripted fake model
```

**No API key needed.** By default every model call runs **locally**: Qwen2.5-3B-Instruct
(4-bit, MLX, about 1.7 GB, downloaded once) on this Mac, with greedy decoding so re-runs
repeat. The app, judge, agent and workflow all use this one model.

Tokens are counted exactly, from the model's own tokenizer. Actual spend is **$0**, so
the cost column is a *reference*: the same tokens priced at Claude Haiku 4.5 list rates
($1/$5 per M). That keeps agent vs workflow comparable in dollars.

Set `ANTHROPIC_API_KEY` and the same code runs on `claude-opus-5` instead
(`DOCS_BACKEND=anthropic`); `src/llm.py` is the only place a model is called.

Run every command from this folder (`ai-learning-week-4/`). The scripts live in `week6/` and
`week7/` and import `src/`, so they are run as modules: `python3 -m week7.agent`, not
`python3 week7/agent.py`.

## Week 6 — run it in this order (the order is the protocol)

| # | command | produces |
|---|---|---|
| 0 | `git init && git add -A && git commit -m "chore: week 6 baseline"` | commit history is the ordering proof |
| 1 | `python3 -m week6.traffic` then `python3 -m week6.traffic --failed` | 30 real app-v1 traces, and the ones that failed |
| 2 | `python3 -m week6.promote <trace_id> --mode <mode> --must ...` (at least twice) | regression cases R01, R02, copied word for word from real failed traces |
| 3 | `python3 -m week6.run_eval --no-judge` | app answers + assertion pass rate by mode (judge stays locked) |
| 4 | `python3 -m week6.label`, then commit `labels_25.json` | **your** 25 blind labels, committed before any judge run |
| 5 | `python3 -m week6.judge_eval run v1` | **agreement_before** + v1's disagreements |
| 6 | write `prediction.txt` (one sentence), commit it | the prediction, dated before the iteration |
| 7 | `python3 -m week6.judge_eval build-v2 <id> <id>` | `evals/judge_v2.txt` = v1 + two of v1's own disagreements as few-shot examples |
| 8 | `python3 -m week6.judge_eval run v2` then `python3 -m week6.judge_eval report` | **agreement_after**, plus agreement on the 23 cases not used as examples |
| 9 | `python3 -m week6.run_eval` | **the one command**: every case, assertions + judge, pass rate by mode, app v1 vs v2 |

Guards in code, not on trust: `week6/label.py` refuses once any judge output exists. The judge
refuses until `labels_25.json` is final, matches the answers file, and was committed
before the run. `build-v2` refuses without `prediction.txt` newer than the v1 run, and
refuses examples that were not v1 disagreements.

**Assertions vs judge**: 7 deterministic assertions (`evals/assertions.py`) against 1
judged criterion (`CORRECT_AND_USABLE`, binary). Four criteria moved out of the judge:
`code_parses`, `endpoints_exist`, `version_stated`, `deprecations_noted`. See
`evals/judge_v0_all_criteria.txt` (before) against `evals/judge_v1.txt` (after).

**Cases**: 25 authored cases in `evals/cases.jsonl`, one taxonomy mode each (6 modes,
`evals/TAXONOMY.md`), plus the regression cases from step 2.

**The one app change** (per-mode before/after in step 9): app v1 retrieves from every
version; app v2 limits retrieval to the version the developer is on. Nothing else differs.

## Week 7

```bash
python3 -m week7.agent "Port our POST /v2/charges call to v3"   # the loop, every lap logged
python3 -m week7.workflow "Port our POST /v2/charges call to v3" # fixed 3 steps + 1 write, no loop
python3 -m week7.race                                            # 10 questions x 2 -> race.csv
python3 -m week7.agent --budget-demo                             # -> logs/budget_termination.log
python3 -m week7.agent --tool-diff                               # -> TOOL_DESCRIPTIONS_DIFF.md
```

- **Third tool**: `check_deprecation(symbol, api_version: enum[v2,v3])`. The same change
  sharpens `search_docs` and `get_openapi_spec`, whose old descriptions overlapped.
- **Budgets** (`agent.Budget`): max iterations, max tokens, max cost, wall clock. All four
  are checked before every call and after it. Tokens are summed over every lap.
- **Race set** (`week7/race_questions.jsonl`): 5 questions where step 3 depends on step 2 (the
  v2 endpoint is deprecated, so the replacement must be looked up), and 5 single-lookup
  questions.
- **Workflow**: the same tool implementations, model and output contract. It cannot take a
  fourth look, so on a deprecated endpoint the replacement's spec is never fetched.

The verdict is written from `race.csv` after the race has run, not before.

## Files

| path | role |
|---|---|
| `corpus/` | 14 docs pages (v2 + v3), `openapi_v2.json`, `openapi_v3.json`, `changelog.json` |
| `src/` | config, corpus search, tools, model wrapper, output contract, the Week 6 app |
| `evals/` | cases, assertions, judge prompts, taxonomy |
| `week6/` | `run_eval.py` · `label.py` · `judge_eval.py` · `traffic.py` · `promote.py` |
| `week7/` | `agent.py` · `workflow.py` · `race.py` · `race_questions.jsonl` |
| `make_report.py` | writes `RESULTS-week6.md` and `RESULTS-week7.md` from the run outputs |
| `selftest.py` | 50 offline checks with a scripted fake model |
