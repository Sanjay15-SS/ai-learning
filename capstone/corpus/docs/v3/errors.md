---
page_id: v3/errors
source: docs
sdk_version: 3.0
title: Errors and retries
url: https://docs.ledgerline.example/sdk/python/v3/errors
---
Errors live in `ledgerline.errors`: `LedgerlineError` (base), `RateLimitError` (HTTP 429),
`TimeoutError`. The 2.x top-level `ledgerline.RateLimited` **no longer exists in 3.0**.

```python
from ledgerline import Client
from ledgerline.errors import RateLimitError

client = Client(api_key="LL_API_KEY", timeout=30.0, retries=3)
try:
    page = client.search("entries", limit=50)
except RateLimitError:
    print("slow down")
```

## Retries

Pass `retries=` to `Client`. `set_retry()` was removed in 3.0.
