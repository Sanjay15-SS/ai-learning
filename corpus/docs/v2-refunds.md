---
page_id: v2-refunds
api_version: v2
title: Refunds (v2)
endpoints: POST /v2/refunds
---
# Refunds (v2)

`POST /v2/refunds` returns money from a previous charge.

| field | type | required | notes |
|---|---|---|---|
| charge | string | yes | the `ch_` id of the charge to refund |
| amount | integer | no | partial refund amount; omit to refund in full |
| reason | string | no | one of `duplicate`, `fraudulent`, `requested_by_customer` |

A charge can be refunded more than once until its full amount is returned.
