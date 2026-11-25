---
page_id: v2/client
source: docs
sdk_version: 2.x
title: Installing and creating a Client
url: https://docs.ledgerline.example/sdk/python/v2/client
---
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
