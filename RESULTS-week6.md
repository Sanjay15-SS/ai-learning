# Week 6 - Validate the docs-answer judge (Task Set E)

Model for app and judge: `mlx-community/Qwen2.5-3B-Instruct-4bit` (local, MLX; no API key).

## 1. Eval set

**25 cases**: 25 authored + **0 regression cases replayed verbatim from real failed traces**. Every case is tagged with exactly one taxonomy mode (`evals/TAXONOMY.md`).

| mode | cases |
|---|---|
| `version_confusion` | 6 |
| `deprecated_no_migration` | 4 |
| `hallucinated_endpoint` | 4 |
| `broken_sample` | 3 |
| `unanswerable` | 4 |
| `conceptual` | 4 |

> **PENDING** - run `python3 -m week6.traffic --failed && python3 -m week6.promote <trace_id> --mode <mode>`

## 2. Assertions vs judged criteria

**7 deterministic assertions vs 1 judged criterion.**

Moved out of the judge prompt into code (`evals/assertions.py`), and deleted from the prompt (`evals/judge_v0_all_criteria.txt` -> `evals/judge_v1.txt`):

- `code_parses`
- `endpoints_exist`
- `version_stated`
- `deprecations_noted`

All assertions: `version_stated`, `code_parses`, `endpoints_exist`, `no_v2_in_v3_code`, `deprecations_noted`, `refusal_correct`, `must_include`. The one judged criterion: `CORRECT_AND_USABLE`, binary PASS/FAIL.

## 3. One command - pass rate by mode

`python3 -m week6.run_eval` - app v1 (retrieval over every version, shipped) vs app v2 (retrieval scoped to the developer's version, the one change).

> **PENDING** - run `python3 -m week6.run_eval --no-judge`

## 4. Blind labels - ordering evidence

> **PENDING** - run `python3 -m week6.label   (you label; the judge refuses to run until this exists)`

## 5. Judge agreement - before -> after

> **PENDING** - run `python3 -m week6.judge_eval run v1   (after labels)`

## 6. Prediction and disagreement notes

> **PENDING** - run `write prediction.txt - one sentence, after reading v1's disagreements`

> **PENDING** - run `write DISAGREEMENTS.md - 2 disagreements, who was right, where the prediction was wrong`

