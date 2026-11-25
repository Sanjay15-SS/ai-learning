# Fresh-eyes note (Thursday)

> To be filled in BY the reviewer from another squad, not by us. Leave blanks blank until then.

- **Reviewer / squad:** ______________________
- **Date:** ______________________
- **Their MCP client** (must not be ours: Claude Code / Claude Desktop / MCP Inspector / their own agent): ______________
- **What they did:**
  1. Cloned the repo and followed README.md only. Time to the first answer: ______
  2. Connected their client to `python3 -m capstone mcp` using `capstone/mcp_client_example.json`
  3. Called `search_sdk_docs` / `symbol_exists` / `check_code` live. Trace ids from `capstone/runs/traces.jsonl` (`trace_id_source: server_minted`): ______________
- **Where they stumbled** (verbatim):
  - ______________________
- **What we changed because of it** (commit sha):
  - ______________________

Checklist for the reviewer: `python3 -m capstone.selftest` passes ☐ · `ask` returns an answer
with a v2.x citation for a 2.4 question ☐ · an outside-client tool call shows up in the trace
log ☐ · they tried to break it with a question of their own: ______________
