---
page_id: v3-payment-methods
api_version: v3
title: Payment methods (v3)
endpoints: POST /v3/payment_methods, POST /v3/payment_methods/{pm_id}/attach
---
# Payment methods (v3)

A payment method replaces the v2 card token.

- `POST /v3/payment_methods` with `type=card` and a `card` object (or a client-side
  `token`) creates a `pm_` payment method.
- `POST /v3/payment_methods/{pm_id}/attach` with `customer=cus_...` saves it on a
  customer so it can be reused for future payment intents.
