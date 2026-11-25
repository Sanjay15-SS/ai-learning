---
page_id: v3/client
source: docs
sdk_version: 3.0
title: Installing and creating a Client
url: https://docs.ledgerline.example/sdk/python/v3/client
---
Install with `pip install "ledgerline>=3,<4"`.

## Creating a client

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
```

**`timeout` is required in 3.0** (seconds). `Client(api_key=...)` without it raises `TypeError`.
`retries` (default 2) replaces 2.x's `set_retry()`.

## Closing

Call `client.close()` when you are done.
