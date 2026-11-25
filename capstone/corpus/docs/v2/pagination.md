---
page_id: v2/pagination
source: docs
sdk_version: 2.x
title: Pagination (page_token)
url: https://docs.ledgerline.example/sdk/python/v2/pagination
---
Results come back in pages of at most `limit` (default 50, max 500). When `page.next_page_token`
is not None there are more results: pass it back as `page_token`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
token = None
while True:
    page = client.query("entries", limit=200, page_token=token)
    for entry in page.items:
        print(entry["id"])
    token = page.next_page_token
    if token is None:
        break
```

## query_all (added in 2.3)

`client.query_all(collection, filter=None, page_size=200)` iterates every result and follows
`next_page_token` for you. **Deprecated in 2.4, removed in 3.0** (renamed `search_iter`).

```python
for entry in client.query_all("entries", filter={"currency": "usd"}):
    print(entry["id"])
```
