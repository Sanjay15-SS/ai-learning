---
page_id: v3-pagination
api_version: v3
title: Pagination (v3)
endpoints:
---
# Pagination (v3)

Every v3 list endpoint uses cursor pagination. Pass `limit` (1-100, default 10)
and, for the next page, `starting_after` set to the `id` of the last object you
received. The response is `{"data": [...], "has_more": true|false}`; stop when
`has_more` is false. There is no page number and no total count, which keeps
results stable while new objects are being created.
