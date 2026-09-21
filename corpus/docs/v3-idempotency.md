---
page_id: v3-idempotency
api_version: v3
title: Idempotent requests (v3)
endpoints:
---
# Idempotent requests (v3)

Send an `Idempotency-Key` header (any unique string, a UUID4 is recommended) on a
POST so that a network retry cannot perform the operation twice. Ledgerline stores
the first response for 24 hours and returns it for any repeat with the same key.
Reusing a key with a different request body returns HTTP 409.

The header is optional on most POST endpoints and required on
`POST /v3/payment_intents`.
