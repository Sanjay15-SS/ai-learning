---
page_id: v2-webhooks
api_version: v2
title: Webhooks (v2)
endpoints: POST /v2/webhooks
---
# Webhooks (v2)

Register a URL with `POST /v2/webhooks` passing `url` and `events` (a list such as
`charge.succeeded`, `charge.refunded`).

Every delivery carries the header `X-Ledgerline-Signature`, which is the hex
HMAC-SHA256 of the raw request body keyed with your webhook secret. Compare it with
`hmac.compare_digest`.
