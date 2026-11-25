# Seam list (not edited after the fact)

Written 2026-11-25 while wiring Weeks 3–11 together. Each seam is where two parts that each
worked alone stopped agreeing once they were joined. The status was added at the end and
the text was left as first written.

| # | seam | parts | status |
|---|---|---|---|
| 1 | The engine resolves the caller's version, but the agent re-types `sdk_version` in its own tool calls and can pass a different one over MCP. The server trusts its argument, so a 2.4 caller can get v3 chunks through the agent. | W7 agent × W9 MCP | **fixed**: engine pins `sdk_version` in code before the MCP call and logs a `tool_version_mismatch` event (counted in the taxonomy) |
| 2 | W11 redaction runs on write, so it also runs over the ANSWER. Its `token=` rule turned generated code `page_token=page_token` into `page_token=[REDACTED]`: the log and the printed answer were corrupted code. Trace `trc12_d54345f79f9e`. | W11 logging × generated code | **fixed**: secret rules only match quoted literals; selftest #7 guards it |
| 3 | The W9 MCP protocol had no way to carry a trace id, so server-side work was invisible in the request trace. | W9 × W11 | **fixed**: `_meta.trace_id` in tools/call; server writes `mcp_server_span` lines under that id |
| 4 | The MCP config says `python3`, and the client spawned the system python, not the venv, so imports failed. | W9 config × env | **fixed** for our engine (maps to `sys.executable`); **accepted** for outside clients: they must use the absolute venv path (`mcp_client_example.json`) |
| 5 | The W6/W7 contract and tools were shaped for an HTTP API (`API version: v2`, OpenAPI paths), and the SDK domain needs symbols, imports and kwargs, so the W6 assertions could not be reused as-is. | W6 × capstone domain | **fixed**: new assertions on `codecheck` + `sdk_spec` |
| 6 | The W6 judge's reference text contained BOTH versions, so it would accept a v3 fact given to a v2 caller. | W6 judge × two live versions | **fixed**: the judge reference is the gold pages plus the symbol table for the caller's version only |
| 7 | Several chunks from one page share a title, which produced duplicate citations. | W4 chunker × citations | **fixed**: dedupe by URL |
| 8 | The W4 chunker splits on `##` only. A long section with code stays one big chunk, and samples are indexed as whole files. | W4 | **accepted**: known limit, not re-chunking in week 12 |
| 9 | The 3B local model sometimes skips tools and answers from context alone, so it never checks the symbol. | W7 loop × model | **accepted**: measured as tool-choice accuracy; the deterministic code check backs it up |
| 10 | Sometimes the model writes the answer twice in one turn (C11), and the guards then prepend and append to the doubled text. | model × output contract | **fixed after after-run 1** (it doubled 6/12 answers): dedupe guard in `engine.py`, `single_answer` assertion |
| 11 | Latency is 25–60 s per question on a local Mac, with no streaming or caching. | W11 × deployment | **ran out of time** (see the 10× plan) |
| 12 | The code check only tracks names assigned from `Client(...)`. A client passed in as a function parameter under another name is not checked. | codecheck | **accepted** (the default name `client` is always tracked) |
| 13 | `async for` / `await` over a sync SDK call passed the symbol check (C30 smoke run, trace `trc12_84700673c026`). | codecheck × model | **fixed**: async-misuse rule in codecheck |
| 14 | *(added after after-run 1)* Doubled answers run into `max_tokens` and leave an **unclosed** code fence. The code-block regex only matches closed fences, so the truncated code was never checked: assertions passed C30 and only the judge failed it (trace `trc12_b3abf1a7f1b5`). | model `max_tokens` × codecheck | **fixed**: an unclosed fence fails `check_answer`; `code_fences_closed` assertion |
| 15 | *(added after after-run 2)* The code guard withholds a bad sample but leaves the PROSE around it alone, so C30 still says "or an asynchronous loop with `async for`". Every assertion passes; only the judge fails it (trace `trc12_8c1f5e3a5013`). | guards × generated prose | **fixed**: when code is withheld the prose is replaced by a plain statement built from the checker's errors. The first fix also appended a salvaged snippet that read an invented `page.has_next` (trace `trc12_179a8038f244`), so salvaging was dropped and result-page attributes are now checked. The 3B judge still FAILs the plain refusal (trace `trc12_2b04dbc33ffb`), which is a likely judge false negative for the hand labels to settle |
