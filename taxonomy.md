# Week 5 — failure taxonomy

Twenty traces drawn at random from 117, read by hand, no fixes applied. **11 of 20
clean, 9 of 20 failed, 5 named modes.** Every mode below changes what an adjuster
would do with the file.

The manager's version of this is "it refuses too much and sometimes cites the wrong
thing". The reading turns that into eight wrong denials or non-answers and one
answer taken off the wrong form, each with a trace id against it.

| # | Failure mode | Count | % of 20 | Severity |
|---|---|---|---|---|
| 1 | Refuses on the question's vocabulary while the answering clause is in the retrieved context | 4 | 20% | wrongly denies |
| 2 | Answers a question the corpus is silent on, quoting an unrelated clause instead of refusing | 2 | 10% | misleads |
| 3 | Answers from the wrong edition of the right form | 1 | 5% | wrongly denies |
| 4 | Answers from the wrong form entirely | 1 | 5% | **wrongly pays** |
| 5 | Quotes the general rule when the question asked for the figure | 1 | 5% | wrong payment |

---

## 1. Refuses on the question's vocabulary while the answering clause is in the retrieved context

**4 of 20 · 20% · wrongly denies**

The term-coverage gate takes the content words of the question, drops stopwords, and
refuses if fewer than 55% of what is left appears anywhere in the endorsements. It runs
before retrieval is consulted and it never looks at what came back. An adjuster who
writes "laptop", "furniture", "ceiling" or "upgrade" is writing about the world, not
about the wording, and the gate reads that as a question the corpus cannot answer.

Example — `trc_48a13e67c68b` (D076):

> Furniture bought specifically for the rental guests was damaged. Covered?

Refused at coverage 0.429, on `furniture`, `bought`, `specifically`, `guests`. Rank 1
was `HO-2199@02-24::006`, which is E-34: *"Loss to property held for rental to others,
or to furnishings provided for the use of a home-sharing guest | Personal property only
| None"*. That is the answer, and it was sitting in the context the gate refused over.

Second example — `trc_e64d09501f72` (D052), "is the ceiling on ACV too?", refused at
0.429 while `HO-0455@01-24::013` sat at rank 2 carrying Clause 4.1: interior water
damage from a covered roof loss is settled on **replacement cost** and is not subject
to the ACV schedule. The refusal denies the insured a broader settlement basis than
the one they asked about.

In the other two, `trc_df27c2e52388` (D067) and `trc_ec0160ef5eef` (D073), the gate
refused **and** the retriever had already gone to the wrong form, so the answering
clause was not in context either. Same gate, two different repairs behind it.

Also in: `trc_df27c2e52388`, `trc_ec0160ef5eef`.

---

## 2. Answers a question the corpus is silent on, quoting an unrelated clause instead of refusing

**2 of 20 · 10% · misleads**

The mirror image of mode 1, and it comes from the same gate. Coverage is a **ratio**,
so a question whose one decisive term is missing still clears 0.55 on the strength of
its ordinary words, and the app then answers from whatever rank 1 happened to be.

Example — `trc_84c1e896e601` (D103):

> Is there any appraisal clause in these endorsements?

Coverage 0.75, missing exactly one term: `appraisal`. There is no appraisal clause
anywhere in the six endorsements, so the correct output is a refusal. Instead it
answered with `HO-0788@05-24::001`, the clause about definitions applying to attached
endorsements, presented in the usual "(Per HO-0788 ed. 05-24, Clause 1)" format that
everything correct also arrives in.

`trc_edb87d154d7f` (D040) asks why the dwelling fire wording is harsher on seepage and
gets the DP-0431 header, which says the endorsement does not apply to homeowners
policies. The corpus does hold the substantive difference — 7 days on DP-0431 against
14 on HO-0304 — and the answer goes nowhere near it.

The severity here is quieter than a wrong denial and worse in one way: the output is
indistinguishable in form from a correct answer, so nothing prompts the reader to check.

---

## 3. Answers from the wrong edition of the right form

**1 of 20 · 5% · wrongly denies**

Example — `trc_53f7f9f70e8d` (D003):

> What is the seepage trigger period for E-17 on the **09-23** edition of HO-0304?

All three editions of the E-17 row came back, at 0.0323, 0.0323 and 0.0315. The two
leaders are tied to four decimal places. The answer step reads rank 1 only, so it
quoted **ed. 03-24** and returned a **14 day** trigger. The 09-23 row, at rank 2, says
**21 days**.

On a loss discovered at day 16 that is the whole file: excluded on the number given,
covered on the number asked for. The edition was named in the question and the trace
shows the right chunk one line below the one that was read.

---

## 4. Answers from the wrong form entirely

**1 of 20 · 5% · wrongly pays**

Example — `trc_d6a10501f0b5` (D054):

> Is the deductible taken before or after the ACV factor?

This is an HO-0455 roof question, and Clause 1 of that form settles it: actual cash
value is the schedule applied to replacement cost, *"less the applicable deductible"*.
Not one HO-0455 chunk reached the top 3. All three were HO-0304 water damage
conditions, and the answer came from Clause 4.4: the **inspection credit** that reduces
the *water damage* deductible to $1,000.

An adjuster who applies that to a roof claim applies a deductible that does not exist
on this loss, and applies it at a quarter of the real figure. This is the one mode in
the sample that pays money it should not.

---

## 5. Quotes the general rule when the question asked for the figure

**1 of 20 · 5% · wrong payment**

Example — `trc_d5c99631e98e` (D042):

> Metal roof, 18 years old, windstorm. What is the ACV factor?

The answer is 70%, in the "16 to 20 years" row of the HO-0455 payment schedule. That
row never reached the top 3. The answer quoted Clause 1, which says actual cash value
is *"determined by applying the Payment Schedule in Clause 2"* — the rule that points
at the table, not the number in it.

The adjuster is handed a pointer and left to pick a row unaided. Six rows differ by as
much as 85 percentage points, so picking one by eye is not a small risk.

---

## The clean eleven

`trc_1eb67415c3a0`, `trc_4dabae102986`, `trc_62e693b1e25b`, `trc_77b4a3dca5a8`,
`trc_79c838a19c66`, `trc_83e0cb0f881d`, `trc_88aa35e78eba`, `trc_8ccacd62478f`,
`trc_8d9cc7750201`, `trc_947eeaeb679c`, `trc_e9474dbae5dd`.

Two of those are close calls and are argued in `notes-week5.md` §8. Moving either takes
the failure count to 10 of 20.

---

Method, seed, the 20 verbatim observation sentences, the replay evidence, the redaction
scan and the demo-set comparison: **[`notes-week5.md`](notes-week5.md)**.
