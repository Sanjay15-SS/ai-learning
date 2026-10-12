"""Server 2: DevRel's Package Registry MCP Server.

Exposes tools over the package registry:
- get_package_version_metadata: version metadata, dependencies, license
- get_package_release_dates: release history and publish dates
- get_package_deprecation_notices: deprecation status, sunset schedule, upgrade guidance
"""
import sys
from typing import Any, Dict, Optional

from week9.mcp_protocol import MCPServer

# Mock registry database
PACKAGES_DB = {
    "ledgerline": {
        "latest_version": "3.2.0",
        "description": "Official Ledgerline Payments SDK for Python",
        "homepage": "https://ledgerline.example/docs/sdk/python",
        "license": "MIT",
        "python_requires": ">=3.9",
        "dependencies": {
            "requests": ">=2.28.0",
            "urllib3": ">=1.26.0",
            "pydantic": ">=2.0.0"
        },
        "releases": {
            "1.0.0": "2023-01-15T10:00:00Z",
            "1.4.2": "2023-05-20T14:30:00Z",
            "2.0.0": "2023-08-10T09:15:00Z",
            "2.4.1": "2024-02-18T16:45:00Z",
            "3.0.0": "2024-06-01T11:00:00Z",
            "3.1.0": "2024-07-15T08:20:00Z",
            "3.2.0": "2024-09-20T12:00:00Z"
        },
        "deprecations": [
            {
                "version_pattern": "<2.0.0",
                "status": "end_of_life",
                "notice": "SDK v1.x is End of Life as of 2024-01-01. Security patches no longer provided.",
                "upgrade_path": "Upgrade to v3.2.0. Replace charge token creation with payment intent."
            },
            {
                "version_pattern": "2.x",
                "status": "deprecated",
                "notice": "SDK v2.x is deprecated as of 2024-06-01. Sunset deadline is 2024-12-31.",
                "upgrade_path": "Migrate to SDK v3.2.0. Legacy Charges API (/v2/charges) replaced by PaymentIntents (/v3/payment_intents)."
            }
        ]
    },
    "ledgerline-python": {
        "latest_version": "3.2.0",
        "description": "Ledgerline Python Client Package (alias to ledgerline)",
        "homepage": "https://ledgerline.example/docs/sdk/python",
        "license": "MIT",
        "python_requires": ">=3.9",
        "dependencies": {
            "requests": ">=2.28.0",
            "urllib3": ">=1.26.0"
        },
        "releases": {
            "2.0.0": "2023-08-10T09:15:00Z",
            "2.4.1": "2024-02-18T16:45:00Z",
            "3.0.0": "2024-06-01T11:00:00Z",
            "3.2.0": "2024-09-20T12:00:00Z"
        },
        "deprecations": [
            {
                "version_pattern": "<3.0.0",
                "status": "deprecated",
                "notice": "SDK v2.x is deprecated; use v3.2.0 for PaymentIntents API support.",
                "upgrade_path": "Upgrade to >=3.2.0"
            }
        ]
    }
}


def get_package_version_metadata(package_name: str) -> Dict[str, Any]:
    """Return version metadata for a package."""
    pkg = PACKAGES_DB.get(package_name.lower().strip())
    if not pkg:
        return {
            "error": f"Package '{package_name}' not found in registry",
            "available_packages": list(PACKAGES_DB.keys())
        }
    return {
        "package_name": package_name,
        "latest_version": pkg["latest_version"],
        "description": pkg["description"],
        "homepage": pkg["homepage"],
        "license": pkg["license"],
        "python_requires": pkg["python_requires"],
        "dependencies": pkg["dependencies"],
    }


def get_package_release_dates(package_name: str) -> Dict[str, Any]:
    """Return release date history for a package."""
    pkg = PACKAGES_DB.get(package_name.lower().strip())
    if not pkg:
        return {
            "error": f"Package '{package_name}' not found in registry",
            "available_packages": list(PACKAGES_DB.keys())
        }
    return {
        "package_name": package_name,
        "latest_version": pkg["latest_version"],
        "release_dates": pkg["releases"]
    }


def get_package_deprecation_notices(package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Return deprecation notices and upgrade guidelines for a package."""
    pkg = PACKAGES_DB.get(package_name.lower().strip())
    if not pkg:
        return {
            "error": f"Package '{package_name}' not found in registry",
            "available_packages": list(PACKAGES_DB.keys())
        }
    return {
        "package_name": package_name,
        "queried_version": version,
        "deprecation_notices": pkg["deprecations"]
    }


def create_registry_server() -> MCPServer:
    server = MCPServer(name="package-registry", version="1.0.0")

    server.register_tool(
        name="get_package_version_metadata",
        description=(
            "Retrieve package metadata, latest published version, dependencies, license, "
            "and runtime requirements from DevRel's package registry."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string",
                    "description": "Name of the package, e.g. 'ledgerline' or 'ledgerline-python'"
                }
            },
            "required": ["package_name"]
        },
        handler=lambda args: get_package_version_metadata(args.get("package_name", ""))
    )

    server.register_tool(
        name="get_package_release_dates",
        description=(
            "Retrieve the complete release history timeline and publication dates for "
            "all versions of a package from the registry."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string",
                    "description": "Name of the package"
                }
            },
            "required": ["package_name"]
        },
        handler=lambda args: get_package_release_dates(args.get("package_name", ""))
    )

    server.register_tool(
        name="get_package_deprecation_notices",
        description=(
            "Query official deprecation warnings, sunset timelines, and migration paths "
            "for specific package versions in DevRel's package registry."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string",
                    "description": "Name of the package"
                },
                "version": {
                    "type": "string",
                    "description": "Optional version string to inspect"
                }
            },
            "required": ["package_name"]
        },
        handler=lambda args: get_package_deprecation_notices(
            args.get("package_name", ""),
            args.get("version")
        )
    )

    return server


if __name__ == "__main__":
    server = create_registry_server()
    server.run_stdio()
