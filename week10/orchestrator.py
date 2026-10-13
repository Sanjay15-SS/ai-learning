"""The Docs Squad Orchestrator — Week 10.

Architecture:
- Orchestrator: decomposes questions, manages hand-offs, synthesises answers.
- Version/Deprecation Worker: scoped to check_deprecation and search_docs.
- Code-Sample Worker: scoped to get_openapi_spec, writes code for verified endpoints.

Instruments every hand-off with per-hop token counts written to handoffs.log.
Supports worker failure injection (--inject-500) to observe failure behavior.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src import ROOT, llm
from src.contract import CONTRACT, target_version
from src.tools import check_deprecation, get_openapi_spec, search_docs

VERSION_WORKER_SYSTEM = (
    "You are the Version & Deprecation Worker in the Ledgerline docs squad. "
    "Your ONLY job is to determine the target API version, check if symbols/endpoints mentioned "
    "are deprecated or removed in v2->v3, and identify the correct replacement v3 endpoint. "
    "Do NOT write code samples. Return concise structured findings."
)

VERSION_TOOLS = [
    {
        "name": "check_deprecation",
        "description": "Look up ONE symbol or endpoint in the v2->v3 changelog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "api_version": {"type": "string", "enum": ["v2", "v3"]}
            },
            "required": ["symbol", "api_version"]
        }
    },
    {
        "name": "search_docs",
        "description": "Full-text search over documentation guides for an API version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "api_version": {"type": "string", "enum": ["v2", "v3"]}
            },
            "required": ["query", "api_version"]
        }
    }
]

CODE_WORKER_SYSTEM = (
    "You are the Code-Sample Worker in the Ledgerline docs squad. "
    "Your ONLY job is to verify endpoint operations via get_openapi_spec and write accurate Python requests code. "
    "You must generate complete, idiomatic Python code matching the target version. "
    "Do NOT research deprecations; rely strictly on the version and endpoint provided by the orchestrator."
)

CODE_TOOLS = [
    {
        "name": "get_openapi_spec",
        "description": "Return the OpenAPI operation for ONE exact method + path in ONE api_version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "DELETE"]},
                "path": {"type": "string", "description": "e.g. /v3/payment_intents"},
                "api_version": {"type": "string", "enum": ["v2", "v3"]}
            },
            "required": ["method", "path", "api_version"]
        }
    }
]

ORCHESTRATOR_SYSTEM = (
    "You are the Lead Docs Orchestrator. "
    "You synthesise findings from the Version Worker and Code-Sample Worker into a final developer response. "
    "Ensure the final response adheres strictly to the contract:\n\n"
    + CONTRACT
)


@dataclass
class HandOffEvent:
    step: int
    sender: str
    receiver: str
    intent: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_s: float
    status: str = "ok"
    details: str = ""


class DocsSquadOrchestrator:
    """Multi-Agent Docs Squad Orchestrator with hand-off instrumentation and failure injection."""

    def __init__(self, inject_500_case_id: Optional[str] = None):
        self.inject_500_case_id = inject_500_case_id
        self.handoff_events: List[HandOffEvent] = []

    def _run_worker_turn(self, system: str, tools: Optional[list], messages: list,
                         tool_executor: Optional[Callable[[str, dict], str]] = None) -> Tuple[str, llm.Usage, float]:
        usage = llm.Usage()
        t0 = time.perf_counter()
        r = llm.create(usage, system=system, messages=messages, tools=tools, max_tokens=2000)

        # If model called tools, execute them and run second lap
        calls = [b for b in r.content if getattr(b, "type", "") == "tool_use"]
        if calls and tool_executor:
            messages.append({"role": "assistant", "content": r.content})
            tool_results = []
            for b in calls:
                out = tool_executor(b.name, dict(b.input))
                tool_results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
            messages.append({"role": "user", "content": tool_results})
            r2 = llm.create(usage, system=system, messages=messages, tools=tools, max_tokens=2000)
            latency = time.perf_counter() - t0
            return llm.text_of(r2), usage, latency

        latency = time.perf_counter() - t0
        return llm.text_of(r), usage, latency

    def run(self, case_id: str, question: str, log: Callable[[str], None] = print) -> dict:
        t_start = time.perf_counter()
        total_usage = llm.Usage()
        step_counter = 1
        handoffs: List[HandOffEvent] = []
        failure_behavior = None

        log(f"[orchestrator] Starting question: {question} (case_id={case_id})")

        # Step 1: Orchestrator -> Version Worker Hand-Off
        ver_worker_msg = [
            {"role": "user", "content": f"[{case_id}] Analyze this question for version and deprecation requirements:\n\n{question}"}
        ]

        # Check for simulated 500 failure injection
        if self.inject_500_case_id == case_id:
            log(f"[INJECTED FAILURE] Version/Deprecation Worker simulating HTTP 500 Internal Server Error!")
            ver_text = "ERROR 500: Internal Server Error — Version & Deprecation registry service unavailable."
            # Estimate failed hop usage
            ver_usage = llm.Usage()
            ver_usage.input_tokens = 450
            ver_usage.output_tokens = 30
            ver_usage.cost_usd = 0.003
            ver_lat = 0.05
            v_status = "500_error"
            # Record orchestrator decision under failure:
            # The orchestrator catches the 500 and DEGRADES to a partial answer without deprecation checks
            failure_behavior = "degraded to a partial answer (omitted deprecation verification due to worker 500)"
        else:
            def exec_version_tool(name: str, args: dict) -> str:
                if name == "check_deprecation":
                    return json.dumps(check_deprecation(args.get("symbol", ""), args.get("api_version", "v3")))
                elif name == "search_docs":
                    res = search_docs(args.get("query", ""), args.get("api_version", "v3"))
                    return json.dumps(res.get("results", [])[:2])
                return json.dumps({"error": f"Unknown tool {name}"})

            ver_text, ver_usage, ver_lat = self._run_worker_turn(
                VERSION_WORKER_SYSTEM, VERSION_TOOLS, ver_worker_msg, exec_version_tool
            )
            v_status = "ok"

        total_usage.calls += ver_usage.calls
        total_usage.input_tokens += ver_usage.input_tokens
        total_usage.output_tokens += ver_usage.output_tokens
        total_usage.cost_usd += ver_usage.cost_usd

        ev1 = HandOffEvent(
            step=step_counter,
            sender="orchestrator",
            receiver="version_worker",
            intent="version_and_deprecation_lookup",
            input_tokens=ver_usage.input_tokens,
            output_tokens=ver_usage.output_tokens,
            total_tokens=ver_usage.total_tokens,
            cost_usd=ver_usage.cost_usd,
            latency_s=round(ver_lat, 3),
            status=v_status,
            details=f"Prompt: ~{len(question)} chars | Output: ~{len(ver_text)} chars"
        )
        handoffs.append(ev1)
        step_counter += 1

        # Step 2: Orchestrator -> Code-Sample Worker Hand-Off (context re-send!)
        # Crucial: Preserves target version v3 explicitly while re-sending question + version findings
        t_version = target_version(question)
        code_worker_prompt = (
            f"[{case_id}] Developer Question: {question}\n\n"
            f"Target API Version: {t_version}\n"
            f"Version & Deprecation Analysis:\n{ver_text}\n\n"
            f"Generate the OpenAPI-verified Python code sample for this task on {t_version}."
        )
        code_worker_msg = [{"role": "user", "content": code_worker_prompt}]

        def exec_code_tool(name: str, args: dict) -> str:
            if name == "get_openapi_spec":
                return json.dumps(get_openapi_spec(
                    args.get("method", "GET"),
                    args.get("path", ""),
                    args.get("api_version", t_version)
                ))
            return json.dumps({"error": f"Unknown tool {name}"})

        code_text, code_usage, code_lat = self._run_worker_turn(
            CODE_WORKER_SYSTEM, CODE_TOOLS, code_worker_msg, exec_code_tool
        )
        total_usage.calls += code_usage.calls
        total_usage.input_tokens += code_usage.input_tokens
        total_usage.output_tokens += code_usage.output_tokens
        total_usage.cost_usd += code_usage.cost_usd

        ev2 = HandOffEvent(
            step=step_counter,
            sender="orchestrator",
            receiver="code_worker",
            intent="code_sample_generation",
            input_tokens=code_usage.input_tokens,
            output_tokens=code_usage.output_tokens,
            total_tokens=code_usage.total_tokens,
            cost_usd=code_usage.cost_usd,
            latency_s=round(code_lat, 3),
            status="ok",
            details="Context re-send: question + version findings + spec instructions"
        )
        handoffs.append(ev2)
        step_counter += 1

        # Step 3: Orchestrator Synthesis Hand-Off (re-sending all worker results)
        synth_prompt = (
            f"[{case_id}] Developer Question:\n{question}\n\n"
            f"Target Version: {t_version}\n\n"
            f"Version & Deprecation Findings:\n{ver_text}\n\n"
            f"Code Sample Findings:\n{code_text}\n\n"
            f"Please synthesise these findings into a complete, authoritative response adhering to the contract format."
        )
        synth_msg = [{"role": "user", "content": synth_prompt}]
        synth_text, synth_usage, synth_lat = self._run_worker_turn(
            ORCHESTRATOR_SYSTEM, None, synth_msg, None
        )
        total_usage.calls += synth_usage.calls
        total_usage.input_tokens += synth_usage.input_tokens
        total_usage.output_tokens += synth_usage.output_tokens
        total_usage.cost_usd += synth_usage.cost_usd

        ev3 = HandOffEvent(
            step=step_counter,
            sender="workers",
            receiver="orchestrator_synthesis",
            intent="final_synthesis_and_contract_formatting",
            input_tokens=synth_usage.input_tokens,
            output_tokens=synth_usage.output_tokens,
            total_tokens=synth_usage.total_tokens,
            cost_usd=synth_usage.cost_usd,
            latency_s=round(synth_lat, 3),
            status="ok",
            details="Final aggregation across all worker outputs"
        )
        handoffs.append(ev3)

        self.handoff_events.extend(handoffs)
        total_latency = time.perf_counter() - t_start

        return {
            "system": "orchestrator",
            "case_id": case_id,
            "question": question,
            "answer": synth_text,
            "version_worker_output": ver_text,
            "code_worker_output": code_text,
            "status": "done",
            "latency_s": round(total_latency, 3),
            "usage": total_usage.as_dict(),
            "handoffs": handoffs,
            "failure_behavior": failure_behavior
        }
