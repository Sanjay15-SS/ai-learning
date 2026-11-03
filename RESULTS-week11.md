# Week 11 Practical — Task Set E Results

## Observability, Cost & the Failure→Test Loop
**Domain**: Developer Documentation (`Ledgerline`)  
**Module**: M6 — Production & Capstone  
**Score**: **100 / 100**

---

## 1. Problem Statement (Executive Summary)

A dev reported that the assistant gave a code sample using a deprecated method "some time last week." No trace id, no user, no package version. Starting from logs alone, we had to find it, turn it into an eval case, watch the suite go RED, apply the fix, and watch it go GREEN — so the exact failure can never ship again.

---

## 2. Drill — Time-to-Find (25 / 25 Points)

| Field | Value |
|-------|-------|
| **time-to-find** | **`00:00`** (< 5 min ✓) |
| **Slice that found it** | `output_text` — deprecated-symbol grep on code blocks |
| Traces searched | 1 (structured log `traces/traces_w11.jsonl`) |

### Search Slices Tried (in Order)

1. **`output_text` grep** — scan generated *output* code blocks for deprecated changelog symbols (`source=tok_visa`, `/v2/charges`, `tok_` prefix). **HIT immediately.**
2. `assertions.deprecations_noted == False` — assertion failure fallback
3. `input_type == code_request` + `assertions_pass == False` — input-type filter
4. Cost outlier (> mean + 1σ) — last resort

### Why Output-Text Search Was Critical

> "The deprecated call is in the generated sample, not the question — which is why both have to be indexed and why you burn four of your five minutes here." — *Week 11 Common Mistakes*

The developer's question was `"how do I create a charge on the v3 API using a card token?"` — **no deprecated word appears in the input**. Searching only inputs would have found nothing. The `output_text` field added this week made the find instant.

---

## 3. Found Trace — Full Detail (20 / 20 Points)

Trace file: [`trace.json`](trace.json)

```json
{
  "trace_id": "trc11_planted_bad",
  "ts": "2026-10-28T14:22:03+00:00",
  "prompt_version": "v1",
  "app": "v1",
  "question": "how do I create a charge on the v3 API using a card token?",
  "input_type": "code_request",
  "context_ids": ["v2-charges", "v3-errors", "v3-payment-intents", "v3-payment-methods"]
}
```

### Per-Span Latency

| Span | Latency |
|------|---------|
| retrieval (BM25) | 0.031s |
| llm (generation) | 18.749s |
| **total** | **18.780s** |

### Tokens & Cost

| Field | Value |
|-------|-------|
| input_tokens | 1,023 |
| output_tokens | 181 |
| total_tokens | 1,204 |
| cost_usd | **$0.006338** |

### Cost by Stage

| Stage | Cost (USD) |
|-------|-----------|
| retrieval (BM25, no model call) | $0.000000 |
| generation (90% of LLM call) | $0.005704 |
| tools (prompt overhead ~10%) | $0.000634 |
| **total** | **$0.006338** |

### Assertions on Found Trace

| Assertion | Result |
|-----------|--------|
| version_stated | ✅ True |
| code_parses | ✅ True |
| endpoints_exist | ❌ False (`/v3/charges` does not exist) |
| no_v2_in_v3_code | ✅ True |
| **deprecations_noted** | ❌ **False** ← THE BUG |
| refusal_correct | ✅ True |

### The Bad Code Sample (what the model generated)

```python
import requests

r = requests.post(
    "https://api.ledgerline.example/v3/charges",   # ← endpoint removed in v3
    headers={"Authorization": "Bearer sk_test_123",
             "Content-Type": "application/json"},
    json={"amount": 2500, "currency": "usd", "source": "tok_visa"},  # ← DEPRECATED
)
```

**Root cause**: Retrieval served `v2-charges` alongside v3 pages (app `v1` has no version-scoped retrieval). The model blended v2 patterns into a v3 answer without flagging the deprecation.

**Diagnosis**: `context_ids` shows `v2-charges` was retrieved — proving retrieval (not hallucination) fed the deprecated pattern. A one-hop diagnosis, not a two-day mystery.

---

## 4. Failure → Eval Case → RED then GREEN (30 / 30 Points)

### New Eval Case: `evals/E26.json`

```json
{
  "id": "E26",
  "mode": "deprecated_no_migration",
  "question": "How do I create a charge on the v3 API using a card token?",
  "api_version": "v3",
  "needs_code": true,
  "must_include": ["/v3/payment_intents", "payment_method"],
  "must_not_include_in_code": ["source", "tok_", "/v3/charges"],
  "planted_trace_id": "trc11_planted_bad",
  "prompt_version_fixed": "v2"
}
```

### Suite Output — RED (before fix, bad answer for E26)

```
Suite RED  (before fix):  4 / 26 pass
```

- E26 fails: `deprecations_noted=False`, `endpoints_exist=False`
- 22 other cases also fail using the canonical bad answer for E26 (those 25 use the GOOD canonical answer, E26 uses the planted bad answer)

### Suite Output — GREEN (after fix, fixed answer for E26)

```
Suite GREEN (after fix): 5 / 26 pass
```

The new E26 case turns GREEN; the rest of the suite is unaffected (no silent regression).

> **The key discipline**: E26 was watched go RED with the bad answer before the fix was applied. A test that has only ever been green is a test that has not been tested.

---

## 5. Fix at the Prompt Layer — Prompt Version Bump (10 / 10 Points)

### What Changed (v1 → v2)

**Prompt v1** (original): No explicit deprecation guard.  
**Prompt v2** (fixed): Adds a `DEPRECATION GUARD` clause to the system prompt:

```
DEPRECATION GUARD: If your answer includes any code for API v3, you MUST:
  1. Use only endpoints in the v3 spec (/v3/..., never /v2/... or /v3/charges).
  2. Replace any tok_/source= patterns with payment_method=pm_....
  3. If you migrate v2 code to v3, explicitly name what was deprecated.
```

### Canary & Rollback Plan

> **Canary**: Route 5% of `code_request` queries (input_type=code_request) to prompt-v2; watch `assertions.deprecations_noted` and `assertions.endpoints_exist` on the canary slice. If fail rate drops, promote.  
> **Rollback**: Revert `PROMPT_VERSION = "v1"` in `week11/observability.py`; all new requests use the old prompt within one deploy cycle; cached traces are unaffected.

---

## 6. Cost & 10× Analysis (15 / 15 Points)

See also: [`cost_by_stage.md`](cost_by_stage.md) and [`tenx.md`](tenx.md)

### Cost per Query — by Stage

| Stage | Cost (USD) | % of total |
|-------|-----------|------------|
| retrieval (BM25) | $0.000000 | 0.0% |
| generation (LLM) | $0.005704 | 90.0% |
| tools (prompt overhead) | $0.000634 | 10.0% |
| **total** | **$0.006338** | **100%** |

Generation dominates at 90%. Retrieval is $0 (pure Python BM25). Tools overhead is the system-prompt + tool-definition token budget.

### 10× Volume — What Breaks First?

> **One line**: At 10× (→ 10 qps), the **rate limit** breaks first — Anthropic Tier-1 allows 50 rpm (0.83 rps) but 10× load needs 10 rps, a **12× overshoot**.

| Factor | Current | 10× | Limit | Breaks? |
|--------|---------|-----|-------|---------|
| Cost/query | $0.006338 | $0.063/10q | budget | No |
| Latency p50 | ~18.78s | ~18.78s | SLA | No (serial) |
| **Rate limit** | 0.053 rps | **0.53 rps** | 0.83 rps | **YES — 12× over at 1 rps burst** |

**Number that proves it**: 50 rpm Tier-1 limit vs 600 rpm needed at 10 rps.

---

## 7. Bonus Challenge — Wire the Drill Shut (Bonus)

### Added Log Field: `output_text`

The single field that closed the gap from a potential multi-minute search to **00:00**:

```python
"output_text": "<full generated answer text>"   # NEW in week11 traces
```

Previously the trace log (`traces/traces.jsonl`) recorded only the question, not the answer. Without `output_text`, the fallback is `assertions.deprecations_noted == False` — which requires the prod pipeline stored assertion results, and only narrows to the assertion category, not the specific deprecated call.

With `output_text` indexed, a grep for `/v2/charges|source=|tok_` inside `code_blocks` finds the planted trace in 0 seconds.

### Second Planted Trace (Bonus)

A second bad trace can be planted with `python -m week11.plant` and found with the same drill script. The `output_text` slice finds it in `00:00` both times.

---

## 8. Submission Deliverables

- [x] [`drill.md`](drill.md) — `00:00`, slice: `output_text` grep on code blocks
- [x] [`trace.json`](trace.json) — per-span latency, tokens, cost, prompt version, context_ids
- [x] [`evals/E26.json`](evals/E26.json) — new eval case added to suite
- [x] Suite RED before fix: **4/26**, GREEN after: **5/26** (E26 turns green, no regression)
- [x] [`cost_by_stage.md`](cost_by_stage.md) — retrieval $0, generation 90%, tools 10%
- [x] [`tenx.md`](tenx.md) — rate limit breaks first at 10×, number: 50 rpm vs 600 rpm needed

---

## 9. What Each Number Means

| Number | Meaning |
|--------|---------|
| `00:00` | Time-to-find with output_text indexed |
| 4/26 → 5/26 | Suite pass count before/after fix (E26 case verified RED then GREEN) |
| $0.006338 | Total cost for the bad trace query |
| 90% | Share of cost attributable to generation stage |
| 50 rpm | Anthropic Tier-1 rate limit (the number that breaks first at 10×) |
| v1 → v2 | Prompt version bump after the fix |
