---
page_id: v3/querying
source: docs
sdk_version: 3.0
title: Searching ledger entries with client.search
url: https://docs.ledgerline.example/sdk/python/v3/querying
---
`client.search(collection, filter=None, limit=50, cursor=None)` returns a `SearchPage` with
`.items` and `.next_cursor`. It replaces 2.x `client.query()`, which **no longer exists in 3.0**.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
page = client.search("entries", filter={"account_id": "acc_123"}, limit=50)
for entry in page.items:
    print(entry["id"], entry["amount"])
```

## Filters

`filter` is a dict of exact-match fields: `account_id`, `currency`, `status`, `created_after`.
