---
page_id: v2/querying
source: docs
sdk_version: 2.x
title: Querying ledger entries with client.query
url: https://docs.ledgerline.example/sdk/python/v2/querying
---
`client.query(collection, filter=None, limit=50, page_token=None)` returns a `Page` with
`.items` and `.next_page_token`.

> **Deprecated in 2.4:** `client.query()` is deprecated and is **removed in 3.0**, where it is
> renamed `client.search()`. It keeps working on every 2.x release.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
page = client.query("entries", filter={"account_id": "acc_123"}, limit=50)
for entry in page.items:
    print(entry["id"], entry["amount"])
```

## Filters

`filter` is a dict of exact-match fields: `account_id`, `currency`, `status`, `created_after`.
