# 10× Volume Analysis — What Breaks First?

**One line**: At 10× today's 1 qps → 10 qps, the **rate limit** breaks first — Anthropic Tier-1 allows 50 rpm (= 0.83 rps) but 10× load needs 0.5 rps, a **1× overshoot**.

| Factor | Current | 10× | Limit | Breaks? |
|--------|---------|-----|-------|---------|
| Cost/query | $0.006338 | $0.06338/10q | budget | No |
| Latency p50 | ~18.8s | ~18.8s | SLA | No (no concurrency) |
| Rate limit | 0.05 rps | 0.5 rps | 0.83 rps | **YES — 1× over** |

**Number that proves it**: 50 rpm Tier-1 limit vs 32 rpm needed at 10×.