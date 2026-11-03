# Cost per Query — by Stage

Request: _how do I create a charge on the v3 API using a card token?_
Trace: `trc11_planted_bad`

| Stage | Tokens | Cost (USD) | % of total |
|-------|--------|-----------|------------|
| retrieval (BM25) | 0 | $0.000000 | 0.0% |
| generation (LLM) | 1204 | $0.005704 | 90.0% |
| tools (prompt overhead) | — | $0.000634 | 10.0% |
| **total** | **1204** | **$0.006338** | **100%** |

## Pricing basis
Model: claude-opus-5  |  $5.00/M input  |  $25.00/M output
Input tokens: 1023  |  Output tokens: 181
Cost = (1023 × $5 + 181 × $25) / 1,000,000
     = $0.006338