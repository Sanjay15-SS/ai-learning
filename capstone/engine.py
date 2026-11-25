"""THE single entry point: question in -> answer out, one trace id across every hop.

    redact -> resolve caller version -> RAG retrieve (Week 3-4, version filter in code)
      -> agent loop (Week 7, hand-built) with tools DISCOVERED over MCP at runtime
      -> guards (code check + one repair, removed-symbol statement, deprecations, citations)
      -> trace written (Week 11, redacted on write)

mode="before": the parts glued naively - version stated in the prompt as words only, no
               metadata filter, Stack Overflow shown raw, no code check, no guards.
mode="after" : version filter enforced in code, SO as phrasing bridge only, tool-arg
               version pinned, code check + repair, deprecation + removed-symbol guards.
"""
import json
import re
import sys
import time
from typing import Optional

from src import llm
from week9.mcp_protocol import MCPClient

from . import HERE, codecheck, retriever, sdk_spec as S, version as V
from .obs import Trace, redact

ROOT = HERE.parent
MAX_LAPS = 3

SYSTEM = """You answer questions from developers who integrate the `ledgerline` Python SDK.
The caller's installed SDK version is {version}. Every code sample you write MUST run on {version}.
Two SDK versions are live: 2.x (2.0-2.4) and 3.0. They differ: 3.0 renamed client.query() to
client.search() (page_token -> cursor), made Client(timeout=...) REQUIRED, moved errors to
ledgerline.errors, and removed set_retry().

Before answering, call symbol_exists (with sdk_version="{version}") for the main method you will use,
or lookup_changelog for a method the developer names. Then answer.
Never invent a method or parameter. If a method the developer names does not exist in {version},
say plainly "`<method>` no longer exists in {version}" (or "does not exist in {version}") and show
the replacement instead.

Answer format:
SDK version: {version}
<2-5 sentence explanation>
```python
<one short runnable snippet for {version}, only if code helps>
```
Sources: <the doc page titles you used, with their version>"""

REPAIR = """Your code sample fails a deterministic check against the ledgerline SDK {version}:
{errors}
Correct facts for {version}:
{facts}
Rewrite the full answer in the same format with a snippet that uses ONLY symbols that exist in {version}."""


class TracedMCPClient(MCPClient):
    """MCP client that forwards the trace id in tools/call `_meta`."""

    def call_tool(self, name, arguments, trace_id=None):
        params = {"name": name, "arguments": arguments}
        if trace_id:
            params["_meta"] = {"trace_id": trace_id}
        return self.send_request("tools/call", params)


class MCPSession:
    """Tools are discovered with tools/list at runtime from mcp_config.json - not hardcoded."""

    def __init__(self, config=HERE / "mcp_config.json"):
        cfg = json.loads(open(config, encoding="utf-8").read())["mcpServers"]
        self.clients, self.route, self.tools = [], {}, []
        for name, c in cfg.items():
            cmd = sys.executable if c.get("command") in ("python3", "python") else c["command"]
            cl = TracedMCPClient(name, cmd, c.get("args", []), cwd=str(ROOT))
            cl.start()
            cl.initialize({"name": "capstone-engine", "version": "1.0"})
            for t in cl.list_tools():
                self.route[t["name"]] = cl
                self.tools.append({"name": t["name"], "description": t["description"],
                                   "input_schema": t["inputSchema"]})
            self.clients.append(cl)

    def call(self, name, args, trace_id):
        cl = self.route.get(name)
        if cl is None:
            return {"error": f"unknown tool {name}"}
        res = cl.call_tool(name, args, trace_id=trace_id)
        text = "".join(c.get("text", "") for c in res.get("content", []))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    def close(self):
        for c in self.clients:
            c.close()


_SESSION: Optional[MCPSession] = None


def session() -> MCPSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = MCPSession()
    return _SESSION


def close_session():
    global _SESSION
    if _SESSION:
        _SESSION.close()
        _SESSION = None


SYM_IN_TEXT = re.compile(r"\b(?:client|Client)\.[a-z_]+(?:\.[a-z_]+)?|\bset_retry\b|\bquery_all\b|"
                         r"\bsearch_iter\b|\bRateLimited\b|\bRateLimitError\b|\bconnect\(")


UNKNOWN_IN_TEXT = re.compile(r"\bclient\.[a-z_]+(?:\.[a-z_]+)?|\b[A-Z][a-zA-Z]*Client\b")


def mentioned_symbols(text: str, include_unknown: bool = False) -> list:
    """SDK symbols named in text. include_unknown also returns client.* / *Client names that
    are NOT in the SDK at all - the invented-signature bait."""
    out = []
    for m in SYM_IN_TEXT.findall(text or "") + (UNKNOWN_IN_TEXT.findall(text or "") if include_unknown else []):
        s = S.normalise(m)
        if s in ("set_retry", "query_all", "search_iter"):
            s = "client." + s
        if (s in S.SYMBOLS or include_unknown) and s not in out:
            out.append(s)
    return out


def replacement_for(sym: str, version: str) -> Optional[str]:
    """For a symbol that does not exist yet in `version`, what is the equivalent there?"""
    for k, e in S.SYMBOLS.items():
        if e.get("replacement") and S.normalise(e["replacement"].split(" ")[0]) == sym \
                and S.status(k, version)["exists"]:
            return k
    return None


def _usage_span(tr, name, fn, **attrs):
    u = llm.Usage()
    with tr.span(name, **attrs) as sp:
        r = fn(u)
        sp.update(input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                  cost_usd=round(u.cost_usd, 6), model=(u.models or [""])[-1])
    return r


def answer(question: str, sdk_version: Optional[str] = None, mode: str = "after",
           case_id: Optional[str] = None, guards: Optional[dict] = None) -> dict:
    after = mode == "after"
    g = {"code_check": after, "deprecations": after, "removed_plain": after, "pin_version": after}
    g.update(guards or {})
    tr = Trace(question, tags={"mode": mode, "case_id": case_id, "guards": g})

    with tr.span("redact") as sp:
        q = redact(question)
        sp["changed"] = q != question

    with tr.span("resolve_version") as sp:
        rv = V.resolve(q, sdk_version)
        ver = rv["version"]
        sp.update(rv)

    cfg = retriever.RetrieverConfig(version_filter=after, so_mode="bridge" if after else "raw")
    with tr.span("rag.retrieve", version_filter=cfg.version_filter, so_mode=cfg.so_mode) as sp:
        hits = retriever.search(q, ver, cfg)
        sp["chunks"] = [f"{c.chunk_id} [{c.version_label}]" for c in hits]
    used = {c.chunk_id: c for c in hits}

    context = "\n\n".join(f'<doc title="{c.title}" version="{c.version_label}" url="{c.url}">\n'
                          f"{c.text}\n</doc>" for c in hits)
    system = SYSTEM.format(version=ver)
    if rv["assumed"]:
        system += ("\nThe developer did not say which version they use: start the explanation with "
                   "'Assuming SDK 3.0 - tell me if you are on 2.x.'")
    messages = [{"role": "user", "content": f"Documentation:\n{context}\n\nQuestion: {q}"}]

    sess = session()
    tools_called, final = [], ""
    for lap in range(1, MAX_LAPS + 1):
        last = lap == MAX_LAPS
        r = _usage_span(tr, f"agent.lap{lap}", lambda u: llm.create(
            u, system=system, messages=messages, max_tokens=500,
            tools=None if last else sess.tools))
        calls = [b for b in r.content if getattr(b, "type", "") == "tool_use"]
        if not calls:
            final = llm.text_of(r)
            break
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in calls[:3]:
            args = dict(b.input or {})
            asked = args.get("sdk_version")
            schema = next((t["input_schema"] for t in sess.tools if t["name"] == b.name), {})
            if "sdk_version" in schema.get("properties", {}):
                if asked != ver:
                    tr.event("tool_version_mismatch", tool=b.name, asked=asked, resolved=ver,
                             pinned=g["pin_version"])
                    if g["pin_version"]:
                        args["sdk_version"] = ver
            with tr.span(f"mcp.call.{b.name}", args=args) as sp:
                out = sess.call(b.name, args, tr.trace_id)
                sp["is_error"] = "error" in out
            tools_called.append({"tool": b.name, "args": args, "asked_version": asked})
            if b.name == "search_sdk_docs":
                for rr in out.get("results", []):
                    used.setdefault(rr["chunk_id"], next(
                        (c for c in retriever.all_chunks() if c.chunk_id == rr["chunk_id"]), None))
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": json.dumps(out)[:2500]})
        messages.append({"role": "user", "content": results})
    raw = final

    # ------------------------------------------------------------------ guards
    ans = final
    g.setdefault("dedupe", after)
    if g["dedupe"] and ans.count("SDK version:") > 1:
        # seam #10: the 3B model writes the whole answer 2-3 times (6/12 after-run-1 answers);
        # the repeat runs into max_tokens and leaves a truncated, unchecked code block (C30).
        first = ans.index("SDK version:")
        second = ans.index("SDK version:", first + 1)
        ans = ans[:second].rstrip()
        tr.event("deduped_answer", kept_chars=len(ans), dropped_chars=len(final) - len(ans))
    check = codecheck.check_answer(ans, ver)
    with tr.span("code_check", enforced=g["code_check"]) as sp:
        sp.update(n_blocks=check["n_blocks"], ok=check["ok"], errors=check["errors"])
    if g["code_check"] and not check["ok"]:
        facts = []
        for sym in mentioned_symbols(ans):
            st = S.status(sym, ver)
            facts.append(f"- {sym}: " + ("exists, params " + ", ".join(st.get("params", []))
                                        + (f"; REQUIRED: {', '.join(st['required'])}" if st.get("required") else "")
                                        if st["exists"] else
                                        f"does NOT exist ({st.get('note') or st['state']}); "
                                        f"use {st.get('replacement') or replacement_for(sym, ver)}"))
        facts.append(f"- Client(...) params in {ver}: {', '.join(S.params('Client', ver))}"
                     + ("; timeout is REQUIRED" if S.required('Client', ver) else ""))
        rep_msgs = messages + [{"role": "assistant", "content": ans},
                               {"role": "user", "content": REPAIR.format(
                                   version=ver, errors="\n".join(check["errors"]),
                                   facts="\n".join(facts))}]
        r = _usage_span(tr, "repair", lambda u: llm.create(u, system=system, messages=rep_msgs,
                                                           max_tokens=500))
        ans2 = llm.text_of(r)
        check2 = codecheck.check_answer(ans2, ver)
        tr.event("repair", ok=check2["ok"], errors_after=check2["errors"])
        if check2["ok"] and check2["n_blocks"]:
            ans, check = ans2, check2
        else:
            ans = codecheck.CODE_BLOCK.sub(
                lambda m: (m.group(0) if codecheck.check(m.group(1), ver)["errors"] == [] else
                           f"_(code sample withheld: it failed the {ver} symbol check: "
                           f"{'; '.join(codecheck.check(m.group(1), ver)['errors'])})_"), ans)
            tr.event("code_withheld", errors=check["errors"])
            check = codecheck.check_answer(ans, ver)

    prefix, notices = [], []
    if g["removed_plain"]:
        for sym in mentioned_symbols(q, include_unknown=True):
            st = S.status(sym, ver)
            if st["state"] == "removed":
                prefix.append(f"`{sym}()` no longer exists in {ver} - it was removed in {st['removed']}"
                              + (f" (deprecated since {st['deprecated']})" if st.get("deprecated") else "")
                              + f". Here is the migration: use `{st['replacement']}`"
                              + " (see the migration guide).")
            elif st["state"] == "not_yet_added":
                alt = replacement_for(sym, ver)
                prefix.append(f"`{sym}()` does not exist in {ver} - it was added in {st['added']}."
                              + (f" On {ver} use `{alt}()`." if alt else ""))
            elif st["state"] == "unknown":
                prefix.append(f"`{sym}` is not part of the ledgerline SDK in any version.")
    if g["deprecations"]:
        dep = {d["symbol"]: d for d in check["deprecated"]}
        for sym in mentioned_symbols(ans) + mentioned_symbols(q):
            st = S.status(sym, ver)
            if st["state"] == "deprecated":
                dep.setdefault(sym, st)
        for sym, d in dep.items():
            notices.append(f"Deprecation: `{sym}` is deprecated since {d['deprecated']} and is "
                           f"removed in {d.get('removed') or 'a future release'}; use "
                           f"`{d.get('replacement')}`.")
    if prefix:
        ans = "\n".join(prefix) + "\n\n" + ans
    if notices:
        ans += "\n\n" + "\n".join(notices)

    srcs, seen_urls = [], set()
    for c in used.values():
        if c is not None and c.url not in seen_urls:
            seen_urls.add(c.url)
            srcs.append(c)
    if after:
        srcs = [c for c in srcs if c.source != "stackoverflow" and retriever.covers(c.sdk_version, ver)]
    ans = re.sub(r"\n+Sources:.*\Z", "", ans, flags=re.S).rstrip()
    ans += "\n\nSources:\n" + "\n".join(f"- [{c.title} ({c.version_label})]({c.url})"
                                        for c in srcs[:5])
    if rv["assumed"] and "Assuming SDK 3.0" not in ans:
        ans = "Assuming SDK 3.0 - tell me if you are on 2.x.\n" + ans

    final_check = codecheck.check_answer(ans, ver)
    rec = tr.write(version=rv, answer=ans, raw_answer=raw, tools_called=tools_called,
                   citations=[{"chunk_id": c.chunk_id, "source": c.source,
                               "version": c.sdk_version, "url": c.url} for c in srcs[:5]],
                   code_check=final_check)
    return rec


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--sdk-version")
    ap.add_argument("--mode", default="after", choices=["before", "after"])
    a = ap.parse_args()
    try:
        r = answer(a.question, a.sdk_version, a.mode)
    finally:
        close_session()
    print(f"trace_id: {r['trace_id']}   version: {r['version']}   "
          f"cost: ${r['total_cost_usd']:.5f}   latency: {r['total_latency_s']}s\n")
    print(r["answer"])


if __name__ == "__main__":
    main()
