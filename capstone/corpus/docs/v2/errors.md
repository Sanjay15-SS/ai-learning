---
page_id: v2/errors
source: docs
sdk_version: 2.x
title: Errors and retries
url: https://docs.ledgerline.example/sdk/python/v2/errors
---
Every SDK error subclasses `ledgerline.LedgerlineError`. HTTP 429 raises `ledgerline.RateLimited`.

```python
from ledgerline import Client, RateLimited

client = Client(api_key="LL_API_KEY", timeout=30)
try:
    page = client.query("entries", limit=50)
except RateLimited:
    print("slow down")
```

## Retries

`client.set_retry(max_retries)` configures automatic retries on 429/5xx.
**Deprecated since 2.2, removed in 3.0** (use `Client(retries=...)` in 3.0).
