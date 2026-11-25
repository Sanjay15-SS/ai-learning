"""The ground truth for the fictional `ledgerline` Python SDK: which symbols exist in which
version, with which parameters, and when each was added / deprecated / removed.

Everything deterministic in the capstone reads this one table: the symbol-exists MCP
tool, the code checker (parse + imports + methods + kwargs), the changelog, and the
generated docs and samples. If the docs and the checker disagree, this file is right.

Versions are (major, minor). v1 is dead (Stack Overflow still uses it). v2.0-2.4 and
v3.0 are BOTH live: ~40% of customers are on 2.x.
"""
from typing import Dict, List, Optional, Tuple

LIVE_VERSIONS = ("2.4", "3.0")
CURRENT = "3.0"


def V(s: str) -> Tuple[int, int]:
    s = s.lower().lstrip("v").strip()
    parts = (s.split(".") + ["0"])[:2]
    return int(parts[0]), int(parts[1] or 0)


# symbol -> {added, deprecated, removed, replacement, params, required, note}
# Symbols are written the way user code reaches them: "Client", "client.search",
# "client.entries.create", "errors.RateLimitError" (import path ledgerline.errors).
SYMBOLS: Dict[str, dict] = {
    # ---------------- v1 only (dead; every Stack Overflow answer still uses these)
    "connect": dict(added="1.0", removed="2.0", replacement="Client(api_key=..., timeout=...)",
                    params=["api_key"], kind="function",
                    note="v1 module-level connect() was replaced by the Client class in 2.0."),
    "conn.find": dict(added="1.0", removed="2.0", replacement="client.query (2.x) / client.search (3.0)",
                      params=["collection", "where"], kind="method",
                      note="v1 Connection.find()."),
    "conn.fetch_more": dict(added="1.0", removed="2.0", replacement="page_token (2.x) / cursor (3.0)",
                            params=[], kind="method", note="v1 pagination."),
    # ---------------- the client
    "Client": dict(added="2.0", params=["api_key", "timeout", "base_url", "retries"],
                   params_by_version={"2": ["api_key", "timeout", "base_url"],
                                      "3": ["api_key", "timeout", "base_url", "retries"]},
                   required_by_version={"3": ["timeout"]}, kind="class",
                   note="In 3.0 `timeout` is REQUIRED (seconds, float). In 2.x it is optional "
                        "and defaults to no timeout."),
    "client.close": dict(added="2.0", params=[], kind="method"),
    # ---------------- querying: renamed in 3.0
    "client.query": dict(added="2.0", deprecated="2.4", removed="3.0",
                         replacement="client.search",
                         params=["collection", "filter", "limit", "page_token"], kind="method",
                         note="Renamed to client.search() in 3.0; page_token became cursor."),
    "client.query_all": dict(added="2.3", deprecated="2.4", removed="3.0",
                             replacement="client.search_iter",
                             params=["collection", "filter", "page_size"], kind="method",
                             note="Auto-paginating iterator. Renamed to search_iter() in 3.0."),
    "client.search": dict(added="3.0", replacement=None,
                          params=["collection", "filter", "limit", "cursor"], kind="method",
                          note="Returns SearchPage(.items, .next_cursor)."),
    "client.search_iter": dict(added="3.0", params=["collection", "filter", "page_size"],
                               kind="method", note="Auto-paginating iterator."),
    # ---------------- retries
    "client.set_retry": dict(added="2.0", deprecated="2.2", removed="3.0",
                             replacement="Client(retries=...)", params=["max_retries"],
                             kind="method", note="Retries became a constructor argument in 3.0."),
    # ---------------- entries
    "client.entries.create": dict(added="2.0",
                                  params=["account_id", "amount", "currency", "memo",
                                          "idempotency_key"],
                                  params_by_version={"2": ["account_id", "amount", "currency", "memo"],
                                                     "3": ["account_id", "amount", "currency", "memo",
                                                           "idempotency_key"]},
                                  kind="method"),
    "client.entries.get": dict(added="2.0", params=["entry_id"], kind="method"),
    "client.entries.reverse": dict(added="2.1", params=["entry_id", "reason"], kind="method"),
    # ---------------- accounts
    "client.accounts.list": dict(added="2.0", params=["limit", "page_token", "cursor"],
                                 params_by_version={"2": ["limit", "page_token"],
                                                    "3": ["limit", "cursor"]}, kind="method"),
    "client.accounts.get": dict(added="2.0", params=["account_id"], kind="method"),
    # ---------------- webhooks
    "client.webhooks.verify": dict(added="2.0", deprecated="3.0", removed="3.2",
                                   replacement="client.webhooks.construct_event",
                                   params=["payload", "signature", "secret", "tolerance"],
                                   params_by_version={"2": ["payload", "signature", "secret"],
                                                      "3": ["payload", "signature", "secret",
                                                            "tolerance"]},
                                   kind="method",
                                   note="Still works in 3.0 and 3.1, removed in 3.2."),
    "client.webhooks.construct_event": dict(added="3.0", params=["payload", "signature", "secret"],
                                            kind="method"),
    # ---------------- errors (import paths)
    "LedgerlineError": dict(added="2.0", removed="3.0", replacement="errors.LedgerlineError",
                            params=[], kind="exception",
                            note="Top-level import moved to ledgerline.errors in 3.0."),
    "RateLimited": dict(added="2.0", removed="3.0", replacement="errors.RateLimitError",
                        params=[], kind="exception",
                        note="Renamed RateLimitError and moved to ledgerline.errors in 3.0."),
    "errors.LedgerlineError": dict(added="3.0", params=[], kind="exception"),
    "errors.RateLimitError": dict(added="3.0", params=[], kind="exception"),
    "errors.TimeoutError": dict(added="3.0", params=[], kind="exception"),
}

# Attribute names a SearchPage / Page result exposes, per major.
RESULT_ATTRS = {"2": {"items", "next_page_token"}, "3": {"items", "next_cursor"}}


def _major(version: str) -> str:
    return str(V(version)[0])


def status(symbol: str, version: str) -> dict:
    """Is `symbol` callable in `version`? Never guesses: unknown symbols are 'unknown'."""
    sym = normalise(symbol)
    e = SYMBOLS.get(sym)
    if e is None:
        return {"symbol": sym, "version": version, "exists": False, "state": "unknown",
                "note": f"`{sym}` is not part of the ledgerline SDK in any version."}
    v = V(version)
    if v < V(e["added"]):
        return {"symbol": sym, "version": version, "exists": False, "state": "not_yet_added",
                "added": e["added"], "note": f"`{sym}` was added in {e['added']}."}
    if e.get("removed") and v >= V(e["removed"]):
        return {"symbol": sym, "version": version, "exists": False, "state": "removed",
                "removed": e["removed"], "deprecated": e.get("deprecated"),
                "replacement": e.get("replacement"), "note": e.get("note", "")}
    out = {"symbol": sym, "version": version, "exists": True,
           "params": params(sym, version), "required": required(sym, version)}
    if e.get("deprecated") and v >= V(e["deprecated"]):
        out.update(state="deprecated", deprecated=e["deprecated"], removed=e.get("removed"),
                   replacement=e.get("replacement"), note=e.get("note", ""))
    else:
        out["state"] = "current"
    return out


def params(sym: str, version: str) -> List[str]:
    e = SYMBOLS[sym]
    return e.get("params_by_version", {}).get(_major(version), e.get("params", []))


def required(sym: str, version: str) -> List[str]:
    return SYMBOLS[sym].get("required_by_version", {}).get(_major(version), [])


def normalise(symbol: str) -> str:
    s = symbol.strip().strip("`").replace("()", "")
    s = s.split("(")[0]
    for pre in ("ledgerline.", "self.client.", "self."):
        if s.startswith(pre):
            s = s[len(pre):]
    if s.startswith("Client."):
        s = "client." + s[len("Client."):]
    return s


def deprecated_in(version: str) -> List[dict]:
    """Every symbol that still exists in `version` but is deprecated there."""
    return [status(s, version) for s in SYMBOLS
            if status(s, version).get("state") == "deprecated"]


def changelog_entry(symbol: str) -> Optional[dict]:
    sym = normalise(symbol)
    e = SYMBOLS.get(sym)
    if e is None:
        return None
    return {"symbol": sym, "added": e["added"], "deprecated": e.get("deprecated"),
            "removed": e.get("removed"), "replacement": e.get("replacement"),
            "note": e.get("note", "")}
