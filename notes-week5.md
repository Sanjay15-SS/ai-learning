# Week 5 — reading notes

Everything behind `taxonomy.md`: how the sample was drawn, the 20 verbatim open-coding
sentences, the replay evidence, the redaction scan, the prediction, the benchmark note,
and the demo-set comparison.

## 1. The population, and how the 20 were drawn

117 desk traces in `traces/traces.jsonl`, one JSON line per answered question, written
by `assistant.py` while it ran the 117 file-note questions in `questions.py`. Zero
errors. The questions were written before anything ran and carry no expected answers,
so nothing about the mix was steered toward failures I already knew about.

Seed: **20250907**. Reproduce the exact 20 with:

```bash
python3 sample.py --seed 20250907 --n 20
```

`sample.py` sorts trace ids before sampling, so the order lines happen to sit in the
file cannot affect the draw.

| # | trace_id | qid | question (as stored, redacted) |
|---|---|---|---|
| 1 | `trc_1eb67415c3a0` | D010 | Does HO-0304 pay to replace the failed section of pipe itself? |
| 2 | `trc_48a13e67c68b` | D076 | Furniture bought specifically for the rental guests was damaged. Covered? |
| 3 | `trc_4dabae102986` | D056 | How much ordinance or law coverage does the increased-amount endorsement provide? |
| 4 | `trc_53f7f9f70e8d` | D003 | What is the seepage trigger period for E-17 on the 09-23 edition of HO-0304? |
| 5 | `trc_62e693b1e25b` | D004 | Under HO-0304 ed. 01-25, does the E-17 burst supply line exception still apply if no shut-off device was installed? |
| 6 | `trc_77b4a3dca5a8` | D026 | House under renovation, utilities on, nobody living there. Is that vacant? |
| 7 | `trc_79c838a19c66` | D093 | Two different editions of HO-0304 are in the file. How do I tell which one is on risk? |
| 8 | `trc_83e0cb0f881d` | D032 | Water damage deductible on DP-0431? |
| 9 | `trc_84c1e896e601` | D103 | Is there any appraisal clause in these endorsements? |
| 10 | `trc_88aa35e78eba` | D079 | What is the home-sharing surcharge? |
| 11 | `trc_8ccacd62478f` | D033 | DP-0431 ed. 04-24 E-17 - is there any sudden and accidental exception on the dwelling fire form? |
| 12 | `trc_8d9cc7750201` | D100 | What is the reserve-setting threshold for a water loss of this size? |
| 13 | `trc_947eeaeb679c` | D087 | Escape started suddenly, insured could not reasonably have known, found after 40 days. Seepage exclusion or the definitions clause? |
| 14 | `trc_d5c99631e98e` | D042 | Metal roof, 18 years old, windstorm. What is the ACV factor? |
| 15 | `trc_d6a10501f0b5` | D054 | Is the deductible taken before or after the ACV factor? |
| 16 | `trc_df27c2e52388` | D067 | Do we pay to upgrade beyond the minimum the code requires if the contractor recommends it? |
| 17 | `trc_e64d09501f72` | D052 | Water got in through the storm-damaged roof and ruined the ceiling. Is the ceiling on ACV too? |
| 18 | `trc_e9474dbae5dd` | D117 | Roof work done 100 days before the loss by an unlicensed contractor. Does E-24 apply? |
| 19 | `trc_ec0160ef5eef` | D073 | Laptop went missing the morning after the short-term guest checked out. Covered? |
| 20 | `trc_edb87d154d7f` | D040 | Client asks why the dwelling fire wording is harsher than the homeowners one on seepage. |

## 2. Open coding — one sentence per trace, what I saw

Written while reading, before any grouping existed. No fix was applied at any point
during this pass: the answering pipeline is the one that wrote the traces, which
`replay.py` confirms by refusing to run when the corpus or policy sha has moved.

1. `trc_1eb67415c3a0` — Quoted HO-0304 Clause 2 saying we do not pay to replace the failed appliance *"except as provided in Clause 4.3"*, and never produced Clause 4.3, which is the $2,000 the insured is owed.
2. `trc_48a13e67c68b` — Refused at coverage 0.429 on the words `furniture`, `bought`, `specifically`, `guests`, with E-34 — the clause that answers it — sitting at rank 1.
3. `trc_4dabae102986` — Answered 25% of Coverage A from HO-0612 Clause 1 and said the amount is additional insurance.
4. `trc_53f7f9f70e8d` — Asked about the **09-23** edition and quoted the **03-24** row, giving a 14 day seepage trigger where the edition named says 21, with the right row at rank 2 and 0.0008 behind.
5. `trc_62e693b1e25b` — Quoted the 01-25 E-17 row for a question naming ed. 01-25, carrying both the 14 day report and the shut-off device condition.
6. `trc_77b4a3dca5a8` — Quoted HO-0788 clause 2.4, which says a dwelling under active renovation with utilities connected is not vacant.
7. `trc_79c838a19c66` — Refused a question about telling which edition is on risk, which the endorsements genuinely do not answer because that lives in the Declarations.
8. `trc_83e0cb0f881d` — Gave $5,000 per occurrence from the DP-0431 schedule with the column header attached.
9. `trc_84c1e896e601` — Answered "is there any appraisal clause" with the HO-0788 clause about definitions applying to attached endorsements, at coverage 0.75 with `appraisal` the single missing term.
10. `trc_88aa35e78eba` — Gave the 18% home-sharing surcharge from HO-2199 Clause 4.
11. `trc_8ccacd62478f` — Quoted the DP-0431 E-17 row including *"No exception"*, which is the answer to a question that asked whether there is one.
12. `trc_8d9cc7750201` — Refused a reserve-setting question at coverage 0.4; nothing in the six endorsements sets reserves.
13. `trc_947eeaeb679c` — Quoted HO-0788 clause 3.2, the clause that governs an escape that begins suddenly and is found after the seepage period.
14. `trc_d5c99631e98e` — Asked for the ACV factor on an 18 year old metal roof and quoted the rule that says apply the Payment Schedule, while the "16 to 20 years" row holding 70% was not among the three retrieved.
15. `trc_d6a10501f0b5` — Asked whether the deductible comes before or after the ACV factor and answered from HO-0304's inspection credit, a different form, a different deductible, and a different number.
16. `trc_df27c2e52388` — Refused at coverage 0.286 on a code-upgrade question that HO-0612 clause 4.2 answers, and the three chunks retrieved were HO-0304 water damage rather than HO-0612.
17. `trc_e64d09501f72` — Refused at coverage 0.429 while HO-0455 clause 4.1, which puts interior water damage on replacement cost, sat at rank 2.
18. `trc_e9474dbae5dd` — Quoted the E-24 row for a loss 100 days after roof work, giving the reader both the 90 day window and the licensed-contractor exception.
19. `trc_ec0160ef5eef` — Refused a theft-after-guest-checkout question at coverage 0.444, with E-31 — which covers exactly the 24 hours after an occupancy ends — nowhere in the three retrieved, all of which were HO-0304 water damage.
20. `trc_edb87d154d7f` — Answered a question about why the dwelling fire seepage wording is harsher with the DP-0431 header, which only says the form does not apply to homeowners policies.

### Where each sentence landed

| Mode | Traces |
|---|---|
| 1 — refused on vocabulary, answer was in context | 2, 16, 17, 19 |
| 2 — corpus silent, answered anyway from rank 1 | 9, 20 |
| 3 — wrong edition of the right form | 4 |
| 4 — wrong form entirely | 15 |
| 5 — general rule instead of the figure | 14 |
| clean | 1, 3, 5, 6, 7, 8, 10, 11, 12, 13, 18 |

Traces 7 and 12 fired the same gate as trace 2 but the corpus really is silent on both,
so the refusal was right. I did not count either as a failure, and I am flagging it
because counting them would have doubled mode 1 for free.

## 3. Replay evidence

The trace to replay was drawn with a second seed so it could not be picked after the
reading:

```bash
python3 sample.py --replay-pick     # seed 20250907 + 1 -> trc_5c105be74703
python3 replay.py trc_5c105be74703
```

`replay.py` reaches into nothing live. It takes the chunk ids off the trace and resolves
them in the pinned corpus, takes the policy by its recorded version id, and takes the
retrieval order off the trace. The question is never re-embedded and the index is never
searched. It refuses to run at all if the corpus fingerprint or the policy sha has moved.

Question: *Two separate water losses four days apart. One deductible or two?*

| field | value from the trace |
|---|---|
| retriever / k | hybrid / 3 |
| chunks + scores | `HO-0304@01-25::003` 0.0310, `DP-0431@04-24::010` 0.0310, `HO-0304@01-25::014` 0.0309 |
| policy | `claims-extractive-v1`, sha `70a289f254db` — matched |
| corpus | sha `9b8a6bebfcbe`, 99 chunks — matched |

Original and replayed are the same refusal, byte for byte, across all five compared
fields: `refused`, `gate`, `citation`, `quote` and `answer text`.

**The honest caveat**: the seeded draw landed on a refusal, which exercises the gate
path and not the quoting path. Rather than draw again until I got a nicer trace, I
replayed **every** trace in both files under the same rules:

```
replayed 127 traces from the trace alone: 127 byte-identical, 0 diverged
```

So the quoting path is covered, and the seeded pick stays the one the seed chose. This
app has no model in it, so byte-identical replay is available here in a way it would
not be behind a sampling API. What a trace can promise is that the same inputs produce
the same determination, the same citation and the same words, and here it delivers all
three.

## 4. Redaction

Claimant names, claim numbers, policy numbers, phones, emails and street addresses are
removed inside `TraceWriter.write()` **before** `json.dumps` is called, so an identifier
never exists in the trace file at any point. This is not a cleanup pass over an
already-written file, and there is no function in `redact.py` that opens one.

The writer re-scans the serialised line and **raises rather than appending** if a
structured identifier survived. `selftest.py` proves that by breaking the name pattern
deliberately and checking that nothing was written.

Scan of the finished files:

```
traces/traces.jsonl  117 lines  residual patterns: []  literal identifiers: []
traces/demo.jsonl     10 lines  residual patterns: []  literal identifiers: []
```

Five of the 117 desk traces carried something to remove: two names, three policy
numbers, two claim numbers, three phone occurrences. The counts are higher than the
question text alone would suggest because a claim number also lands in
`gates.missing_terms`, which is a different field of the same record. That is the point
of sweeping every field rather than the question string.

The hard half is what must **survive**. `HO-0304`, `E-17`, `03-24`, `$15,000`, `14 days`
and `Clause 3` are all identifier-shaped and all load-bearing. A policy number is told
from a form number by digit count — five or more against four — and the stoplist that
protects policy vocabulary is derived from the corpus itself rather than typed by hand,
so a new endorsement protects its own wording the moment it is dropped into `data/`.
`selftest.py` checks nine of these keep-cases; the one that would have bitten is
`"Water Backup and Sump Discharge Coverage"`, four capitalised words in a row that a
naive two-word name rule turns into `[NAME] Coverage`.

## 5. The prediction

`PREDICTION.md`, written 2026-09-07 after the reading and before any edit.
sha256 `e9fb07bdd5bbead2f618b19282d277a0844671d049588afc163eb4f77893cf55`.

In one line: drop `COVERAGE_FLOOR` from 0.55 to 0.35 and expect term-coverage refusals
to fall 25/117 → 7/117, at least 7 of the 18 released questions to come back correctly
cited, at most 12 unsupported, and all four genuinely out-of-corpus questions to stop
refusing and start answering — which is why I expect to conclude **do not ship**.

This folder is not a git repository, so ordering rests on the file timestamps and on
that hash being recorded in `results-week5.md` at the time. Said plainly rather than
dressed up as a commit.

## 6. Why a public benchmark would have missed four of the five modes

Modes 1 and 2 are two faces of a gate that is **in my own code** and set to a number I
chose. No public retrieval benchmark ships with my 0.55 in it, and neither mode is
visible from the ranked list at all: mode 1 refuses with the right chunk at rank 1, and
mode 2 answers with a chunk any relevance judgement would score as topical.

Mode 4 is a retrieval miss and is the one a hit-rate would have caught. Mode 5 is
half-caught: the schedule row was not retrieved, but what makes it a failure is that
the chunk which *was* retrieved is genuinely relevant — it is the rule about the table
— and a relevance metric would score it as a hit.

Mode 3 is the one no general benchmark could encode at any threshold. `HO-0304@09-23`,
`@03-24` and `@01-25` are three editions of one form whose E-17 rows differ by a single
number, 21 days against 14. They are near-identical text, they retrieve within 0.0008
of each other, and every one of them is topically perfect. Which is correct depends on
which edition is attached to the policy, and that is a fact about this endorsement pack
that no general corpus contains.

## 7. Bonus — the demo set, and what we have been telling ourselves

The 10 questions we bring to the monthly review, in `questions.DEMO_SET`, run through
the same pipeline into `traces/demo.jsonl` and were open-coded the same way.

**Ten of ten clean. Not one refusal.**

| | random sample of 20 | demo set of 10 |
|---|---|---|
| top mode — refused while the answer was in context | 4 of 20 = **20%** | 0 of 10 = **0%** |
| any failure at all | 9 of 20 = **45%** | 0 of 10 = **0%** |
| refusals | 6 of 20 | 0 of 10 |

### The paragraph

Every demo question names its form. Eight of the ten name a form number outright, and
the answer to each lives in one self-contained chunk that retrieves at or near rank 1:
the $15,000 sublimit, the $2,500 deductible, the 60% row, the "None" in the E-22
exception column. Because they name the form, their vocabulary is the corpus's own
vocabulary, and the coverage gate they have to clear is a gate they were always going
to clear. We did not pick them to flatter the app. We picked them because they are the
ones that demo well, and what makes a question demo well is exactly the property that
makes this app work. Then we read 100% back to ourselves as a hit rate. The random draw
says the desk sees 45% failures, and the gap is not the model struggling on harder
questions — there is no model. It is that a real file note says "laptop" and "ceiling"
and "furniture", it names a loss rather than a form, and it asks about the 09-23 edition
by name. None of that is in the demo set. The uncomfortable part is that the demo set is
not wrong about the app: it is an accurate picture of the app on ten questions we chose.
That is precisely why nobody noticed. What we have been saying is that we tested it.
What we did was show it.

## 8. Caveats I would put in the ticket

- Twenty traces. One trace moves any frequency by 5 points. Modes 3, 4 and 5 are one
  trace each; they are real, but their ordering against each other is not settled by
  this sample.
- Mode 1 is the only count I checked against the whole file. Term-coverage refusals run
  at **25/117 = 21%** there against 4/20 = 20% in the sample, which is close enough to
  trust. Modes 2 to 5 are sample-only and are not extrapolated.
- I judged correctness myself, against the six endorsements, with no second reader.
  **Trace 1 and trace 20 were the two closest calls.** Trace 1 quotes a clause that
  names the carve-out it does not produce, which I read as a fair verbatim answer that
  points the reader onward; trace 20 answers a "why" question the corpus cannot really
  explain, which I read as a failure because the answer given is about applicability
  rather than seepage. Moving trace 1 into the failure column takes the count to 10 of
  20 and gives mode 5 a second member.
- The traffic is my own writing. It is not a real desk log, and if adjusters phrase
  things differently the mix of modes moves with them. What it is not is tuned: it was
  written before the first run, and D050, D065, D080 and D115 are all questions I
  expected to work and which do not.
- The app traced is the shipped one, which uses `hybrid_search` even though Week 4
  measured dense as the better retriever on hit-rate@3 and recommended not shipping it.
  I did not change it. A taxonomy is only about the app it was read from.
- The corpus itself is a reconstruction; two of the eight source files were rebuilt from
  the surviving records, as `RECONSTRUCTION.md` sets out. Mode 3 turns on the three
  HO-0304 editions being near-identical, and two of those three are rebuilt files. The
  mode is real — the app reads rank 1 and the editions tie — but its exact 0.0008 margin
  is not evidence about the original pack.
