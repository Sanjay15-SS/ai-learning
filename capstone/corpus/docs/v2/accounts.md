---
page_id: v2/accounts
source: docs
sdk_version: 2.x
title: Accounts
url: https://docs.ledgerline.example/sdk/python/v2/accounts
---
`client.accounts.list(limit=50, page_token=None)` and `client.accounts.get(account_id)`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
page = client.accounts.list(limit=100)
for acc in page.items:
    print(acc["id"], acc["balance"])
```
