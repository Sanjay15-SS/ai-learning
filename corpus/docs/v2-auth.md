---
page_id: v2-auth
api_version: v2
title: Authentication (v2)
endpoints:
---
# Authentication (v2)

v2 accepts your secret key either as a bearer token
(`Authorization: Bearer sk_live_...`) or as the `api_key` query parameter
(`?api_key=sk_live_...`). Test keys start with `sk_test_`.

Requests are limited to 100 per second per key; over the limit you receive HTTP 429.
