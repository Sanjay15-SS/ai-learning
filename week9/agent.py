"""The Week 9 MCP Agent: Dynamic Tool Discovery across configured MCP servers.

Requirements Met:
- Server discovery is 100% dynamic via config ('mcpServers' object) and JSON-RPC tools/list.
- ZERO lines of code in this agent module change when adding, removing, or swapping servers.
- Supports budget enforcement, multi-server tool routing, and clean termination.
"""
import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src import LOGS, ROOT, llm
from src.contract import CONTRACT
from week9.mcp_protocol import MCPClient

SYSTEM = (
    "You answer questions about the Ledgerline API, its SDKs, packages, and migration. "
    "You discover tools dynamically from configured MCP servers. "
    "Before writing code or final answers: search docs, inspect OpenAPI specs, check deprecations, "
    "and look up package version metadata when packages or SDKs are referenced.\n\n"
    + CONTRACT
)


@dataclass
class Budget:
    max_iters: int = 8
    max_tokens: int = 80_000
    max_cost_usd: float = 0.60
    max_wall_s: float = 180.0

    def check(self, laps: int, usage: llm.Usage, elapsed: float, next_est: int = 0) -> Optional[str]:
        if laps >= self.max_iters:
            return f"max_iters ({laps}/{self.max_iters} laps)"
        if usage.total_tokens + next_est >= self.max_tokens:
            return f"max_tokens ({usage.total_tokens:,} used + ~{next_est:,} next >= {self.max_tokens:,})"
        if usage.cost_usd >= self.max_cost_usd:
            return f"max_cost (${usage.cost_usd:.4f} >= ${self.max_cost_usd:.2f})"
        if elapsed >= self.max_wall_s:
            return f"max_wall ({elapsed:.1f}s >= {self.max_wall_s:.0f}s)"
        return None


class MCPAgentSession:
    """Manages MCP server subprocess lifecycles and tool routing for the agent."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.clients: Dict[str, MCPClient] = {}
        self.tool_to_client: Dict[str, MCPClient] = {}
        self.discovered_tools: List[Dict[str, Any]] = []
        self._load_and_connect()

    def _load_and_connect(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"MCP config file not found: {self.config_path}")

        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        servers = config.get("mcpServers", {})

        for srv_name, srv_conf in servers.items():
            cmd = srv_conf.get("command", sys.executable)
            args = srv_conf.get("args", [])
            client = MCPClient(
                name=srv_name,
                command=cmd,
                args=args,
                cwd=str(ROOT)
            )
            client.start()
            client.initialize()
            self.clients[srv_name] = client

            # Discover tools dynamically from tools/list
            tools = client.list_tools()
            for t in tools:
                tool_name = t["name"]
                self.tool_to_client[tool_name] = client
                # Adapt MCP inputSchema to Anthropic format
                anthropic_tool = {
                    "name": tool_name,
                    "description": t.get("description", ""),
                    "input_schema": t.get("inputSchema", {"type": "object", "properties": {}})
                }
                self.discovered_tools.append(anthropic_tool)

    def close(self) -> None:
        for client in self.clients.values():
            client.close()

    def call_tool(self, tool_name: str, arguments: dict) -> Tuple[str, bool]:
        client = self.tool_to_client.get(tool_name)
        if not client:
            return json.dumps({"error": f"Tool '{tool_name}' not found on any connected MCP server"}), True
        res = client.call_tool(tool_name, arguments)
        content_items = res.get("content", [])
        text_parts = [c.get("text", "") for c in content_items if c.get("type") == "text"]
        out_text = "\n".join(text_parts) if text_parts else json.dumps(res)
        return out_text, res.get("isError", False)


def run_agent(question: str, config_path: str, budget: Budget = Budget(),
              log: Callable[[str], None] = print) -> dict:
    """Run agent against MCP servers specified in config_path. ZERO code changes between configs."""
    t0 = time.perf_counter()
    usage = llm.Usage()
    messages = [{"role": "user", "content": question}]
    steps, laps, next_est = [], 0, 0
    final, status = "", "done"

    session = MCPAgentSession(config_path)
    log(f"[start] {question}")
    log(f"[mcp] Discovered {len(session.discovered_tools)} tools from {len(session.clients)} server(s): "
        f"{[t['name'] for t in session.discovered_tools]}")

    try:
        while True:
            stop = budget.check(laps, usage, time.perf_counter() - t0, next_est)
            if stop:
                status = "budget:" + stop.split(" ")[0]
                log(f"[stop] budget fired: {stop}. Terminating cleanly after {laps} laps.")
                break

            remaining_wall = budget.max_wall_s - (time.perf_counter() - t0)
            out_cap = max(256, min(8000, budget.max_tokens - usage.total_tokens - next_est))
            r = llm.create(usage, system=SYSTEM, messages=messages,
                           tools=session.discovered_tools,
                           max_tokens=out_cap, timeout=remaining_wall)
            laps += 1
            calls = [b for b in r.content if getattr(b, "type", "") == "tool_use"]
            log(f"[lap {laps}] stop_reason={r.stop_reason} tool_calls={len(calls)} "
                f"in={r.usage.input_tokens} out={r.usage.output_tokens} | total "
                f"{usage.total_tokens:,} tok ${usage.cost_usd:.4f} {time.perf_counter() - t0:.1f}s")

            if r.stop_reason == "refusal":
                status = "refused"
                break
            if r.stop_reason == "max_tokens":
                final, status = llm.text_of(r), "truncated"
                break
            if r.stop_reason in ("end_turn", "stop_sequence") or not calls:
                final = llm.text_of(r)
                break

            messages.append({"role": "assistant", "content": r.content})
            results = []
            for b in calls:
                srv = session.tool_to_client[b.name].name if b.name in session.tool_to_client else "unknown"
                out, is_err = session.call_tool(b.name, dict(b.input))
                steps.append({
                    "lap": laps,
                    "server": srv,
                    "tool": b.name,
                    "input": dict(b.input),
                    "output_chars": len(out),
                    "is_error": is_err
                })
                log(f"    -> [{srv}] {b.name}({json.dumps(dict(b.input))}) => {out[:140]}"
                    + ("..." if len(out) > 140 else ""))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})

            messages.append({"role": "user", "content": results})
            next_est = (r.usage.input_tokens + r.usage.output_tokens
                        + sum(len(x["content"]) for x in results) // 3)
    finally:
        session.close()

    latency = time.perf_counter() - t0
    log(f"[end] status={status} laps={laps} tools={len(steps)} tokens={usage.total_tokens:,} "
        f"cost=${usage.cost_usd:.4f} latency={latency:.1f}s")

    return {
        "system": "mcp_agent",
        "question": question,
        "answer": final,
        "status": status,
        "laps": laps,
        "steps": steps,
        "latency_s": round(latency, 3),
        "usage": usage.as_dict(),
        "discovered_tools": [t["name"] for t in session.discovered_tools]
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Week 9 MCP Agent with Dynamic Tool Discovery")
    ap.add_argument("question", nargs="?", default="What is the latest published version of ledgerline-python?")
    ap.add_argument("--config", default="week9/config_server1_plus_2.json", help="Path to MCP config JSON")
    ap.add_argument("--max-iters", type=int, default=Budget.max_iters)
    ap.add_argument("--max-tokens", type=int, default=Budget.max_tokens)
    ap.add_argument("--max-cost", type=float, default=Budget.max_cost_usd)
    ap.add_argument("--max-wall", type=float, default=Budget.max_wall_s)
    args = ap.parse_args()

    budget = Budget(args.max_iters, args.max_tokens, args.max_cost, args.max_wall)
    res = run_agent(args.question, args.config, budget)
    print("\n--- Final Answer ---")
    print(res["answer"])


if __name__ == "__main__":
    main()
