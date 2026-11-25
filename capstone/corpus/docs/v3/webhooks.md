---
page_id: v3/webhooks
source: docs
sdk_version: 3.0
title: Verifying webhooks
url: https://docs.ledgerline.example/sdk/python/v3/webhooks
---
Use `client.webhooks.construct_event(payload, signature, secret)`.

> **Deprecated in 3.0:** `client.webhooks.verify()` still works in 3.0 and 3.1 and is
> **removed in 3.2**. Switch to `construct_event()`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
event = client.webhooks.construct_event(payload=body, signature=sig_header, secret="whsec_...")
print(event["type"])
```
