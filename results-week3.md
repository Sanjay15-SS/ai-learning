# Task Set D — Results

Insurance claims RAG. Two chunking strategies over the same 6 new endorsements, the same embedding model, and the same 8 known-answer questions.

- Embedding model: `BAAI/bge-small-en-v1.5` (384-dim bi-encoder) — **held fixed across both runs**, so the only variable is the chunker.
- Answering: extractive — the answer is quoted verbatim from the cited chunk, never composed by a model, so it cannot state anything the cited chunk does not.
- Vector database: **Chroma** (embedded), one collection per strategy, **HNSW** index in cosine space
- Retrieval: top-K = 5; `policy_line` filtering is executed by the database as a `where` clause, not post-filtered in Python

## 0. Scope of this ingest

**Only the 6 new endorsements were indexed.** The base homeowners policy wording library was not re-indexed and was not read by this pipeline. The endorsement drop is the unit of work; re-indexing the library would have spent the whole session on plumbing and produced no measurement.

| Strategy | Chunks | Of which single exclusion/table rows |
|---|---|---|
| `baseline` | 39 | 0 |
| `structure_aware` | 99 | 60 |

Per-form chunk counts (every chunk carries source_file, form_number, policy_line, edition_date):

| Form | `baseline` | `structure_aware` |
|---|---|---|
| DP-0431 | 4 | 11 |
| HO-0304 | 21 | 48 |
| HO-0455 | 3 | 14 |
| HO-0612 | 4 | 12 |
| HO-0788 | 4 | 5 |
| HO-2199 | 3 | 9 |

## 1. The 8 questions and their known-correct form + clause

Written from the endorsements before any search was run.

| # | Question | Gold form | Gold clause | Marker | Answer marker | From a table row |
|---|---|---|---|---|---|---|
| Q1 | Does exclusion E-17 apply to water damage from a burst supply line under HO-0304? | HO-0304 | Clause 3 | `E-17` | `burst supply line` | yes |
| Q2 | The dwelling was left vacant and the pipes froze. Is that loss excluded under HO-0304? | HO-0304 | Clause 3 | `E-18` | `maintain heat` | yes |
| Q3 | Is granule loss on a shingle roof covered, or is it treated as cosmetic damage? | HO-0455 | Clause 3 | `E-21` | `water-shedding` | yes |
| Q4 | Can the insured run a small home office and keep coverage under the home business exclusion? | HO-2199 | Clause 2 | `E-33` | `$10,000` | yes |
| Q5 | What percentage of replacement cost is paid for a 12-year-old asphalt shingle roof? | HO-0455 | Clause 2 | `60%` | `11 to 15 years` | yes |
| Q6 | What is the water damage deductible per occurrence under the limited water damage endorsement? | HO-0304 | Clause 1 | `$2,500` | `Water Damage Deductible` | yes |
| Q7 | How much ordinance or law coverage does the increased-amount endorsement provide? | HO-0612 | Clause 1 | `25%` | `Coverage A` | no |
| Q8 | How is 'sudden and accidental' defined for the purposes of these endorsements? | HO-0788 | Clause 2 | `unexpected and unintended` | `identifiable point in time` | no |

**Q1 known answer** — No. E-17 excludes seepage lasting 14 days or more, but carries an express exception for a sudden and accidental discharge including a burst supply line, provided the loss is reported within 30 days.

**Q2 known answer** — Excluded under E-18, unless the insured used reasonable care to maintain heat, or shut off the water supply and drained the system.

**Q3 known answer** — Excluded under E-21 as cosmetic damage that does not compromise the water-shedding function, unless the Cosmetic Damage Buy-Back is shown in the Declarations.

**Q4 known answer** — Yes. E-33 excludes business losses but excepts an incidental office occupancy with no employees and no customer visits where annual gross receipts do not exceed $10,000.

**Q5 known answer** — 60% - the 11 to 15 year band of the HO-0455 Payment Schedule.

**Q6 known answer** — $2,500 per occurrence, reduced to $1,000 where a licensed plumber's inspection report dated within 12 months of the loss is produced.

**Q7 known answer** — 25% of the Coverage A limit, up from 10% in the base wording, as additional insurance.

**Q8 known answer** — An event both unexpected and unintended from the insured's standpoint that begins at an identifiable point in time; a slow weep or drip is not sudden and accidental even if it later worsens abruptly.

## 2. Hit-in-top-5 — two strategies, same 8 questions

| Chunking strategy | Hit-in-top-5 | Hit-at-rank-1 | MRR |
|---|---|---|---|
| `baseline` | **8/8** | 6/8 | 0.812 |
| `structure_aware` | **8/8** | 5/8 | 0.792 |

Headline: `baseline` **8/8**, `structure_aware` **8/8**.

Hit-at-rank-1 and MRR are reported alongside because top-5 over a 39-chunk index is a soft test — 5 of 39 is a fifth of the whole corpus. Rank-1 is the number that reflects what a user actually reads.

Per-question record (rank at which the correct chunk was found, or MISS):

| # | Gold | `baseline` | `structure_aware` |
|---|---|---|---|
| Q1 | HO-0304 Clause 3 | hit @ rank 1 | hit @ rank 1 |
| Q2 | HO-0304 Clause 3 | hit @ rank 1 | hit @ rank 1 |
| Q3 | HO-0455 Clause 3 | hit @ rank 1 | hit @ rank 1 |
| Q4 | HO-2199 Clause 2 | hit @ rank 4 | hit @ rank 1 |
| Q5 | HO-0455 Clause 2 | hit @ rank 1 | hit @ rank 3 |
| Q6 | HO-0304 Clause 1 | hit @ rank 4 | hit @ rank 2 |
| Q7 | HO-0612 Clause 1 | hit @ rank 1 | hit @ rank 1 |
| Q8 | HO-0788 Clause 2 | hit @ rank 1 | hit @ rank 2 |

### Search-only dump, all 8 questions, both strategies

#### Q1 — Does exclusion E-17 apply to water damage from a burst supply line under HO-0304?

Gold: **HO-0304 Clause 3** (needs `E-17` AND `burst supply line` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.7893  HO-0304 (HO-3, ed.01-25)  Clause 3  `baseline::HO-0304@01-25::003`
   | E-16 | Water or waterborne material which backs up through sewers or drains, or which overflows or is discharged from a sump, sump pump, or related ...
2. score=0.7781  DP-0431 (DP-3, ed.04-24)  Clause 3  `baseline::DP-0431@04-24::002`
   humidity, moisture, or condensation, that occurs over a period of 7 days or more | All covered property | No exception. This exclusion applies whether...
3. score=0.7778  HO-0304 (HO-3, ed.09-23)  Clause 2  `baseline::HO-0304@09-23::002`
   the water escaped. We do not pay to repair or replace the system or appliance itself, except as provided in Clause 4.3. ## Clause 3 — Exclusions We do...
4. score=0.7764  HO-0304 (HO-3, ed.03-24)  Clause 3  `baseline::HO-0304@03-24::003`
   ws or is discharged from a sump, sump pump, or related equipment | All covered property | Does not apply where the Sump Overflow Buy-Back is shown in ...
5. score=0.7639  HO-0304 (HO-3, ed.01-25)  Clause 2  `baseline::HO-0304@01-25::002`
   ppliance itself, except as provided in Clause 4.3. ## Clause 3 — Exclusions We do not cover loss caused directly or indirectly by any of the following...
```

`structure_aware` — HIT at rank 1

```
1. score=0.8292  HO-0304 (HO-3, ed.09-23)  Clause 3  `structure_aware::HO-0304@09-23::010`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
2. score=0.8222  HO-0304 (HO-3, ed.01-25)  Clause 3  `structure_aware::HO-0304@01-25::010`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
3. score=0.8189  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::010`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
4. score=0.8007  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::012`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
5. score=0.7994  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::009`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
```

#### Q2 — The dwelling was left vacant and the pipes froze. Is that loss excluded under HO-0304?

Gold: **HO-0304 Clause 3** (needs `E-18` AND `maintain heat` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.7718  HO-0304 (HO-3, ed.01-25)  Clause 3  `baseline::HO-0304@01-25::004`
   f device was installed and operational at the time of loss | | E-18 | Freezing of a plumbing, heating, air conditioning, or automatic fire protective ...
2. score=0.7424  HO-0304 (HO-3, ed.03-24)  Clause 3  `baseline::HO-0304@03-24::004`
   e, while the dwelling is vacant, unoccupied, or under construction | Building and contents | Does not apply if the insured used reasonable care to mai...
3. score=0.7286  HO-0304 (HO-3, ed.03-24)  Clause 3  `baseline::HO-0304@03-24::003`
   ws or is discharged from a sump, sump pump, or related equipment | All covered property | Does not apply where the Sump Overflow Buy-Back is shown in ...
4. score=0.7272  HO-0304 (HO-3, ed.09-23)  Clause 3  `baseline::HO-0304@09-23::004`
   pliance, while the dwelling is vacant, unoccupied, or under construction | Building and contents | Does not apply if the insured used reasonable care ...
5. score=0.7271  HO-0304 (HO-3, ed.09-23)  Clause 2  `baseline::HO-0304@09-23::002`
   the water escaped. We do not pay to repair or replace the system or appliance itself, except as provided in Clause 4.3. ## Clause 3 — Exclusions We do...
```

`structure_aware` — HIT at rank 1

```
1. score=0.8142  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::011`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
2. score=0.8126  HO-0304 (HO-3, ed.09-23)  Clause 3  `structure_aware::HO-0304@09-23::011`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
3. score=0.8122  HO-0304 (HO-3, ed.01-25)  Clause 3  `structure_aware::HO-0304@01-25::011`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
4. score=0.7519  HO-0304 (HO-3, ed.01-25)  Clause 3  `structure_aware::HO-0304@01-25::010`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
5. score=0.7497  HO-0304 (HO-3, ed.03-24)  Clause 2  `structure_aware::HO-0304@03-24::005`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 2 — Coverage Grant We will pay for direct physical ...
```

#### Q3 — Is granule loss on a shingle roof covered, or is it treated as cosmetic damage?

Gold: **HO-0455 Clause 3** (needs `E-21` AND `water-shedding` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.7354  HO-0455 (HO-3, ed.01-24)  Clause 2  `baseline::HO-0455@01-24::001`
   11 to 15 years | 60% | 85% | | 16 to 20 years | 40% | 70% | | 21 to 25 years | 25% | 55% | | Over 25 years | 15% | 40% | Roof age is measured from the...
2. score=0.7166  HO-0455 (HO-3, ed.01-24)  Header  `baseline::HO-0455@01-24::000`
   # HO-0455 (ed. 01-24) — ROOF SURFACING — ACTUAL CASH VALUE LOSS SETTLEMENT Policy Line: HO-3 Homeowners | Edition Date: 01-24 | Effective: January 15,...
3. score=0.7044  HO-0455 (HO-3, ed.01-24)  Clause 3  `baseline::HO-0455@01-24::002`
   | E-23 | Loss to roof surfacing more than 30 years old at the date of loss | Roof surfacing only | None. Such roofs are ineligible and coverage is del...
4. score=0.6350  DP-0431 (DP-3, ed.04-24)  Clause 2  `baseline::DP-0431@04-24::001`
   pliance, is deleted in its entirety unless the Water Damage Buy-Back shown in the Declarations has been purchased. | Item | Amount | |---|---| | Water...
5. score=0.6199  HO-0304 (HO-3, ed.03-24)  Clause 1  `baseline::HO-0304@03-24::001`
   Annual aggregate | $30,000 | ## Clause 2 — Coverage Grant We will pay for direct physical loss to covered property caused by the sudden and accidental...
```

`structure_aware` — HIT at rank 1

```
1. score=0.7504  HO-0455 (HO-3, ed.01-24)  Clause 3  `structure_aware::HO-0455@01-24::009`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of lo...
2. score=0.7120  HO-0455 (HO-3, ed.01-24)  Clause 1  `structure_aware::HO-0455@01-24::001`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 1 — Loss Settlement Basis Loss to roof surfa...
3. score=0.6895  HO-0455 (HO-3, ed.01-24)  Clause 4  `structure_aware::HO-0455@01-24::013`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 4 — Conditions 4.1 Interior water damage res...
4. score=0.6765  HO-0455 (HO-3, ed.01-24)  Clause 3  `structure_aware::HO-0455@01-24::012`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of lo...
5. score=0.6746  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::007`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
```

#### Q4 — Can the insured run a small home office and keep coverage under the home business exclusion?

Gold: **HO-2199 Clause 2** (needs `E-33` AND `$10,000` in the same chunk)

`baseline` — HIT at rank 4

```
1. score=0.7281  HO-2199 (HO-3, ed.02-24)  Header  `baseline::HO-2199@02-24::000`
   # HO-2199 (ed. 02-24) — HOME-SHARING AND HOME BUSINESS EXCLUSION Policy Line: HO-3 Homeowners | Edition Date: 02-24 | Effective: February 1, 2024 This...
2. score=0.6981  HO-2199 (HO-3, ed.02-24)  Clause 2  `baseline::HO-2199@02-24::002`
   visits, where annual gross receipts do not exceed $10,000 | | E-34 | Loss to property held for rental to others, or to furnishings provided for the us...
3. score=0.6733  HO-0304 (HO-3, ed.03-24)  Clause 3  `baseline::HO-0304@03-24::004`
   e, while the dwelling is vacant, unoccupied, or under construction | Building and contents | Does not apply if the insured used reasonable care to mai...
4. score=0.6680  HO-2199 (HO-3, ed.02-24)  Clause 2  `baseline::HO-2199@02-24::001`
   a home-sharing occupancy | Building and contents | Does not apply to loss by fire, lightning, or explosion | | E-31 | Theft or mysterious disappearanc...
5. score=0.6674  HO-0304 (HO-3, ed.03-24)  Clause 1  `baseline::HO-0304@03-24::001`
   Annual aggregate | $30,000 | ## Clause 2 — Coverage Grant We will pay for direct physical loss to covered property caused by the sudden and accidental...
```

`structure_aware` — HIT at rank 1

```
1. score=0.7419  HO-2199 (HO-3, ed.02-24)  Clause 2  `structure_aware::HO-2199@02-24::005`
   Form HO-2199 (ed. 02-24) — Home-Sharing and Home Business Exclusion — Policy Line HO-3 — Clause 2 — Exclusions | Code | Excluded cause of loss | Appli...
2. score=0.7209  HO-2199 (HO-3, ed.02-24)  Clause 3  `structure_aware::HO-2199@02-24::007`
   Form HO-2199 (ed. 02-24) — Home-Sharing and Home Business Exclusion — Policy Line HO-3 — Clause 3 — Notice Requirement 3.1 The insured must notify us ...
3. score=0.7151  HO-2199 (HO-3, ed.02-24)  Header  `structure_aware::HO-2199@02-24::000`
   Form HO-2199 (ed. 02-24) — Home-Sharing and Home Business Exclusion — Policy Line HO-3 — Header # HO-2199 (ed. 02-24) — HOME-SHARING AND HOME BUSINESS...
4. score=0.7130  HO-2199 (HO-3, ed.02-24)  Clause 2  `structure_aware::HO-2199@02-24::002`
   Form HO-2199 (ed. 02-24) — Home-Sharing and Home Business Exclusion — Policy Line HO-3 — Clause 2 — Exclusions | Code | Excluded cause of loss | Appli...
5. score=0.7035  HO-2199 (HO-3, ed.02-24)  Clause 2  `structure_aware::HO-2199@02-24::004`
   Form HO-2199 (ed. 02-24) — Home-Sharing and Home Business Exclusion — Policy Line HO-3 — Clause 2 — Exclusions | Code | Excluded cause of loss | Appli...
```

#### Q5 — What percentage of replacement cost is paid for a 12-year-old asphalt shingle roof?

Gold: **HO-0455 Clause 2** (needs `60%` AND `11 to 15 years` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.7280  HO-0455 (HO-3, ed.01-24)  Header  `baseline::HO-0455@01-24::000`
   # HO-0455 (ed. 01-24) — ROOF SURFACING — ACTUAL CASH VALUE LOSS SETTLEMENT Policy Line: HO-3 Homeowners | Edition Date: 01-24 | Effective: January 15,...
2. score=0.6844  HO-0455 (HO-3, ed.01-24)  Clause 2  `baseline::HO-0455@01-24::001`
   11 to 15 years | 60% | 85% | | 16 to 20 years | 40% | 70% | | 21 to 25 years | 25% | 55% | | Over 25 years | 15% | 40% | Roof age is measured from the...
3. score=0.6780  HO-0455 (HO-3, ed.01-24)  Clause 3  `baseline::HO-0455@01-24::002`
   | E-23 | Loss to roof surfacing more than 30 years old at the date of loss | Roof surfacing only | None. Such roofs are ineligible and coverage is del...
4. score=0.6145  HO-0304 (HO-3, ed.03-24)  Clause 1  `baseline::HO-0304@03-24::001`
   Annual aggregate | $30,000 | ## Clause 2 — Coverage Grant We will pay for direct physical loss to covered property caused by the sudden and accidental...
5. score=0.6126  HO-0612 (HO-5, ed.06-24)  Clause 1  `baseline::HO-0612@06-24::001`
   onstruction cap | $25,000 | $75,000 | ## Clause 2 — Covered Costs 2.1 The increased amount in Clause 1 covers the increased cost to repair, rebuild, o...
```

`structure_aware` — HIT at rank 3

```
1. score=0.7174  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::004`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
2. score=0.7172  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::007`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
3. score=0.7156  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::005`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
4. score=0.7121  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::006`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
5. score=0.7097  HO-0455 (HO-3, ed.01-24)  Clause 2  `structure_aware::HO-0455@01-24::008`
   Form HO-0455 (ed. 01-24) — Roof Surfacing - Actual Cash Value Loss Settlement — Policy Line HO-3 — Clause 2 — Payment Schedule | Roof age at date of l...
```

#### Q6 — What is the water damage deductible per occurrence under the limited water damage endorsement?

Gold: **HO-0304 Clause 1** (needs `$2,500` AND `Water Damage Deductible` in the same chunk)

`baseline` — HIT at rank 4

```
1. score=0.8562  HO-0304 (HO-3, ed.09-23)  Clause 1  `baseline::HO-0304@09-23::001`
   is endorsement applies. | Item | Amount | |---|---| | Limited Water Damage Sublimit | $10,000 per occurrence | | Water Damage Deductible | $1,500 per ...
2. score=0.8313  DP-0431 (DP-3, ed.04-24)  Clause 2  `baseline::DP-0431@04-24::001`
   pliance, is deleted in its entirety unless the Water Damage Buy-Back shown in the Declarations has been purchased. | Item | Amount | |---|---| | Water...
3. score=0.8273  HO-0304 (HO-3, ed.09-23)  Clause 4  `baseline::HO-0304@09-23::005`
   insured must report any loss under this endorsement to us within 60 days of discovery. 4.2 Mitigation. The insured must take reasonable steps to prote...
4. score=0.8252  HO-0304 (HO-3, ed.03-24)  Header  `baseline::HO-0304@03-24::000`
   # HO-0304 (ed. 03-24) — WATER DAMAGE — LIMITED COVERAGE ENDORSEMENT Policy Line: HO-3 Homeowners | Edition Date: 03-24 | Effective: March 1, 2024 This...
5. score=0.8070  HO-0304 (HO-3, ed.03-24)  Clause 4  `baseline::HO-0304@03-24::006`
   nsed plumber's inspection report dated within 12 months before the date of loss is produced, the Water Damage Deductible in Clause 1 is reduced to $1,...
```

`structure_aware` — HIT at rank 2

```
1. score=0.8595  HO-0304 (HO-3, ed.09-23)  Clause 1  `structure_aware::HO-0304@09-23::003`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability | Item | Amount | | ...
2. score=0.8587  HO-0304 (HO-3, ed.01-25)  Clause 1  `structure_aware::HO-0304@01-25::003`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability | Item | Amount | | ...
3. score=0.8564  HO-0304 (HO-3, ed.03-24)  Clause 1  `structure_aware::HO-0304@03-24::003`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability | Item | Amount | | ...
4. score=0.8298  HO-0304 (HO-3, ed.01-25)  Clause 1  `structure_aware::HO-0304@01-25::002`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability | Item | Amount | | ...
5. score=0.8291  HO-0304 (HO-3, ed.09-23)  Clause 1  `structure_aware::HO-0304@09-23::002`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability | Item | Amount | | ...
```

#### Q7 — How much ordinance or law coverage does the increased-amount endorsement provide?

Gold: **HO-0612 Clause 1** (needs `25%` AND `Coverage A` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.8110  HO-0612 (HO-5, ed.06-24)  Header  `baseline::HO-0612@06-24::000`
   # HO-0612 (ed. 06-24) — ORDINANCE OR LAW — INCREASED AMOUNT OF COVERAGE Policy Line: HO-5 Homeowners | Edition Date: 06-24 | Effective: June 1, 2024 T...
2. score=0.7081  HO-0612 (HO-5, ed.06-24)  Clause 1  `baseline::HO-0612@06-24::001`
   onstruction cap | $25,000 | $75,000 | ## Clause 2 — Covered Costs 2.1 The increased amount in Clause 1 covers the increased cost to repair, rebuild, o...
3. score=0.7025  HO-0304 (HO-3, ed.09-23)  Clause 1  `baseline::HO-0304@09-23::001`
   is endorsement applies. | Item | Amount | |---|---| | Limited Water Damage Sublimit | $10,000 per occurrence | | Water Damage Deductible | $1,500 per ...
4. score=0.6999  HO-0304 (HO-3, ed.03-24)  Header  `baseline::HO-0304@03-24::000`
   # HO-0304 (ed. 03-24) — WATER DAMAGE — LIMITED COVERAGE ENDORSEMENT Policy Line: HO-3 Homeowners | Edition Date: 03-24 | Effective: March 1, 2024 This...
5. score=0.6859  HO-0304 (HO-3, ed.01-25)  Header  `baseline::HO-0304@01-25::000`
   # HO-0304 (ed. 01-25) — WATER DAMAGE — LIMITED COVERAGE ENDORSEMENT Policy Line: HO-3 Homeowners | Edition Date: 01-25 | Effective: January 1, 2025 Th...
```

`structure_aware` — HIT at rank 1

```
1. score=0.7968  HO-0612 (HO-5, ed.06-24)  Clause 1  `structure_aware::HO-0612@06-24::001`
   Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Clause 1 — Increased Limit The Ordinance or Law limit ...
2. score=0.7625  HO-0612 (HO-5, ed.06-24)  Clause 1  `structure_aware::HO-0612@06-24::005`
   Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Clause 1 — Increased Limit | Item | Base wording | As ...
3. score=0.7592  HO-0612 (HO-5, ed.06-24)  Header  `structure_aware::HO-0612@06-24::000`
   Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Header # HO-0612 (ed. 06-24) — ORDINANCE OR LAW — INCR...
4. score=0.7397  HO-0612 (HO-5, ed.06-24)  Clause 1  `structure_aware::HO-0612@06-24::002`
   Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Clause 1 — Increased Limit | Item | Base wording | As ...
5. score=0.7375  HO-0612 (HO-5, ed.06-24)  Clause 1  `structure_aware::HO-0612@06-24::004`
   Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Clause 1 — Increased Limit | Item | Base wording | As ...
```

#### Q8 — How is 'sudden and accidental' defined for the purposes of these endorsements?

Gold: **HO-0788 Clause 2** (needs `unexpected and unintended` AND `identifiable point in time` in the same chunk)

`baseline` — HIT at rank 1

```
1. score=0.8216  HO-0788 (HO-3, ed.05-24)  Header  `baseline::HO-0788@05-24::000`
   # HO-0788 (ed. 05-24) — DEFINITIONS AMENDMENT ENDORSEMENT Policy Line: HO-3 Homeowners | Edition Date: 05-24 | Effective: May 1, 2024 This endorsement...
2. score=0.7676  HO-0788 (HO-3, ed.05-24)  Clause 3  `baseline::HO-0788@05-24::003`
   exclusion in another endorsement carries an exception for a sudden and accidental discharge, that exception is read using the definition in Clause 2.1...
3. score=0.6407  HO-0304 (HO-3, ed.09-23)  Clause 1  `baseline::HO-0304@09-23::001`
   is endorsement applies. | Item | Amount | |---|---| | Limited Water Damage Sublimit | $10,000 per occurrence | | Water Damage Deductible | $1,500 per ...
4. score=0.6331  HO-0788 (HO-3, ed.05-24)  Clause 2  `baseline::HO-0788@05-24::001`
   n time. A discharge of water is sudden and accidental where the escape begins abruptly, regardless of how long the resulting water continues to flow b...
5. score=0.6322  HO-0304 (HO-3, ed.03-24)  Header  `baseline::HO-0304@03-24::000`
   # HO-0304 (ed. 03-24) — WATER DAMAGE — LIMITED COVERAGE ENDORSEMENT Policy Line: HO-3 Homeowners | Edition Date: 03-24 | Effective: March 1, 2024 This...
```

`structure_aware` — HIT at rank 2

```
1. score=0.7743  HO-0788 (HO-3, ed.05-24)  Clause 3  `structure_aware::HO-0788@05-24::004`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Clause 3 — Interaction With Exclusions 3.1 Where an exclusion in ano...
2. score=0.7233  HO-0788 (HO-3, ed.05-24)  Clause 2  `structure_aware::HO-0788@05-24::002`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Clause 2 — Amended Definitions 2.1 Sudden and accidental means an ev...
3. score=0.6324  HO-0788 (HO-3, ed.05-24)  Clause 1  `structure_aware::HO-0788@05-24::001`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Clause 1 — Scope The definitions in Clause 2 replace any conflicting...
4. score=0.6256  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::010`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
5. score=0.6174  HO-0788 (HO-3, ed.05-24)  Header  `structure_aware::HO-0788@05-24::000`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Header # HO-0788 (ed. 05-24) — DEFINITIONS AMENDMENT ENDORSEMENT Pol...
```

## 3. Metadata filter on policy_line

Query: *Does the seepage exclusion apply to water escaping from a burst supply line, and how many days does it take to trigger?*

Both the homeowners form (HO-0304) and the dwelling-fire form (DP-0431) carry an exclusion coded **E-17**, and they say opposite things: HO-0304 excepts a sudden and accidental burst supply line and triggers at 14 days, DP-0431 has no exception at all and triggers at 7 days. Unfiltered dense retrieval cannot tell which policy line the user means. The filter can.

**Unfiltered** (`structure_aware`, top-5):

```
1. score=0.7994  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::010`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
2. score=0.7971  HO-0304 (HO-3, ed.01-25)  Clause 3  `structure_aware::HO-0304@01-25::010`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
3. score=0.7963  DP-0431 (DP-3, ed.04-24)  Clause 3  `structure_aware::DP-0431@04-24::007`
   Form DP-0431 (ed. 04-24) — Dwelling Fire - Water Damage and Seepage Exclusion — Policy Line DP-3 — Clause 3 — Exclusions | Code | Excluded cause of lo...
4. score=0.7832  HO-0304 (HO-3, ed.09-23)  Clause 3  `structure_aware::HO-0304@09-23::010`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
5. score=0.7767  HO-0788 (HO-3, ed.05-24)  Clause 2  `structure_aware::HO-0788@05-24::002`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Clause 2 — Amended Definitions 2.1 Sudden and accidental means an ev...
```

**Filtered** on `policy_line == "HO-3"`:

```
1. score=0.7994  HO-0304 (HO-3, ed.03-24)  Clause 3  `structure_aware::HO-0304@03-24::010`
   Form HO-0304 (ed. 03-24) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
2. score=0.7971  HO-0304 (HO-3, ed.01-25)  Clause 3  `structure_aware::HO-0304@01-25::010`
   Form HO-0304 (ed. 01-25) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
3. score=0.7832  HO-0304 (HO-3, ed.09-23)  Clause 3  `structure_aware::HO-0304@09-23::010`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions | Code | Excluded cause of loss | Ap...
4. score=0.7767  HO-0788 (HO-3, ed.05-24)  Clause 2  `structure_aware::HO-0788@05-24::002`
   Form HO-0788 (ed. 05-24) — Definitions Amendment Endorsement — Policy Line HO-3 — Clause 2 — Amended Definitions 2.1 Sudden and accidental means an ev...
5. score=0.7305  HO-0304 (HO-3, ed.09-23)  Clause 2  `structure_aware::HO-0304@09-23::005`
   Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 2 — Coverage Grant We will pay for direct physical ...
```

Top-1 changed: **False** — `HO-0304` (`structure_aware::HO-0304@03-24::010`, score 0.7994) → `HO-0304` (`structure_aware::HO-0304@03-24::010`, score 0.7994).

## 4. Cited answers (3 answerable questions)

### Q1 — Does exclusion E-17 apply to water damage from a burst supply line under HO-0304?

**Refused:** False  |  **Top retrieval score:** 0.8292

**Answer:** | Code | Excluded cause of loss | Applies to | Exception |
| E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or condensation of humidity, moisture, or vapour, that occurs over a period of 21 days or more | All covered property | Does not apply to a sudden and accidental discharge, including a burst supply line |

(Per HO-0304 ed. 09-23, Clause 3, policy line HO-3.)

**Citations:**

- [`structure_aware::HO-0304@09-23::010`](#structure_awareho-0304@09-23010) — **HO-0304 Clause 3** — "| Code | Excluded cause of loss | Applies to | Exception |
| E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or condensation of humidity, moisture, or vapour, that occurs over a period of 21 days or more | All covered property | Does not apply to a sudden and accidental discharge, including a burst supply line |"

Each chunk_id links to appendix A, which reproduces the indexed chunk verbatim.

**Known-correct answer:** No. E-17 excludes seepage lasting 14 days or more, but carries an express exception for a sudden and accidental discharge including a burst supply line, provided the loss is reported within 30 days.

### Q6 — What is the water damage deductible per occurrence under the limited water damage endorsement?

**Refused:** False  |  **Top retrieval score:** 0.8595

**Answer:** | Item | Amount |
| Water Damage Deductible | $1,500 per occurrence |

(Per HO-0304 ed. 09-23, Clause 1, policy line HO-3.)

**Citations:**

- [`structure_aware::HO-0304@09-23::003`](#structure_awareho-0304@09-23003) — **HO-0304 Clause 1** — "| Item | Amount |
| Water Damage Deductible | $1,500 per occurrence |"

Each chunk_id links to appendix A, which reproduces the indexed chunk verbatim.

**Known-correct answer:** $2,500 per occurrence, reduced to $1,000 where a licensed plumber's inspection report dated within 12 months of the loss is produced.

### Q7 — How much ordinance or law coverage does the increased-amount endorsement provide?

**Refused:** False  |  **Top retrieval score:** 0.7968

**Answer:** The Ordinance or Law limit is increased from 10% of the Coverage A limit to 25% of the Coverage A limit. This increased amount is additional insurance and does not reduce the Coverage A limit.

(Per HO-0612 ed. 06-24, Clause 1, policy line HO-5.)

**Citations:**

- [`structure_aware::HO-0612@06-24::001`](#structure_awareho-0612@06-24001) — **HO-0612 Clause 1** — "The Ordinance or Law limit is increased from 10% of the Coverage A limit to 25% of the Coverage A limit. This increased amount is additional insurance and does not reduce the Coverage A limit."

Each chunk_id links to appendix A, which reproduces the indexed chunk verbatim.

**Known-correct answer:** 25% of the Coverage A limit, up from 10% in the base wording, as additional insurance.

## 5. Refusal transcripts (3 out-of-corpus questions)

### R1 — What is the reserve-setting threshold for claim CLM-2024-88431?

```
refused    : True
gate       : term_coverage
top_score  : 0.6929
answer     : I could not find this in the indexed endorsements, so I cannot answer it. Answering would mean inventing a coverage position.
reason     : Only 25% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: reserve-setting, threshold, clm-2024-88431. Refused without composing an answer.
citations  : []
```

Best chunks retrieved before the refusal:

```
1. score=0.6929  HO-0304  Clause 1  `structure_aware::HO-0304@01-25::002`
2. score=0.6923  HO-0304  Clause 1  `structure_aware::HO-0304@03-24::002`
3. score=0.6917  HO-0304  Clause 1  `structure_aware::HO-0304@01-25::004`
```

### R2 — Who is the assigned adjuster for policy HO-99213, and what is their direct phone number?

```
refused    : True
gate       : term_coverage
top_score  : 0.7034
answer     : I could not find this in the indexed endorsements, so I cannot answer it. Answering would mean inventing a coverage position.
reason     : Only 43% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: assigned, adjuster, ho-99213, phone. Refused without composing an answer.
citations  : []
```

Best chunks retrieved before the refusal:

```
1. score=0.7034  HO-2199  Header  `structure_aware::HO-2199@02-24::000`
2. score=0.7  HO-0304  Header  `structure_aware::HO-0304@01-25::000`
3. score=0.697  HO-0304  Header  `structure_aware::HO-0304@09-23::000`
```

### R3 — What is the current reinsurance attachment point for our homeowners book this treaty year?

```
refused    : True
gate       : term_coverage
top_score  : 0.7133
answer     : I could not find this in the indexed endorsements, so I cannot answer it. Answering would mean inventing a coverage position.
reason     : Only 50% of the question's content terms appear anywhere in the indexed endorsements (floor 55%). Absent entirely: reinsurance, attachment, book, treaty. Refused without composing an answer.
citations  : []
```

Best chunks retrieved before the refusal:

```
1. score=0.7133  HO-2199  Header  `structure_aware::HO-2199@02-24::000`
2. score=0.7002  HO-2199  Clause 4  `structure_aware::HO-2199@02-24::008`
3. score=0.679  HO-0304  Header  `structure_aware::HO-0304@01-25::000`
```

### 5.1 What actually gates the refusal

The obvious gate is a retrieval-score floor: if nothing scores above T, refuse. We measured whether such a T exists, and it does not.

| Question | Top-1 cosine | Term coverage | In corpus? |
|---|---|---|---|
| Q6 — What is the water damage deductible per occurrence under the limited water damage endorsement? | 0.8595 | 100% | yes |
| Q1 — Does exclusion E-17 apply to water damage from a burst supply line under HO-0304? | 0.8292 | 100% | yes |
| Q2 — The dwelling was left vacant and the pipes froze. Is that loss excluded under HO-0304? | 0.8142 | 62% | yes |
| Q7 — How much ordinance or law coverage does the increased-amount endorsement provide? | 0.7968 | 80% | yes |
| Q8 — How is 'sudden and accidental' defined for the purposes of these endorsements? | 0.7743 | 100% | yes |
| Q3 — Is granule loss on a shingle roof covered, or is it treated as cosmetic damage? | 0.7504 | 88% | yes |
| Q4 — Can the insured run a small home office and keep coverage under the home business exclusion? | 0.7419 | 78% | yes |
| Q5 — What percentage of replacement cost is paid for a 12-year-old asphalt shingle roof? | 0.7174 | 75% | yes |
| What is the current reinsurance attachment point for our homeowners book this treaty year? | 0.7133 | 50% | **no** |
| Who is the assigned adjuster for policy HO-99213, and what is their direct phone number? | 0.7034 | 43% | **no** |
| What is the reserve-setting threshold for claim CLM-2024-88431? | 0.6929 | 25% | **no** |

**Cosine cannot separate them.** Weakest in-corpus question: **0.7174**. Strongest out-of-corpus question: **0.7133**. A gap of 0.0041 of a cosine point — any threshold that refuses all three out-of-corpus questions is within a rounding error of rejecting a question the corpus can answer.

Diagnosis: cosine measures topical proximity, not whether the answer is present. "What is the reserve-setting threshold for claim CLM-2024-88431?" is *about* insurance claims, so it lands near insurance-claims text; the corpus simply has no reserve-setting rules in it. A bi-encoder cannot express that difference.

**Term coverage can.** Checking the question's content words against the indexed corpus separates cleanly: worst in-corpus **62%** versus best out-of-corpus **50%** — a margin of 12%, roughly 31x wider than the cosine gap. The gate is set at 55%. Terms like `reserve-setting`, `CLM-2024-88431`, `adjuster`, `reinsurance` and `treaty` appear nowhere in the six endorsements, and that absence is a fact about the corpus rather than a similarity score.

**The refusal is forced, not suggested.** There is no model deciding whether to be helpful: `generation.py` returns the refusal before any answer is composed. And the answer text, when there is one, is quoted verbatim from the cited chunk rather than written, so it cannot state anything the cited chunk does not.

Honest limitation: 55% is tuned against 11 questions on a 6-form corpus. It is a defensible gate at this scale, not a universal constant — a larger corpus would need it re-measured, and a question phrased entirely in policy vocabulary about a fact the corpus lacks would still slip past gate 1 to gate 2.

## 6. Bonus — precision wins retrieval, loses the answer

Question: *A supply line under the kitchen sink burst while the family was away for three weeks. The water ran the entire time and was only found when they got home. Is the loss covered under HO-0304?*

### `baseline`

Forms present in top-5: HO-0304

**Refused:** False

**Answer:** | E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or condensation of humidity, moisture, or vapour, that occurs over a period of 14 days or more, whether or not the seepage was known to any insured | All covered property, including the plumbing system itself | Does not apply to a sudden and accidental discharge as defined in HO-0788, including a burst supply line, provided the loss is reported within 30 days |

(Per HO-0304 ed. 03-24, Clause 3, policy line HO-3.)

- `baseline::HO-0304@03-24::003` — HO-0304 Clause 3

### `structure_aware`

Forms present in top-5: HO-0304

**Refused:** False

**Answer:** | Code | Excluded cause of loss | Applies to | Exception |
| E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or condensation of humidity, moisture, or vapour, that occurs over a period of 14 days or more, whether or not the seepage was known to any insured | All covered property, including the plumbing system itself | Does not apply to a sudden and accidental discharge as defined in HO-0788, including a burst supply line, provided the loss is reported within 14 days and an approved automatic water shut-off device was installed and operational at the time of loss |

(Per HO-0304 ed. 01-25, Clause 3, policy line HO-3.)

- `structure_aware::HO-0304@01-25::010` — HO-0304 Clause 3

## 7. Which chunker ships, and why

**`structure_aware` ships.** It scored 8/8 hit-in-top-5 against 8/8 for the baseline, and the gap is wider than that headline: 5/8 versus 6/8 at rank 1, MRR 0.792 versus 0.812. It won while being handicapped — it indexes 99 chunks against the baseline's 39, so a fixed top-5 is a materially harder test for it (5.1% of its corpus versus 12.8% of the baseline's). Correcting for that would widen the gap, not narrow it.

The mechanism is the one the task predicted. The baseline's 900-character window is blind to table structure, so it slices exclusion tables mid-row: the exclusion code lands in one chunk and the rule it scopes lands in the next. The structure-aware chunker emits one chunk per exclusion row, each stamped with its form number, edition date, policy line, clause and the table's own header row, so a row is never separated from what scopes it.

### The retrieval that embarrassed us

**Q1, baseline, rank 1: the wrong policy line.** Asked whether E-17 excludes a burst supply line *under HO-0304*, the baseline index returned `HO-0304` — a **HO-3 dwelling-fire form** — at rank 1 with score 0.7893, ahead of the correct `DP-0431` chunk at 0.7781. DP-0431's E-17 is not a near-miss, it is the inverse rule: it triggers at 7 days instead of 14 and carries **no sudden-and-accidental exception at all**. A claims handler reading top-1 would have denied a covered burst-pipe claim.

The filter demo in section 3 is the same wound: DP-0431 takes top-1 by **0.0000** — a few ten-thousandths of a cosine point. Nothing about the embedding separates these two forms, because textually they are near-identical; the only thing that separates them is the `policy_line` metadata. That is the argument for filtering rather than for a better embedding model.

**Q2, baseline: a miss that no amount of top-K would fix.** The baseline returned a chunk holding the E-18 *rule* without the code at rank 1, and a chunk holding the *code* without the rule at rank 2. We then checked the whole index: chunks carrying both `E-18` and "maintain heat" — baseline: **1**; structure-aware: **3** (structure_aware::HO-0304@01-25::011, structure_aware::HO-0304@03-24::011, structure_aware::HO-0304@09-23::011). The E-18 row is split across a chunk boundary, so the answer does not exist in the baseline index as a single retrievable unit. Raising top-K to 25 would not have found it. This is the failure we would never have seen by eyeballing retrieved text and calling it 'looks about right'.

### What the structure-aware chunker costs

It is not free. 2 question(s) got *worse*: Q5 (rank 1 → 3), Q8 (rank 1 → 2). Splitting a table into one chunk per row means the rows of a rate schedule now compete with each other for the same query — the 11-to-15-year band no longer arrives inside a chunk that shows the whole schedule, so its lone row is a weaker match than the baseline's fat chunk containing every band at once. Precision on exclusion rows was bought with recall on continuous tables.

**Q5 is the sharpest version of that cost, and it is the retrieval that embarrassed us twice.** Asked for the payout on a *12-year-old* asphalt roof, the structure-aware index returns five sibling rows of the same payment schedule, spanning only 0.0076 of a cosine point:

```
1. score=0.7174  | 6 to 10 years | 80% | 95% |
2. score=0.7172  | 21 to 25 years | 25% | 55% |
3. score=0.7156  | 11 to 15 years | 60% | 85% |
4. score=0.7121  | 16 to 20 years | 40% | 70% |
5. score=0.7097  | Over 25 years | 15% | 40% |
```

The gold row (`11 to 15 years | 60%`) lands at rank 3, behind `6 to 10 years | 80%`. The embedding has nothing to work with: once a row is severed from its schedule, `| 6 to 10 years | 80% | 95% |` and `| 11 to 15 years | 60% | 85% |` are near-identical strings of digits, and no bi-encoder maps "12-year-old" onto the arithmetic band that contains 12. Answering Q5 extractively from rank 1 would have confidently quoted **80%** — the wrong payout on a real claim. That is why Q5 is not one of the three questions taken through to generation in section 4, and why it is written up here instead of quietly dropped.

The fix is not a better embedding, it is a chunking rule: a rate schedule is one answerable unit and must not be split per row, whereas an exclusions table must be. Same document, opposite treatment, decided by what the table *is*.

It also grows the index: 39 chunks → 99, of which 60 are single table rows. At six endorsements that is free. Across a full wording library it is the cost to watch.

**Next change, not made today:** keep the per-row chunks for exclusion tables and stop splitting per row for rate schedules, where the whole table is the answerable unit. That is one variable and it gets measured on its own run.

## Appendix A — cited chunks resolved

Every chunk_id cited in section 4, fetched back out of the index by id and reproduced verbatim.

<a id="structure_awareho-0304@09-23010"></a>

### `structure_aware::HO-0304@09-23::010`

- source_file: `HO-0304_ed09-23_water-damage-limited.md`
- form_number: `HO-0304`  ·  policy_line: `HO-3`  ·  edition_date: `09-23`  ·  clause: `Clause 3`

```
Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 3 — Exclusions

| Code | Excluded cause of loss | Applies to | Exception |
| E-17 | Constant or repeated seepage or leakage of water or steam, or the presence or condensation of humidity, moisture, or vapour, that occurs over a period of 21 days or more | All covered property | Does not apply to a sudden and accidental discharge, including a burst supply line |
```

<a id="structure_awareho-0304@09-23003"></a>

### `structure_aware::HO-0304@09-23::003`

- source_file: `HO-0304_ed09-23_water-damage-limited.md`
- form_number: `HO-0304`  ·  policy_line: `HO-3`  ·  edition_date: `09-23`  ·  clause: `Clause 1`

```
Form HO-0304 (ed. 09-23) — Water Damage - Limited Coverage Endorsement — Policy Line HO-3 — Clause 1 — Schedule and Applicability

| Item | Amount |
| Water Damage Deductible | $1,500 per occurrence |
```

<a id="structure_awareho-0612@06-24001"></a>

### `structure_aware::HO-0612@06-24::001`

- source_file: `HO-0612_ed06-24_ordinance-or-law.md`
- form_number: `HO-0612`  ·  policy_line: `HO-5`  ·  edition_date: `06-24`  ·  clause: `Clause 1`

```
Form HO-0612 (ed. 06-24) — Ordinance or Law - Increased Amount of Coverage — Policy Line HO-5 — Clause 1 — Increased Limit

The Ordinance or Law limit is increased from 10% of the Coverage A limit to 25% of the Coverage A limit. This increased amount is additional insurance and does not reduce the Coverage A limit.
```

