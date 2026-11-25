---
page_id: v3/entries
source: docs
sdk_version: 3.0
title: Creating and reversing entries
url: https://docs.ledgerline.example/sdk/python/v3/entries
---
`client.entries.create(account_id, amount, currency, memo=None, idempotency_key=None)`.
Amounts are integers in minor units. Pass `idempotency_key` so a retried create posts once.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
entry = client.entries.create(account_id="acc_123", amount=2500, currency="usd",
                              idempotency_key="invoice-42")
print(entry["id"])
```

## Reversing an entry

`client.entries.reverse(entry_id, reason=None)` posts the opposite entry.
