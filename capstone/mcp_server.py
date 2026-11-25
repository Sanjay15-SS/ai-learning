"""Our MCP server (stdio, JSON-RPC 2.0, protocol 2024-11-05) - the genuine capability:
version-scoped SDK doc search, changelog lookup, symbol-exists, and the code checker.

Run it for ANY MCP client (Claude Code, Claude Desktop, MCP Inspector, another squad's agent):

    python3 -m capstone.mcp_server

or add capstone/mcp_client_example.json to your client's MCP config.

Trace propagation: if tools/call params carry `_meta.trace_id`, the server writes its own
span line (kind=mcp_server_span) to the shared trace log under that id. Calls with no
trace id get a server-minted one, so an outside client's calls are logged too.
"""
import json
import time

from week9.mcp_protocol import MCPServer

from . import codecheck, retriever, sdk_spec as S
from .obs import new_trace_id, redact, write_line

VERSION_PROP = {"type": "string", "description": "The CALLER'S installed SDK version, e.g. '2.4' "
                "or '3.0'. Results are filtered to this version in code."}


def search_sdk_docs(args):
    v = args.get("sdk_version") or S.CURRENT
    hits = retriever.search(redact(args.get("query", "")), v,
                            retriever.RetrieverConfig(version_filter=True, so_mode="bridge",
                                                      k=int(args.get("k", 4))))
    return {"sdk_version": v, "results": [
        {"chunk_id": c.chunk_id, "page_id": c.page_id, "source": c.source, "title": c.title,
         "version": c.version_label, "url": c.url, "text": c.text[:1200]} for c in hits]}


def lookup_changelog(args):
    e = S.changelog_entry(args.get("symbol", ""))
    if e is None:
        return {"symbol": args.get("symbol"), "found": False,
                "note": "No changelog entry: either current in every version, or not a ledgerline symbol."}
    return {"found": True, **e}


def symbol_exists(args):
    return S.status(args.get("symbol", ""), args.get("sdk_version") or S.CURRENT)


def check_code(args):
    return codecheck.check(args.get("code", ""), args.get("sdk_version") or S.CURRENT)


TOOLS = [
    ("search_sdk_docs",
     "Search the ledgerline Python SDK docs, migration guide, changelog and runnable samples "
     "for ONE sdk_version. Pages from other versions are filtered out in code. Returns the best "
     "chunks with their doc URL and the version each belongs to. Use it to find HOW to do a task.",
     {"type": "object", "properties": {"query": {"type": "string"}, "sdk_version": VERSION_PROP,
                                       "k": {"type": "integer", "default": 4}},
      "required": ["query", "sdk_version"]}, search_sdk_docs),
    ("lookup_changelog",
     "Look up ONE SDK symbol (e.g. 'client.query', 'Client', 'RateLimited') in the CHANGELOG: "
     "version added, deprecated, removed, and its replacement. Use it to surface deprecations.",
     {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
     lookup_changelog),
    ("symbol_exists",
     "Check whether ONE symbol (method, class, exception) exists in the caller's sdk_version, "
     "with its valid parameters and required ones. Use it BEFORE writing code that calls it.",
     {"type": "object", "properties": {"symbol": {"type": "string"}, "sdk_version": VERSION_PROP},
      "required": ["symbol", "sdk_version"]}, symbol_exists),
    ("check_code",
     "Parse a Python snippet and check every ledgerline import, method and keyword argument "
     "against the symbol table of sdk_version. Returns errors (empty list = it would run).",
     {"type": "object", "properties": {"code": {"type": "string"}, "sdk_version": VERSION_PROP},
      "required": ["code", "sdk_version"]}, check_code),
]


class TracedServer(MCPServer):
    def _handle_tools_call(self, params):
        meta = params.get("_meta") or {}
        tid = meta.get("trace_id") or new_trace_id()
        t = time.perf_counter()
        out = super()._handle_tools_call(params)
        write_line({"kind": "mcp_server_span", "trace_id": tid,
                    "span": f"mcp.server.{params.get('name')}",
                    "arguments": params.get("arguments", {}),
                    "latency_s": round(time.perf_counter() - t, 4), "cost_usd": 0.0,
                    "is_error": out.get("isError", False),
                    "trace_id_source": "client" if meta.get("trace_id") else "server_minted"})
        return out


def build() -> TracedServer:
    srv = TracedServer("ledgerline-sdk-docs", "1.0.0")
    for name, desc, schema, fn in TOOLS:
        srv.register_tool(name, desc, schema, fn)
    return srv


if __name__ == "__main__":
    build().run_stdio()
