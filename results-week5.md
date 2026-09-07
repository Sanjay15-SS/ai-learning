# Week 5 — Task Set D — Insurance claims

Read 20 real traces by hand, no fixes, and hand back a ranked taxonomy.

**11 of 20 clean, 9 of 20 failed, 5 named modes.** The manager's "it refuses too much
and sometimes cites the wrong thing" turns out to be six wrong or empty denials, one
answer taken off the wrong form, and two confident answers to questions the wording
does not address, with a trace id against each.

| # | Failure mode | Count | % of 20 | Severity |
|---|---|---|---|---|
| 1 | Refuses on the question's vocabulary while the answering clause is in the retrieved context | 4 | 20% | wrongly denies |
| 2 | Answers a question the corpus is silent on, quoting an unrelated clause instead of refusing | 2 | 10% | misleads |
| 3 | Answers from the wrong edition of the right form | 1 | 5% | wrongly denies |
| 4 | Answers from the wrong form entirely | 1 | 5% | **wrongly pays** |
| 5 | Quotes the general rule when the question asked for the figure | 1 | 5% | wrong payment |

Full taxonomy with example trace ids: **[`taxonomy.md`](taxonomy.md)**. The 20
observation sentences, the seed, the replay evidence, the redaction scan and the
demo-set comparison: **[`notes-week5.md`](notes-week5.md)**.

**Prediction, written before any fix** — 2026-09-07, sha256
`e9fb07bdd5bbead2f618b19282d277a0844671d049588afc163eb4f77893cf55`. Drop
`COVERAGE_FLOOR` from 0.55 to 0.35; expect term-coverage refusals 25/117 → 7/117, at
least 7 of those 18 correctly cited, at most 12 unsupported, and all four out-of-corpus
questions to start answering. Expected verdict: do not ship.
**[`PREDICTION.md`](PREDICTION.md)**.

**Bonus** — the top mode runs at **20% in the random 20 and 0% in the demo 10**. Overall
failures: **45% random, 0% demo**. The paragraph about what that means is
`notes-week5.md` §7.

## Run

Week 5 sits on top of the Week 3/4 pipeline in this folder and changes none of it.

```bash
python3 selftest.py                    # 42 checks on the plumbing, nothing indexed
python3 run_traffic.py                 # 117 desk questions -> traces/traces.jsonl
python3 run_traffic.py demo            # 10 review questions -> traces/demo.jsonl
python3 sample.py                      # the seeded 20
python3 sample.py --replay-pick        # the trace to replay
python3 replay.py <trace_id>           # original vs replayed
python3 show.py --sample               # the 20, laid out for reading
```

`run_traffic.py` refuses to overwrite an existing trace file. Delete it to re-run.

## Files

| file | role |
|---|---|
| `data/`, `src/`, `app.py` | the Week 3/4 pipeline, carried over untouched |
| `assistant.py` | the Week 4 answering logic with a trace written around it |
| `prompts.py` | the answering policy under a version id, so a trace can be replayed after an edit |
| `redact.py` | strips claimant identifiers on the way **in** to the writer |
| `trace.py` | one JSON line per question; redacts, asserts, then appends |
| `questions.py` | 117 desk questions and the 10 demo questions, written before anything ran |
| `run_traffic.py` | fills the trace files |
| `sample.py` | the seeded random draw |
| `replay.py` | rebuilds one trace from the trace alone |
| `show.py` | lays traces out for reading, and computes nothing |
| `selftest.py` | 42 mechanical checks on the plumbing, retrieval stubbed |
| `traces/` | 117 desk traces, 10 demo traces |

## Notes

Nothing here needs an API key or a network. There is no model in the answering path:
answers are quoted verbatim from the cited chunk, which is why `replay.py` can rebuild
all 127 traces byte for byte and why the two mistake-shaped modes, 2 and 4, are the app
citing the wrong passage rather than writing something the passage does not say.

The answering pipeline is unchanged from Week 4, including its use of the hybrid
retriever, which Week 4 measured as no better than dense on hit-rate@3 and recommended
against shipping. Fixing that first would have produced a taxonomy of an app nobody is
running.

Two of the eight source documents in `data/endorsements/` are reconstructions, as
`RECONSTRUCTION.md` records. Mode 3 turns on three near-identical editions of HO-0304,
two of which are rebuilt files, so the mode is real but its exact retrieval margin is
not evidence about the original pack. That caveat is repeated in `notes-week5.md` §8.
