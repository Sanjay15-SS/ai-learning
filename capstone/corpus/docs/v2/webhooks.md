---
page_id: v2/webhooks
source: docs
sdk_version: 2.x
title: Verifying webhooks
url: https://docs.ledgerline.example/sdk/python/v2/webhooks
---
`client.webhooks.verify(payload, signature, secret)` returns the parsed event or raises
`LedgerlineError` on a signature mismatch.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
event = client.webhooks.verify(payload=body, signature=sig_header, secret="whsec_...")
print(event["type"])
```
