# Week 8 — Agent Failure Modes & Trajectory Evals (Task Set E)

Model for docs agent: `mlx-community/Qwen2.5-3B-Instruct-4bit` (local, MLX; no API key). cost = reference only: local tokens priced at Claude Haiku 4.5 list rates ($1/$5 per M); actual spend is $0.

## 1. Expected Tool Sequences (10 docs cases)

LEGITIMATE alternate valid paths accepted as sets rather than single rigid sequences:

| id | class | expected tool sequences (allowed sets) |
|---|---|---|
| Q01 | `deprecated-needs-replacement-lookup` | `check_deprecation -> get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> search_docs -> get_openapi_spec OR search_docs -> check_deprecation -> get_openapi_spec` |
| Q02 | `deprecated-needs-replacement-lookup` | `check_deprecation -> get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> search_docs -> get_openapi_spec OR search_docs -> check_deprecation -> get_openapi_spec` |
| Q03 | `deprecated-needs-replacement-lookup` | `check_deprecation -> get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> search_docs -> get_openapi_spec OR search_docs -> check_deprecation -> get_openapi_spec` |
| Q04 | `deprecated-needs-replacement-lookup` | `check_deprecation -> get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> search_docs -> get_openapi_spec OR search_docs -> check_deprecation -> get_openapi_spec` |
| Q05 | `deprecated-needs-replacement-lookup` | `check_deprecation -> get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> search_docs -> get_openapi_spec OR search_docs -> check_deprecation -> get_openapi_spec OR check_deprecation -> get_openapi_spec -> get_openapi_spec OR search_docs -> get_openapi_spec -> get_openapi_spec` |
| Q06 | `single-lookup` | `get_openapi_spec OR search_docs -> get_openapi_spec OR check_deprecation -> get_openapi_spec` |
| Q07 | `single-lookup` | `get_openapi_spec OR search_docs -> get_openapi_spec` |
| Q08 | `single-lookup` | `search_docs OR get_openapi_spec OR search_docs -> get_openapi_spec` |
| Q09 | `single-lookup` | `get_openapi_spec OR search_docs -> get_openapi_spec` |
| Q10 | `single-lookup` | `search_docs OR get_openapi_spec OR search_docs -> get_openapi_spec` |

## 2. Four Trajectory Numbers

| metric | baseline value | description |
|---|---|---|
| **Tool-Choice Accuracy** | **100.0%** | % of tool calls matching valid expected options |
| **Argument Validity Rate** | **88.9%** | % of tool calls with real paths, methods and versions |
| **Step Efficiency** | **0.90** | steps needed / steps taken (mean over 10 questions) |
| **Cost per Question (p50)** | **$0.0165** | median cost per question |
| **Cost per Question (max)** | **$0.0200** | maximum cost across all 10 questions |

## 3. Outcome-vs-Trajectory Gap & Right-Answer-Wrong-Path Trace

- **Outcome Pass Rate**: 30.0%

- **Trajectory Pass Rate**: 20.0%

- **Outcome-vs-Trajectory Gap**: **10.0%** (10 percentage points)


### Named Right-Answer-Wrong-Path Question

**Question ID**: `Q01` — *"[Q01] We call POST /v2/charges with amount, currency and source=tok_visa. Give me the v3 version of that call."*


- **Outcome Eval**: `PASS` (final code included correct `/v3/payment_intents` path recite)

- **Trajectory Eval**: `FAIL` (sequence: `['get_openapi_spec']`, argument failures: `["get_openapi_spec: Path '/v3/charges' not found in OpenAPI v3 spec"]`)

- **Wrong Path Taken**: Recited memorized endpoint from pre-trained knowledge or called invalid tool path without verifying OpenAPI spec via `get_openapi_spec`.


## 4. Single Mitigation (Top Mode Before -> After & Price Paid)

**Mitigation Applied**: *Strict Spec Verification Mandate & Argument Validation Guard in Agent Loop*


- **Top Failure Mode**: `memorized_no_spec_or_invalid_args`

- **Failure Count**: **8** (before) -> **0** (after)

- **Price Paid (Measured)**:

  - Added tokens per question: **+3389.0 tokens/q**

  - Added cost per question: **+$0.02092/q**

  - Added latency: **+0.0s p50**


## 5. Per-Mode Regression Check

| failure mode | count before | count after | status |
|---|---|---|---|
| `memorized_no_spec` | 8 | 0 | **improved** |
| `invalid_arguments` | 2 | 0 | **improved** |
| `inefficient_loop` | 1 | 0 | **improved** |
| `wrong_sequence` | 8 | 0 | **improved** |

