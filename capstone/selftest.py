"""Offline checks, no model, ~2 s:  python3 -m capstone.selftest

Includes the docs-drift guard: every deprecated/removed symbol in sdk_spec must be covered by
an eval case. When v3.1 adds two deprecations to sdk_spec.py, check #9 goes RED until a case
watches each one - the suite is watching the thing that moves."""
import json
import sys

from . import codecheck, retriever, sdk_spec as S, version as V
from .build_corpus import samples
from .engine import MCPSession, mentioned_symbols
from .evaluate import load_cases, so_ablation
from .obs import redact

OK, BAD = [], []


def check(name, cond, detail=""):
    (OK if cond else BAD).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f"   {detail}" if not cond and detail else ""))


def main():
    sm = samples()
    own = [s["id"] for s in sm if codecheck.check(s["code"], s["sdk_version"])["errors"]]
    check("1 all 200 samples pass the symbol check for THEIR version", not own, own[:3])
    check("2 a v2.4 caller's client.search() snippet is caught",
          any("client.search" in e for e in codecheck.check(
              "from ledgerline import Client\nc = Client(api_key='k', timeout=3)\nc.search('entries')", "2.4")["errors"]))
    check("3 3.0 Client() without timeout= is caught",
          codecheck.check("from ledgerline import Client\nc = Client(api_key='k')", "3.0")["errors"] != [])
    check("4 version resolved from 'ledgerline==2.2.1'", V.resolve("ledgerline==2.2.1 x")["version"] == "2.2")
    check("5 no version -> 3.0, flagged assumed", V.resolve("how do I list accounts")["assumed"])
    hits = retriever.search("paginate entries", "2.4")
    check("6 version filter: a 2.4 caller never retrieves a v3 chunk",
          all(retriever.covers(c.sdk_version, "2.4") for c in hits), [c.chunk_id for c in hits])
    check("7 redaction: key + conn string gone, code untouched",
          redact("LL_live_abcdef123456 postgres://u:p4ss@h/db page_token=page_token")
          == "[REDACTED_API_KEY] [REDACTED_CONN_STRING] page_token=page_token")
    s = MCPSession()
    try:
        names = sorted(t["name"] for t in s.tools)
        check("8 MCP tools discovered at runtime via tools/list",
              names == ["check_code", "lookup_changelog", "search_sdk_docs", "symbol_exists"], names)
    finally:
        s.close()
    cases = load_cases()
    text = json.dumps(cases)
    moving = [k for k, e in S.SYMBOLS.items() if (e.get("deprecated") or e.get("removed"))
              and not k.startswith("conn") and k != "connect" and k != "LedgerlineError"]
    uncovered = [k for k in moving if k.split(".")[-1] not in text]
    check("9 docs-drift guard: every deprecated/removed symbol has an eval case", not uncovered, uncovered)
    check("10 'client.search_entries_by_date' is detected as invented",
          S.status(mentioned_symbols("client.search_entries_by_date", True)[0], "3.0")["state"] == "unknown")
    ab = so_ablation()
    check("11 SO bridge keeps recall >= drop and shows no SO text",
          ab["bridge (after)"]["hit_rate"] >= ab["drop"]["hit_rate"]
          and ab["bridge (after)"]["cases_with_SO_text_in_context"] == 0)
    print(f"\n{len(OK)} passed, {len(BAD)} failed")
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
