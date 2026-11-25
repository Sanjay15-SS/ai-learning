---
page_id: v3/accounts
source: docs
sdk_version: 3.0
title: Accounts
url: https://docs.ledgerline.example/sdk/python/v3/accounts
---
`client.accounts.list(limit=50, cursor=None)` and `client.accounts.get(account_id)`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
page = client.accounts.list(limit=100)
for acc in page.items:
    print(acc["id"], acc["balance"])
```
