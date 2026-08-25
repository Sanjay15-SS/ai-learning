# Week 3 Task Set D — Insurance Claims RAG

Ingest the new endorsement pack and prove the chunking finds the answer.

**The deliverable is [`results.md`](results.md)** — the 8 questions with their gold
form_number/clause, both hit-in-top-5 numbers, the per-question record, the
search-only dump, the unfiltered vs filtered lists, the 3 cited answers, the 3
refusal transcripts, the bonus, and the chunking defence.
[`code-diff.md`](code-diff.md) is the checklist's code diff.

Everything runs locally. **No API key, no network, no model service.**

## Run

```bash
pip3 install --user -r requirements.txt
python3 run_eval.py
```

That writes `results.md`. Takes about 30 seconds.

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
 run_pipeline.py  measures both strategies, writes results.md
```

## Files

```
ai-task/
├── data/
│   └── endorsements/      the 6 new forms
├── src/
│   ├── __init__.py        config + the Document / Chunk records
│   ├── chunkers.py        BOTH chunking strategies
│   ├── indexer.py         load + form metadata, embed, Chroma HNSW index
│   ├── retriever.py       top-K search + policy_line filtering
│   └── generator.py       extractive answer + forced refusal
├── app.py                 ask one question by hand
├── questions.json         the 8 gold questions + 3 unanswerable (data, not code)
├── run_pipeline.py        <- ONE COMMAND: writes results.md
├── requirements.txt
├── results.md             <- THE DELIVERABLE (generated)
├── code-diff.md           <- the checklist's code diff (generated)
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
legitimate 0.7174). `results.md` section 5.1 shows the full measurement.

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
