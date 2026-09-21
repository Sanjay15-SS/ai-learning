---
page_id: v3-customers
api_version: v3
title: Customers (v3)
endpoints: POST /v3/customers, GET /v3/customers, POST /v3/customers/{customer_id}, GET /v3/customers/{customer_id}/payment_methods
---
# Customers (v3)

- `POST /v3/customers` creates a customer from `email` and `name`. v3 does not
  accept card details on the customer; attach a payment method instead (see
  Payment methods).
- `POST /v3/customers/{customer_id}` updates `email`, `name` or `metadata`.
- `GET /v3/customers` lists customers with cursor pagination (see Pagination).
- `GET /v3/customers/{customer_id}/payment_methods` lists the payment methods
  attached to a customer, each with `id` (prefix `pm_`), `type`, and a `card`
  object holding `brand`, `last4`, `exp_year`.
