---
page_id: v3-errors
api_version: v3
title: Errors (v3)
endpoints:
---
# Errors (v3)

Errors return JSON `{"error": {"type": ..., "code": ..., "message": ...}}`.

| HTTP | type | meaning |
|---|---|---|
| 400 | invalid_request_error | a parameter is missing or malformed |
| 401 | authentication_error | missing or invalid key |
| 402 | card_error | the card was declined; see `decline_code` |
| 409 | idempotency_error | an idempotency key was reused with a different body |
| 429 | rate_limit_error | back off for `Retry-After` seconds |

Retry 429 and 5xx with the same `Idempotency-Key`. Do not retry 400, 401 or 402.
