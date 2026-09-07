# Task Set D — Insurance Claims RAG

> This folder is the Week 3 snapshot and the Week 4 tree merged back into one
> runnable project. `src/` and `data/` had been lost from the Week 4 tree and were
> restored from the Week 3 snapshot plus the code diffs. What was rebuilt, and what
> the rebuild does and does not reproduce, is in [`RECONSTRUCTION.md`](RECONSTRUCTION.md).

**Week 5 is the current deliverable: [`results-week5.md`](results-week5.md)** — 117 traced
questions, 20 read by hand, a ranked failure taxonomy in [`taxonomy.md`](taxonomy.md), the
reading notes in [`notes-week5.md`](notes-week5.md), and a dated prediction in
[`PREDICTION.md`](PREDICTION.md). Week 5 changes nothing in the answering path.

**Week 4 is [`results.md`](results.md):** label the failures, then try to buy back
hit-rate@3 with exactly one retrieval change.

```bash
python3 -m pip install --user -r requirements.txt   # NOT `pip3` - see note below
python3 run_week4.py                         # writes results.md + eval_record.json
python3 inspect_query.py --qid G01           # the inspection view for one question
python3 inspect_query.py --qid G01 --mode dense
```

> **Use `python3 -m pip`, not `pip3`.** On a Mac with both Homebrew Python and the
> python.org build installed, `pip3` and `python3` can be *different interpreters*: `pip3`
> then fails with `error: externally-managed-environment` (PEP 668) while installing into a
> Python that never runs this project. `python3 -m pip` always uses the pip belonging to the
> `python3` you just named. Do not pass `--break-system-packages`. A venv works too:
> `python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install -r requirements.txt`

| Week 4 headline | |
|---|---|
| Golden set | 12 real adjuster questions, `golden_set.jsonl`, each with its known-correct chunk_id; 7 carry an exact token (exclusion code / form number / edition) |
| Baseline hit-rate@3 | **9/12**, frozen to `baseline_record.json` before any change |
| Failure tally | 3 R · 5 G · 0 Not-In-Corpus (+1 uncounted NIC probe) |
| The one change | `RETRIEVAL_MODE` dense → hybrid: dense top-25 + BM25 top-25, RRF k=60 |
| After | **8/12**, p50 +~1.5 ms (inside the noise floor; `results.md` §6 has the run's exact figures) |
| Decision | **do not ship** — see `results.md` §9 |

Week 4 files: `golden_set.jsonl`, `probes.jsonl`, `src/bm25.py`, `src/inspect_view.py`,
`src/mmr.py`, `inspect_query.py`, `run_week4.py`, `write_results.py`,
[`code-diff-week4.md`](code-diff-week4.md).

The Week 3 deliverable is still reproducible and now writes
[`results-week3.md`](results-week3.md): `python3 run_pipeline.py`. It is pinned to the dense
retriever it was measured with, so Week 4's change cannot silently restate Week 3's numbers.

---

## Week 3 — ingest the new endorsement pack and prove the chunking finds the answer

**The Week 3 deliverable is [`results-week3.md`](results-week3.md)** — the 8 questions with their gold
form_number/clause, both hit-in-top-5 numbers, the per-question record, the
search-only dump, the unfiltered vs filtered lists, the 3 cited answers, the 3
refusal transcripts, the bonus, and the chunking defence.
[`code-diff.md`](code-diff.md) is the checklist's code diff.

Everything runs locally. **No API key, no network, no model service.**

## Run

```bash
python3 -m pip install --user -r requirements.txt
python3 run_pipeline.py
```

That writes `results-week3.md`. Takes about 30 seconds.

## Pipeline

```
              6 endorsements
                     |
 src/indexer.py   load + stamp form_number / policy_line / edition_date / source_file
                     |
 src/chunkers.py  Strategy 1: Naive  ──┐   Strategy 2: Structure-Aware ──┐
                                       |                                 |
 src/indexer.py   BAAI/bge-small-en-v1.5  (same model, both strategies)
                                       |                                 |
                  Chroma collection        Chroma collection
                  (in-memory, HNSW, cosine)
                                       |                                 |
 src/retriever.py top-K + policy_line filter (DB-side `where` clause)
                     |
 src/generator.py answer quoted from the cited chunk, or a forced refusal
                     |
 run_pipeline.py  measures both strategies, writes results-week3.md
```

## Files

```
ai-task/
├── data/
│   └── endorsements/      the 6 forms + 2 further HO-0304 editions (Week 4)
├── src/
│   ├── __init__.py        config + the Document / Chunk records
│   ├── chunkers.py        BOTH chunking strategies
│   ├── indexer.py         load + form metadata, embed, Chroma HNSW index
│   ├── retriever.py       top-K search + policy_line filtering
│   └── generator.py       extractive answer + forced refusal
│   ├── bm25.py            WEEK 4: BM25 over the indexed chunks
│   ├── mmr.py             WEEK 4: MMR over the fused list (bonus)
│   └── inspect_view.py    WEEK 4: the inspection view + the R/G/NIC label rule
├── app.py                 ask one question by hand
├── inspect_query.py       WEEK 4: inspection view for one question
├── questions.json         the 8 Week 3 gold questions + 3 unanswerable
├── golden_set.jsonl       WEEK 4: 12 adjuster questions + known-correct chunk_id
├── probes.jsonl           WEEK 4: the uncounted Not-In-Corpus probe
├── run_pipeline.py        Week 3: writes results-week3.md (pinned to dense)
├── run_week4.py           <- WEEK 4 ONE COMMAND: writes results.md
├── write_results.py       WEEK 4: renders results.md from eval_record.json
├── baseline_record.json   WEEK 4: the 9/12 baseline, frozen before any change
├── eval_record.json       WEEK 4: every number in results.md, machine-readable
├── requirements.txt
├── results.md             <- THE WEEK 4 DELIVERABLE (generated)
├── results-week3.md       the Week 3 deliverable (generated)
├── code-diff-week4.md     <- the ONE retrieval change (generated)
├── code-diff.md           the Week 3 code diff (generated)
└── README.md
```

## The two chunkers

| | `baseline` | `structure_aware` |
|---|---|---|
| Split on | fixed 900-char windows, 150 overlap | form / clause headers |
| Tables | cut wherever the window lands | one chunk per row |
| Row context | whatever the window happened to include | form number + edition + policy line + clause + table header, always |

Both stamp `source_file`, `form_number`, `policy_line`, `edition_date` on every
chunk, and both use the same embedding model — changing the chunker and the
embedding model in one run would teach you nothing about which one moved.

## How answers and refusals work without a model

The answer is **quoted verbatim** from the highest-scoring chunk, never composed,
so it cannot state anything the cited chunk does not say. Refusal is a gate in
code, not a request to a model:

1. **Term coverage** — the question's content words are checked against the
   indexed corpus. Measured margin: worst in-corpus 62%, best out-of-corpus 50%.
2. **Score floor** — backstop for a query with no topical neighbour.

Cosine similarity alone cannot gate this (out-of-corpus scores 0.69–0.71 against a
legitimate 0.7174). `results-week3.md` section 5.1 shows the full measurement.

## The questions

`questions.json` holds the 8 known-answer questions with their gold form_number and
clause, the 3 out-of-corpus questions, the filter-demo query and the bonus probe.
They are data, so they can be reviewed without reading any code — and they were
written from the endorsements before any search was run.

## Swapping in the real endorsement pack

Drop `.md`, `.txt` or `.pdf` files into `data/endorsements/` and re-run. Markdown
uses YAML front matter for metadata; PDFs and plain text fall back to regex over
the header block (`HO-0304 (ed. 03-24)`, `Policy Line: HO-3`). A document missing
`form_number`, `policy_line` or `edition_date` raises at ingest rather than
indexing a chunk with no provenance.

> The 6 forms in `data/endorsements/` are stand-ins written to the spec in the task
> statement (form numbers, edition dates, exclusions tables, exclusion code E-17
> under HO-0304 ed. 03-24). Replace them with the supplied drop before submitting.
