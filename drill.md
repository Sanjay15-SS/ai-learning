# Week 11 — Drill Report

**Time-to-find**: `00:00`
**Slice that found it**: output_text (deprecated-symbol grep on code blocks)
**Traces searched**: 1

## Found Trace
- **trace_id**: `trc11_planted_bad`
- **timestamp**: `2026-10-28T14:22:03+00:00`
- **prompt_version**: `v1`
- **app**: `v1`
- **question**: _how do I create a charge on the v3 API using a card token?_
- **input_type**: `code_request`
- **context_ids**: `['v2-charges', 'v3-errors', 'v3-payment-intents', 'v3-payment-methods']`

## Per-Span Latency
| Span | Latency |
|------|---------|
| retrieval | 0.031s |
| llm | 18.749s |
| **total** | **18.78s** |

## Tokens & Cost
| Field | Value |
|-------|-------|
| input_tokens | 1023 |
| output_tokens | 181 |
| total_tokens | 1204 |
| cost_usd | $0.006338 |

## Cost by Stage
| Stage | Cost |
|-------|------|
| retrieval | $0.000000 |
| generation | $0.005704 |
| tools | $0.000634 |
| **total** | **$0.006338** |

## Why It Was Hard to Find
The deprecated call (`source=tok_visa`) appeared **only in the generated output**,
not in the developer's question. A log search over *inputs* alone would miss it.
The `output_text` field (added this week) made the find instant.

## Missing Log Field (if time > 5 min)
N/A — found in 00:00 because `output_text` was indexed.
Without `output_text` the fallback is `assertions.deprecations_noted == False`,
which requires that the prod pipeline stores assertion results per trace.