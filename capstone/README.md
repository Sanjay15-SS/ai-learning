# Week 12 Capstone, Variant E: SDK Docs Answer Engine

Answers `ledgerline` Python SDK questions against the caller's **actual** version (2.4 or 3.0;
both are live). It surfaces deprecations and their removal versions without being asked, cites
every doc page with the version it belongs to, and says "that method no longer exists in 3.0,
here is the migration" instead of inventing a signature. Every emitted code sample is parsed
and checked against the caller version's symbol table.

The corpus is synthetic: a fictional SDK shaped like the brief (two live doc versions, migration
guide, CHANGELOG, 200 version-tagged samples, 50 mostly-v1 Stack Overflow answers, issues).

## Run it (from the repo root)

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate

python3 -m capstone.selftest          # 11 offline checks, ~2 s, no model
python3 -m capstone all               # THE one command: demo + full eval before/after + loop + report
```

No API key needed: the model is local Qwen2.5-3B (MLX, about 1.7 GB, downloaded once). Set
`ANTHROPIC_API_KEY` and the same code runs on Claude (`src/llm.py` is the only model call
site). On a local Mac, `all` takes roughly an hour: 60 engine runs plus 30 judge calls.

| command | what |
|---|---|
| `python3 -m capstone ask "I'm on 2.4 - how do I paginate?"` | one question end to end; prints the trace id |
| `python3 -m capstone ask "..." --mode before` | the same question through the naive integration |
| `python3 -m capstone eval --mode both` | 30 cases + regressions, before and after, judge on after |
| `python3 -m capstone report` | recomputes every number into `EVAL_REPORT.md` (no model) |
| `python3 -m capstone trace <trace_id>` | one trace: engine spans plus MCP-server spans, same id |
| `python3 -m capstone loop` | the closed failure→test loop, live: guard off = RED, on = GREEN |
| `python3 -m capstone label` | hand-label the after-run answers (for judge agreement) |
| `python3 -m capstone mcp` | our MCP server on stdio, for any outside client |

## Use the MCP server from another client

Copy `capstone/mcp_client_example.json` into your client's MCP config (Claude Code
`.mcp.json`, Claude Desktop, MCP Inspector). Fill in the absolute paths. Tools:
`search_sdk_docs(query, sdk_version)`, `lookup_changelog(symbol)`,
`symbol_exists(symbol, sdk_version)`, `check_code(code, sdk_version)`.

## Files

| file | contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | one-page sketch: boxes, arrows, model calls, money |
| [SEAMS.md](SEAMS.md) | seam list, each marked fixed / accepted / ran-out-of-time |
| [WEAKNESSES.md](WEAKNESSES.md) | top-3 known weaknesses, dated Wednesday |
| [EVAL_REPORT.md](EVAL_REPORT.md) | generated: before→after, per-category pass, judge agreement, taxonomy, trajectory, SO ablation, cost, 10×, non-coverage |
| [TRACE_EXAMPLE.json](TRACE_EXAMPLE.json) | one end-to-end trace with cost and latency per span, intact across the agent and MCP hops |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | the 10-minute, four-part demo |
| [FRESH_EYES.md](FRESH_EYES.md) | Thursday reviewer note (filled in by the reviewer) |

Code: `engine.py` (entry point) · `retriever.py` (RAG + version filter) · `mcp_server.py` ·
`codecheck.py` · `sdk_spec.py` (symbol table, the source of truth) · `obs.py` (trace + redaction) ·
`version.py` · `evaluate.py` · `report.py` · `loop.py` · `build_corpus.py`.
