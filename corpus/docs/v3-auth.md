---
page_id: v3-auth
api_version: v3
title: Authentication (v3)
endpoints:
---
# Authentication (v3)

v3 accepts the secret key **only** as a bearer token:
`Authorization: Bearer sk_live_...`. The `api_key` query parameter is no longer
accepted and returns HTTP 401.

Requests are limited to 100 per second per key. A 429 response carries a
`Retry-After` header giving the seconds to wait.
