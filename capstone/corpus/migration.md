---
page_id: migration
source: migration
sdk_version: all
title: Migrating from 2.x to 3.0
url: https://docs.ledgerline.example/sdk/python/migration
---
# Migrating from 2.x to 3.0

Both 2.x and 3.0 are supported. Upgrade when you can; nothing in 2.4 stops working.

## 1. timeout is required
`Client(api_key=...)` becomes `Client(api_key=..., timeout=30.0)`. There is no default.

## 2. client.query() is now client.search()
`client.query(...)` (deprecated 2.4) was removed in 3.0. Rename the call to `client.search(...)`.
`page_token=` becomes `cursor=` and `page.next_page_token` becomes `page.next_cursor`.
`client.query_all()` becomes `client.search_iter()`.

```python
# 2.4
page = client.query("entries", limit=50, page_token=token)
token = page.next_page_token
# 3.0
page = client.search("entries", limit=50, cursor=cursor)
cursor = page.next_cursor
```

## 3. Retries move to the constructor
`client.set_retry(3)` becomes `Client(..., retries=3)`.

## 4. Errors moved to ledgerline.errors
`from ledgerline import RateLimited` becomes `from ledgerline.errors import RateLimitError`.

## 5. Webhooks
`client.webhooks.verify()` is deprecated in 3.0 and removed in 3.2: use `construct_event()`.

## 6. Idempotency
`client.entries.create(..., idempotency_key=...)` is new in 3.0. Use it on every retried create.
