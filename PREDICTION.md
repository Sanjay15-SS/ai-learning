# Prediction — written before the change, 2026-09-07

Written after reading the 20 sampled traces and before editing a single line of the
answering pipeline. Nothing in `src/` has been touched since the traces were written;
`traces/traces.jsonl` and `traces/demo.jsonl` carry the corpus fingerprint
`9b8a6bebfcbe` and the policy sha `70a289f254db`, and both still match what the code
produces today, which `replay.py` checks before it will run at all.

This folder is not a git repository, so there is no commit hash to point at. What
stands in for one: `results-week5.md` records the sha256 of this file as it was when
the prediction was made. If the file is edited afterwards, that number stops matching.

## The change

One line in `src/__init__.py`:

```
COVERAGE_FLOOR = 0.55   ->   0.35
```

Nothing else. Same corpus, same chunker, same embedding model, same hybrid retriever,
same top-3, same extraction rule.

## Why this change and not another

The top failure mode in the sample is the term-coverage gate refusing a question the
corpus can answer. It fired on 4 of the 20 traces I read, and on 25 of the 117 in the
file. It is the only mode in the taxonomy that is a single tunable number, so it is
the only one where a prediction can be stated in figures and then checked.

## What I expect, in numbers

Read off the coverage scores already recorded in the traces:

| | now | predicted after |
|---|---|---|
| term-coverage refusals | 25/117 | **7/117** |
| refusals of any kind | 25/117 | **7/117** |
| questions released by the change | — | **18** |

Of those 18 released questions:

- **at least 7** come back citing a chunk that genuinely answers the question.
- **at most 12** come back citing a chunk that does not answer it — an answer with a
  citation attached that does not support it.
- **all four** of the questions this corpus cannot answer (D099 subrogation deadline,
  D100 reserve threshold, D101 assigned adjuster, D102 reinsurance attachment point)
  stop refusing and start answering, each from an unrelated clause. That is four new
  confident wrong answers where there were four correct refusals.

## The verdict I expect to reach

**Do not ship it.** I expect the change to buy back roughly seven correct answers and
to cost four correct refusals plus a tail of unsupported ones. A gate that refuses on
the fraction of question words found in the corpus is measuring the wrong thing, and
moving its threshold trades one failure mode for another rather than removing either.
The number to watch is not the refusal count, it is the four out-of-corpus questions.

If the released answers come back better than this — say 12 or more correctly cited
and the four out-of-corpus questions still refused — then the gate was simply set too
high and I have misread the mechanism.
