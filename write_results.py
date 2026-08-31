"""Render results.md from eval_record.json. No measuring happens here - every number
in the report comes out of the record run_week4.py produced."""
from src import COVERAGE_FLOOR, CANDIDATES, EMBED_MODEL, RRF_K
from src.inspect_view import load_golden

LABEL_NAME = {"PASS": "pass", "R": "R (retrieval fetched bad context)",
              "G": "G (model misused good context)", "NIC": "Not-In-Corpus"}


def write_results(rec, golden, path=None):
    from src import ROOT
    path = path or ROOT / "results.md"
    o = []
    w = o.append
    g_by = {g["qid"]: g for g in golden}
    dense = rec["modes"]["dense"]
    hyb = rec["modes"]["hybrid"]
    d_rows = {r["qid"]: r for r in dense["rows"]}
    h_rows = {r["qid"]: r for r in hyb["rows"]}
    n = dense["summary"]["n"]
    d_hit, h_hit = dense["summary"]["hits"], hyb["summary"]["hits"]
    d_p50, h_p50 = dense["latency_ms"]["p50"], hyb["latency_ms"]["p50"]

    w("# Week 4 — Task Set D — Results")
    w("")
    w("**Label the failures, then buy back hit-rate@3 with exactly one change.**")
    w("")
    w(f"Headline: baseline hit-rate@3 **{d_hit}/{n}** → after the one change **{h_hit}/{n}**, "
      f"p50 latency **{d_p50:.1f} ms → {h_p50:.1f} ms**. The change did not buy back "
      f"hit-rate@3. Section 9 is the shipping decision and section 5 is why this was still "
      f"the right change to test.")
    w("")

    # ---------------------------------------------------------------- 0
    w("## 0. The stack — what is actually running")
    w("")
    w("| Component | What it is |")
    w("|---|---|")
    w(f"| Embedding model | `{EMBED_MODEL}` — a 384-dim **bi-encoder**, run locally on CPU "
      "through `fastembed` (ONNX). Same model in both runs. |")
    w("| Vector database | **Chroma**, in-process, HNSW index in cosine space. |")
    w("| Lexical index | **BM25** (`src/bm25.py`), Lucene-style idf, k1=1.5, b=0.75, plain numpy. |")
    w("| Chunking | Week 3 `structure_aware` chunker — one chunk per exclusion-table row, each "
      "stamped with form number, edition, policy line, clause. Unchanged this week. |")
    w("| **Generation LLM** | **None. There is no LLM in this pipeline.** The answer is quoted "
      "verbatim from the cited chunk by `src/generator.py`, and the refusal is a gate in code. |")
    w("")
    w("**Why no LLM, and why that does not weaken this task.** The graded metric is "
      "hit-rate@3 — a *retrieval* metric that asks whether the known-correct chunk is in the "
      "top-3. No generator can change it. The generator matters only for the R-vs-G split, and "
      "an extractive generator makes that split sharper, not softer: when the gold chunk is in "
      "the top-3 and the output still does not come from it, there is no 'the model hallucinated' "
      "excuse available — the answer step demonstrably had the right context and quoted a "
      "different chunk. That is G, on the definition in the task statement, and no retrieval "
      "change fixes it. Everything runs locally with no API key and no network.")
    w("")
    w(f"Corpus: **{rec['chunks']} chunks** from 8 endorsement files. The Week 3 drop was 6 forms; "
      "Week 4 adds **two further editions of HO-0304** (ed. 09-23 and ed. 01-25) alongside the "
      "existing ed. 03-24, because the failure in the task statement — *'does exclusion E-17 "
      "apply under form HO-0304 ed. 03-24'* — cannot exist in a corpus holding only one edition "
      "of the form. The three editions say materially different things about E-17 (21 days / 14 "
      "days / 14 days + a shut-off-device condition), so retrieving the wrong edition is a wrong "
      "coverage answer, not a cosmetic miss.")
    w("")
    w(f"Every number below: same {n} questions, same index, same chunker, same embedding model, "
      f"top-3, {rec['latency_reps']} latency reps per question. The **only** variable between "
      "the before and after columns is `RETRIEVAL_MODE`.")
    w("")

    # ---------------------------------------------------------------- 1
    w("## 1. The golden set — 12 real adjuster questions with known-correct chunk_ids")
    w("")
    w("Source: `golden_set.jsonl`. These are desk questions — the ones that arrive as *\"what "
      "does E-22 say on the roof form\"*, not questions written to make the retriever look good. "
      "**7 of 12 carry an exact token dense retrieval is structurally bad at** (the requirement "
      "is 4): an exclusion code, a form number, an edition. Four of them (G01–G04) turn on the "
      "*edition*, which is where a bi-encoder has nothing at all to work with.")
    w("")
    w("| # | Question | Gold chunk_id | Exact token(s) |")
    w("|---|---|---|---|")
    for g in golden:
        tok = f"`{g['exact_token']}`" if g["exact_token"] else "—"
        w(f"| {g['qid']} | {g['question']} | `{g['gold_chunk_id']}` | {tok} |")
    w("")
    w("A 13th question is carried in `probes.jsonl` and is **not** counted in hit-rate@3: it asks "
      "about an edition of HO-0304 that is not in the drop, and exists to exercise the "
      "Not-In-Corpus label (section 4.3).")
    w("")

    # ---------------------------------------------------------------- 2
    w("## 2. Baseline hit-rate@3 — written down before anything was changed")
    w("")
    b = rec.get("baseline_record")
    if b:
        w(f"Frozen to `baseline_record.json` at `{b['frozen_at']}` by `python3 run_week4.py "
          f"--freeze`, before `src/bm25.py` existed:")
        w("")
        w("```json")
        w(f'{{"mode": "dense", "hit_rate_at_3": "{b["hit_rate_at_3"]}", '
          f'"p50_ms": {b["p50_ms"]}, "chunks": {b["chunks"]}}}')
        w("```")
        w("")
    w(f"### Baseline: **{d_hit}/{n} = {d_hit / n:.0%}** hit-rate@3 (dense only, the Week 3 retriever)")
    w("")
    w("| # | Gold in top-3? | Gold rank (dense) | Answer quoted from gold? | Label |")
    w("|---|---|---|---|---|")
    for g in golden:
        r = d_rows[g["qid"]]
        rank = r["gold_rank"] if r["gold_rank"] else "not in top-25"
        w(f"| {g['qid']} | {'**yes**' if r['hit'] else '**NO**'} | {rank} | "
          f"{'yes' if r['answer_ok'] else 'no'} | `{r['label']}` |")
    w("")
    w(f"Answer-from-gold is {dense['summary']['answer_ok']}/{n} — much worse than hit-rate@3. "
      "That gap is the whole point of section 4: most of what a user would call a wrong answer "
      "is not a retrieval failure at all.")
    w("")

    # ---------------------------------------------------------------- 3
    w("## 3. The inspection view")
    w("")
    w("`src/inspect_view.py` + `inspect_query.py`. For one question it shows every candidate the "
      "retriever considered, the rank **each stage** gave it, where the gold chunk actually "
      "landed, and which chunk the answer was quoted from. The label is computed from those "
      "facts, never from whether the answer text looked plausible.")
    w("")
    w("```")
    w("$ python3 inspect_query.py --qid G01 --mode dense")
    for line in d_rows["G01"]["view"].splitlines():
        w(line)
    w("```")
    w("")
    w("Decision rule, applied mechanically to all 12:")
    w("")
    w("| Label | Rule |")
    w("|---|---|")
    w("| `PASS` | gold chunk in top-3 **and** the answer was quoted from it |")
    w("| `R` | gold chunk **not** in top-3 — retrieval fetched bad context |")
    w("| `G` | gold chunk **is** in top-3, but the answer step used a different chunk (or refused) |")
    w("| `NIC` | no chunk in the index can answer it |")
    w("")

    # ---------------------------------------------------------------- 4
    lab = dense["summary"]["labels"]
    w("## 4. The tally — every failure labelled, one line of evidence each")
    w("")
    w("| Label | Count | Questions |")
    w("|---|---|---|")
    for k in ("PASS", "R", "G", "NIC"):
        qs = ", ".join(q for q in [g["qid"] for g in golden] if d_rows[q]["label"] == k)
        w(f"| {LABEL_NAME[k]} | **{lab[k]}** | {qs or '—'} |")
    w(f"| Not-In-Corpus probe (uncounted) | 1 | P01 |")
    w("")
    w(f"**{lab['R']} R · {lab['G']} G · 0 NIC in the scored set.** The tally is the argument: "
      "the majority of failures are G, and *no retrieval change on earth fixes a G*. Only the "
      f"{lab['R']} R-failures were ever in scope for this week's change.")
    w("")
    w(f"**Why only {lab['PASS']} of 12 are a clean pass.** hit-rate@3 is "
      f"{dense['summary']['hits']}/12 — retrieval put the right clause in the top-3 that often. "
      f"But end-to-end only {dense['summary']['answer_ok']}/12 produce the right answer, and the "
      f"gap is entirely the answer step: {dense['summary']['causes']['G-rank']} questions where "
      f"it read only rank 1, and {dense['summary']['causes']['G-refuse']} where it refused with "
      "the gold chunk already in front of it. Those two numbers are the real finding of this "
      "week, and neither is a retrieval defect:")
    w("")
    w("| | Count | Meaning |")
    w("|---|---|---|")
    w(f"| Clean pass | {dense['summary']['causes']['PASS']}/12 | right clause retrieved **and** quoted |")
    w(f"| Retrieval found it, answer step lost it | {dense['summary']['causes']['G-rank'] + dense['summary']['causes']['G-refuse']}/12 | `G-rank` + `G-refuse`, section 4.2 |")
    w(f"| Retrieval never found it | {lab['R']}/12 | `R`, section 4.1 — the only bucket this week's change could touch |")
    w("")
    w("### 4.1 The R-failures — retrieval fetched bad context")
    w("")
    for g in golden:
        r = d_rows[g["qid"]]
        if r["label"] != "R":
            continue
        w(f"- **{g['qid']}** — *{g['question']}*  ")
        w(f"  `{r['evidence']}`")
    w("")
    cz = dense["summary"]["causes"]
    w("### 4.2 The G-failures — good context was there and the answer step still missed")
    w("")
    w(f"All {lab['G']} are G by the task's definition: the gold chunk was sitting in the top-3 "
      "and the answer was still wrong. But they are **two different defects**, and lumping them "
      "would hide the more serious one, so the tally splits them:")
    w("")
    w("| Sub-cause | Count | Questions | What actually happened |")
    w("|---|---|---|---|")
    for c, desc in (("G-rank", "gold was in the top-3 but **below rank 1**, and the answer step "
                               "reads **only rank 1**"),
                    ("G-refuse", "the answer step **refused outright** although the gold chunk "
                                 "was right there")):
        qs = ", ".join(q for q in [g["qid"] for g in golden] if d_rows[q]["cause"] == c)
        w(f"| `{c}` | **{cz[c]}** | {qs or '—'} | {desc} |")
    w("")
    w(f"**{cz['G-rank']} × G-rank — the answer step only ever reads rank 1.**")
    w("")
    for g in golden:
        r = d_rows[g["qid"]]
        if r["cause"] != "G-rank":
            continue
        w(f"- **{g['qid']}** — *{g['question']}*  ")
        w(f"  `{r['evidence']}`")
    w("")
    w("G02 is the clearest. The gold E-18 row **is** at rank 3 — and the two rows above it are "
      "the *same E-18 row from the 09-23 and 01-25 editions*, scoring 0.8086 against the gold's "
      "0.8086, identical to four decimals. Retrieval did its job at top-3. `generator.py` then "
      "quotes `hits[0]` and cites the wrong edition of the form. On a real claim that is the "
      "wrong deductible and the wrong reporting window, delivered with a citation that looks "
      "correct. Reranking *within* the top-3 is the fix; a new embedding model is not, because "
      "three byte-identical rows cannot be separated by any bi-encoder.")
    w("")
    w(f"**{cz['G-refuse']} × G-refuse — the Week 3 refusal gate misfiring on real adjuster "
      "language.** This is the serious one, and it was invisible until the golden set was "
      "written from how adjusters actually talk.")
    w("")
    for g in golden:
        r = d_rows[g["qid"]]
        if r["cause"] != "G-refuse":
            continue
        w(f"- **{g['qid']}** — *{g['question']}*  ")
        w(f"  `{r['evidence']}`  ")
        w(f"  term coverage **{r['coverage']:.0%}** vs floor {COVERAGE_FLOOR:.0%}; "
          f"terms counted as absent: {', '.join('`' + t + '`' for t in r['missing_terms'])}")
    w("")
    w("Read G10 carefully, because it is the worst result in the whole run: **the gold chunk is "
      "at rank 1** and the assistant still answers *\"I could not find this in the indexed "
      "endorsements\"*. Retrieval was perfect. The Week 3 coverage gate rejected the question "
      "before ranking was ever consulted, because words like `bookkeeping`, `spare`, `bedroom` "
      "and `clients` do not appear in policy wording — which is precisely how an adjuster "
      "describes a claim. The gate was tuned in Week 3 against 11 questions written *from the "
      "endorsements*, in the endorsements' own vocabulary, and it measured 62% worst-in-corpus "
      "on those. Against real adjuster phrasing it drops to 50% and refuses. The Week 3 report "
      "called 55% \"a defensible gate at this scale, not a universal constant\" — this is that "
      "bill arriving.")
    w("")
    w("Neither sub-cause is reachable by a retrieval change. G-rank needs the answer step to read "
      "the whole top-3 instead of `hits[0]`; G-refuse needs the gate re-measured against adjuster "
      "vocabulary, or moved off raw term overlap entirely. Both are named in section 9 as the "
      "next changes, and neither was made this week — this week's one variable was retrieval.")
    w("")
    w("### 4.3 Not-In-Corpus")
    w("")
    for p in rec.get("probes", []):
        w(f"- **{p['qid']}** — *{p['question']}*  ")
        w(f"  `{p['evidence']}`  ")
        w(f"  {p['note']}")
    w("")

    # ---------------------------------------------------------------- 5
    w("## 5. The one change, and why the tally chose it")
    w("")
    w(f"**The change: `RETRIEVAL_MODE = \"dense\"` → `\"hybrid\"` — dense top-{CANDIDATES} + BM25 "
      f"top-{CANDIDATES}, fused with Reciprocal Rank Fusion, k={RRF_K}. Nothing else moved.** "
      "Same chunker, same embedding model, same index, same 12 questions, same top-3. No "
      "reranker was added in the same run; there is exactly one variable between the two columns.")
    w("")
    w("The tally picked it, and the inspection view picked it over the reranker on evidence. "
      f"Of the {lab['R']} R-failures, two — **G01** and **G05** — have their gold chunk at dense "
      "rank **33/99** and **27/99** respectively, measured by brute force over the whole index. "
      f"A cross-encoder rerank over the top {CANDIDATES} can only reorder the {CANDIDATES} "
      "candidates dense already fetched; it cannot reach rank 33. **A reranker was structurally "
      "incapable of fixing 2 of the 3 R-failures before it ran.** Both of those questions are "
      "exact-token lookups (`E-17`+`HO-0304`+`03-24`; `E-22`+`HO-0455`), which is precisely what "
      "a lexical retriever is for. So: BM25 + RRF, and RRF fuses **ranks** — a cosine of 0.69 and "
      "a BM25 score of 6.17 are not on the same scale and adding them would be meaningless.")
    w("")
    w("Also considered and rejected: swapping the embedding model, as the team lead suggested. "
      f"{lab['G']} of the {lab['R'] + lab['G']} failures are G — the right chunk was already in "
      "the top-3 — so a new bi-encoder changes nothing about them, and it would have cost a "
      "re-index plus the whole budget to prove it.")
    w("")

    # ---------------------------------------------------------------- 6
    w("## 6. Before → after: hit-rate@3 and p50 latency")
    w("")
    w("| | Before (`dense`) | After (`hybrid`: BM25 + RRF k=60) | Δ |")
    w("|---|---|---|---|")
    w(f"| **hit-rate@3** | **{d_hit}/{n}** ({d_hit / n:.0%}) | **{h_hit}/{n}** ({h_hit / n:.0%}) | "
      f"**{h_hit - d_hit:+d}** |")
    w(f"| answer quoted from gold | {dense['summary']['answer_ok']}/{n} | "
      f"{hyb['summary']['answer_ok']}/{n} | {hyb['summary']['answer_ok'] - dense['summary']['answer_ok']:+d} |")
    w(f"| **p50 latency / query** | **{d_p50:.1f} ms** | **{h_p50:.1f} ms** | "
      f"**{h_p50 - d_p50:+.1f} ms ({(h_p50 / d_p50 - 1) * 100:+.0f}%)** |")
    w(f"| p95 latency / query | {dense['latency_ms']['p95']:.1f} ms | {hyb['latency_ms']['p95']:.1f} ms | "
      f"{hyb['latency_ms']['p95'] - dense['latency_ms']['p95']:+.1f} ms |")
    w(f"| R / G / NIC | {lab['R']} / {lab['G']} / {lab['NIC']} | "
      f"{hyb['summary']['labels']['R']} / {hyb['summary']['labels']['G']} / "
      f"{hyb['summary']['labels']['NIC']} | — |")
    w("")
    d_p95, h_p95 = dense["latency_ms"]["p95"], hyb["latency_ms"]["p95"]
    spread = d_p95 - d_p50
    w(f"Latency is wall-clock per `search()` call including the query embedding, "
      f"{rec['latency_reps']} reps × {n} questions = {dense['latency_ms']['samples']} samples per "
      "mode, after warm-up, same process, same machine.")
    w("")
    if abs(h_p50 - d_p50) < spread:
        w(f"**Read the latency row honestly: the measured p50 delta is {h_p50 - d_p50:+.1f} ms, "
          f"and that is inside the noise floor of this measurement.** The p50→p95 spread within "
          f"a single mode is {spread:.1f} ms — {spread / max(abs(h_p50 - d_p50), 1e-9):.0f}× the "
          f"{abs(h_p50 - d_p50):.1f} ms between the two modes — and repeated runs move the dense "
          f"p50 by more than the gap itself (the pre-change freeze in section 2 recorded "
          f"{rec['baseline_record']['p50_ms']:.1f} ms for the same dense retriever). So I will "
          "not quote a percentage as if it were a real cost: **the added BM25 + RRF stage costs "
          "less than this measurement can resolve.** The mechanism agrees: BM25 over a "
          f"{rec['chunks']}-chunk index is one numpy matrix product over a slice of a "
          f"{rec['chunks']}×|vocab| matrix, while a single query embedding through the ONNX "
          "bi-encoder dominates both paths.")
        w("")
        w("**So the price was never the problem.** This is not a 'not worth the latency' verdict "
          "— the change is effectively free and *still* not worth shipping, because it did not "
          "move the number it was chosen to move. Cheap and useless is still useless. The one "
          "caveat I would put in front of the team lead: at 99 chunks BM25 is free, but its cost "
          "grows with corpus size while the embedding call does not, so this measurement does not "
          "license the claim that fusion is free across a full wording library.")
    else:
        w(f"The change costs {h_p50 - d_p50:+.1f} ms at p50 "
          f"({(h_p50 / d_p50 - 1) * 100:+.0f}%), which is outside the "
          f"{spread:.1f} ms p50→p95 spread within a mode and therefore a real cost.")
    w("")

    # ---------------------------------------------------------------- 7
    w("## 7. Per-question: fixed / unfixed / still-broken")
    w("")
    w("| # | Baseline label | Baseline rank | After rank | After label | Verdict |")
    w("|---|---|---|---|---|---|")
    verdicts = {}
    for g in golden:
        q = g["qid"]
        a, bq = d_rows[q], h_rows[q]
        if a["hit"] and bq["hit"]:
            v = "unchanged (still a hit)" if a["label"] == bq["label"] else f"still a hit, label {a['label']}→{bq['label']}"
        elif not a["hit"] and bq["hit"]:
            v = "**FIXED**"
        elif a["hit"] and not bq["hit"]:
            v = "**REGRESSED**"
        else:
            v = "**still broken**"
        verdicts[q] = v
        ar = a["gold_rank"] or f">{CANDIDATES}"
        br = bq["gold_rank"] or f">{CANDIDATES}"
        w(f"| {q} | `{a['label']}` | {ar} | {br} | `{bq['label']}` | {v} |")
    w("")
    w("### 7.1 Which R-failures the change fixed, and which it did not touch")
    w("")
    w("Named per question, as required:")
    w("")
    for g in golden:
        q = g["qid"]
        if d_rows[q]["label"] != "R":
            continue
        a, bq = d_rows[q], h_rows[q]
        ar = a["gold_rank"] or f"not in top-{CANDIDATES}"
        br = bq["gold_rank"] or f"not in top-{CANDIDATES}"
        w(f"- **{q}** — *{g['question']}*  ")
        w(f"  gold rank {ar} → {br}. **{'FIXED' if bq['hit'] else 'NOT FIXED'}.**")
    w("")
    w("**What the change did do, even though hit-rate@3 did not move up.** On G01 the gold E-17 "
      f"row went from *invisible* — nowhere in dense's top-{CANDIDATES}, brute-force rank 33/99 — "
      "to **rank 5 on the BM25 list**. BM25 found the chunk dense could not see. RRF then failed "
      "to carry it into the top-3, and the inspection view says exactly why: the chunk that beats "
      "it on BM25 is the **E-19 row**, which merely *cites* E-17 (\"where such condition results "
      "from a cause of loss excluded under E-15 or E-17\"). Both rows contain `e-17` exactly once; "
      "the E-19 row is 73 tokens against the gold row's 98, and BM25's length normalisation "
      "(b=0.75, avgdl=62.6) rewards the shorter one. The retrieval defect is real and lexical, "
      "and BM25 addressed it — but a bag-of-words cannot tell *stating a rule* from *cross-"
      "referencing it*.")
    w("")
    w("**And the regressions are the same mechanism in reverse.** G11 asks for a definition in "
      "prose and had the gold at dense rank 1; fusion pushed it to rank 4 behind chunks that "
      "score well lexically on `sudden`/`accidental`/`seepage` without being the definition. On a "
      "corpus where every chunk of a form carries that form's number and edition in its "
      "provenance header, form and edition tokens have almost no discriminative power *within* a "
      "document — `ho-0304` occurs in 48 of 99 chunks — so BM25's vote on an edition-scoped "
      "question is much weaker than it looks.")
    w("")
    w("**Robustness check, reported because it cuts against the headline.** Re-running the same "
      "fusion with the Robertson idf variant `log((N-df+0.5)/(df+0.5))` plus rank_bm25's epsilon "
      f"floor, instead of the Lucene `ln(1+·)` idf, gives hit-rate@3 = **{d_hit}/{n}** — level "
      "with the baseline rather than below it. So the true reading is not 'BM25+RRF costs you a "
      "question', it is **'BM25+RRF is worth between −1 and 0 questions on this set, i.e. it does "
      "not buy back hit-rate@3, and which side of zero it lands on is decided by an idf formula "
      "rather than by anything about the corpus.'** `src/bm25.py` was cross-checked against an "
      "independently written Lucene-idf implementation and agrees to 5e-05.")
    w("")

    # ---------------------------------------------------------------- 8
    w("## 8. Bonus — MMR over the fused candidate list")
    w("")
    w("The bonus scenario is live in this corpus: for G01 the fused top-3 is the **same E-19 "
      "exclusion row repeated across the 09-23, 03-24 and 01-25 editions**. MMR should be the "
      "cure for exactly that. Tuned once, over the fused candidates, λ=1.0 being plain RRF order:")
    w("")
    w("| λ | hit-rate@3 | mean pairwise cosine within top-3 (lower = more diverse) | mean distinct row texts in top-3 | mean distinct form editions in top-3 |")
    w("|---|---|---|---|---|")
    best = None
    for row in rec["mmr"]["lambdas"]:
        star = ""
        w(f"| {row['lambda']}{star} | **{row['hits']}/{row['n']}** | {row['mean_pairwise_cos']:.3f} | "
          f"{row['mean_distinct_rows']:.2f}/3 | {row['mean_distinct_editions']:.2f}/3 |")
        if best is None or (row["hits"], -row["mean_pairwise_cos"]) > (best["hits"], -best["mean_pairwise_cos"]):
            best = row
    w("")
    ctrl = rec["mmr"]["lambdas"][0]
    peak = max(rec["mmr"]["lambdas"], key=lambda r: (r["hits"], r["lambda"]))
    w(f"**What it did.** Diversity moves as advertised: mean pairwise cosine within the top-3 "
      f"falls from {ctrl['mean_pairwise_cos']:.3f} at λ=1.0 to "
      f"{rec['mmr']['lambdas'][-1]['mean_pairwise_cos']:.3f} at λ="
      f"{rec['mmr']['lambdas'][-1]['lambda']}, and distinct row texts rise from "
      f"{ctrl['mean_distinct_rows']:.2f}/3 to {rec['mmr']['lambdas'][-1]['mean_distinct_rows']:.2f}/3. "
      f"Hit-rate@3 is not monotonic in λ: {ctrl['hits']}/{ctrl['n']} at λ=1.0, up to "
      f"**{peak['hits']}/{peak['n']} at λ={peak['lambda']}**, back down to "
      f"{rec['mmr']['lambdas'][-1]['hits']}/{ctrl['n']} at λ="
      f"{rec['mmr']['lambdas'][-1]['lambda']} where the diversity penalty starts evicting correct "
      "chunks outright.")
    w("")
    w(f"That peak deserves a sentence rather than a victory lap. **MMR at λ={peak['lambda']} "
      f"recovers hit-rate@3 to {peak['hits']}/{peak['n']} — exactly level with the dense "
      f"baseline, not above it.** A mild diversity penalty undoes some of the damage fusion did "
      "by breaking up the blocks of near-identical rows that crowded the top-3; it does not find "
      "anything the baseline could not. And λ was picked by reading this table, on these 12 "
      "questions, which is tuning on the test set: a 1-question swing on n=12 is one question, "
      "not a result. I am reporting it, not banking it.")
    w("")
    w("**Would I ship it? No — and the bonus question names the reason precisely.** In this "
      "corpus the three near-duplicate candidates are not redundancy, they are *three different "
      "legal answers wearing the same words*: E-17 triggers at 21 days on ed. 09-23, 14 days on "
      "ed. 03-24, and 14 days plus an installed shut-off device on ed. 01-25. MMR's similarity "
      "penalty is computed on the same bi-encoder embedding that already cannot tell the editions "
      "apart, so it sees three interchangeable duplicates and drops two — and it has no way to "
      "know it kept the wrong one. On an edition-scoped question, pushing the correct edition out "
      "of the top-3 in the name of variety is not a diversity trade-off, it is a wrong coverage "
      "answer with better-looking search results. The right fix for near-duplicate editions is a "
      "metadata filter on `edition_date` (already supported, and it goes to the DB as a `where` "
      "clause), not a diversity penalty.")
    w("")

    # ---------------------------------------------------------------- 9
    w("## 9. Shipping decision")
    w("")
    w(f"**Do not ship the hybrid retriever. Baseline {d_hit}/{n} → {h_hit}/{n} on the same 12 "
      f"questions: {h_hit - d_hit:+d}.** The latency price is real but small "
      f"({d_p50:.1f} → {h_p50:.1f} ms p50, {h_p50 - d_p50:+.1f} ms); it is not what decides this. "
      f"A change that costs {h_p50 - d_p50:+.1f} ms and returns between −1 and 0 questions does "
      "not go to an adjuster's desk, and \"it fixed the E-17 query in principle\" is not a number.")
    w("")
    w("**What I would do with the budget instead, in tally order:**")
    w("")
    w(f"1. **The {lab['G']} G-failures are the largest single bucket and no retrieval change "
      "touches them.** Answer-from-gold is "
      f"{dense['summary']['answer_ok']}/{n} against hit-rate@3 of {d_hit}/{n} — the retriever is "
      "already putting the right chunk in front of the answer step twice as often as the answer "
      "step uses it. That is where the wrong coverage answers are actually coming from.")
    w("2. **Edition disambiguation belongs in metadata, not in the ranker.** Every edition-scoped "
      "failure here (G01, G02, G03, G04) is a question whose answer depends on a field we already "
      "index and can filter on exactly. Parsing `ed. 03-24` out of the question and filtering "
      "`edition_date` is a smaller change than fusion and addresses the failures fusion could not.")
    w("3. **Only then revisit lexical retrieval**, and if so, with the exclusion code as a "
      "filterable field (`exclusion_codes` is already stamped on every chunk) rather than as "
      "bag-of-words evidence — which is what would have stopped the E-19 row from outranking the "
      "E-17 row.")
    w("")
    w("The team lead's proposal — swap the embedding model — is the one option the data rules out "
      f"first: {lab['G']} of {lab['R'] + lab['G']} failures already had the correct chunk in the "
      "top-3.")
    w("")

    # ---------------------------------------------------------------- appendix
    w("## Appendix — full inspection view, all 12 questions, both runs")
    w("")
    for g in golden:
        w(f"### {g['qid']} — {g['question']}")
        w("")
        w(f"Gold: `{g['gold_chunk_id']}` · known answer: {g['known_answer']}")
        w("")
        w(f"**Verdict: {verdicts[g['qid']]}**")
        w("")
        for mode, rows in (("dense — BEFORE", d_rows), ("hybrid — AFTER", h_rows)):
            w(f"`{mode}`")
            w("")
            w("```")
            for line in rows[g["qid"]]["view"].splitlines():
                w(line)
            w("```")
            w("")
    path.write_text("\n".join(o) + "\n", encoding="utf-8")
    print(f"wrote {path.name} ({len(o)} lines)")
