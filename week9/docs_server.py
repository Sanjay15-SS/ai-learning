"""Server 1: Ledgerline Docs Search MCP Server.

Discovers tools from the local documentation corpus.
Includes Requirement 5:
- Tool docstring rewritten as a prompt
- Recoverable error path for non-existent versions (e.g. v4.x -> explains latest is v3.2,
  lists valid versions, points to migration guide).
"""
import sys
from typing import Any, Dict

from src import API_VERSIONS
from src.tools import check_deprecation, get_openapi_spec, search_docs
from week9.mcp_protocol import MCPServer

# Docstring rewritten as prompt for get_openapi_spec (Requirement 5)
GET_OPENAPI_SPEC_DOCSTRING_PROMPT = (
    "Retrieve the exact OpenAPI operation specification for a method and path in the "
    "Ledgerline API. You must specify a valid API version ('v2' or 'v3') and an exact path. "
    "Note: Ledgerline API v4.x is unreleased; latest available is v3.2. If the user asks for v4, "
    "examine v3 endpoints or check changelog notes."
)


def recoverable_get_openapi_spec(method: str, path: str, api_version: str) -> Dict[str, Any]:
    """Execute get_openapi_spec with a recoverable error path for v4/unsupported versions."""
    v = str(api_version).strip().lower()
    if v == "v4" or v.startswith("v4") or v not in API_VERSIONS:
        # Recoverable error path (Requirement 5)
        return {
            "error": "no docs for v4.x: latest published is v3.2, deprecated methods listed under v3.2/migration",
            "latest_published_version": "v3.2",
            "valid_versions": list(API_VERSIONS),
            "recovery_hint": (
                "Ledgerline v4 does not exist. The latest published release is v3.2. "
                "Query get_openapi_spec with api_version='v3' or use search_docs with api_version='v3' "
                "and check_deprecation for migration details."
            )
        }
    return get_openapi_spec(method=method, path=path, api_version=v)


def unrecoverable_get_openapi_spec(method: str, path: str, api_version: str) -> Dict[str, Any]:
    """Old unrecoverable error path returning a cryptic code/error message."""
    v = str(api_version).strip().lower()
    if v not in API_VERSIONS:
        return {"error": "Error 3: invalid version"}
    return get_openapi_spec(method=method, path=path, api_version=v)


def create_docs_server(recoverable: bool = True) -> MCPServer:
    server = MCPServer(name="docs-search", version="1.0.0")

    server.register_tool(
        name="search_docs",
        description=(
            "Full-text search over the prose guide pages of ONE api_version ('v2' or 'v3'). "
            "Returns the 3 best pages (id, title, endpoints listed on the page, text). "
            "Use it to find which endpoint does a task."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "what the developer wants to do"},
                "api_version": {"type": "string", "enum": list(API_VERSIONS)}
            },
            "required": ["query", "api_version"]
        },
        handler=lambda args: search_docs(args.get("query", ""), args.get("api_version", "v3"))
    )

    spec_fn = recoverable_get_openapi_spec if recoverable else unrecoverable_get_openapi_spec
    server.register_tool(
        name="get_openapi_spec",
        description=GET_OPENAPI_SPEC_DOCSTRING_PROMPT,
        input_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "DELETE"]},
                "path": {"type": "string", "description": "e.g. /v3/payment_intents"},
                "api_version": {"type": "string", "description": "API version: 'v2' or 'v3'"}
            },
            "required": ["method", "path", "api_version"]
        },
        handler=lambda args: spec_fn(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("api_version", "v3")
        )
    )

    server.register_tool(
        name="check_deprecation",
        description=(
            "Look up ONE symbol - an endpoint ('POST /v2/charges'), parameter ('source'), "
            "header or event name - in the v2->v3 changelog. Returns whether it is deprecated, "
            "removed or renamed in api_version and what replaces it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "symbol or endpoint"},
                "api_version": {"type": "string", "enum": list(API_VERSIONS)}
            },
            "required": ["symbol", "api_version"]
        },
        handler=lambda args: check_deprecation(args.get("symbol", ""), args.get("api_version", "v3"))
    )

    return server


if __name__ == "__main__":
    recoverable_mode = "--unrecoverable" not in sys.argv
    server = create_docs_server(recoverable=recoverable_mode)
    server.run_stdio()
