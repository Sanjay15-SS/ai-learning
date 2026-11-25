"""Week 11 per-request logging, carried across the agent hop and the MCP hop.

- One trace id per question, minted at the entry point.
- Spans: name, start offset, latency, tokens, cost. The MCP server receives the trace id in
  tools/call `_meta.trace_id` and writes its OWN span lines to the same log with that id.
- PII held at the line: redact() runs on the question BEFORE the model sees it, and again on
  every string at write time (belt and braces). API keys, connection strings, bearer tokens,
  webhook secrets, emails, passwords.
"""
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import TRACE_LOG

REDACTIONS = [
    (re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@]+@[^\s'\"]+", re.I), "[REDACTED_CONN_STRING]"),
    (re.compile(r"\bLL_(?:live|test)_[A-Za-z0-9]{8,}\b", re.I), "[REDACTED_API_KEY]"),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"\bwhsec_[A-Za-z0-9]{8,}\b"), "[REDACTED_WEBHOOK_SECRET]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*"), "Bearer [REDACTED_TOKEN]"),
    # Secrets are QUOTED literals. The first version also matched unquoted values and turned
    # generated code `page_token=page_token` into `page_token=[REDACTED]` (trace
    # trc12_d54345f79f9e, runs/found_redactor_corrupts_code.jsonl) - a mode integration created.
    (re.compile(r"(?i)((?:api_key|apikey|password|passwd|secret|token)\s*[=:]\s*)(['\"])"
                r"(?!LL_API_KEY|KEY['\"]|whsec_\.\.\.)([^'\"\s]{8,})\2"), r"\1\2[REDACTED]\2"),
    (re.compile(r"(?i)(\bpass(?:word|wd)\s*[=:]\s*)(?=[^\s'\"]*[\d!@#$%^&*])([^\s'\",)]{6,})"),
     r"\1[REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    for pat, rep in REDACTIONS:
        text = pat.sub(rep, text)
    return text


def redact_obj(o):
    if isinstance(o, str):
        return redact(o)
    if isinstance(o, list):
        return [redact_obj(x) for x in o]
    if isinstance(o, dict):
        return {k: redact_obj(v) for k, v in o.items()}
    return o


_lock = threading.Lock()


def write_line(record: dict, path=None) -> None:
    """The ONLY way anything reaches disk. Redact on write, not later."""
    path = path or os.environ.get("CAPSTONE_TRACE_LOG") or TRACE_LOG
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock, p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(redact_obj(record), ensure_ascii=False) + "\n")


def new_trace_id() -> str:
    return "trc12_" + uuid.uuid4().hex[:12]


class Trace:
    def __init__(self, question: str, tags: dict = None, trace_id: str = None):
        self.trace_id = trace_id or new_trace_id()
        self.t0 = time.perf_counter()
        self.ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.spans = []
        self.events = []
        self.tags = tags or {}
        self.question = redact(question)

    @contextmanager
    def span(self, name: str, **attrs):
        s = {"span": name, "start_s": round(time.perf_counter() - self.t0, 3), **attrs}
        t = time.perf_counter()
        try:
            yield s
        finally:
            s["latency_s"] = round(time.perf_counter() - t, 3)
            s.setdefault("cost_usd", 0.0)
            self.spans.append(s)

    def event(self, name: str, **attrs):
        self.events.append({"event": name, "at_s": round(time.perf_counter() - self.t0, 3), **attrs})

    def record(self, **extra) -> dict:
        total_cost = round(sum(s.get("cost_usd", 0.0) for s in self.spans), 6)
        return {"kind": "request", "trace_id": self.trace_id, "ts": self.ts,
                "question": self.question, **self.tags,
                "total_latency_s": round(time.perf_counter() - self.t0, 3),
                "total_cost_usd": total_cost,
                "spans": self.spans, "events": self.events, **extra}

    def write(self, **extra) -> dict:
        rec = self.record(**extra)
        write_line(rec)
        return redact_obj(rec)


def read_log(path=None) -> list:
    from pathlib import Path
    p = Path(path or os.environ.get("CAPSTONE_TRACE_LOG") or TRACE_LOG)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def full_trace(trace_id: str, path=None) -> dict:
    """Join the engine's request record with the MCP server's own span lines."""
    lines = [r for r in read_log(path) if r.get("trace_id") == trace_id]
    req = next((r for r in lines if r.get("kind") == "request"), None)
    server = [r for r in lines if r.get("kind") == "mcp_server_span"]
    return {"trace_id": trace_id, "request": req, "mcp_server_spans": server}
