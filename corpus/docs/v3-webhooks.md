---
page_id: v3-webhooks
api_version: v3
title: Webhook endpoints (v3)
endpoints: POST /v3/webhook_endpoints, DELETE /v3/webhook_endpoints/{endpoint_id}
---
# Webhook endpoints (v3)

Register with `POST /v3/webhook_endpoints`, passing `url` and `enabled_events`
(for example `payment_intent.succeeded`, `refund.created`). Remove one with
`DELETE /v3/webhook_endpoints/{endpoint_id}`.

## Verifying signatures

Each delivery carries a `Ledgerline-Signature` header of the form
`t=<unix timestamp>,v1=<hex signature>`. The signature is HMAC-SHA256, keyed with
the endpoint secret, over the string `"<t>.<raw body>"`. Reject deliveries whose
timestamp is more than 300 seconds old, and compare with `hmac.compare_digest`.
