"""MCP (Model Context Protocol) JSON-RPC 2.0 stdio protocol engine.

Provides:
- MCPServer: base class for stdio-driven JSON-RPC 2.0 servers.
- MCPClient: subprocess stdio client with wire message tracing and request-response handling.
Conforms to MCP protocolVersion '2024-11-05'.
"""
import json
import os
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """Stdio-based MCP JSON-RPC 2.0 server."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "initialize": self._handle_initialize,
            "notifications/initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": lambda params: {},
        }

    def register_tool(self, name: str, description: str, input_schema: dict, handler: Callable[[dict], Any]) -> None:
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "_handler": handler,
        }

    def _handle_initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False}
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            }
        }

    def _handle_initialized(self, params: dict) -> None:
        return None

    def _handle_tools_list(self, params: dict) -> dict:
        tool_specs = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in self.tools.values()
        ]
        return {"tools": tool_specs}

    def _handle_tools_call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in self.tools:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": f"Tool '{name}' not found on server {self.name}"})}],
                "isError": True,
            }
        try:
            handler = self.tools[name]["_handler"]
            res = handler(arguments)
            text_out = res if isinstance(res, str) else json.dumps(res, indent=2)
            is_err = isinstance(res, dict) and "error" in res
            return {
                "content": [{"type": "text", "text": text_out}],
                "isError": is_err,
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "isError": True,
            }

    def run_stdio(self) -> None:
        """Run the server reading JSON-RPC lines from stdin and writing to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"}
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            # Notifications have no id
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method not in self.handlers:
                if req_id is not None:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                    sys.stdout.write(json.dumps(err_resp) + "\n")
                    sys.stdout.flush()
                continue

            try:
                result = self.handlers[method](params)
                if req_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": result
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                if req_id is not None:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": f"Internal error: {e}"}
                    }
                    sys.stdout.write(json.dumps(err_resp) + "\n")
                    sys.stdout.flush()


class MCPClient:
    """Subprocess stdio client for an MCP server."""

    def __init__(self, name: str, command: str, args: List[str], cwd: Optional[str] = None):
        self.name = name
        self.command = command
        self.args = args
        self.cwd = cwd
        self.proc: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self.wire_trace: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        cmd = [self.command] + self.args
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self.cwd,
            env=env
        )

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def send_request(self, method: str, params: Optional[dict] = None) -> dict:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError(f"Server {self.name} is not running")

        msg_id = self._next_id()
        req: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            req["params"] = params

        line = json.dumps(req)
        self.wire_trace.append({"direction": "out", "server": self.name, "message": req})

        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

        resp_line = self.proc.stdout.readline()
        if not resp_line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"Server {self.name} closed stdout unexpectedly. Stderr: {err}")

        resp = json.loads(resp_line.strip())
        self.wire_trace.append({"direction": "in", "server": self.name, "message": resp})

        if "error" in resp:
            raise RuntimeError(f"MCP error from {self.name}: {resp['error']}")
        return resp.get("result", {})

    def send_notification(self, method: str, params: Optional[dict] = None) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError(f"Server {self.name} is not running")

        notif: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notif["params"] = params

        line = json.dumps(notif)
        self.wire_trace.append({"direction": "out", "server": self.name, "message": notif})

        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def initialize(self, client_info: Optional[dict] = None) -> dict:
        params = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": client_info or {"name": "ledgerline-docs-agent", "version": "1.0.0"}
        }
        res = self.send_request("initialize", params)
        self.send_notification("notifications/initialized")
        return res

    def list_tools(self) -> List[dict]:
        res = self.send_request("tools/list")
        return res.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        params = {
            "name": name,
            "arguments": arguments
        }
        return self.send_request("tools/call", params)

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
            self.proc = None
