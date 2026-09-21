---
page_id: v3-refunds
api_version: v3
title: Refunds (v3)
endpoints: POST /v3/refunds, GET /v3/refunds
---
# Refunds (v3)

`POST /v3/refunds` returns money from a succeeded payment intent.

| field | type | required | notes |
|---|---|---|---|
| payment_intent | string | yes | the `pi_` id to refund |
| amount | integer | no | partial refund; omit to refund in full |
| reason | string | no | `duplicate`, `fraudulent`, `requested_by_customer` |

`GET /v3/refunds?payment_intent=pi_...` lists the refunds on one payment intent,
using the same cursor pagination as every v3 list endpoint.
