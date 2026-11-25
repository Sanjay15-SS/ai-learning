---
page_id: v2/entries
source: docs
sdk_version: 2.x
title: Creating and reversing entries
url: https://docs.ledgerline.example/sdk/python/v2/entries
---
`client.entries.create(account_id, amount, currency, memo=None)` posts a ledger entry.
Amounts are integers in minor units (2500 = $25.00). `client.entries.get(entry_id)` fetches one.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
entry = client.entries.create(account_id="acc_123", amount=2500, currency="usd", memo="invoice 42")
print(entry["id"])
```

## Reversing an entry (added in 2.1)

Entries are immutable. `client.entries.reverse(entry_id, reason=None)` posts the opposite entry.
There is no idempotency key in 2.x: retrying a create after a network error can post twice.
