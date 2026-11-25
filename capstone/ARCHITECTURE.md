# Architecture: one page

```
 integrator question (may contain pasted keys / DSNs)
        │
        ▼
 ┌──────────────────────── capstone/engine.py :: answer()  ── ONE trace id minted here ────────────┐
 │                                                                                                 │
 │  [redact]  obs.redact(): keys, DSNs, bearer tokens, whsec_, emails removed BEFORE the model    │
 │      │                                                                                          │
 │  [resolve_version]  version.py: flag > ledgerline==x.y > "I'm on 2.4" > mention > 3.0(assumed) │
 │      │                                                                                          │
 │  [rag.retrieve]  retriever.py (Week 3-4): structure-aware chunks, BM25,                         │
 │      │           METADATA FILTER sdk_version enforced in code; SO = matching bridge only        │
 │      ▼                                                                                          │
 │  [agent.lap1..3]  hand-built loop (Week 7)  ──── $ MODEL CALL (1-3×) ────                        │
 │      │   tools discovered at runtime: tools/list over MCP  (mcp_config.json)                    │
 │      │   sdk_version arg PINNED to the resolved version before the call                         │
 │      ├──► [mcp.call.*] ── stdio JSON-RPC, _meta.trace_id ──► capstone/mcp_server.py ───────────┐ │
 │      │                                                      search_sdk_docs  (version filter) │ │
 │      │                                                      lookup_changelog                  │ │
 │      │                                                      symbol_exists                     │ │
 │      │                                                      check_code                        │ │
 │      │                                    writes its own span line under the SAME trace id ◄──┘ │
 │      ▼                                                                                          │
 │  [code_check]  codecheck.py: ast.parse + imports + methods + kwargs + result attrs vs THE       │
 │      │         caller's version (sdk_spec.py symbol table). Free, deterministic.                 │
 │      ├── fails ──► [repair]  ──── $ MODEL CALL (0-1×) ──── re-check ──► still bad: withhold code  │
 │      ▼                                                                                          │
 │  [guards]  removed/invented symbol → "X no longer exists in 3.0 - here is the migration"        │
 │            deprecated symbol used/mentioned → "deprecated since 2.4, removed in 3.0, use Y"     │
 │            Sources rebuilt from retrieved chunks, each with its version; SO never cited         │
 │      ▼                                                                                          │
 │  [trace write]  obs.write_line(): redact AGAIN on write → capstone/runs/traces.jsonl            │
 └─────────────────────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼  answer + trace_id

 evals (python3 -m capstone eval): cases.jsonl → engine.answer() → assertions (free) → judge ($ MODEL CALL, 1×)
                                   → taxonomy, trajectory, SO ablation, report.py → EVAL_REPORT.md
```

**Where the money goes** (per question, measured in `EVAL_REPORT.md` §7): agent laps are 1–3
model calls, each re-sending the retrieved docs (~1.2–2k input tokens), plus an optional repair
call when the code check fails. Retrieval, the MCP tools, the code check, redaction and the
guards cost $0 (pure Python). The eval judge adds one short call per case and runs only in
evals, never in production.

**Single source of truth:** `sdk_spec.py`. The CHANGELOG, the docs' deprecation notes, the
samples, the symbol-exists tool and the code checker all derive from it.
