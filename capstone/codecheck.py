"""Stop judging code, execute the check.

Every emitted ```python block goes through:
  1. ast.parse                      - does it parse?
  2. import resolution              - does `from ledgerline import X` exist in THIS version?
  3. symbol-table check             - does every client.* method called exist in THIS version?
  4. kwargs check                   - are the keyword args valid, are required ones present
                                      (3.0 Client() without timeout= fails here)?
  5. result-attribute check         - .next_page_token on a 3.0 SearchPage, .next_cursor on 2.x

Free, deterministic, no model. If you can assert it, never judge it.
"""
import ast
import re
from typing import Dict, List

from . import sdk_spec as S

CODE_BLOCK = re.compile(r"```(?:python|py)[^\n]*\n(.*?)```", re.S)


def code_blocks(text: str) -> List[str]:
    return CODE_BLOCK.findall(text or "")


def _chain(node) -> List[str]:
    out = []
    while isinstance(node, ast.Attribute):
        out.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif isinstance(node, ast.Call):
        out.append("<call>")
    return list(reversed(out))


def check(code: str, version: str) -> Dict:
    major = str(S.V(version)[0])
    res = {"version": version, "parses": True, "errors": [], "deprecated": [], "symbols": []}
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        res["parses"] = False
        res["errors"].append(f"does not parse: {e.msg} (line {e.lineno})")
        return res

    sdk_aliases = set()          # names bound to the ledgerline module
    errors_aliases = set()       # names bound to ledgerline.errors
    imported: Dict[str, str] = {}  # local name -> symbol
    clients, conns = {"client"}, set()

    def use(sym: str, call: ast.Call = None, where: str = ""):
        st = S.status(sym, version)
        res["symbols"].append(sym)
        if not st["exists"]:
            if st["state"] == "removed":
                res["errors"].append(f"`{sym}` does not exist in {version} (removed in "
                                     f"{st['removed']}; use {st['replacement']})")
            elif st["state"] == "not_yet_added":
                res["errors"].append(f"`{sym}` does not exist in {version} (added in {st['added']})")
            else:
                res["errors"].append(f"`{sym}` is not an ledgerline SDK symbol (invented)")
            return
        if st["state"] == "deprecated":
            res["deprecated"].append(st)
        if call is not None:
            allowed = set(st.get("params", []))
            for kw in call.keywords:
                if kw.arg and kw.arg not in allowed:
                    res["errors"].append(f"`{sym}()` has no parameter `{kw.arg}` in {version}")
            given = {kw.arg for kw in call.keywords}
            for req in st.get("required", []):
                if req not in given:
                    res["errors"].append(f"`{sym}()` requires `{req}=` in {version}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "ledgerline":
                    sdk_aliases.add(a.asname or "ledgerline")
                elif a.name == "ledgerline.errors":
                    if a.asname:
                        errors_aliases.add(a.asname)
                    else:
                        sdk_aliases.add("ledgerline")
                    if major == "2":
                        res["errors"].append(f"module `ledgerline.errors` does not exist in {version}")
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ledgerline"):
            if node.module == "ledgerline":
                for a in node.names:
                    if a.name == "errors":
                        if major == "2":
                            res["errors"].append(f"module `ledgerline.errors` does not exist in {version}")
                        errors_aliases.add(a.asname or "errors")
                        continue
                    imported[a.asname or a.name] = a.name
                    use(a.name)
            elif node.module == "ledgerline.errors":
                if major == "2":
                    res["errors"].append(f"module `ledgerline.errors` does not exist in {version}")
                    continue
                for a in node.names:
                    imported[a.asname or a.name] = "errors." + a.name
                    use("errors." + a.name)
            else:
                res["errors"].append(f"module `{node.module}` does not exist in {version}")

    # which names hold a Client / a v1 connection
    for node in ast.walk(tree):
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets, value = [node.optional_vars], node.context_expr
        if isinstance(value, ast.Call):
            ch = _chain(value.func)
            name = ch[-1] if ch else ""
            sym = imported.get(name, name) if len(ch) == 1 else name
            for t in targets:
                if isinstance(t, ast.Name):
                    if sym == "Client":
                        clients.add(t.id)
                    elif sym == "connect":
                        conns.add(t.id)

    # Result pages expose only .items and the version's cursor attribute. An invented one such as
    # `page.has_next` passed the symbol check (C30 re-run, trace trc12_179a8038f244).
    pages = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            ch = _chain(node.value.func)
            if len(ch) >= 2 and ch[0] in clients and ch[-1] in ("search", "query", "list"):
                pages |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id in pages and node.attr not in S.RESULT_ATTRS[major]
                and node.attr not in ("next_page_token", "next_cursor")):
            res["errors"].append(f"`.{node.attr}` is not an attribute of a result page in {version} "
                                 f"(it has {', '.join(sorted(S.RESULT_ATTRS[major]))})")

    # The SDK is sync-only in every version: `await client.x()` / `async for .. in client.x()`
    # passes a pure symbol check but fails at runtime (found: trace trc12_84700673c026, C30).
    for node in ast.walk(tree):
        it = node.iter if isinstance(node, ast.AsyncFor) else node.value if isinstance(node, ast.Await) else None
        if isinstance(it, ast.Call):
            ch = _chain(it.func)
            if ch and (ch[0] in clients or ch[0] in sdk_aliases):
                res["errors"].append(f"`{'.'.join(ch)}()` is synchronous in {version}: it cannot be "
                                     f"awaited or used with `async for`")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            ch = _chain(node.func)
            if not ch:
                continue
            root = ch[0]
            if len(ch) == 1 and root in imported:
                use(imported[root], node)
            elif root in sdk_aliases and len(ch) >= 2:
                if ch[1] == "errors":
                    use("errors." + ".".join(ch[2:]), None)
                else:
                    use(".".join(ch[1:]), node)
            elif root in clients and len(ch) >= 2:
                use("client." + ".".join(ch[1:]), node)
            elif root in conns and len(ch) >= 2:
                use("conn." + ".".join(ch[1:]), node)
        elif isinstance(node, ast.Attribute) and not isinstance(getattr(node, "ctx", None), ast.Store):
            ch = _chain(node)
            if ch and ch[0] in sdk_aliases and len(ch) == 2 and ch[1][:1].isupper():
                use(ch[1])                                  # ledgerline.RateLimited
            if ch and ch[0] in sdk_aliases and len(ch) == 3 and ch[1] == "errors":
                use("errors." + ch[2])
            if ch and ch[0] in errors_aliases and len(ch) == 2:
                use("errors." + ch[1])
            if node.attr in ("next_page_token", "next_cursor"):
                if node.attr not in S.RESULT_ATTRS[major]:
                    good = next(iter(S.RESULT_ATTRS[major] - {"items"}))
                    res["errors"].append(f"result attribute `.{node.attr}` does not exist in "
                                         f"{version} (use `.{good}`)")
    res["errors"] = sorted(set(res["errors"]))
    res["symbols"] = sorted(set(res["symbols"]))
    seen, dep = set(), []
    for d in res["deprecated"]:
        if d["symbol"] not in seen:
            seen.add(d["symbol"])
            dep.append(d)
    res["deprecated"] = dep
    return res


def check_answer(answer: str, version: str) -> Dict:
    blocks = code_blocks(answer)
    results = [check(b, version) for b in blocks]
    if (answer or "").count("```") % 2:
        # A truncated answer leaves an unclosed fence that CODE_BLOCK never matches, so the code
        # inside escaped every check (C30 after-run, trace trc12_b3abf1a7f1b5). Fail it.
        results.append({"parses": False, "errors": ["unclosed code block (truncated output): "
                                                     "the code inside was never checked"],
                        "deprecated": [], "symbols": []})
    return {"n_blocks": len(results), "ok": all(r["parses"] and not r["errors"] for r in results),
            "blocks": results,
            "errors": [e for r in results for e in r["errors"]],
            "deprecated": [d for r in results for d in r["deprecated"]]}
