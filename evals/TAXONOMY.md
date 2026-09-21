# Failure taxonomy - the modes every eval case is tagged with

Six modes. Every case in `cases.jsonl` carries exactly one in its `mode` field, and
`week6/run_eval.py` reports pass rate per mode so an average cannot hide one of them.

| mode | what goes wrong | checked by |
|---|---|---|
| `version_confusion` | a v2 endpoint or field is recommended to a developer on v3 | `no_v2_in_v3_code`, `must_include`, judge |
| `deprecated_no_migration` | a deprecated/removed symbol appears with no note on what replaces it | `deprecations_noted`, `must_include`, judge |
| `hallucinated_endpoint` | a path that is not in the OpenAPI spec | `endpoints_exist`, judge |
| `broken_sample` | the code sample does not parse, or is missing when code was asked for | `code_parses`, judge |
| `unanswerable` | the docs are silent and the answer guesses instead of saying so | `refusal_correct`, judge |
| `conceptual` | an explanation that is wrong or unhelpful | judge (only the judge can) |

Regression cases (`source: trace:<id>`) are promoted verbatim from failed traces in
`traces/traces.jsonl` with `python3 -m week6.promote <trace_id> --mode <mode>`.
