Who wrote it: DevRel internal tooling team maintaining the package registry MCP wrapper.
What it can reach: Internal registry metadata API, package release manifests, and local network services.
What it logs: Incoming client JSON-RPC queries, package lookup names, timestamps, and caller IP addresses.
What a stolen token could do: Impersonate package metadata, publish malicious release manifests, or poison SDK dependency resolution.
Ship or don't: Ship with scoped read-only registry credentials, local sandbox isolation, and outbound network filtering.
