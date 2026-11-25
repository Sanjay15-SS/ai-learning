# 10-minute demo script (four parts, to the clock)

Numbers in «» come from `EVAL_REPORT.md` / `runs/summary.json`. Read them off the screen;
don't quote them from memory. Pre-warm the model before going on stage with
`python3 -m capstone ask "warmup" ` (the first load takes ~10 s).

## Part 1: a real run (0:00–3:00)

```bash
python3 -m capstone ask "I'm on 2.4 - how do I paginate through all entries for an account?"
```
Point at, in order:
1. `version: 2.4 (from question)`: resolved **before** retrieval (`resolve_version` span precedes `rag.retrieve`).
2. Code uses `client.query(..., page_token=...)` and `page.next_page_token`: the v2 API.
3. `Sources: [Pagination (page_token) (v2.x)](.../v2/pagination)`: every citation names its version.
4. `Deprecation: client.query is deprecated since 2.4 and is removed in 3.0; use client.search`: nobody asked.

```bash
python3 -m capstone ask "How do I call client.query() in 3.0?"
```
5. First line: "`client.query()` no longer exists in 3.0 - it was removed in 3.0 (deprecated since 2.4). Here is the migration: use `client.search`".

```bash
python3 -m capstone trace <trace_id from the first run>
```
6. One trace id: `redact → resolve_version → rag.retrieve → agent.lap1 → mcp.call.* → code_check → repair?` with latency + cost per span, plus the MCP server's own `mcp_server_span` lines under the **same id**.

## Part 2: the failures we found (3:00–5:30)

- **Top mode:** the trace where a v2.4 caller got a v3 `client.search(cursor=...)` snippet: `trc12_d54345f79f9e` (`runs/found_redactor_corrupts_code.jsonl`, `raw_answer`). Then the before-run trace for C01 «trace id from report §3 before table».
  Frequency in the re-scored taxonomy: «wrong_version_code freq % before → after».
- **The mode integration created:** `redactor_corrupts_code`. Week 11's redact-on-write rewrote `page_token=page_token` into `page_token=[REDACTED]` in the logged answer. Two parts that were each correct broke each other once joined. Also show `version_dropped_at_mcp_hop` «count, trace id»: the agent passing its own `sdk_version` over MCP.
- **The other two weaknesses written down Wednesday** (WEAKNESSES.md): (2) the agent mostly doesn't verify, the guards do; (3) version resolution is a regex, and an unstated version defaults to 3.0 for a population that is 40% on 2.x.

## Part 3: a number that moved (5:30–7:30)

- **Wrong-version code-sample rate: «before X/N = a%» → «after Y/M = b%»**, n = «30» cases, same model, same prompts.
- Bonus: «k» of the before-run answers that pass with "looks like code" go **red** once the parse + symbol-table check counts.
- Judge agreement on integrated outputs: «agreement» on n=«n» against hand labels by «labeler».
- Stack Overflow: dropped hit@4 «20/29», raw «5/29» with SO text in «24» contexts, bridged «27/29» with SO text in 0.
- **What the suite does not measure at all:** it never executes code against a real SDK install. The symbol table is our model of the SDK, and if it is wrong the check is confidently wrong.

## Part 4: what's next (7:30–10:00)

```bash
python3 -m capstone loop      # R01 promoted word for word from trc12_d54345f79f9e: guard OFF = RED, ON = GREEN
```
- That case now permanently guards the failure (`evals/regressions.jsonl`), and selftest #9 goes red the morning v3.1 adds a deprecation with no case.
- Cost per question: «$ reference», «calls», «tokens»; at Sonnet-class list prices «$».
- **What breaks first at 9,000 integrators in-IDE: serving throughput.** «peak q/s» needed vs «local q/s» per Mac → «N×» short. On an API that is «requests/min» and «input tokens/min» at peak, checked against the rate-limit tier. Then latency: p95 «s» is unusable inline.
- Ranked next steps: (1) generate `sdk_spec` from the released wheel in CI (cost: ~1 day, kills weakness #1); (2) read the version from the IDE's lockfile (~0.5 day, kills #3); (3) a stop sequence and dedupe for doubled answers (~1 h); (4) cache retrieval + a prompt prefix (~0.5 day, latency).
