# Week 4 — Task Set D — Results

**Label the failures, then buy back hit-rate@3 with exactly one change.**

Headline: baseline hit-rate@3 **9/12** → after the one change **8/12**, p50 latency **67.9 ms → 43.9 ms**. The change did not buy back hit-rate@3. Section 9 is the shipping decision and section 5 is why this was still the right change to test.

## 0. The stack — what is actually running

| Component | What it is |
|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` — a 384-dim **bi-encoder**, run locally on CPU through `fastembed` (ONNX). Same model in both runs. |
| Vector database | **Chroma**, in-process, HNSW index in cosine space. |
| Lexical index | **BM25** (`src/bm25.py`), Lucene-style idf, k1=1.5, b=0.75, plain numpy. |
| Chunking | Week 3 `structure_aware` chunker — one chunk per exclusion-table row, each stamped with form number, edition, policy line, clause. Unchanged this week. |
| **Generation LLM** | **None. There is no LLM in this pipeline.** The answer is quoted verbatim from the cited chunk by `src/generator.py`, and the refusal is a gate in code. |

**Why no LLM, and why that does not weaken this task.** The graded metric is hit-rate@3 — a *retrieval* metric that asks whether the known-correct chunk is in the top-3. No generator can change it. The generator matters only for the R-vs-G split, and an extractive generator makes that split sharper, not softer: when the gold chunk is in the top-3 and the output still does not come from it, there is no 'the model hallucinated' excuse available — the answer step demonstrably had the right context and quoted a different chunk. That is G, on the definition in the task statement, and no retrieval change fixes it. Everything runs locally with no API key and no network.

Corpus: **99 chunks** from 8 endorsement files. The Week 3 drop was 6 forms; Week 4 adds **two further editions of HO-0304** (ed. 09-23 and ed. 01-25) alongside the existing ed. 03-24, because the failure in the task statement — *'does exclusion E-17 apply under form HO-0304 ed. 03-24'* — cannot exist in a corpus holding only one edition of the form. The three editions say materially different things about E-17 (21 days / 14 days / 14 days + a shut-off-device condition), so retrieving the wrong edition is a wrong coverage answer, not a cosmetic miss.

Every number below: same 12 questions, same index, same chunker, same embedding model, top-3, 7 latency reps per question. The **only** variable between the before and after columns is `RETRIEVAL_MODE`.

## 1. The golden set — 12 real adjuster questions with known-correct chunk_ids

Source: `golden_set.jsonl`. These are desk questions — the ones that arrive as *"what does E-22 say on the roof form"*, not questions written to make the retriever look good. **7 of 12 carry an exact token dense retrieval is structurally bad at** (the requirement is 4): an exclusion code, a form number, an edition. Four of them (G01–G04) turn on the *edition*, which is where a bi-encoder has nothing at all to work with.

| # | Question | Gold chunk_id | Exact token(s) |
|---|---|---|---|
| G01 | Does exclusion E-17 apply under form HO-0304 ed. 03-24? | `structure_aware::HO-0304@03-24::010` | `E-17, HO-0304 ed. 03-24` |
| G02 | HO-0304 ed. 03-24, E-18: insured left the house vacant over winter and a pipe froze. Excluded if they kept the heat on? | `structure_aware::HO-0304@03-24::011` | `E-18, HO-0304 ed. 03-24` |
| G03 | What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304? | `structure_aware::HO-0304@09-23::010` | `E-17, HO-0304 ed. 09-23` |
| G04 | Under HO-0304 ed. 01-25, does the E-17 burst supply line exception still apply if no shut-off device was installed? | `structure_aware::HO-0304@01-25::010` | `E-17, HO-0304 ed. 01-25` |
| G05 | What does E-22 exclude on endorsement HO-0455 ed. 01-24? | `structure_aware::HO-0455@01-24::010` | `E-22, HO-0455 ed. 01-24` |
| G06 | Is there a buy-back for E-32 under HO-2199 ed. 02-24? | `structure_aware::HO-2199@02-24::004` | `E-32, HO-2199 ed. 02-24` |
| G07 | DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form? | `structure_aware::DP-0431@04-24::007` | `E-17, DP-0431 ed. 04-24` |
| G08 | Insured says hail knocked granules off the shingles but the roof is not leaking. Covered, or cosmetic? | `structure_aware::HO-0455@01-24::009` | — |
| G09 | Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay? | `structure_aware::HO-0455@01-24::005` | — |
| G10 | Policyholder runs a bookkeeping business from a spare bedroom, no staff, no clients on site, about $8k a year. Does the business exclusion knock out the claim? | `structure_aware::HO-2199@02-24::005` | — |
| G11 | What definition of sudden and accidental do we apply when reading the seepage exclusion's exception? | `structure_aware::HO-0788@05-24::002` | — |
| G12 | After the ordinance or law increase endorsement, what is the cap on increased cost of construction? | `structure_aware::HO-0612@06-24::005` | — |

A 13th question is carried in `probes.jsonl` and is **not** counted in hit-rate@3: it asks about an edition of HO-0304 that is not in the drop, and exists to exercise the Not-In-Corpus label (section 4.3).

## 2. Baseline hit-rate@3 — written down before anything was changed

Frozen to `baseline_record.json` at `2026-08-31T12:37:04+00:00` by `python3 run_week4.py --freeze`, before `src/bm25.py` existed:

```json
{"mode": "dense", "hit_rate_at_3": "9/12", "p50_ms": 24.17, "chunks": 99}
```

### Baseline: **9/12 = 75%** hit-rate@3 (dense only, the Week 3 retriever)

| # | Gold in top-3? | Gold rank (dense) | Answer quoted from gold? | Label |
|---|---|---|---|---|
| G01 | **NO** | not in top-25 | no | `R` |
| G02 | **yes** | 3 | no | `G` |
| G03 | **yes** | 3 | no | `G` |
| G04 | **yes** | 1 | yes | `PASS` |
| G05 | **NO** | not in top-25 | no | `R` |
| G06 | **yes** | 1 | yes | `PASS` |
| G07 | **yes** | 3 | no | `G` |
| G08 | **yes** | 2 | no | `G` |
| G09 | **NO** | 4 | no | `R` |
| G10 | **yes** | 1 | no | `G` |
| G11 | **yes** | 1 | yes | `PASS` |
| G12 | **yes** | 1 | yes | `PASS` |

Answer-from-gold is 4/12 — much worse than hit-rate@3. That gap is the whole point of section 4: most of what a user would call a wrong answer is not a retrieval failure at all.

## 3. The inspection view

`src/inspect_view.py` + `inspect_query.py`. For one question it shows every candidate the retriever considered, the rank **each stage** gave it, where the gold chunk actually landed, and which chunk the answer was quoted from. The label is computed from those facts, never from whether the answer text looked plausible.

```
$ python3 inspect_query.py --qid G01 --mode dense
Q: Does exclusion E-17 apply under form HO-0304 ed. 03-24?
mode=dense  gold=structure_aware::HO-0304@03-24::010  gold_rank=None  hit@3=False  answer_ok=False  label=R (R)
exact tokens in question: ['E-17', 'HO-0304', '03-24']  (top-3 chunks carrying all of them: 0/3)
candidates (final order):
   1. dense#1(0.779)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   2. dense#2(0.766)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
   3. dense#3(0.761)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   4. dense#4(0.754)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   5. dense#5(0.746)  structure_aware::HO-2199@02-24::003
      HO-2199 ed.02-24 Clause 2: | E-31 | Theft or mysterious disappearance of personal property during a home-sharing o...
  gold structure_aware::HO-0304@03-24::010 not within the 25 candidates
answer quoted from: structure_aware::HO-2199@02-24::005
evidence: gold `structure_aware::HO-0304@03-24::010` at dense below rank 25 [-]; top-3 = HO-2199@02-24 E-33, HO-2199@02-24 E-30, HO-2199@02-24 E-34; 0/3 of the top-3 carry ['E-17', 'HO-0304', '03-24']
```

Decision rule, applied mechanically to all 12:

| Label | Rule |
|---|---|
| `PASS` | gold chunk in top-3 **and** the answer was quoted from it |
| `R` | gold chunk **not** in top-3 — retrieval fetched bad context |
| `G` | gold chunk **is** in top-3, but the answer step used a different chunk (or refused) |
| `NIC` | no chunk in the index can answer it |

## 4. The tally — every failure labelled, one line of evidence each

| Label | Count | Questions |
|---|---|---|
| pass | **4** | G04, G06, G11, G12 |
| R (retrieval fetched bad context) | **3** | G01, G05, G09 |
| G (model misused good context) | **5** | G02, G03, G07, G08, G10 |
| Not-In-Corpus | **0** | — |
| Not-In-Corpus probe (uncounted) | 1 | P01 |

**3 R · 5 G · 0 NIC in the scored set.** The tally is the argument: the majority of failures are G, and *no retrieval change on earth fixes a G*. Only the 3 R-failures were ever in scope for this week's change.

**Why only 4 of 12 are a clean pass.** hit-rate@3 is 9/12 — retrieval put the right clause in the top-3 that often. But end-to-end only 4/12 produce the right answer, and the gap is entirely the answer step: 3 questions where it read only rank 1, and 2 where it refused with the gold chunk already in front of it. Those two numbers are the real finding of this week, and neither is a retrieval defect:

| | Count | Meaning |
|---|---|---|
| Clean pass | 4/12 | right clause retrieved **and** quoted |
| Retrieval found it, answer step lost it | 5/12 | `G-rank` + `G-refuse`, section 4.2 |
| Retrieval never found it | 3/12 | `R`, section 4.1 — the only bucket this week's change could touch |

### 4.1 The R-failures — retrieval fetched bad context

- **G01** — *Does exclusion E-17 apply under form HO-0304 ed. 03-24?*  
  `gold `structure_aware::HO-0304@03-24::010` at dense below rank 25 [-]; top-3 = HO-2199@02-24 E-33, HO-2199@02-24 E-30, HO-2199@02-24 E-34; 0/3 of the top-3 carry ['E-17', 'HO-0304', '03-24']`
- **G05** — *What does E-22 exclude on endorsement HO-0455 ed. 01-24?*  
  `gold `structure_aware::HO-0455@01-24::010` at dense below rank 25 [-]; top-3 = HO-0788@05-24 Clause 1, HO-2199@02-24 E-30, HO-2199@02-24 E-33; 0/3 of the top-3 carry ['E-22', 'HO-0455', '01-24']`
- **G09** — *Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay?*  
  `gold `structure_aware::HO-0455@01-24::005` at dense rank 4 [dense#4(0.755)]; top-3 = HO-0455@01-24 Clause 1, HO-0455@01-24 Clause 2, HO-0455@01-24 Clause 2`

### 4.2 The G-failures — good context was there and the answer step still missed

All 5 are G by the task's definition: the gold chunk was sitting in the top-3 and the answer was still wrong. But they are **two different defects**, and lumping them would hide the more serious one, so the tally splits them:

| Sub-cause | Count | Questions | What actually happened |
|---|---|---|---|
| `G-rank` | **3** | G02, G03, G07 | gold was in the top-3 but **below rank 1**, and the answer step reads **only rank 1** |
| `G-refuse` | **2** | G08, G10 | the answer step **refused outright** although the gold chunk was right there |

**3 × G-rank — the answer step only ever reads rank 1.**

- **G02** — *HO-0304 ed. 03-24, E-18: insured left the house vacant over winter and a pipe froze. Excluded if they kept the heat on?*  
  `gold `structure_aware::HO-0304@03-24::011` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@09-23::011` (HO-0304@09-23 E-18)`
- **G03** — *What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304?*  
  `gold `structure_aware::HO-0304@09-23::010` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@03-24::010` (HO-0304@03-24 E-17)`
- **G07** — *DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form?*  
  `gold `structure_aware::DP-0431@04-24::007` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::DP-0431@04-24::008` (DP-0431@04-24 E-21)`

G02 is the clearest. The gold E-18 row **is** at rank 3 — and the two rows above it are the *same E-18 row from the 09-23 and 01-25 editions*, scoring 0.8086 against the gold's 0.8086, identical to four decimals. Retrieval did its job at top-3. `generator.py` then quotes `hits[0]` and cites the wrong edition of the form. On a real claim that is the wrong deductible and the wrong reporting window, delivered with a citation that looks correct. Reranking *within* the top-3 is the fix; a new embedding model is not, because three byte-identical rows cannot be separated by any bi-encoder.

**2 × G-refuse — the Week 3 refusal gate misfiring on real adjuster language.** This is the serious one, and it was invisible until the golden set was written from how adjusters actually talk.

- **G08** — *Insured says hail knocked granules off the shingles but the roof is not leaking. Covered, or cosmetic?*  
  `gold `structure_aware::HO-0455@01-24::009` IS in the top-3 at rank 2, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: says, knocked, granules, shingles, leaking)`  
  term coverage **50%** vs floor 55%; terms counted as absent: `says`, `knocked`, `granules`, `shingles`, `leaking`
- **G10** — *Policyholder runs a bookkeeping business from a spare bedroom, no staff, no clients on site, about $8k a year. Does the business exclusion knock out the claim?*  
  `gold `structure_aware::HO-2199@02-24::005` IS in the top-3 at rank 1, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: policyholder, bookkeeping, spare, bedroom, staff, clients, knock)`  
  term coverage **50%** vs floor 55%; terms counted as absent: `policyholder`, `bookkeeping`, `spare`, `bedroom`, `staff`, `clients`, `knock`

Read G10 carefully, because it is the worst result in the whole run: **the gold chunk is at rank 1** and the assistant still answers *"I could not find this in the indexed endorsements"*. Retrieval was perfect. The Week 3 coverage gate rejected the question before ranking was ever consulted, because words like `bookkeeping`, `spare`, `bedroom` and `clients` do not appear in policy wording — which is precisely how an adjuster describes a claim. The gate was tuned in Week 3 against 11 questions written *from the endorsements*, in the endorsements' own vocabulary, and it measured 62% worst-in-corpus on those. Against real adjuster phrasing it drops to 50% and refuses. The Week 3 report called 55% "a defensible gate at this scale, not a universal constant" — this is that bill arriving.

Neither sub-cause is reachable by a retrieval change. G-rank needs the answer step to read the whole top-3 instead of `hits[0]`; G-refuse needs the gate re-measured against adjuster vocabulary, or moved off raw term overlap entirely. Both are named in section 9 as the next changes, and neither was made this week — this week's one variable was retrieval.

### 4.3 Not-In-Corpus

- **P01** — *What does E-17 say on HO-0304 ed. 06-22?*  
  `no chunk_id is known to be correct; 0 of 99 indexed chunks carry all of ['E-17', 'HO-0304', '06-22']; top-3 = HO-2199@02-24 E-30, HO-0612@06-24 E-43, HO-2199@02-24 E-33`  
  Not in the drop: the pack holds ed. 09-23, 03-24 and 01-25 only. Not counted in hit-rate@3; used to demonstrate the Not-In-Corpus label.

## 5. The one change, and why the tally chose it

**The change: `RETRIEVAL_MODE = "dense"` → `"hybrid"` — dense top-25 + BM25 top-25, fused with Reciprocal Rank Fusion, k=60. Nothing else moved.** Same chunker, same embedding model, same index, same 12 questions, same top-3. No reranker was added in the same run; there is exactly one variable between the two columns.

The tally picked it, and the inspection view picked it over the reranker on evidence. Of the 3 R-failures, two — **G01** and **G05** — have their gold chunk at dense rank **33/99** and **27/99** respectively, measured by brute force over the whole index. A cross-encoder rerank over the top 25 can only reorder the 25 candidates dense already fetched; it cannot reach rank 33. **A reranker was structurally incapable of fixing 2 of the 3 R-failures before it ran.** Both of those questions are exact-token lookups (`E-17`+`HO-0304`+`03-24`; `E-22`+`HO-0455`), which is precisely what a lexical retriever is for. So: BM25 + RRF, and RRF fuses **ranks** — a cosine of 0.69 and a BM25 score of 6.17 are not on the same scale and adding them would be meaningless.

Also considered and rejected: swapping the embedding model, as the team lead suggested. 5 of the 8 failures are G — the right chunk was already in the top-3 — so a new bi-encoder changes nothing about them, and it would have cost a re-index plus the whole budget to prove it.

## 6. Before → after: hit-rate@3 and p50 latency

| | Before (`dense`) | After (`hybrid`: BM25 + RRF k=60) | Δ |
|---|---|---|---|
| **hit-rate@3** | **9/12** (75%) | **8/12** (67%) | **-1** |
| answer quoted from gold | 4/12 | 4/12 | +0 |
| **p50 latency / query** | **67.9 ms** | **43.9 ms** | **-24.0 ms (-35%)** |
| p95 latency / query | 262.8 ms | 61.5 ms | -201.2 ms |
| R / G / NIC | 3 / 5 / 0 | 4 / 4 / 0 | — |

Latency is wall-clock per `search()` call including the query embedding, 7 reps × 12 questions = 84 samples per mode, after warm-up, same process, same machine.

**Read the latency row honestly: the measured p50 delta is -24.0 ms, and that is inside the noise floor of this measurement.** The p50→p95 spread within a single mode is 194.9 ms — 8× the 24.0 ms between the two modes — and repeated runs move the dense p50 by more than the gap itself (the pre-change freeze in section 2 recorded 24.2 ms for the same dense retriever). So I will not quote a percentage as if it were a real cost: **the added BM25 + RRF stage costs less than this measurement can resolve.** The mechanism agrees: BM25 over a 99-chunk index is one numpy matrix product over a slice of a 99×|vocab| matrix, while a single query embedding through the ONNX bi-encoder dominates both paths.

**So the price was never the problem.** This is not a 'not worth the latency' verdict — the change is effectively free and *still* not worth shipping, because it did not move the number it was chosen to move. Cheap and useless is still useless. The one caveat I would put in front of the team lead: at 99 chunks BM25 is free, but its cost grows with corpus size while the embedding call does not, so this measurement does not license the claim that fusion is free across a full wording library.

## 7. Per-question: fixed / unfixed / still-broken

| # | Baseline label | Baseline rank | After rank | After label | Verdict |
|---|---|---|---|---|---|
| G01 | `R` | >25 | 17 | `R` | **still broken** |
| G02 | `G` | 3 | 2 | `G` | unchanged (still a hit) |
| G03 | `G` | 3 | 2 | `G` | unchanged (still a hit) |
| G04 | `PASS` | 1 | 1 | `PASS` | unchanged (still a hit) |
| G05 | `R` | >25 | 4 | `R` | **still broken** |
| G06 | `PASS` | 1 | 1 | `PASS` | unchanged (still a hit) |
| G07 | `G` | 3 | 1 | `PASS` | still a hit, label G→PASS |
| G08 | `G` | 2 | 2 | `G` | unchanged (still a hit) |
| G09 | `R` | 4 | 5 | `R` | **still broken** |
| G10 | `G` | 1 | 1 | `G` | unchanged (still a hit) |
| G11 | `PASS` | 1 | 4 | `R` | **REGRESSED** |
| G12 | `PASS` | 1 | 1 | `PASS` | unchanged (still a hit) |

### 7.1 Which R-failures the change fixed, and which it did not touch

Named per question, as required:

- **G01** — *Does exclusion E-17 apply under form HO-0304 ed. 03-24?*  
  gold rank not in top-25 → 17. **NOT FIXED.**
- **G05** — *What does E-22 exclude on endorsement HO-0455 ed. 01-24?*  
  gold rank not in top-25 → 4. **NOT FIXED.**
- **G09** — *Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay?*  
  gold rank 4 → 5. **NOT FIXED.**

**What the change did do, even though hit-rate@3 did not move up.** On G01 the gold E-17 row went from *invisible* — nowhere in dense's top-25, brute-force rank 33/99 — to **rank 5 on the BM25 list**. BM25 found the chunk dense could not see. RRF then failed to carry it into the top-3, and the inspection view says exactly why: the chunk that beats it on BM25 is the **E-19 row**, which merely *cites* E-17 ("where such condition results from a cause of loss excluded under E-15 or E-17"). Both rows contain `e-17` exactly once; the E-19 row is 73 tokens against the gold row's 98, and BM25's length normalisation (b=0.75, avgdl=62.6) rewards the shorter one. The retrieval defect is real and lexical, and BM25 addressed it — but a bag-of-words cannot tell *stating a rule* from *cross-referencing it*.

**And the regressions are the same mechanism in reverse.** G11 asks for a definition in prose and had the gold at dense rank 1; fusion pushed it to rank 4 behind chunks that score well lexically on `sudden`/`accidental`/`seepage` without being the definition. On a corpus where every chunk of a form carries that form's number and edition in its provenance header, form and edition tokens have almost no discriminative power *within* a document — `ho-0304` occurs in 48 of 99 chunks — so BM25's vote on an edition-scoped question is much weaker than it looks.

**Robustness check, reported because it cuts against the headline.** Re-running the same fusion with the Robertson idf variant `log((N-df+0.5)/(df+0.5))` plus rank_bm25's epsilon floor, instead of the Lucene `ln(1+·)` idf, gives hit-rate@3 = **9/12** — level with the baseline rather than below it. So the true reading is not 'BM25+RRF costs you a question', it is **'BM25+RRF is worth between −1 and 0 questions on this set, i.e. it does not buy back hit-rate@3, and which side of zero it lands on is decided by an idf formula rather than by anything about the corpus.'** `src/bm25.py` was cross-checked against an independently written Lucene-idf implementation and agrees to 5e-05.

## 8. Bonus — MMR over the fused candidate list

The bonus scenario is live in this corpus: for G01 the fused top-3 is the **same E-19 exclusion row repeated across the 09-23, 03-24 and 01-25 editions**. MMR should be the cure for exactly that. Tuned once, over the fused candidates, λ=1.0 being plain RRF order:

| λ | hit-rate@3 | mean pairwise cosine within top-3 (lower = more diverse) | mean distinct row texts in top-3 | mean distinct form editions in top-3 |
|---|---|---|---|---|
| 1.0 | **8/12** | 0.899 | 2.67/3 | 1.92/3 |
| 0.9 | **8/12** | 0.899 | 2.67/3 | 1.92/3 |
| 0.8 | **9/12** | 0.886 | 2.75/3 | 1.83/3 |
| 0.7 | **9/12** | 0.880 | 2.75/3 | 1.75/3 |
| 0.5 | **8/12** | 0.836 | 2.92/3 | 1.83/3 |
| 0.3 | **7/12** | 0.773 | 3.00/3 | 2.25/3 |

**What it did.** Diversity moves as advertised: mean pairwise cosine within the top-3 falls from 0.899 at λ=1.0 to 0.773 at λ=0.3, and distinct row texts rise from 2.67/3 to 3.00/3. Hit-rate@3 is not monotonic in λ: 8/12 at λ=1.0, up to **9/12 at λ=0.8**, back down to 7/12 at λ=0.3 where the diversity penalty starts evicting correct chunks outright.

That peak deserves a sentence rather than a victory lap. **MMR at λ=0.8 recovers hit-rate@3 to 9/12 — exactly level with the dense baseline, not above it.** A mild diversity penalty undoes some of the damage fusion did by breaking up the blocks of near-identical rows that crowded the top-3; it does not find anything the baseline could not. And λ was picked by reading this table, on these 12 questions, which is tuning on the test set: a 1-question swing on n=12 is one question, not a result. I am reporting it, not banking it.

**Would I ship it? No — and the bonus question names the reason precisely.** In this corpus the three near-duplicate candidates are not redundancy, they are *three different legal answers wearing the same words*: E-17 triggers at 21 days on ed. 09-23, 14 days on ed. 03-24, and 14 days plus an installed shut-off device on ed. 01-25. MMR's similarity penalty is computed on the same bi-encoder embedding that already cannot tell the editions apart, so it sees three interchangeable duplicates and drops two — and it has no way to know it kept the wrong one. On an edition-scoped question, pushing the correct edition out of the top-3 in the name of variety is not a diversity trade-off, it is a wrong coverage answer with better-looking search results. The right fix for near-duplicate editions is a metadata filter on `edition_date` (already supported, and it goes to the DB as a `where` clause), not a diversity penalty.

## 9. Shipping decision

**Do not ship the hybrid retriever. Baseline 9/12 → 8/12 on the same 12 questions: -1.** The latency price is real but small (67.9 → 43.9 ms p50, -24.0 ms); it is not what decides this. A change that costs -24.0 ms and returns between −1 and 0 questions does not go to an adjuster's desk, and "it fixed the E-17 query in principle" is not a number.

**What I would do with the budget instead, in tally order:**

1. **The 5 G-failures are the largest single bucket and no retrieval change touches them.** Answer-from-gold is 4/12 against hit-rate@3 of 9/12 — the retriever is already putting the right chunk in front of the answer step twice as often as the answer step uses it. That is where the wrong coverage answers are actually coming from.
2. **Edition disambiguation belongs in metadata, not in the ranker.** Every edition-scoped failure here (G01, G02, G03, G04) is a question whose answer depends on a field we already index and can filter on exactly. Parsing `ed. 03-24` out of the question and filtering `edition_date` is a smaller change than fusion and addresses the failures fusion could not.
3. **Only then revisit lexical retrieval**, and if so, with the exclusion code as a filterable field (`exclusion_codes` is already stamped on every chunk) rather than as bag-of-words evidence — which is what would have stopped the E-19 row from outranking the E-17 row.

The team lead's proposal — swap the embedding model — is the one option the data rules out first: 5 of 8 failures already had the correct chunk in the top-3.

## Appendix — full inspection view, all 12 questions, both runs

### G01 — Does exclusion E-17 apply under form HO-0304 ed. 03-24?

Gold: `structure_aware::HO-0304@03-24::010` · known answer: E-17 (ed. 03-24) excludes seepage over 14 days or more, whether or not known to the insured; it does not apply to a sudden and accidental discharge as defined in HO-0788, including a burst supply line, provided the loss is reported within 30 days.

**Verdict: **still broken****

`dense — BEFORE`

```
Q: Does exclusion E-17 apply under form HO-0304 ed. 03-24?
mode=dense  gold=structure_aware::HO-0304@03-24::010  gold_rank=None  hit@3=False  answer_ok=False  label=R (R)
exact tokens in question: ['E-17', 'HO-0304', '03-24']  (top-3 chunks carrying all of them: 0/3)
candidates (final order):
   1. dense#1(0.779)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   2. dense#2(0.766)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
   3. dense#3(0.761)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   4. dense#4(0.754)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   5. dense#5(0.746)  structure_aware::HO-2199@02-24::003
      HO-2199 ed.02-24 Clause 2: | E-31 | Theft or mysterious disappearance of personal property during a home-sharing o...
  gold structure_aware::HO-0304@03-24::010 not within the 25 candidates
answer quoted from: structure_aware::HO-2199@02-24::005
evidence: gold `structure_aware::HO-0304@03-24::010` at dense below rank 25 [-]; top-3 = HO-2199@02-24 E-33, HO-2199@02-24 E-30, HO-2199@02-24 E-34; 0/3 of the top-3 carry ['E-17', 'HO-0304', '03-24']
```

`hybrid — AFTER`

```
Q: Does exclusion E-17 apply under form HO-0304 ed. 03-24?
mode=hybrid  gold=structure_aware::HO-0304@03-24::010  gold_rank=17  hit@3=False  answer_ok=False  label=R (R)
exact tokens in question: ['E-17', 'HO-0304', '03-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#6(0.739)  bm25#1(8.861)  rrf#1(0.032)  structure_aware::HO-0304@03-24::012
      HO-0304 ed.03-24 Clause 3: | E-19 | Mould, fungus, wet rot, dry rot, or bacteria, where such condition results fro...
   2. dense#8(0.736)  bm25#2(7.291)  rrf#2(0.031)  structure_aware::HO-0304@01-25::012
      HO-0304 ed.01-25 Clause 3: | E-19 | Mould, fungus, wet rot, dry rot, or bacteria, where such condition results fro...
   3. dense#7(0.737)  bm25#3(7.291)  rrf#3(0.031)  structure_aware::HO-0304@09-23::012
      HO-0304 ed.09-23 Clause 3: | E-19 | Mould, fungus, wet rot, dry rot, or bacteria, where such condition results fro...
   4. dense#2(0.766)  bm25#10(4.955)  rrf#4(0.030)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
   5. dense#4(0.754)  bm25#11(4.799)  rrf#5(0.030)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
  ...
  17. dense#-  bm25#5(6.174)  rrf#17(0.015)  structure_aware::HO-0304@03-24::010  <-- GOLD
answer quoted from: structure_aware::HO-0304@03-24::012
evidence: gold `structure_aware::HO-0304@03-24::010` at hybrid rank 17 [bm25#5(6.174), rrf#17(0.015)]; top-3 = HO-0304@03-24 E-19, HO-0304@01-25 E-19, HO-0304@09-23 E-19; 1/3 of the top-3 carry ['E-17', 'HO-0304', '03-24']
```

### G02 — HO-0304 ed. 03-24, E-18: insured left the house vacant over winter and a pipe froze. Excluded if they kept the heat on?

Gold: `structure_aware::HO-0304@03-24::011` · known answer: E-18 excludes freezing while vacant, but the exception applies if the insured used reasonable care to maintain heat, or shut off the water and drained the system - so with heat maintained it is not excluded.

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: HO-0304 ed. 03-24, E-18: insured left the house vacant over winter and a pipe froze. Excluded if they kept the heat on?
mode=dense  gold=structure_aware::HO-0304@03-24::011  gold_rank=3  hit@3=True  answer_ok=False  label=G (G-rank)
exact tokens in question: ['E-18', 'HO-0304', '03-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.809)  structure_aware::HO-0304@09-23::011
      HO-0304 ed.09-23 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   2. dense#2(0.809)  structure_aware::HO-0304@01-25::011
      HO-0304 ed.01-25 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   3. dense#3(0.809)  structure_aware::HO-0304@03-24::011  <-- GOLD
      HO-0304 ed.03-24 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   4. dense#4(0.731)  structure_aware::HO-0304@01-25::005
      HO-0304 ed.01-25 Clause 2: Coverage under this clause includes the reasonable cost to tear out and replace that pa...
   5. dense#5(0.731)  structure_aware::HO-0304@03-24::005
      HO-0304 ed.03-24 Clause 2: Coverage under this clause includes the reasonable cost to tear out and replace that pa...
answer quoted from: structure_aware::HO-0304@09-23::011
evidence: gold `structure_aware::HO-0304@03-24::011` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@09-23::011` (HO-0304@09-23 E-18)
```

`hybrid — AFTER`

```
Q: HO-0304 ed. 03-24, E-18: insured left the house vacant over winter and a pipe froze. Excluded if they kept the heat on?
mode=hybrid  gold=structure_aware::HO-0304@03-24::011  gold_rank=2  hit@3=True  answer_ok=False  label=G (G-rank)
exact tokens in question: ['E-18', 'HO-0304', '03-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.809)  bm25#3(17.313)  rrf#1(0.032)  structure_aware::HO-0304@09-23::011
      HO-0304 ed.09-23 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   2. dense#3(0.809)  bm25#1(18.823)  rrf#2(0.032)  structure_aware::HO-0304@03-24::011  <-- GOLD
      HO-0304 ed.03-24 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   3. dense#2(0.809)  bm25#2(17.313)  rrf#3(0.032)  structure_aware::HO-0304@01-25::011
      HO-0304 ed.01-25 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   4. dense#8(0.715)  bm25#4(8.910)  rrf#4(0.030)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   5. dense#7(0.719)  bm25#7(7.449)  rrf#5(0.030)  structure_aware::HO-0304@01-25::010
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
answer quoted from: structure_aware::HO-0304@09-23::011
evidence: gold `structure_aware::HO-0304@03-24::011` IS in the top-3 at rank 2, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@09-23::011` (HO-0304@09-23 E-18)
```

### G03 — What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304?

Gold: `structure_aware::HO-0304@09-23::010` · known answer: 21 days or more on ed. 09-23 (versus 14 days on ed. 03-24 and ed. 01-25).

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304?
mode=dense  gold=structure_aware::HO-0304@09-23::010  gold_rank=3  hit@3=True  answer_ok=False  label=G (G-rank)
exact tokens in question: ['E-17', 'HO-0304', '09-23']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.733)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   2. dense#2(0.730)  structure_aware::HO-0304@01-25::010
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   3. dense#3(0.718)  structure_aware::HO-0304@09-23::010  <-- GOLD
      HO-0304 ed.09-23 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   4. dense#4(0.697)  structure_aware::HO-0612@06-24::010
      HO-0612 ed.06-24 Clause 3: | E-43 | The cost to comply with an ordinance or law where the loss triggering enforcem...
   5. dense#5(0.688)  structure_aware::HO-0304@03-24::004
      HO-0304 ed.03-24 Clause 1: | Annual aggregate | $30,000 |
answer quoted from: structure_aware::HO-0304@03-24::010
evidence: gold `structure_aware::HO-0304@09-23::010` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@03-24::010` (HO-0304@03-24 E-17)
```

`hybrid — AFTER`

```
Q: What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304?
mode=hybrid  gold=structure_aware::HO-0304@09-23::010  gold_rank=2  hit@3=True  answer_ok=False  label=G (G-rank)
exact tokens in question: ['E-17', 'HO-0304', '09-23']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.733)  bm25#4(8.886)  rrf#1(0.032)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   2. dense#3(0.718)  bm25#3(9.498)  rrf#2(0.032)  structure_aware::HO-0304@09-23::010  <-- GOLD
      HO-0304 ed.09-23 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   3. dense#6(0.686)  bm25#1(11.863)  rrf#3(0.032)  structure_aware::HO-0304@09-23::000
      HO-0304 ed.09-23 Header: This endorsement modifies insurance provided under the HOMEOWNERS POLICY WORDING. All o...
   4. dense#2(0.730)  bm25#7(8.372)  rrf#4(0.031)  structure_aware::HO-0304@01-25::010
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   5. dense#10(0.677)  bm25#5(8.722)  rrf#5(0.030)  structure_aware::HO-0304@01-25::000
      HO-0304 ed.01-25 Header: This endorsement modifies insurance provided under the HOMEOWNERS POLICY WORDING. All o...
answer quoted from: structure_aware::HO-0304@03-24::010
evidence: gold `structure_aware::HO-0304@09-23::010` IS in the top-3 at rank 2, but the answer step reads ONLY rank 1 and quoted `structure_aware::HO-0304@03-24::010` (HO-0304@03-24 E-17)
```

### G04 — Under HO-0304 ed. 01-25, does the E-17 burst supply line exception still apply if no shut-off device was installed?

Gold: `structure_aware::HO-0304@01-25::010` · known answer: No. On ed. 01-25 the exception requires the loss to be reported within 14 days AND an approved automatic shut-off device installed and operational at the time of loss.

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: Under HO-0304 ed. 01-25, does the E-17 burst supply line exception still apply if no shut-off device was installed?
mode=dense  gold=structure_aware::HO-0304@01-25::010  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
exact tokens in question: ['E-17', 'HO-0304', '01-25']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.711)  structure_aware::HO-0304@01-25::010  <-- GOLD
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   2. dense#2(0.700)  structure_aware::HO-0304@09-23::010
      HO-0304 ed.09-23 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   3. dense#3(0.692)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   4. dense#4(0.671)  structure_aware::HO-0304@03-24::011
      HO-0304 ed.03-24 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   5. dense#5(0.670)  structure_aware::HO-0304@01-25::011
      HO-0304 ed.01-25 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
answer quoted from: structure_aware::HO-0304@01-25::010
evidence: gold at dense rank 1; quoted from it
```

`hybrid — AFTER`

```
Q: Under HO-0304 ed. 01-25, does the E-17 burst supply line exception still apply if no shut-off device was installed?
mode=hybrid  gold=structure_aware::HO-0304@01-25::010  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
exact tokens in question: ['E-17', 'HO-0304', '01-25']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.711)  bm25#1(20.474)  rrf#1(0.033)  structure_aware::HO-0304@01-25::010  <-- GOLD
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   2. dense#3(0.692)  bm25#5(12.293)  rrf#2(0.031)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   3. dense#2(0.700)  bm25#7(11.815)  rrf#3(0.031)  structure_aware::HO-0304@09-23::010
      HO-0304 ed.09-23 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   4. dense#5(0.670)  bm25#6(12.090)  rrf#4(0.031)  structure_aware::HO-0304@01-25::011
      HO-0304 ed.01-25 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
   5. dense#4(0.671)  bm25#8(10.477)  rrf#5(0.030)  structure_aware::HO-0304@03-24::011
      HO-0304 ed.03-24 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
answer quoted from: structure_aware::HO-0304@01-25::010
evidence: gold at hybrid rank 1; quoted from it
```

### G05 — What does E-22 exclude on endorsement HO-0455 ed. 01-24?

Gold: `structure_aware::HO-0455@01-24::010` · known answer: Loss to roof surfacing caused by wear, tear, deterioration, or manufacturing defect; no exception. (DP-0431 also has an E-22 and it says something different - supply line older than 10 years.)

**Verdict: **still broken****

`dense — BEFORE`

```
Q: What does E-22 exclude on endorsement HO-0455 ed. 01-24?
mode=dense  gold=structure_aware::HO-0455@01-24::010  gold_rank=None  hit@3=False  answer_ok=False  label=R (R)
exact tokens in question: ['E-22', 'HO-0455', '01-24']  (top-3 chunks carrying all of them: 0/3)
candidates (final order):
   1. dense#1(0.721)  structure_aware::HO-0788@05-24::001
      HO-0788 ed.05-24 Clause 1: The definitions in Clause 2 replace any conflicting definition in the base wording and ...
   2. dense#2(0.719)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
   3. dense#3(0.717)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   4. dense#4(0.710)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   5. dense#5(0.710)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
  gold structure_aware::HO-0455@01-24::010 not within the 25 candidates
answer quoted from: structure_aware::HO-0788@05-24::001
evidence: gold `structure_aware::HO-0455@01-24::010` at dense below rank 25 [-]; top-3 = HO-0788@05-24 Clause 1, HO-2199@02-24 E-30, HO-2199@02-24 E-33; 0/3 of the top-3 carry ['E-22', 'HO-0455', '01-24']
```

`hybrid — AFTER`

```
Q: What does E-22 exclude on endorsement HO-0455 ed. 01-24?
mode=hybrid  gold=structure_aware::HO-0455@01-24::010  gold_rank=4  hit@3=False  answer_ok=False  label=R (R)
exact tokens in question: ['E-22', 'HO-0455', '01-24']  (top-3 chunks carrying all of them: 0/3)
candidates (final order):
   1. dense#1(0.721)  bm25#19(2.828)  rrf#1(0.029)  structure_aware::HO-0788@05-24::001
      HO-0788 ed.05-24 Clause 1: The definitions in Clause 2 replace any conflicting definition in the base wording and ...
   2. dense#3(0.717)  bm25#20(2.772)  rrf#2(0.028)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   3. dense#13(0.676)  bm25#24(2.367)  rrf#3(0.026)  structure_aware::HO-0304@01-25::000
      HO-0304 ed.01-25 Header: This endorsement modifies insurance provided under the HOMEOWNERS POLICY WORDING. All o...
   4. dense#-  bm25#1(8.793)  rrf#4(0.016)  structure_aware::HO-0455@01-24::010  <-- GOLD
      HO-0455 ed.01-24 Clause 3: | E-22 | Loss to roof surfacing caused by wear, tear, deterioration, or manufacturing d...
   5. dense#2(0.719)  bm25#-  rrf#5(0.016)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
answer quoted from: structure_aware::HO-0788@05-24::001
evidence: gold `structure_aware::HO-0455@01-24::010` at hybrid rank 4 [bm25#1(8.793), rrf#4(0.016)]; top-3 = HO-0788@05-24 Clause 1, HO-2199@02-24 E-33, HO-0304@01-25 Header; 0/3 of the top-3 carry ['E-22', 'HO-0455', '01-24']
```

### G06 — Is there a buy-back for E-32 under HO-2199 ed. 02-24?

Gold: `structure_aware::HO-2199@02-24::004` · known answer: Yes - E-32 (liability arising out of a home-sharing occupancy) does not apply where the Home-Sharing Liability Buy-Back is shown in the Declarations.

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: Is there a buy-back for E-32 under HO-2199 ed. 02-24?
mode=dense  gold=structure_aware::HO-2199@02-24::004  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
exact tokens in question: ['E-32', 'HO-2199', '02-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.728)  structure_aware::HO-2199@02-24::004  <-- GOLD
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   2. dense#2(0.701)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   3. dense#3(0.695)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
   4. dense#4(0.693)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   5. dense#5(0.683)  structure_aware::HO-2199@02-24::003
      HO-2199 ed.02-24 Clause 2: | E-31 | Theft or mysterious disappearance of personal property during a home-sharing o...
answer quoted from: structure_aware::HO-2199@02-24::004
evidence: gold at dense rank 1; quoted from it
```

`hybrid — AFTER`

```
Q: Is there a buy-back for E-32 under HO-2199 ed. 02-24?
mode=hybrid  gold=structure_aware::HO-2199@02-24::004  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
exact tokens in question: ['E-32', 'HO-2199', '02-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.728)  bm25#1(14.071)  rrf#1(0.033)  structure_aware::HO-2199@02-24::004  <-- GOLD
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   2. dense#6(0.666)  bm25#3(9.318)  rrf#2(0.031)  structure_aware::HO-2199@02-24::000
      HO-2199 ed.02-24 Header: This endorsement modifies insurance provided under the HOMEOWNERS POLICY WORDING.
   3. dense#4(0.693)  bm25#5(8.069)  rrf#3(0.031)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   4. dense#2(0.701)  bm25#9(6.035)  rrf#4(0.031)  structure_aware::HO-2199@02-24::005
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   5. dense#3(0.695)  bm25#11(5.820)  rrf#5(0.030)  structure_aware::HO-2199@02-24::002
      HO-2199 ed.02-24 Clause 2: | E-30 | Any loss to covered property occurring during a home-sharing occupancy | Build...
answer quoted from: structure_aware::HO-2199@02-24::004
evidence: gold at hybrid rank 1; quoted from it
```

### G07 — DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form?

Gold: `structure_aware::DP-0431@04-24::007` · known answer: No exception. DP-0431 E-17 applies whether or not the discharge was sudden and accidental, and applies to a burst supply line; it triggers at 7 days.

**Verdict: still a hit, label G→PASS**

`dense — BEFORE`

```
Q: DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form?
mode=dense  gold=structure_aware::DP-0431@04-24::007  gold_rank=3  hit@3=True  answer_ok=False  label=G (G-rank)
exact tokens in question: ['E-17', 'DP-0431', '04-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#1(0.764)  structure_aware::DP-0431@04-24::008
      DP-0431 ed.04-24 Clause 3: | E-21 | Any escape of water occurring while the dwelling has been vacant or unoccupied...
   2. dense#2(0.752)  structure_aware::DP-0431@04-24::009
      DP-0431 ed.04-24 Clause 3: | E-22 | Loss caused by the failure of a supply line, hose, or fitting older than 10 ye...
   3. dense#3(0.747)  structure_aware::DP-0431@04-24::007  <-- GOLD
      DP-0431 ed.04-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence of ...
   4. dense#4(0.746)  structure_aware::DP-0431@04-24::005
      DP-0431 ed.04-24 Clause 3: | E-14 | Flood, surface water, waves, tidal water, or overflow of a body of water | All...
   5. dense#5(0.729)  structure_aware::DP-0431@04-24::006
      DP-0431 ed.04-24 Clause 3: | E-15 | Water below the surface of the ground, including water exerting pressure on or...
answer quoted from: structure_aware::DP-0431@04-24::008
evidence: gold `structure_aware::DP-0431@04-24::007` IS in the top-3 at rank 3, but the answer step reads ONLY rank 1 and quoted `structure_aware::DP-0431@04-24::008` (DP-0431@04-24 E-21)
```

`hybrid — AFTER`

```
Q: DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form?
mode=hybrid  gold=structure_aware::DP-0431@04-24::007  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
exact tokens in question: ['E-17', 'DP-0431', '04-24']  (top-3 chunks carrying all of them: 1/3)
candidates (final order):
   1. dense#3(0.747)  bm25#2(15.206)  rrf#1(0.032)  structure_aware::DP-0431@04-24::007  <-- GOLD
      DP-0431 ed.04-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence of ...
   2. dense#6(0.722)  bm25#1(16.081)  rrf#2(0.032)  structure_aware::DP-0431@04-24::000
      DP-0431 ed.04-24 Header: This endorsement modifies insurance provided under the DWELLING FIRE POLICY WORDING. It...
   3. dense#1(0.764)  bm25#7(11.366)  rrf#3(0.031)  structure_aware::DP-0431@04-24::008
      DP-0431 ed.04-24 Clause 3: | E-21 | Any escape of water occurring while the dwelling has been vacant or unoccupied...
   4. dense#5(0.729)  bm25#5(12.018)  rrf#4(0.031)  structure_aware::DP-0431@04-24::006
      DP-0431 ed.04-24 Clause 3: | E-15 | Water below the surface of the ground, including water exerting pressure on or...
   5. dense#2(0.752)  bm25#9(10.337)  rrf#5(0.031)  structure_aware::DP-0431@04-24::009
      DP-0431 ed.04-24 Clause 3: | E-22 | Loss caused by the failure of a supply line, hose, or fitting older than 10 ye...
answer quoted from: structure_aware::DP-0431@04-24::007
evidence: gold at hybrid rank 1; quoted from it
```

### G08 — Insured says hail knocked granules off the shingles but the roof is not leaking. Covered, or cosmetic?

Gold: `structure_aware::HO-0455@01-24::009` · known answer: Excluded under E-21 as cosmetic damage that does not compromise the water-shedding function (granule loss is named), unless the Cosmetic Damage Buy-Back is shown in the Declarations.

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: Insured says hail knocked granules off the shingles but the roof is not leaking. Covered, or cosmetic?
mode=dense  gold=structure_aware::HO-0455@01-24::009  gold_rank=2  hit@3=True  answer_ok=False  label=G (G-refuse)
candidates (final order):
   1. dense#1(0.719)  structure_aware::HO-0455@01-24::001
      HO-0455 ed.01-24 Clause 1: Loss to roof surfacing caused by windstorm or hail is settled at actual cash value, not...
   2. dense#2(0.705)  structure_aware::HO-0455@01-24::009  <-- GOLD
      HO-0455 ed.01-24 Clause 3: | E-21 | Cosmetic damage to roof surfacing that does not compromise the water-shedding ...
   3. dense#3(0.665)  structure_aware::HO-0455@01-24::013
      HO-0455 ed.01-24 Clause 4: 4.2 The insured must produce documentation of roof age. Where no documentation is produ...
   4. dense#4(0.657)  structure_aware::HO-0455@01-24::010
      HO-0455 ed.01-24 Clause 3: | E-22 | Loss to roof surfacing caused by wear, tear, deterioration, or manufacturing d...
   5. dense#5(0.657)  structure_aware::HO-0455@01-24::012
      HO-0455 ed.01-24 Clause 3: | E-24 | Loss caused by repair, alteration, or installation work performed on the roof ...
answer quoted from: None
evidence: gold `structure_aware::HO-0455@01-24::009` IS in the top-3 at rank 2, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: says, knocked, granules, shingles, leaking)
```

`hybrid — AFTER`

```
Q: Insured says hail knocked granules off the shingles but the roof is not leaking. Covered, or cosmetic?
mode=hybrid  gold=structure_aware::HO-0455@01-24::009  gold_rank=2  hit@3=True  answer_ok=False  label=G (G-refuse)
candidates (final order):
   1. dense#1(0.719)  bm25#2(11.594)  rrf#1(0.033)  structure_aware::HO-0455@01-24::001
      HO-0455 ed.01-24 Clause 1: Loss to roof surfacing caused by windstorm or hail is settled at actual cash value, not...
   2. dense#2(0.705)  bm25#1(13.133)  rrf#2(0.033)  structure_aware::HO-0455@01-24::009  <-- GOLD
      HO-0455 ed.01-24 Clause 3: | E-21 | Cosmetic damage to roof surfacing that does not compromise the water-shedding ...
   3. dense#3(0.665)  bm25#3(10.133)  rrf#3(0.032)  structure_aware::HO-0455@01-24::013
      HO-0455 ed.01-24 Clause 4: 4.2 The insured must produce documentation of roof age. Where no documentation is produ...
   4. dense#5(0.657)  bm25#17(5.646)  rrf#4(0.028)  structure_aware::HO-0455@01-24::012
      HO-0455 ed.01-24 Clause 3: | E-24 | Loss caused by repair, alteration, or installation work performed on the roof ...
   5. dense#22(0.600)  bm25#7(7.847)  rrf#5(0.027)  structure_aware::HO-0304@01-25::011
      HO-0304 ed.01-25 Clause 3: | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protectiv...
answer quoted from: None
evidence: gold `structure_aware::HO-0455@01-24::009` IS in the top-3 at rank 2, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: says, knocked, granules, shingles, leaking)
```

### G09 — Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay?

Gold: `structure_aware::HO-0455@01-24::005` · known answer: 60% - the 11 to 15 years band of the Payment Schedule.

**Verdict: **still broken****

`dense — BEFORE`

```
Q: Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay?
mode=dense  gold=structure_aware::HO-0455@01-24::005  gold_rank=4  hit@3=False  answer_ok=False  label=R (R)
candidates (final order):
   1. dense#1(0.768)  structure_aware::HO-0455@01-24::001
      HO-0455 ed.01-24 Clause 1: Loss to roof surfacing caused by windstorm or hail is settled at actual cash value, not...
   2. dense#2(0.756)  structure_aware::HO-0455@01-24::004
      HO-0455 ed.01-24 Clause 2: | 6 to 10 years | 80% | 95% |
   3. dense#3(0.756)  structure_aware::HO-0455@01-24::007
      HO-0455 ed.01-24 Clause 2: | 21 to 25 years | 25% | 55% |
   4. dense#4(0.755)  structure_aware::HO-0455@01-24::005  <-- GOLD
      HO-0455 ed.01-24 Clause 2: | 11 to 15 years | 60% | 85% |
   5. dense#5(0.751)  structure_aware::HO-0455@01-24::006
      HO-0455 ed.01-24 Clause 2: | 16 to 20 years | 40% | 70% |
answer quoted from: structure_aware::HO-0455@01-24::001
evidence: gold `structure_aware::HO-0455@01-24::005` at dense rank 4 [dense#4(0.755)]; top-3 = HO-0455@01-24 Clause 1, HO-0455@01-24 Clause 2, HO-0455@01-24 Clause 2
```

`hybrid — AFTER`

```
Q: Asphalt shingle roof, 12 years old, hail loss. What percentage of replacement cost do we pay?
mode=hybrid  gold=structure_aware::HO-0455@01-24::005  gold_rank=5  hit@3=False  answer_ok=False  label=R (R)
candidates (final order):
   1. dense#1(0.768)  bm25#1(15.616)  rrf#1(0.033)  structure_aware::HO-0455@01-24::001
      HO-0455 ed.01-24 Clause 1: Loss to roof surfacing caused by windstorm or hail is settled at actual cash value, not...
   2. dense#2(0.756)  bm25#5(13.705)  rrf#2(0.032)  structure_aware::HO-0455@01-24::004
      HO-0455 ed.01-24 Clause 2: | 6 to 10 years | 80% | 95% |
   3. dense#8(0.727)  bm25#2(14.325)  rrf#3(0.031)  structure_aware::HO-0455@01-24::013
      HO-0455 ed.01-24 Clause 4: 4.2 The insured must produce documentation of roof age. Where no documentation is produ...
   4. dense#7(0.747)  bm25#3(13.815)  rrf#4(0.031)  structure_aware::HO-0455@01-24::008
      HO-0455 ed.01-24 Clause 2: | Over 25 years | 15% | 40% |
   5. dense#4(0.755)  bm25#6(13.705)  rrf#5(0.031)  structure_aware::HO-0455@01-24::005  <-- GOLD
      HO-0455 ed.01-24 Clause 2: | 11 to 15 years | 60% | 85% |
answer quoted from: structure_aware::HO-0455@01-24::001
evidence: gold `structure_aware::HO-0455@01-24::005` at hybrid rank 5 [dense#4(0.755), bm25#6(13.705), rrf#5(0.031)]; top-3 = HO-0455@01-24 Clause 1, HO-0455@01-24 Clause 2, HO-0455@01-24 Clause 4
```

### G10 — Policyholder runs a bookkeeping business from a spare bedroom, no staff, no clients on site, about $8k a year. Does the business exclusion knock out the claim?

Gold: `structure_aware::HO-2199@02-24::005` · known answer: No. E-33 does not apply to an incidental office occupancy with no employees and no customer visits where annual gross receipts do not exceed $10,000.

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: Policyholder runs a bookkeeping business from a spare bedroom, no staff, no clients on site, about $8k a year. Does the business exclusion knock out the claim?
mode=dense  gold=structure_aware::HO-2199@02-24::005  gold_rank=1  hit@3=True  answer_ok=False  label=G (G-refuse)
candidates (final order):
   1. dense#1(0.742)  structure_aware::HO-2199@02-24::005  <-- GOLD
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   2. dense#2(0.682)  structure_aware::HO-2199@02-24::008
      HO-2199 ed.02-24 Clause 4: A home-sharing surcharge of 18% of the base premium applies for any policy year in whic...
   3. dense#3(0.682)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
   4. dense#4(0.677)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   5. dense#5(0.676)  structure_aware::HO-2199@02-24::003
      HO-2199 ed.02-24 Clause 2: | E-31 | Theft or mysterious disappearance of personal property during a home-sharing o...
answer quoted from: None
evidence: gold `structure_aware::HO-2199@02-24::005` IS in the top-3 at rank 1, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: policyholder, bookkeeping, spare, bedroom, staff, clients, knock)
```

`hybrid — AFTER`

```
Q: Policyholder runs a bookkeeping business from a spare bedroom, no staff, no clients on site, about $8k a year. Does the business exclusion knock out the claim?
mode=hybrid  gold=structure_aware::HO-2199@02-24::005  gold_rank=1  hit@3=True  answer_ok=False  label=G (G-refuse)
candidates (final order):
   1. dense#1(0.742)  bm25#1(23.161)  rrf#1(0.033)  structure_aware::HO-2199@02-24::005  <-- GOLD
      HO-2199 ed.02-24 Clause 2: | E-33 | Any loss arising out of a business conducted on the residence premises, includ...
   2. dense#2(0.682)  bm25#2(15.737)  rrf#2(0.032)  structure_aware::HO-2199@02-24::008
      HO-2199 ed.02-24 Clause 4: A home-sharing surcharge of 18% of the base premium applies for any policy year in whic...
   3. dense#4(0.677)  bm25#4(14.343)  rrf#3(0.031)  structure_aware::HO-2199@02-24::004
      HO-2199 ed.02-24 Clause 2: | E-32 | Bodily injury or property damage arising out of a home-sharing occupancy | Sec...
   4. dense#7(0.664)  bm25#5(11.725)  rrf#4(0.030)  structure_aware::HO-2199@02-24::007
      HO-2199 ed.02-24 Clause 3: 3.2 More than 60 days of home-sharing occupancy in any policy year renders the risk ine...
   5. dense#3(0.682)  bm25#11(9.548)  rrf#5(0.030)  structure_aware::HO-2199@02-24::006
      HO-2199 ed.02-24 Clause 2: | E-34 | Loss to property held for rental to others, or to furnishings provided for the...
answer quoted from: None
evidence: gold `structure_aware::HO-2199@02-24::005` IS in the top-3 at rank 1, but the answer step REFUSED (gate=term_coverage: Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: policyholder, bookkeeping, spare, bedroom, staff, clients, knock)
```

### G11 — What definition of sudden and accidental do we apply when reading the seepage exclusion's exception?

Gold: `structure_aware::HO-0788@05-24::002` · known answer: HO-0788 2.1: unexpected and unintended from the insured's standpoint, beginning at an identifiable point in time; a slow weep or drip is not sudden and accidental even if it later worsens abruptly.

**Verdict: **REGRESSED****

`dense — BEFORE`

```
Q: What definition of sudden and accidental do we apply when reading the seepage exclusion's exception?
mode=dense  gold=structure_aware::HO-0788@05-24::002  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
candidates (final order):
   1. dense#1(0.784)  structure_aware::HO-0788@05-24::002  <-- GOLD
      HO-0788 ed.05-24 Clause 2: 2.3 Constant or repeated seepage or leakage means an escape of water that is continuous...
   2. dense#2(0.774)  structure_aware::HO-0788@05-24::004
      HO-0788 ed.05-24 Clause 3: 3.3 Nothing in this endorsement creates coverage that is otherwise excluded, nor increa...
   3. dense#3(0.735)  structure_aware::DP-0431@04-24::007
      DP-0431 ed.04-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence of ...
   4. dense#4(0.725)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   5. dense#5(0.711)  structure_aware::HO-0304@01-25::010
      HO-0304 ed.01-25 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
answer quoted from: structure_aware::HO-0788@05-24::002
evidence: gold at dense rank 1; quoted from it
```

`hybrid — AFTER`

```
Q: What definition of sudden and accidental do we apply when reading the seepage exclusion's exception?
mode=hybrid  gold=structure_aware::HO-0788@05-24::002  gold_rank=4  hit@3=False  answer_ok=False  label=R (R)
candidates (final order):
   1. dense#2(0.774)  bm25#1(13.829)  rrf#1(0.033)  structure_aware::HO-0788@05-24::004
      HO-0788 ed.05-24 Clause 3: 3.3 Nothing in this endorsement creates coverage that is otherwise excluded, nor increa...
   2. dense#3(0.735)  bm25#2(10.939)  rrf#2(0.032)  structure_aware::DP-0431@04-24::007
      DP-0431 ed.04-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence of ...
   3. dense#4(0.725)  bm25#4(8.724)  rrf#3(0.031)  structure_aware::HO-0304@03-24::010
      HO-0304 ed.03-24 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
   4. dense#1(0.784)  bm25#9(8.015)  rrf#4(0.031)  structure_aware::HO-0788@05-24::002  <-- GOLD
      HO-0788 ed.05-24 Clause 2: 2.3 Constant or repeated seepage or leakage means an escape of water that is continuous...
   5. dense#7(0.701)  bm25#3(9.012)  rrf#5(0.031)  structure_aware::HO-0304@09-23::010
      HO-0304 ed.09-23 Clause 3: | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or ...
answer quoted from: structure_aware::HO-0788@05-24::004
evidence: gold `structure_aware::HO-0788@05-24::002` at hybrid rank 4 [dense#1(0.784), bm25#9(8.015), rrf#4(0.031)]; top-3 = HO-0788@05-24 Clause 3, DP-0431@04-24 E-17, HO-0304@03-24 E-17
```

### G12 — After the ordinance or law increase endorsement, what is the cap on increased cost of construction?

Gold: `structure_aware::HO-0612@06-24::005` · known answer: $75,000 (up from $25,000 in the base wording).

**Verdict: unchanged (still a hit)**

`dense — BEFORE`

```
Q: After the ordinance or law increase endorsement, what is the cap on increased cost of construction?
mode=dense  gold=structure_aware::HO-0612@06-24::005  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
candidates (final order):
   1. dense#1(0.800)  structure_aware::HO-0612@06-24::005  <-- GOLD
      HO-0612 ed.06-24 Clause 1: | Increased cost of construction cap | $25,000 | $75,000 |
   2. dense#2(0.742)  structure_aware::HO-0612@06-24::001
      HO-0612 ed.06-24 Clause 1: The Ordinance or Law limit is increased from 10% of the Coverage A limit to 25% of the ...
   3. dense#3(0.739)  structure_aware::HO-0612@06-24::006
      HO-0612 ed.06-24 Clause 2: 2.3 Covered costs include the cost of bringing electrical, plumbing, and mechanical sys...
   4. dense#4(0.715)  structure_aware::HO-0612@06-24::000
      HO-0612 ed.06-24 Header: This endorsement increases the Ordinance or Law coverage provided under the HOMEOWNERS ...
   5. dense#5(0.698)  structure_aware::HO-0612@06-24::003
      HO-0612 ed.06-24 Clause 1: | Applies to demolition cost | Yes | Yes |
answer quoted from: structure_aware::HO-0612@06-24::005
evidence: gold at dense rank 1; quoted from it
```

`hybrid — AFTER`

```
Q: After the ordinance or law increase endorsement, what is the cap on increased cost of construction?
mode=hybrid  gold=structure_aware::HO-0612@06-24::005  gold_rank=1  hit@3=True  answer_ok=True  label=PASS (PASS)
candidates (final order):
   1. dense#1(0.800)  bm25#1(21.518)  rrf#1(0.033)  structure_aware::HO-0612@06-24::005  <-- GOLD
      HO-0612 ed.06-24 Clause 1: | Increased cost of construction cap | $25,000 | $75,000 |
   2. dense#3(0.739)  bm25#2(17.711)  rrf#2(0.032)  structure_aware::HO-0612@06-24::006
      HO-0612 ed.06-24 Clause 2: 2.3 Covered costs include the cost of bringing electrical, plumbing, and mechanical sys...
   3. dense#2(0.742)  bm25#5(14.081)  rrf#3(0.032)  structure_aware::HO-0612@06-24::001
      HO-0612 ed.06-24 Clause 1: The Ordinance or Law limit is increased from 10% of the Coverage A limit to 25% of the ...
   4. dense#4(0.715)  bm25#3(14.429)  rrf#4(0.031)  structure_aware::HO-0612@06-24::000
      HO-0612 ed.06-24 Header: This endorsement increases the Ordinance or Law coverage provided under the HOMEOWNERS ...
   5. dense#6(0.691)  bm25#6(13.114)  rrf#5(0.030)  structure_aware::HO-0612@06-24::011
      HO-0612 ed.06-24 Clause 4: 4.2 The insured must produce the written permit condition or code citation relied upon....
answer quoted from: structure_aware::HO-0612@06-24::005
evidence: gold at hybrid rank 1; quoted from it
```

