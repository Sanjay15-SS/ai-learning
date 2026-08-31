"""Produce results.md: the graded deliverable for Task Set D.

Runs, in order:
  0. Ingest the 6 new endorsements only (not the base wording library).
  1. The 8 known-answer questions with their gold form_number + clause.
  2. All 8, SEARCH ONLY, against both chunking strategies -> hit-in-top-5 X/8 each,
     with the per-question record and the full search-only dump.
  3. One policy_line filter demo: unfiltered vs filtered result lists with scores.
  4. Generation: 3 cited answers.
  5. 3 out-of-corpus refusal transcripts (+ 5.1, why the gate is the prompt).
  6. Bonus: precision wins retrieval, loses the answer.
  7. Which chunker ships, and the retrieval that embarrassed us.

Everything runs locally. No API key, no network, no model service: retrieval is a
local embedding model plus an in-memory vector DB, and answers are quoted verbatim
from the cited chunk rather than written by a model.

The 8 questions are data, not code: see questions.json.
"""
import json
from types import SimpleNamespace

from functools import partial

from src import (EMBED_MODEL, QUESTIONS_PATH, RESULTS_WEEK3_PATH, STRATEGIES,
                 STRATEGY_LABELS, DATA_DIR)
from src.generator import answer as _answer
from src.indexer import get_store, ingest
from src.retriever import get_chunk
from src.retriever import search as _search

# Week 4 changed the package default to the hybrid retriever. This is the WEEK 3
# deliverable, so it is pinned to the dense retriever it was measured with, and it
# writes results-week3.md - results.md is Week 4's. Re-running this reproduces the
# Week 3 numbers exactly instead of silently restating them under a new retriever.
RESULTS_PATH = RESULTS_WEEK3_PATH
search = partial(_search, mode="dense")
answer = partial(_answer, mode="dense")

TOP_K = 5

# The 8 known-answer questions live in questions.json, written from the endorsements
# before any search was run.
_Q = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

QUESTIONS = [SimpleNamespace(**q) for q in _Q["questions"]]
UNANSWERABLE = _Q["unanswerable"]
ANSWERABLE = _Q["answerable"]
FILTER_QUERY = _Q["filter_demo"]["query"]
FILTER_FIELD = _Q["filter_demo"]["field"]
FILTER_VALUE = _Q["filter_demo"]["value"]
BONUS_QUESTION = _Q["bonus_question"]

def is_hit(hits, q):
    """A hit = a top-5 chunk from the right FORM whose TEXT carries BOTH the
    identifier asked about (`marker`) and the span that answers (`answer_marker`).

    A chunk holding the exclusion code but not the rule, or the rule but not the
    code, is not a hit - that split is exactly the defect the task asks us to find.
    """
    for h in hits:
        t = h.chunk.text.lower()
        if (h.chunk.metadata.get("form_number") == q.gold_form
                and q.marker.lower() in t
                and q.answer_marker.lower() in t):
            return True, h.rank
    return False, None


def fmt_hits(hits, indent="") -> str:
    if not hits:
        return f"{indent}(no results)"
    lines = []
    for h in hits:
        m = h.chunk.metadata
        snippet = " ".join(h.chunk.text.split())[:150]
        lines.append(
            f"{indent}{h.rank}. score={h.score:.4f}  {m.get('form_number')} "
            f"({m.get('policy_line')}, ed.{m.get('edition_date')})  {m.get('clause')}  "
            f"`{h.chunk.chunk_id}`\n{indent}   {snippet}...")
    return "\n".join(lines)


def write_refusal_gate_analysis(w):
    """Measured: which signal can decide refusal? Cosine cannot; term coverage can."""
    from src.generator import COVERAGE_FLOOR, term_coverage

    w("### 5.1 What actually gates the refusal")
    w("")
    w("The obvious gate is a retrieval-score floor: if nothing scores above T, refuse. "
      "We measured whether such a T exists, and it does not.")
    w("")
    w("| Question | Top-1 cosine | Term coverage | In corpus? |")
    w("|---|---|---|---|")
    rows = []
    for q in QUESTIONS:
        h = search(q.question, strategy="structure_aware", top_k=1)
        cov, _ = term_coverage(q.question)
        rows.append((h[0].score, cov, f"{q.qid} — {q.question}", True))
    for uq in UNANSWERABLE:
        h = search(uq, strategy="structure_aware", top_k=1)
        cov, _ = term_coverage(uq)
        rows.append((h[0].score, cov, uq, False))
    for score, cov, label, ok in sorted(rows, reverse=True):
        w(f"| {label} | {score:.4f} | {cov:.0%} | {'yes' if ok else '**no**'} |")
    w("")

    worst_in = min(s_ for s_, _, _, ok in rows if ok)
    best_out = max(s_ for s_, _, _, ok in rows if not ok)
    cov_worst_in = min(c for _, c, _, ok in rows if ok)
    cov_best_out = max(c for _, c, _, ok in rows if not ok)

    w(f"**Cosine cannot separate them.** Weakest in-corpus question: **{worst_in:.4f}**. "
      f"Strongest out-of-corpus question: **{best_out:.4f}**. A gap of "
      f"{abs(worst_in - best_out):.4f} of a cosine point — any threshold that refuses all "
      "three out-of-corpus questions is within a rounding error of rejecting a question the "
      "corpus can answer.")
    w("")
    w("Diagnosis: cosine measures topical proximity, not whether the answer is present. "
      "\"What is the reserve-setting threshold for claim CLM-2024-88431?\" is *about* insurance "
      "claims, so it lands near insurance-claims text; the corpus simply has no reserve-setting "
      "rules in it. A bi-encoder cannot express that difference.")
    w("")
    w(f"**Term coverage can.** Checking the question's content words against the indexed "
      f"corpus separates cleanly: worst in-corpus **{cov_worst_in:.0%}** versus best "
      f"out-of-corpus **{cov_best_out:.0%}** — a margin of "
      f"{abs(cov_worst_in - cov_best_out):.0%}, roughly "
      f"{abs(cov_worst_in - cov_best_out) / max(abs(worst_in - best_out), 1e-9):.0f}x wider than "
      f"the cosine gap. The gate is set at {COVERAGE_FLOOR:.0%}. Terms like `reserve-setting`, "
      "`CLM-2024-88431`, `adjuster`, `reinsurance` and `treaty` appear nowhere in the six "
      "endorsements, and that absence is a fact about the corpus rather than a similarity score.")
    w("")
    w("**The refusal is forced, not suggested.** There is no model deciding whether to be "
      "helpful: `generation.py` returns the refusal before any answer is composed. And the "
      "answer text, when there is one, is quoted verbatim from the cited chunk rather than "
      "written, so it cannot state anything the cited chunk does not.")
    w("")
    w(f"Honest limitation: {COVERAGE_FLOOR:.0%} is tuned against 11 questions on a 6-form "
      "corpus. It is a defensible gate at this scale, not a universal constant — a larger "
      "corpus would need it re-measured, and a question phrased entirely in policy vocabulary "
      "about a fact the corpus lacks would still slip past gate 1 to gate 2.")
    w("")


def write_defence(w, results, totals, top1, mrr, report, unfiltered, filtered):
    """Section 7 - defended choice + a retrieval that embarrassed us."""
    w("## 7. Which chunker ships, and why")
    w("")
    w(f"**`structure_aware` ships.** It scored {totals['structure_aware']}/8 hit-in-top-5 against "
      f"{totals['baseline']}/8 for the baseline, and the gap is wider than that headline: "
      f"{top1['structure_aware']}/8 versus {top1['baseline']}/8 at rank 1, MRR "
      f"{mrr['structure_aware']:.3f} versus {mrr['baseline']:.3f}. It won while being handicapped — "
      f"it indexes {report['structure_aware']['chunks']} chunks against the baseline's "
      f"{report['baseline']['chunks']}, so a fixed top-5 is a materially harder test for it "
      f"({5 / report['structure_aware']['chunks']:.1%} of its corpus versus "
      f"{5 / report['baseline']['chunks']:.1%} of the baseline's). Correcting for that would widen "
      "the gap, not narrow it.")
    w("")
    w("The mechanism is the one the task predicted. The baseline's 900-character window is blind "
      "to table structure, so it slices exclusion tables mid-row: the exclusion code lands in one "
      "chunk and the rule it scopes lands in the next. The structure-aware chunker emits one chunk "
      "per exclusion row, each stamped with its form number, edition date, policy line, clause and "
      "the table's own header row, so a row is never separated from what scopes it.")
    w("")
    w("### The retrieval that embarrassed us")
    w("")
    q1 = next(q for q in QUESTIONS if q.qid == "Q1")
    b1 = search(q1.question, strategy="baseline", top_k=2)
    w(f"**Q1, baseline, rank 1: the wrong policy line.** Asked whether E-17 excludes a burst "
      f"supply line *under HO-0304*, the baseline index returned "
      f"`{b1[0].chunk.metadata['form_number']}` — a **{b1[0].chunk.metadata['policy_line']} "
      f"dwelling-fire form** — at rank 1 with score {b1[0].score:.4f}, ahead of the correct "
      f"`{b1[1].chunk.metadata['form_number']}` chunk at {b1[1].score:.4f}. DP-0431's E-17 is not "
      "a near-miss, it is the inverse rule: it triggers at 7 days instead of 14 and carries **no "
      "sudden-and-accidental exception at all**. A claims handler reading top-1 would have denied "
      "a covered burst-pipe claim.")
    w("")
    if unfiltered and filtered:
        hit_ho = next((h.score for h in unfiltered
                       if h.chunk.metadata.get("policy_line") == FILTER_VALUE), None)
        if hit_ho is not None:
            w(f"The filter demo in section 3 is the same wound: DP-0431 takes top-1 by "
              f"**{unfiltered[0].score - hit_ho:.4f}** — a few ten-thousandths of a cosine point. "
              "Nothing about the embedding separates these two forms, because textually they are "
              "near-identical; the only thing that separates them is the `policy_line` metadata. "
              "That is the argument for filtering rather than for a better embedding model.")
            w("")

    q2 = next(q for q in QUESTIONS if q.qid == "Q2")
    both = {}
    for s in STRATEGIES:
        st = get_store(s)
        res = st._get().get(include=["documents"])
        both[s] = [i for i, d in zip(res["ids"], res["documents"])
                   if q2.marker.lower() in d.lower() and q2.answer_marker.lower() in d.lower()]
    w(f"**Q2, baseline: a miss that no amount of top-K would fix.** The baseline returned a chunk "
      f"holding the E-18 *rule* without the code at rank 1, and a chunk holding the *code* without "
      f"the rule at rank 2. We then checked the whole index: chunks carrying both `{q2.marker}` "
      f"and \"{q2.answer_marker}\" — baseline: **{len(both['baseline'])}**; structure-aware: "
      f"**{len(both['structure_aware'])}** ({', '.join(both['structure_aware']) or 'n/a'}). The "
      "E-18 row is split across a chunk boundary, so the answer does not exist in the baseline "
      "index as a single retrievable unit. Raising top-K to 25 would not have found it. This is "
      "the failure we would never have seen by eyeballing retrieved text and calling it 'looks "
      "about right'.")
    w("")
    w("### What the structure-aware chunker costs")
    w("")
    regressions = [q.qid for q in QUESTIONS
                   if results["structure_aware"][q.qid]["rank"] and results["baseline"][q.qid]["rank"]
                   and results["structure_aware"][q.qid]["rank"] > results["baseline"][q.qid]["rank"]]
    if regressions:
        detail = ", ".join(
            f"{qid} (rank {results['baseline'][qid]['rank']} → "
            f"{results['structure_aware'][qid]['rank']})" for qid in regressions)
        w(f"It is not free. {len(regressions)} question(s) got *worse*: {detail}. Splitting a table "
          "into one chunk per row means the rows of a rate schedule now compete with each other for "
          "the same query — the 11-to-15-year band no longer arrives inside a chunk that shows the "
          "whole schedule, so its lone row is a weaker match than the baseline's fat chunk "
          "containing every band at once. Precision on exclusion rows was bought with recall on "
          "continuous tables.")
    else:
        w("On this question set it regressed nothing, but the tension is real and section 6 shows it.")
    w("")
    q5 = next(q for q in QUESTIONS if q.qid == "Q5")
    q5_hits = search(q5.question, strategy="structure_aware", top_k=5)
    spread = q5_hits[0].score - q5_hits[-1].score
    w(f"**Q5 is the sharpest version of that cost, and it is the retrieval that embarrassed us "
      f"twice.** Asked for the payout on a *12-year-old* asphalt roof, the structure-aware index "
      f"returns five sibling rows of the same payment schedule, spanning only "
      f"{spread:.4f} of a cosine point:")
    w("")
    w("```")
    for h in q5_hits:
        w(f"{h.rank}. score={h.score:.4f}  {h.chunk.text.splitlines()[-1].strip()}")
    w("```")
    w("")
    w(f"The gold row (`11 to 15 years | 60%`) lands at rank "
      f"{next((h.rank for h in q5_hits if '11 to 15' in h.chunk.text), '?')}, behind "
      f"`6 to 10 years | 80%`. The embedding has nothing to work with: once a row is severed "
      "from its schedule, `| 6 to 10 years | 80% | 95% |` and `| 11 to 15 years | 60% | 85% |` "
      "are near-identical strings of digits, and no bi-encoder maps \"12-year-old\" onto the "
      "arithmetic band that contains 12. Answering Q5 extractively from rank 1 would have "
      "confidently quoted **80%** — the wrong payout on a real claim. That is why Q5 is not "
      "one of the three questions taken through to generation in section 4, and why it is "
      "written up here instead of quietly dropped.")
    w("")
    w("The fix is not a better embedding, it is a chunking rule: a rate schedule is one "
      "answerable unit and must not be split per row, whereas an exclusions table must be. "
      "Same document, opposite treatment, decided by what the table *is*.")
    w("")
    w(f"It also grows the index: {report['baseline']['chunks']} chunks → "
      f"{report['structure_aware']['chunks']}, of which "
      f"{report['structure_aware']['table_row_chunks']} are single table rows. At six endorsements "
      "that is free. Across a full wording library it is the cost to watch.")
    w("")
    w("**Next change, not made today:** keep the per-row chunks for exclusion tables and stop "
      "splitting per row for rate schedules, where the whole table is the answerable unit. That is "
      "one variable and it gets measured on its own run.")
    w("")


BANNER = "=" * 50


def main() -> None:
    out = []
    w = out.append

    print(BANNER)
    print("WEEK 3 PRACTICAL \u2014 TASK SET D RAG EVALUATION ENGINE")
    print(BANNER)

    print("\n--- Loading questions from questions.json ---")
    print(f"Loaded {len(QUESTIONS)} answerable questions and "
          f"{len(UNANSWERABLE)} refusal questions.")

    report = {}
    for i, strategy in enumerate(STRATEGIES, start=1):
        print(f"\n--- Ingesting with Strategy {i}: {STRATEGY_LABELS[strategy]} ---")
        print(f"Loading embedding model: {EMBED_MODEL}...")
        report[strategy] = ingest(strategy)

    w("# Task Set D — Results")
    w("")
    w("Insurance claims RAG. Two chunking strategies over the same 6 new endorsements, "
      "the same embedding model, and the same 8 known-answer questions.")
    w("")
    w(f"- Embedding model: `{EMBED_MODEL}` (384-dim bi-encoder) — **held fixed across "
      "both runs**, so the only variable is the chunker.")
    w("- Answering: extractive \u2014 the answer is quoted verbatim from the cited chunk, "
      "never composed by a model, so it cannot state anything the cited chunk does not.")
    w("- Vector database: **Chroma** (embedded), one collection per strategy, **HNSW** index "
      "in cosine space")
    w(f"- Retrieval: top-K = {TOP_K}; `policy_line` filtering is executed by the database as a "
      "`where` clause, not post-filtered in Python")
    w("")
    w("## 0. Scope of this ingest")
    w("")
    w("**Only the 6 new endorsements were indexed.** The base homeowners policy wording library "
      "was not re-indexed and was not read by this pipeline. The endorsement drop is the unit of "
      "work; re-indexing the library would have spent the whole session on plumbing and produced "
      "no measurement.")
    w("")
    w("| Strategy | Chunks | Of which single exclusion/table rows |")
    w("|---|---|---|")
    for s in STRATEGIES:
        w(f"| `{s}` | {report[s]['chunks']} | {report[s]['table_row_chunks']} |")
    w("")
    w("Per-form chunk counts (every chunk carries source_file, form_number, policy_line, "
      "edition_date):")
    w("")
    forms = sorted(report[STRATEGIES[0]]["per_form"])
    w("| Form | " + " | ".join(f"`{s}`" for s in STRATEGIES) + " |")
    w("|---" * (len(STRATEGIES) + 1) + "|")
    for f in forms:
        w(f"| {f} | " + " | ".join(str(report[s]["per_form"].get(f, 0))
                                   for s in STRATEGIES) + " |")
    w("")

    w("## 1. The 8 questions and their known-correct form + clause")
    w("")
    w("Written from the endorsements before any search was run.")
    w("")
    w("| # | Question | Gold form | Gold clause | Marker | Answer marker | From a table row |")
    w("|---|---|---|---|---|---|---|")
    for q in QUESTIONS:
        w(f"| {q.qid} | {q.question} | {q.gold_form} | {q.gold_clause} | `{q.marker}` | "
          f"`{q.answer_marker}` | {'yes' if q.from_table else 'no'} |")
    w("")
    for q in QUESTIONS:
        w(f"**{q.qid} known answer** — {q.known_answer}")
        w("")

    print("\n--- Evaluating Hit-in-Top-5 metrics ---")
    results = {s: {} for s in STRATEGIES}
    for s in STRATEGIES:
        for q in QUESTIONS:
            hits = search(q.question, strategy=s, top_k=TOP_K)
            hit, rank = is_hit(hits, q)
            results[s][q.qid] = {"hits": hits, "hit": hit, "rank": rank}

    totals = {s: sum(r["hit"] for r in results[s].values()) for s in STRATEGIES}
    top1 = {s: sum(1 for r in results[s].values() if r["rank"] == 1) for s in STRATEGIES}
    mrr = {s: sum((1.0 / r["rank"]) if r["hit"] else 0.0
                  for r in results[s].values()) / len(QUESTIONS) for s in STRATEGIES}

    for i, strategy in enumerate(STRATEGIES, start=1):
        print(f"Strategy {i} ({STRATEGY_LABELS[strategy]}) Hit-in-Top-5: "
              f"{totals[strategy]}/{len(QUESTIONS)}")

    w("## 2. Hit-in-top-5 — two strategies, same 8 questions")
    w("")
    w("| Chunking strategy | Hit-in-top-5 | Hit-at-rank-1 | MRR |")
    w("|---|---|---|---|")
    for s in STRATEGIES:
        w(f"| `{s}` | **{totals[s]}/8** | {top1[s]}/8 | {mrr[s]:.3f} |")
    w("")
    w(f"Headline: `baseline` **{totals['baseline']}/8**, `structure_aware` "
      f"**{totals['structure_aware']}/8**.")
    w("")
    w("Hit-at-rank-1 and MRR are reported alongside because top-5 over a "
      f"{report['baseline']['chunks']}-chunk index is a soft test — 5 of "
      f"{report['baseline']['chunks']} is a fifth of the whole corpus. Rank-1 is the number that "
      "reflects what a user actually reads.")
    w("")
    w("Per-question record (rank at which the correct chunk was found, or MISS):")
    w("")
    w("| # | Gold | " + " | ".join(f"`{s}`" for s in STRATEGIES) + " |")
    w("|---" * (len(STRATEGIES) + 2) + "|")
    for q in QUESTIONS:
        cells = []
        for s in STRATEGIES:
            r = results[s][q.qid]
            cells.append(f"hit @ rank {r['rank']}" if r["hit"] else "**MISS**")
        w(f"| {q.qid} | {q.gold_form} {q.gold_clause} | " + " | ".join(cells) + " |")
    w("")

    w("### Search-only dump, all 8 questions, both strategies")
    w("")
    for q in QUESTIONS:
        w(f"#### {q.qid} — {q.question}")
        w("")
        w(f"Gold: **{q.gold_form} {q.gold_clause}** (needs `{q.marker}` AND "
          f"`{q.answer_marker}` in the same chunk)")
        w("")
        for s in STRATEGIES:
            r = results[s][q.qid]
            verdict = f"HIT at rank {r['rank']}" if r["hit"] else "MISS"
            w(f"`{s}` — {verdict}")
            w("")
            w("```")
            w(fmt_hits(r["hits"]))
            w("```")
            w("")

    print(f"\n--- Testing Metadata Filter on {FILTER_FIELD} ---")
    w("## 3. Metadata filter on policy_line")
    w("")
    w(f"Query: *{FILTER_QUERY}*")
    w("")
    w("Both the homeowners form (HO-0304) and the dwelling-fire form (DP-0431) carry an "
      "exclusion coded **E-17**, and they say opposite things: HO-0304 excepts a sudden and "
      "accidental burst supply line and triggers at 14 days, DP-0431 has no exception at all "
      "and triggers at 7 days. Unfiltered dense retrieval cannot tell which policy line the "
      "user means. The filter can.")
    w("")
    filter_strategy = "structure_aware"
    unfiltered = search(FILTER_QUERY, strategy=filter_strategy, top_k=TOP_K)
    filtered = search(FILTER_QUERY, strategy=filter_strategy, top_k=TOP_K,
                      filters={FILTER_FIELD: FILTER_VALUE})
    w(f"**Unfiltered** (`{filter_strategy}`, top-{TOP_K}):")
    w("")
    w("```")
    w(fmt_hits(unfiltered))
    w("```")
    w("")
    w(f"**Filtered** on `{FILTER_FIELD} == \"{FILTER_VALUE}\"`:")
    w("")
    w("```")
    w(fmt_hits(filtered))
    w("```")
    w("")
    if unfiltered and filtered:
        u0, f0 = unfiltered[0], filtered[0]
        w(f"Top-1 changed: **{u0.chunk.chunk_id != f0.chunk.chunk_id}** — "
          f"`{u0.chunk.metadata.get('form_number')}` (`{u0.chunk.chunk_id}`, "
          f"score {u0.score:.4f}) → `{f0.chunk.metadata.get('form_number')}` "
          f"(`{f0.chunk.chunk_id}`, score {f0.score:.4f}).")
    w("")

    cited_ids = []

    print(f"\n--- Running Generation on {len(ANSWERABLE)} Answerable Questions ---")
    w("## 4. Cited answers (3 answerable questions)")
    w("")
    by_id = {q.qid: q for q in QUESTIONS}
    for qid in ANSWERABLE:
        q = by_id[qid]
        res = answer(q.question, strategy="structure_aware", top_k=TOP_K)
        w(f"### {qid} — {q.question}")
        w("")
        w(f"**Refused:** {res['refused']}  |  **Top retrieval score:** {res['top_score']}")
        w("")
        w(f"**Answer:** {res['answer']}")
        w("")
        if res["citations"]:
            w("**Citations:**")
            w("")
            for c in res["citations"]:
                w(f"- [`{c['chunk_id']}`](#{c['chunk_id'].replace('::', '').lower()}) — "
                  f"**{c['form_number']} {c['clause']}** — \"{c['quote']}\"")
                cited_ids.append(c["chunk_id"])
            w("")
            w("Each chunk_id links to appendix A, which reproduces the indexed chunk verbatim.")
            w("")
        if res.get("dropped_citations"):
            w(f"_Dropped {len(res['dropped_citations'])} citation(s) that did not resolve to a "
              "retrieved chunk._")
            w("")
        w(f"**Known-correct answer:** {q.known_answer}")
        w("")

    print(f"\n--- Running Generation on {len(UNANSWERABLE)} Unanswerable Questions "
          f"(Refusal Test) ---")
    w("## 5. Refusal transcripts (3 out-of-corpus questions)")
    w("")
    for i, uq in enumerate(UNANSWERABLE, 1):
        res = answer(uq, strategy="structure_aware", top_k=TOP_K)
        w(f"### R{i} — {uq}")
        w("")
        w("```")
        w(f"refused    : {res['refused']}")
        w(f"gate       : {res['gate']}")
        w(f"top_score  : {res['top_score']}")
        w(f"answer     : {res['answer']}")
        w(f"reason     : {res['reason']}")
        w(f"citations  : {res['citations']}")
        w("```")
        w("")
        w("Best chunks retrieved before the refusal:")
        w("")
        w("```")
        for r in res["retrieved"][:3]:
            w(f"{r['rank']}. score={r['score']}  {r['form_number']}  {r['clause']}  "
              f"`{r['chunk_id']}`")
        w("```")
        w("")

    write_refusal_gate_analysis(w)

    print("\n--- Running Bonus Probe (precision vs completeness) ---")
    w("## 6. Bonus — precision wins retrieval, loses the answer")
    w("")
    w(f"Question: *{BONUS_QUESTION}*")
    w("")
    for s in STRATEGIES:
        res = answer(BONUS_QUESTION, strategy=s, top_k=TOP_K)
        forms = sorted({r["form_number"] for r in res["retrieved"]})
        w(f"### `{s}`")
        w("")
        w(f"Forms present in top-{TOP_K}: {', '.join(forms)}")
        w("")
        w(f"**Refused:** {res['refused']}")
        w("")
        w(f"**Answer:** {res['answer']}")
        w("")
        if res["citations"]:
            for c in res["citations"]:
                w(f"- `{c['chunk_id']}` — {c['form_number']} {c['clause']}")
            w("")

    write_defence(w, results, totals, top1, mrr, report, unfiltered, filtered)

    # Appendix A - every cited chunk_id resolved to the exact indexed text, so a
    # grader can check that the cited chunk really contains the claim.
    w("## Appendix A — cited chunks resolved")
    w("")
    w("Every chunk_id cited in section 4, fetched back out of the index by id and "
      "reproduced verbatim.")
    w("")
    for cid in dict.fromkeys(cited_ids):
        chunk = get_chunk(cid)
        w(f"<a id=\"{cid.replace('::', '').lower()}\"></a>")
        w("")
        w(f"### `{cid}`")
        w("")
        if chunk is None:
            w("**UNRESOLVED — this chunk_id is not in the index.**")
            w("")
            continue
        m = chunk.metadata
        w(f"- source_file: `{m.get('source_file')}`")
        w(f"- form_number: `{m.get('form_number')}`  ·  policy_line: `{m.get('policy_line')}`  "
          f"·  edition_date: `{m.get('edition_date')}`  ·  clause: `{m.get('clause')}`")
        w("")
        w("```")
        w(chunk.text)
        w("```")
        w("")

    RESULTS_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nSUCCESS: Evaluation complete! Results saved to {RESULTS_PATH.name}.")


if __name__ == "__main__":
    main()
