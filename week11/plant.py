"""Plant a bad trace into traces_w11.jsonl for the Week-11 drill.

The 'squadmate' plants this exactly once.  Running plant_bad_trace() twice
is idempotent by trace_id, so it is safe to call from tests.

The bad answer contains:
  - A v3 code sample that uses the deprecated `source=tok_visa` parameter
    (it should use `payment_method=pm_...` in v3)
  - No deprecation note (the model just ships the bad call without warning)
This matches trace_id trc_edc0147b5b32 in the original traces but is written
into the new structured log so it can be found by output_text search.
"""
import json
from pathlib import Path

from week11.observability import STRUCTURED_LOG, write_trace

BAD_TRACE_ID = "trc11_planted_bad"

BAD_OUTPUT = """API version: v3

To create a charge in v3, use the `/v3/charges` endpoint with your card token:

```python
import requests

r = requests.post(
    "https://api.ledgerline.example/v3/charges",
    headers={"Authorization": "Bearer sk_test_123",
             "Content-Type": "application/json"},
    json={"amount": 2500, "currency": "usd", "source": "tok_visa"},
)
print(r.status_code, r.json())
```

Pass `source=tok_visa` as the card token and the charge will be created immediately.
"""

BAD_TRACE = {
    "trace_id": BAD_TRACE_ID,
    "ts": "2026-10-28T14:22:03+00:00",
    "prompt_version": "v1",
    "app": "v1",
    "question": "how do I create a charge on the v3 API using a card token?",
    "input_type": "code_request",
    "context_ids": ["v2-charges", "v3-errors", "v3-payment-intents", "v3-payment-methods"],
    "output_text": BAD_OUTPUT,
    "stop_reason": "end_turn",
    "spans": {
        "retrieval_s": 0.031,
        "llm_s": 18.749,
        "total_s": 18.780,
    },
    "usage": {
        "calls": 1,
        "input_tokens": 1023,
        "output_tokens": 181,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 1204,
        "cost_usd": 0.006338,
    },
    "cost_by_stage": {
        "retrieval_usd": 0.0,
        "generation_usd": 0.005704,
        "tools_usd": 0.000634,
        "total_usd": 0.006338,
    },
    "assertions": {
        "version_stated": True,
        "code_parses": True,
        "endpoints_exist": False,
        "no_v2_in_v3_code": True,
        "deprecations_noted": False,
        "refusal_correct": True,
        "must_include": None,
    },
    "assertions_pass": False,
}


def _already_planted(path: Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                if json.loads(line).get("trace_id") == BAD_TRACE_ID:
                    return True
            except json.JSONDecodeError:
                pass
    return False


def plant_bad_trace(path: Path = STRUCTURED_LOG) -> str:
    """Write the bad trace.  Idempotent."""
    if _already_planted(path):
        return BAD_TRACE_ID
    write_trace(BAD_TRACE, path=path)
    return BAD_TRACE_ID


if __name__ == "__main__":
    tid = plant_bad_trace()
    print(f"Planted trace: {tid}")
    print(f"Log: {STRUCTURED_LOG}")
