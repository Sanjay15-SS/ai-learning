---
page_id: v2-charges
api_version: v2
title: Charges (v2)
endpoints: POST /v2/charges, GET /v2/charges/{charge_id}
---
# Charges (v2)

A charge moves money from a card to your Ledgerline balance in a single call.

## Create a charge

`POST /v2/charges`

| field | type | required | notes |
|---|---|---|---|
| amount | integer | yes | smallest currency unit, e.g. 1999 for $19.99 |
| currency | string | yes | three-letter ISO code, lowercase |
| source | string | yes | a card token such as `tok_visa` |
| customer | string | no | attach the charge to a customer id |
| description | string | no | free text shown on the dashboard |

The charge is authorised and captured immediately. A successful call returns a
`charge` object with `id` (prefix `ch_`) and `status` of `succeeded` or `failed`.

```python
import requests
r = requests.post(
    "https://api.ledgerline.example/v2/charges",
    headers={"Authorization": "Bearer sk_test_123"},
    data={"amount": 1999, "currency": "usd", "source": "tok_visa"},
)
```

## Retrieve a charge

`GET /v2/charges/{charge_id}` returns the charge object.
