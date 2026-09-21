"""Deterministic checks. These are the criteria that were moved OUT of the judge:
a parser, a spec lookup and a changelog scan do them for free and never have an off day.

Each check returns True (pass), False (fail) or None (does not apply to this case).
"""
import ast
import re

from src.contract import code_blocks, is_refusal, stated_version
from src.corpus import changelog
from src.tools import match_path

PATH = re.compile(r"/v[23]/[A-Za-z0-9_{}\-/.]*")
MIGRATION_WORDS = re.compile(r"deprecat|removed|replaced|renamed|no longer|instead of", re.I)


def paths_in(text: str) -> list:
    out = []
    for m in PATH.findall(text or ""):
        p = m.split("?")[0].rstrip("./")
        if p.count("/") >= 2:
            out.append(p)
    return out


def version_stated(case, answer):
    return stated_version(answer) == case["api_version"]


def code_parses(case, answer):
    blocks = code_blocks(answer)
    if not blocks:
        return False if case.get("needs_code") and not case.get("expect_refusal") else None
    for b in blocks:
        try:
            ast.parse(b)
        except SyntaxError:
            return False
    return True


def endpoints_exist(case, answer):
    paths = paths_in(answer)
    if not paths:
        return None
    return all(match_path(p, p.split("/")[1]) is not None for p in paths)


def no_v2_in_v3_code(case, answer):
    if case["api_version"] != "v3":
        return None
    blocks = code_blocks(answer)
    if not blocks:
        return None
    return not any("/v2/" in b for b in blocks)


def deprecations_noted(case, answer):
    """Every changelog symbol that appears must come with a migration note."""
    if case["api_version"] != "v3":
        return None
    hit = [e for e in changelog() if re.search(e["pattern"], answer or "")]
    if not hit:
        return None
    for e in hit:
        repl = e["replacement"].split(" ", 1)[-1].split("{")[0].rstrip("/")
        if repl.lower() not in (answer or "").lower() and not MIGRATION_WORDS.search(answer or ""):
            return False
    return True


def refusal_correct(case, answer):
    return is_refusal(answer) == bool(case.get("expect_refusal"))


def must_include(case, answer):
    if not case.get("must_include"):
        return None
    low = (answer or "").lower()
    return all(s.lower() in low for s in case["must_include"])


ASSERTIONS = [
    ("version_stated", version_stated),
    ("code_parses", code_parses),
    ("endpoints_exist", endpoints_exist),
    ("no_v2_in_v3_code", no_v2_in_v3_code),
    ("deprecations_noted", deprecations_noted),
    ("refusal_correct", refusal_correct),
    ("must_include", must_include),
]

# The four criteria that used to be in the judge prompt (judge_v0_all_criteria.txt)
# and now live here instead.
MOVED_FROM_JUDGE = ["code_parses", "endpoints_exist", "version_stated", "deprecations_noted"]


def run_assertions(case, answer) -> dict:
    return {name: fn(case, answer) for name, fn in ASSERTIONS}


def passed(results: dict) -> bool:
    return all(v is not False for v in results.values())
