---
page_id: changelog
source: changelog
sdk_version: all
title: CHANGELOG
url: https://docs.ledgerline.example/sdk/python/changelog
---
# CHANGELOG (deprecations and removals)

- `connect`: added 1.0, removed 2.0 -> use `Client(api_key=..., timeout=...)`. v1 module-level connect() was replaced by the Client class in 2.0.
- `conn.find`: added 1.0, removed 2.0 -> use `client.query (2.x) / client.search (3.0)`. v1 Connection.find().
- `conn.fetch_more`: added 1.0, removed 2.0 -> use `page_token (2.x) / cursor (3.0)`. v1 pagination.
- `client.query`: added 2.0, deprecated 2.4, removed 3.0 -> use `client.search`. Renamed to client.search() in 3.0; page_token became cursor.
- `client.query_all`: added 2.3, deprecated 2.4, removed 3.0 -> use `client.search_iter`. Auto-paginating iterator. Renamed to search_iter() in 3.0.
- `client.set_retry`: added 2.0, deprecated 2.2, removed 3.0 -> use `Client(retries=...)`. Retries became a constructor argument in 3.0.
- `client.webhooks.verify`: added 2.0, deprecated 3.0, removed 3.2 -> use `client.webhooks.construct_event`. Still works in 3.0 and 3.1, removed in 3.2.
- `LedgerlineError`: added 2.0, removed 3.0 -> use `errors.LedgerlineError`. Top-level import moved to ledgerline.errors in 3.0.
- `RateLimited`: added 2.0, removed 3.0 -> use `errors.RateLimitError`. Renamed RateLimitError and moved to ledgerline.errors in 3.0.
