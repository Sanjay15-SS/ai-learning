"""Structured observability layer for the Ledgerline docs assistant.

Each request is written as a JSON-L trace record enriched with:
  - trace_id, ts, prompt_version, app, question
  - per-span latency (retrieval_s, llm_s, total_s)
  - token counts and cost_usd broken down by stage (retrieval, generation, tools)
  - retrieved page ids (context_ids)
  - output_text  ← the full generated answer (indexed for output-content search)
  - assertions result
  - input_type  (code_request | conceptual | version_migration | refusal_expected)

Having output_text indexed ends the "deprecated call is in the *output*, not the
question" mystery that the Common Mistakes section warns about.
"""
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src import TRACES

# -----------------------------------------------------------------------------
# Prompt version registry.  Bump this whenever the system prompt changes.
# -----------------------------------------------------------------------------
PROMPT_VERSION = "v1"


def _trace_id() -> str:
    return "trc11_" + uuid.uuid4().hex[:10]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


INPUT_TYPE_PATTERNS = [
    ("code_request", re.compile(r"\b(code|function|snippet|python|example|write|show)\b", re.I)),
    ("version_migration", re.compile(r"\bv[23]\b|migrat|replac|deprecat|moving to", re.I)),
    ("refusal_expected", re.compile(r"\b(sandbox|apple pay|graphql|rust sdk|payout)\b", re.I)),
]


def classify_input(question: str) -> str:
    for label, pat in INPUT_TYPE_PATTERNS:
        if pat.search(question):
            return label
    return "conceptual"


# ---------------------------------------------------------------------------
# Cost breakdown helpers
# ---------------------------------------------------------------------------

def cost_by_stage(usage_dict: dict, retrieval_hits: int = 4) -> dict:
    """Split total cost into three buckets.

    Retrieval is pure Python BM25 (no LLM call) — its cost is $0.
    Tools are embedded in the single LLM call; we attribute 10 % of input
    tokens to 'tools' (system prompt + tool definitions overhead) and the
    remaining 90 % to 'generation'.
    """
    total_cost = usage_dict.get("cost_usd", 0.0)
    retrieval_cost = 0.0            # BM25 — no model call
    tool_fraction = 0.10            # ~10 % of prompt tokens are tool defs
    tools_cost = round(total_cost * tool_fraction, 9)
    generation_cost = round(total_cost - tools_cost, 9)
    return {
        "retrieval_usd": retrieval_cost,
        "generation_usd": generation_cost,
        "tools_usd": tools_cost,
        "total_usd": round(total_cost, 9),
    }


# ---------------------------------------------------------------------------
# Span-level timing
# ---------------------------------------------------------------------------

class Tracer:
    """Wraps a single request and records per-span timing."""

    def __init__(self, question: str, app: str = "v1",
                 prompt_version: str = PROMPT_VERSION):
        self.trace_id = _trace_id()
        self.ts = _now_iso()
        self.question = question
        self.app = app
        self.prompt_version = prompt_version
        self.input_type = classify_input(question)
        self._t_start = time.perf_counter()
        self._t_after_retrieval: Optional[float] = None
        self._t_after_llm: Optional[float] = None
        self.context_ids: list = []
        self.usage: dict = {}
        self.output_text: str = ""
        self.assertions: dict = {}
        self.assertions_pass: bool = False
        self.stop_reason: str = ""

    def mark_retrieval_done(self, hits) -> None:
        self._t_after_retrieval = time.perf_counter()
        self.context_ids = [p.page_id for p in hits]

    def mark_llm_done(self, response_text: str, usage: dict, stop_reason: str) -> None:
        self._t_after_llm = time.perf_counter()
        self.output_text = response_text
        self.usage = usage
        self.stop_reason = stop_reason

    def mark_assertions(self, assertions: dict, assertions_pass: bool) -> None:
        self.assertions = assertions
        self.assertions_pass = assertions_pass

    def to_record(self) -> dict:
        t0 = self._t_start
        t1 = self._t_after_retrieval or t0
        t2 = self._t_after_llm or t1
        retrieval_s = round(t1 - t0, 3)
        llm_s = round(t2 - t1, 3)
        total_s = round(t2 - t0, 3)
        return {
            "trace_id": self.trace_id,
            "ts": self.ts,
            "prompt_version": self.prompt_version,
            "app": self.app,
            "question": self.question,
            "input_type": self.input_type,
            "context_ids": self.context_ids,
            "output_text": self.output_text,
            "stop_reason": self.stop_reason,
            "spans": {
                "retrieval_s": retrieval_s,
                "llm_s": llm_s,
                "total_s": total_s,
            },
            "usage": self.usage,
            "cost_by_stage": cost_by_stage(self.usage, len(self.context_ids)),
            "assertions": self.assertions,
            "assertions_pass": self.assertions_pass,
        }


# ---------------------------------------------------------------------------
# Structured trace log
# ---------------------------------------------------------------------------

STRUCTURED_LOG = TRACES / "traces_w11.jsonl"


def write_trace(record: dict, path: Path = STRUCTURED_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_traces(path: Path = STRUCTURED_LOG) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
