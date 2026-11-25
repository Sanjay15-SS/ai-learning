"""Generate the capstone corpus into capstone/corpus/ (deterministic, idempotent).

    python3 -m capstone.build_corpus

Sources (each chunk carries metadata the retriever FILTERS on, not words in the text):
  docs/v2/*.md       SDK reference 2.x    sdk_version=2.x   (live: ~40% of customers)
  docs/v3/*.md       SDK reference 3.0    sdk_version=3.0   (live)
  migration.md       v2 -> v3 guide       sdk_version=all
  CHANGELOG.md       deprecations + removal versions (generated from sdk_spec.SYMBOLS)
  samples.jsonl      200 runnable samples, each tagged with the version it runs against
  stackoverflow.jsonl 50 most-viewed answers; mostly v1, confidently wrong today
  issues.jsonl       open-issues export

The corpus is synthetic (fictional SDK); its shape matches the brief.
"""
import json
import random
from pathlib import Path

from . import sdk_spec as S

OUT = Path(__file__).resolve().parent / "corpus"
BASE = "https://docs.ledgerline.example/sdk/python"

V2 = {
"client": ("Installing and creating a Client", """
Install the 2.x SDK with `pip install "ledgerline>=2.4,<3"`.

## Creating a client

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY")
```

`timeout` is optional in 2.x and defaults to **no timeout** - a stalled connection can block
forever. Pass `timeout=30` to bound every call. `base_url` overrides the API host.

## Closing

Call `client.close()` when you are done, or let the process exit.
"""),
"querying": ("Querying ledger entries with client.query", """
`client.query(collection, filter=None, limit=50, page_token=None)` returns a `Page` with
`.items` and `.next_page_token`.

> **Deprecated in 2.4:** `client.query()` is deprecated and is **removed in 3.0**, where it is
> renamed `client.search()`. It keeps working on every 2.x release.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
page = client.query("entries", filter={"account_id": "acc_123"}, limit=50)
for entry in page.items:
    print(entry["id"], entry["amount"])
```

## Filters

`filter` is a dict of exact-match fields: `account_id`, `currency`, `status`, `created_after`.
"""),
"pagination": ("Pagination (page_token)", """
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
"""),
"entries": ("Creating and reversing entries", """
`client.entries.create(account_id, amount, currency, memo=None)` posts a ledger entry.
Amounts are integers in minor units (2500 = $25.00). `client.entries.get(entry_id)` fetches one.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
entry = client.entries.create(account_id="acc_123", amount=2500, currency="usd", memo="invoice 42")
print(entry["id"])
```

## Reversing an entry (added in 2.1)

Entries are immutable. `client.entries.reverse(entry_id, reason=None)` posts the opposite entry.
There is no idempotency key in 2.x: retrying a create after a network error can post twice.
"""),
"accounts": ("Accounts", """
`client.accounts.list(limit=50, page_token=None)` and `client.accounts.get(account_id)`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
page = client.accounts.list(limit=100)
for acc in page.items:
    print(acc["id"], acc["balance"])
```
"""),
"errors": ("Errors and retries", """
Every SDK error subclasses `ledgerline.LedgerlineError`. HTTP 429 raises `ledgerline.RateLimited`.

```python
from ledgerline import Client, RateLimited

client = Client(api_key="LL_API_KEY", timeout=30)
try:
    page = client.query("entries", limit=50)
except RateLimited:
    print("slow down")
```

## Retries

`client.set_retry(max_retries)` configures automatic retries on 429/5xx.
**Deprecated since 2.2, removed in 3.0** (use `Client(retries=...)` in 3.0).
"""),
"webhooks": ("Verifying webhooks", """
`client.webhooks.verify(payload, signature, secret)` returns the parsed event or raises
`LedgerlineError` on a signature mismatch.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30)
event = client.webhooks.verify(payload=body, signature=sig_header, secret="whsec_...")
print(event["type"])
```
"""),
}

V3 = {
"client": ("Installing and creating a Client", """
Install with `pip install "ledgerline>=3,<4"`.

## Creating a client

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
```

**`timeout` is required in 3.0** (seconds). `Client(api_key=...)` without it raises `TypeError`.
`retries` (default 2) replaces 2.x's `set_retry()`.

## Closing

Call `client.close()` when you are done.
"""),
"querying": ("Searching ledger entries with client.search", """
`client.search(collection, filter=None, limit=50, cursor=None)` returns a `SearchPage` with
`.items` and `.next_cursor`. It replaces 2.x `client.query()`, which **no longer exists in 3.0**.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
page = client.search("entries", filter={"account_id": "acc_123"}, limit=50)
for entry in page.items:
    print(entry["id"], entry["amount"])
```

## Filters

`filter` is a dict of exact-match fields: `account_id`, `currency`, `status`, `created_after`.
"""),
"pagination": ("Pagination (cursor)", """
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
"""),
"entries": ("Creating and reversing entries", """
`client.entries.create(account_id, amount, currency, memo=None, idempotency_key=None)`.
Amounts are integers in minor units. Pass `idempotency_key` so a retried create posts once.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
entry = client.entries.create(account_id="acc_123", amount=2500, currency="usd",
                              idempotency_key="invoice-42")
print(entry["id"])
```

## Reversing an entry

`client.entries.reverse(entry_id, reason=None)` posts the opposite entry.
"""),
"accounts": ("Accounts", """
`client.accounts.list(limit=50, cursor=None)` and `client.accounts.get(account_id)`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
page = client.accounts.list(limit=100)
for acc in page.items:
    print(acc["id"], acc["balance"])
```
"""),
"errors": ("Errors and retries", """
Errors live in `ledgerline.errors`: `LedgerlineError` (base), `RateLimitError` (HTTP 429),
`TimeoutError`. The 2.x top-level `ledgerline.RateLimited` **no longer exists in 3.0**.

```python
from ledgerline import Client
from ledgerline.errors import RateLimitError

client = Client(api_key="LL_API_KEY", timeout=30.0, retries=3)
try:
    page = client.search("entries", limit=50)
except RateLimitError:
    print("slow down")
```

## Retries

Pass `retries=` to `Client`. `set_retry()` was removed in 3.0.
"""),
"webhooks": ("Verifying webhooks", """
Use `client.webhooks.construct_event(payload, signature, secret)`.

> **Deprecated in 3.0:** `client.webhooks.verify()` still works in 3.0 and 3.1 and is
> **removed in 3.2**. Switch to `construct_event()`.

```python
from ledgerline import Client

client = Client(api_key="LL_API_KEY", timeout=30.0)
event = client.webhooks.construct_event(payload=body, signature=sig_header, secret="whsec_...")
print(event["type"])
```
"""),
}

MIGRATION = """
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
"""

TOPIC_PHRASES = {   # how integrators actually ask - the phrasing Stack Overflow carries
    "pagination": ["How to paginate ledgerline results", "ledgerline only returns 50 rows, how do I get the rest",
                   "fetch next page of entries ledgerline python", "get ALL entries ledgerline loop",
                   "ledgerline python iterate every row"],
    "client": ["ledgerline python hangs forever on request", "ledgerline call stuck never returns",
               "how to connect to ledgerline from python", "ledgerline init api key python"],
    "errors": ["ledgerline too many requests 429 python", "catch ledgerline throttling exception",
               "ledgerline retry automatically on failure", "ledgerline backoff when throttled"],
    "entries": ["ledgerline duplicate entries after retry", "undo a ledgerline entry",
                "post a transaction ledgerline python", "ledgerline amount cents or dollars"],
    "webhooks": ["ledgerline webhook signature mismatch", "validate ledgerline webhook payload python"],
    "querying": ["filter ledgerline entries by account", "ledgerline find entries by currency",
                 "lookup transactions for an account ledgerline"],
    "accounts": ["list all ledgerline accounts balance", "get account balance ledgerline python"],
}

V1_CODE = {
    "pagination": 'import ledgerline\nconn = ledgerline.connect("KEY")\nrows = conn.find("entries", where={})\nwhile rows:\n    rows = conn.fetch_more()\n',
    "client": 'import ledgerline\nconn = ledgerline.connect("KEY")\n',
    "errors": 'import ledgerline\nconn = ledgerline.connect("KEY")\ntry:\n    conn.find("entries", where={})\nexcept ledgerline.RateLimited:\n    pass\n',
    "entries": 'import ledgerline\nconn = ledgerline.connect("KEY")\nconn.find("entries", where={"memo": "x"})\n',
    "webhooks": 'import ledgerline\nconn = ledgerline.connect("KEY")\n',
    "querying": 'import ledgerline\nconn = ledgerline.connect("KEY")\nconn.find("entries", where={"account_id": "acc_1"})\n',
    "accounts": 'import ledgerline\nconn = ledgerline.connect("KEY")\nconn.find("accounts", where={})\n',
}
V2_CODE = {
    "pagination": 'from ledgerline import Client\nclient = Client(api_key="KEY")\npage = client.query("entries", page_token=None)\n',
    "errors": 'from ledgerline import Client\nclient = Client(api_key="KEY")\nclient.set_retry(5)\n',
    "client": 'from ledgerline import Client\nclient = Client(api_key="KEY")\n',
}


def _page(meta: dict, body: str) -> str:
    front = "\n".join(f"{k}: {v}" for k, v in meta.items())
    return f"---\n{front}\n---\n{body.strip()}\n"


def samples():
    """200 runnable samples: 20 templates x 10 variants, each tagged with its version."""
    colls = ["entries", "accounts"]
    accts = [f"acc_{i:03d}" for i in range(1, 11)]
    curs = ["usd", "eur", "gbp", "inr", "jpy"]
    T = {
        "2.4": [
            ("query", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\npage = client.query("entries", filter={{"account_id": "{a}"}}, limit=50)\nfor e in page.items:\n    print(e["id"])\n'),
            ("paginate", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\ntoken = None\nwhile True:\n    page = client.query("entries", filter={{"currency": "{c}"}}, limit=200, page_token=token)\n    for e in page.items:\n        print(e["id"])\n    token = page.next_page_token\n    if token is None:\n        break\n'),
            ("query_all", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nfor e in client.query_all("entries", filter={{"account_id": "{a}"}}, page_size=200):\n    print(e["id"])\n'),
            ("create", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nentry = client.entries.create(account_id="{a}", amount={n}, currency="{c}", memo="sample")\nprint(entry["id"])\n'),
            ("reverse", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nclient.entries.reverse("ent_{n}", reason="duplicate")\n'),
            ("accounts", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\npage = client.accounts.list(limit=100)\nfor acc in page.items:\n    print(acc["id"])\n'),
            ("errors", 'from ledgerline import Client, RateLimited\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\ntry:\n    client.query("{coll}", limit=10)\nexcept RateLimited:\n    print("throttled")\n'),
            ("retry", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nclient.set_retry(3)\nclient.entries.get("ent_{n}")\n'),
            ("webhook", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nevent = client.webhooks.verify(payload=b"{{}}", signature="t=1,v1=abc", secret="whsec_{n}")\nprint(event["type"])\n'),
            ("get", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30)\nacc = client.accounts.get("{a}")\nprint(acc["balance"])\n'),
        ],
        "3.0": [
            ("search", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\npage = client.search("entries", filter={{"account_id": "{a}"}}, limit=50)\nfor e in page.items:\n    print(e["id"])\n'),
            ("paginate", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\ncursor = None\nwhile True:\n    page = client.search("entries", filter={{"currency": "{c}"}}, limit=200, cursor=cursor)\n    for e in page.items:\n        print(e["id"])\n    cursor = page.next_cursor\n    if cursor is None:\n        break\n'),
            ("search_iter", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\nfor e in client.search_iter("entries", filter={{"account_id": "{a}"}}, page_size=200):\n    print(e["id"])\n'),
            ("create", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\nentry = client.entries.create(account_id="{a}", amount={n}, currency="{c}", idempotency_key="k-{n}")\nprint(entry["id"])\n'),
            ("reverse", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\nclient.entries.reverse("ent_{n}", reason="duplicate")\n'),
            ("accounts", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\npage = client.accounts.list(limit=100)\nfor acc in page.items:\n    print(acc["id"])\n'),
            ("errors", 'from ledgerline import Client\nfrom ledgerline.errors import RateLimitError\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\ntry:\n    client.search("{coll}", limit=10)\nexcept RateLimitError:\n    print("throttled")\n'),
            ("retry", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0, retries=3)\nclient.entries.get("ent_{n}")\n'),
            ("webhook", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\nevent = client.webhooks.construct_event(payload=b"{{}}", signature="t=1,v1=abc", secret="whsec_{n}")\nprint(event["type"])\n'),
            ("get", 'from ledgerline import Client\n\nclient = Client(api_key="LL_API_KEY", timeout=30.0)\nacc = client.accounts.get("{a}")\nprint(acc["balance"])\n'),
        ],
    }
    out = []
    for ver, temps in T.items():
        for name, tpl in temps:
            for i in range(10):
                code = tpl.format(a=accts[i], c=curs[i % 5], n=1000 + i * 37, coll=colls[i % 2])
                out.append({"id": f"s{ver.replace('.', '')}-{name}-{i}", "sdk_version": ver,
                            "topic": name, "code": code})
    return out


def build() -> dict:
    random.seed(7)
    for d in ("docs/v2", "docs/v3"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    for slug, (title, body) in V2.items():
        (OUT / "docs/v2" / f"{slug}.md").write_text(_page(
            {"page_id": f"v2/{slug}", "source": "docs", "sdk_version": "2.x", "title": title,
             "url": f"{BASE}/v2/{slug}"}, body), encoding="utf-8")
    for slug, (title, body) in V3.items():
        (OUT / "docs/v3" / f"{slug}.md").write_text(_page(
            {"page_id": f"v3/{slug}", "source": "docs", "sdk_version": "3.0", "title": title,
             "url": f"{BASE}/v3/{slug}"}, body), encoding="utf-8")
    (OUT / "migration.md").write_text(_page(
        {"page_id": "migration", "source": "migration", "sdk_version": "all",
         "title": "Migrating from 2.x to 3.0", "url": f"{BASE}/migration"}, MIGRATION), encoding="utf-8")

    # CHANGELOG generated from the symbol table, so it can never disagree with the checker
    lines = ["# CHANGELOG (deprecations and removals)", ""]
    for sym, e in S.SYMBOLS.items():
        if e.get("deprecated") or e.get("removed"):
            lines.append(f"- `{sym}`: added {e['added']}"
                         + (f", deprecated {e['deprecated']}" if e.get("deprecated") else "")
                         + (f", removed {e['removed']}" if e.get("removed") else "")
                         + (f" -> use `{e['replacement']}`" if e.get("replacement") else "")
                         + (f". {e['note']}" if e.get("note") else ""))
    (OUT / "CHANGELOG.md").write_text(_page(
        {"page_id": "changelog", "source": "changelog", "sdk_version": "all",
         "title": "CHANGELOG", "url": f"{BASE}/changelog"}, "\n".join(lines)), encoding="utf-8")

    smp = samples()       # one JSONL, not 200 files: id, sdk_version, topic, code
    (OUT / "samples.jsonl").write_text("\n".join(json.dumps(x) for x in smp) + "\n", encoding="utf-8")

    so = []
    n = 0
    for topic, phrases in TOPIC_PHRASES.items():
        for p in phrases:
            for era in ("1.x", "1.x") if topic in ("pagination", "client", "errors") else ("1.x",):
                n += 1
                code = V1_CODE[topic] if (era == "1.x" and n % 4) else V2_CODE.get(topic, V1_CODE[topic])
                ver = "1.x" if code in V1_CODE.values() else "2.x"
                so.append({"id": f"so{n:02d}", "source": "stackoverflow", "sdk_version": ver,
                           "year": 2018 + n % 4, "title": p if n % 2 else p.capitalize() + "?",
                           "score": 400 - n * 5, "linked_doc": topic,
                           "url": f"https://stackoverflow.com/q/{6100000 + n * 131}",
                           "body": f"Accepted answer ({2018 + n % 4}): this worked for me.\n\n```python\n{code}```"})
    while len(so) < 50:     # pad to the 50 most-viewed with near-duplicate phrasings
        base = so[len(so) % 20]
        n += 1
        so.append({**base, "id": f"so{n:02d}", "title": base["title"] + " (python 3)",
                   "url": f"https://stackoverflow.com/q/{6100000 + n * 131}", "score": 400 - n * 5})
    so = so[:50]
    (OUT / "stackoverflow.jsonl").write_text("\n".join(json.dumps(x) for x in so) + "\n", encoding="utf-8")

    issues = [
        {"id": "GH-412", "sdk_version": "3.0", "title": "search_iter stops one page early when page_size > 500",
         "body": "search_iter(page_size=1000) silently caps at 500 and stops after the first cursor. Workaround: page_size<=500."},
        {"id": "GH-398", "sdk_version": "2.x", "title": "query_all emits DeprecationWarning on every page in 2.4",
         "body": "Expected: one warning per process. Workaround: warnings.filterwarnings."},
        {"id": "GH-377", "sdk_version": "3.0", "title": "TypeError: Client() missing required keyword-only argument 'timeout'",
         "body": "Upgrading from 2.x. timeout is required in 3.0, see migration guide section 1."},
        {"id": "GH-366", "sdk_version": "2.x", "title": "Client hangs indefinitely without timeout",
         "body": "2.x default timeout is None. Pass timeout=30."},
        {"id": "GH-351", "sdk_version": "3.0", "title": "webhooks.verify DeprecationWarning but docs still show it",
         "body": "verify() is deprecated in 3.0 and removed in 3.2; use construct_event()."},
    ]
    (OUT / "issues.jsonl").write_text("\n".join(json.dumps(x) for x in issues) + "\n", encoding="utf-8")
    return {"docs_v2": len(V2), "docs_v3": len(V3), "samples": len(smp), "stackoverflow": len(so),
            "issues": len(issues)}


if __name__ == "__main__":
    print(build())
