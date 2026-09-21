---
page_id: v3-payment-intents
api_version: v3
title: Payment intents (v3)
endpoints: POST /v3/payment_intents, GET /v3/payment_intents/{intent_id}, POST /v3/payment_intents/{intent_id}/confirm, POST /v3/payment_intents/{intent_id}/capture
---
# Payment intents (v3)

v3 replaces charges with payment intents. A payment intent tracks one payment
through its life: `requires_payment_method` -> `requires_confirmation` ->
`processing` -> `succeeded` (or `requires_capture` when `capture_method` is
`manual`).

## Create a payment intent

`POST /v3/payment_intents`. The `Idempotency-Key` header is **required** on this
endpoint in v3; a retry with the same key returns the original intent instead of
creating a second payment.

| field | type | required | notes |
|---|---|---|---|
| amount | integer | yes | smallest currency unit |
| currency | string | yes | three-letter ISO code, lowercase |
| payment_method | string | no | a `pm_` id; required if `confirm` is true |
| customer | string | no | a `cus_` id |
| confirm | boolean | no | confirm immediately; default false |
| capture_method | string | no | `automatic` (default) or `manual` |

```python
import requests, uuid
r = requests.post(
    "https://api.ledgerline.example/v3/payment_intents",
    headers={"Authorization": "Bearer sk_test_123",
             "Idempotency-Key": str(uuid.uuid4())},
    json={"amount": 1999, "currency": "usd",
          "payment_method": "pm_card_visa", "confirm": True},
)
```

## Retrieve, confirm, capture

- `GET /v3/payment_intents/{intent_id}` returns the intent (id prefix `pi_`).
- `POST /v3/payment_intents/{intent_id}/confirm` confirms an unconfirmed intent.
- `POST /v3/payment_intents/{intent_id}/capture` captures an intent created with
  `capture_method=manual`; optional `amount_to_capture` for a partial capture.
  Uncaptured intents are cancelled automatically after 7 days.
