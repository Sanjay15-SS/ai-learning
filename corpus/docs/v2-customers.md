---
page_id: v2-customers
api_version: v2
title: Customers and cards (v2)
endpoints: POST /v2/customers, GET /v2/customers, GET /v2/customers/{customer_id}/cards
---
# Customers and cards (v2)

## Create a customer

`POST /v2/customers` with `email`, `name` and optionally `card_token`. Passing
`card_token` saves the card on the customer in the same call.

## List customers

`GET /v2/customers` is paginated with `page` (1-based) and `per_page`
(default 20, max 100). The response carries `total_pages`.

## List a customer's cards

`GET /v2/customers/{customer_id}/cards` returns the saved cards on a customer,
each with `id` (prefix `card_`), `brand`, `last4` and `exp_year`.
