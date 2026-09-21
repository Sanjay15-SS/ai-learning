"""The agent's tools: implementations, plus the tool definitions the model sees.

TOOLS_TWO is the loop as it started: two tools whose descriptions overlap ("docs",
"spec", "endpoints" in both), so the model could not tell which one to call.
TOOLS_THREE sharpens those two and adds check_deprecation. Each now names exactly one
job and says what it does NOT return. `python3 -m week7.agent --tool-diff` prints the diff.
"""
import json
import re
from typing import Optional

from . import API_VERSIONS
from .corpus import changelog, search, spec

METHODS = ("GET", "POST", "DELETE")


# --------------------------------------------------------------------------
# implementations - identical for the agent and the workflow
# --------------------------------------------------------------------------

def search_docs(query: str, api_version: str) -> dict:
    hits = search(query, api_version=api_version, k=3)
    return {"api_version": api_version, "results": [
        {"page_id": p.page_id, "title": p.title, "endpoints": p.endpoints, "text": p.body}
        for p in hits]}


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path.strip().rstrip("/"))


def match_path(path: str, version: str) -> Optional[str]:
    """Resolve a written path (templated or with a real id) to a spec path."""
    want = _norm(path).split("/")
    for p in spec(version)["paths"]:
        have = _norm(p).split("/")
        if len(have) == len(want) and all(h == w or h == "{}" for h, w in zip(have, want)):
            return p
    return None


def get_openapi_spec(method: str, path: str, api_version: str) -> dict:
    real = match_path(path, api_version)
    if real is None:
        return {"error": f"{path} is not a path in the {api_version} spec",
                "paths": sorted(spec(api_version)["paths"])}
    ops = spec(api_version)["paths"][real]
    m = method.lower()
    if m not in ops:
        return {"error": f"{method} is not defined on {real} in {api_version}",
                "methods": sorted(k.upper() for k in ops)}
    return {"api_version": api_version, "method": method.upper(), "path": real, "operation": ops[m]}


def check_deprecation(symbol: str, api_version: str) -> dict:
    s = symbol.strip().lower()
    for e in changelog():
        sym = e["symbol"].lower()
        bare = sym.split(" ", 1)[-1]
        if s in (sym, bare) or (s.startswith("/") and _norm(s) == _norm(bare)):
            if api_version == "v2":
                return {"symbol": e["symbol"], "status": "current in v2",
                        "note": f"{e['status']} in v3 -> {e['replacement']}"}
            return {"symbol": e["symbol"], "status": e["status"], "since": e["since"],
                    "replacement": e["replacement"], "note": e["note"]}
    return {"symbol": symbol, "status": "not deprecated",
            "note": f"no changelog entry for this symbol in {api_version}"}


IMPLS = {"search_docs": search_docs, "get_openapi_spec": get_openapi_spec,
         "check_deprecation": check_deprecation}


def run_tool(name: str, args: dict) -> str:
    """Execute one tool call. Bad input comes back as an error result, never a crash."""
    fn = IMPLS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        if "method" not in args and name == "get_openapi_spec":
            args = {**args, "method": "GET"}          # the two-tool definition had no method
        if args.get("api_version") not in API_VERSIONS:
            return json.dumps({"error": f"api_version must be one of {list(API_VERSIONS)}"})
        return json.dumps(fn(**args))
    except TypeError as e:
        return json.dumps({"error": f"bad arguments for {name}: {e}"})


# --------------------------------------------------------------------------
# what the model sees
# --------------------------------------------------------------------------

TOOLS_TWO = [
    {"name": "search_docs",
     "description": "Search the Ledgerline API documentation and specification for "
                    "information about endpoints, parameters and versions.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "api_version": {"type": "string", "description": "API version"}},
         "required": ["query", "api_version"]}},
    {"name": "get_openapi_spec",
     "description": "Get API reference information for an endpoint, including docs and "
                    "details about the API.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "api_version": {"type": "string", "description": "API version"}},
         "required": ["path", "api_version"]}},
]

TOOLS_THREE = [
    {"name": "search_docs",
     "description": "Full-text search over the prose guide pages of ONE api_version. Returns "
                    "the 3 best pages (id, title, endpoints listed on the page, text). Use it "
                    "to find which endpoint does a task. It does not return parameter "
                    "schemas and does not report deprecations.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "what the developer wants to do"},
         "api_version": {"type": "string", "enum": list(API_VERSIONS)}},
         "required": ["query", "api_version"], "additionalProperties": False}},
    {"name": "get_openapi_spec",
     "description": "Return the OpenAPI operation for ONE exact method + path in ONE "
                    "api_version: path/query/header parameters, required body fields, "
                    "deprecated flag. Needs an exact path such as /v3/refunds; it does not "
                    "search and does not say what replaces a deprecated operation.",
     "input_schema": {"type": "object", "properties": {
         "method": {"type": "string", "enum": list(METHODS)},
         "path": {"type": "string", "description": "e.g. /v3/payment_intents/{intent_id}"},
         "api_version": {"type": "string", "enum": list(API_VERSIONS)}},
         "required": ["method", "path", "api_version"], "additionalProperties": False}},
    {"name": "check_deprecation",
     "description": "Look up ONE symbol - an endpoint ('POST /v2/charges'), parameter "
                    "('source'), header or event name - in the v2->v3 changelog. Returns "
                    "whether it is deprecated, removed or renamed in api_version and what "
                    "replaces it. It returns no docs text and no schema.",
     "input_schema": {"type": "object", "properties": {
         "symbol": {"type": "string"},
         "api_version": {"type": "string", "enum": list(API_VERSIONS)}},
         "required": ["symbol", "api_version"], "additionalProperties": False}},
]
