---
page_id: v3/pagination
source: docs
sdk_version: 3.0
title: Pagination (cursor)
url: https://docs.ledgerline.example/sdk/python/v3/pagination
---
Results come back in pages of at most `limit` (default 50, max 500). When `page.next_cursor`
is not None, pass it back as `cursor`. (2.x used `page_token` / `next_page_token`.)

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
cursor = None
while True:
    page = client.search("entries", limit=200, cursor=cursor)
    for entry in page.items:
        print(entry["id"])
    cursor = page.next_cursor
    if cursor is None:
        break
```

## search_iter

`client.search_iter(collection, filter=None, page_size=200)` follows the cursor for you.

```python
for entry in client.search_iter("entries", filter={"currency": "usd"}):
    print(entry["id"])
```
