"""The one place a model is called. Counts every token of every call, so a loop that
re-sends its whole history is charged for every lap, not just the last one."""
import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import BACKEND, MODEL, PRICES

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    models: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens
                + self.cache_write_tokens + self.cache_read_tokens)

    def add(self, response) -> None:
        u = response.usage
        inp = u.input_tokens or 0
        out = u.output_tokens or 0
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        pin, pout = PRICES.get(response.model, PRICES[MODEL])
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.cache_write_tokens += cw
        self.cache_read_tokens += cr
        self.cost_usd += (inp * pin + out * pout + cw * pin * 1.25 + cr * pin * 0.10) / 1e6
        self.models.append(response.model)

    def as_dict(self) -> dict:
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_read_tokens": self.cache_read_tokens,
                "total_tokens": self.total_tokens, "cost_usd": round(self.cost_usd, 6)}


_client = None


def client():
    """Real client, built on first use so offline commands never need a key."""
    global _client
    if _client is None:
        import os
        from pathlib import Path
        import anthropic
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or (Path.home() / ".config" / "anthropic").exists()):
            raise SystemExit("No Anthropic credentials. Run `export ANTHROPIC_API_KEY=sk-ant-...` "
                             "(or `ant auth login`) and try again. Offline checks: "
                             "python3 selftest.py")
        _client = anthropic.Anthropic()
    return _client


def set_client(c) -> None:
    """selftest.py swaps in a scripted client here."""
    global _client
    _client = c


def create(usage: Usage, *, system, messages, max_tokens: int = 8000,
           tools: Optional[list] = None, timeout: Optional[float] = None):
    """One Messages call on the shared model, with server-side refusal fallback on.
    Adds the call's usage to `usage` before returning."""
    if BACKEND == "local" and _client is None:        # selftest injects a fake client
        from . import local_llm
        t0 = time.perf_counter()
        response = local_llm.create(system=system, messages=messages, max_tokens=max_tokens,
                                    tools=tools)
        response._latency_s = time.perf_counter() - t0
        usage.add(response)
        return response
    kw = dict(model=MODEL, max_tokens=max_tokens, system=system, messages=messages,
              betas=[FALLBACK_BETA], fallbacks="default")
    if tools:
        kw["tools"] = tools
    c = client()
    if timeout is not None:
        c = c.with_options(timeout=max(timeout, 1.0), max_retries=0)
    t0 = time.perf_counter()
    response = c.beta.messages.create(**kw)
    response._latency_s = time.perf_counter() - t0
    usage.add(response)
    return response


def text_of(response) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
