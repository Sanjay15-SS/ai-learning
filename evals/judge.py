"""The LLM judge: one binary criterion, CORRECT_AND_USABLE. Verdicts are cached by
(judge version, answer hash) so re-running the eval does not pay twice."""
import json
import re

from src import EVALS, RUNS, llm
from src.corpus import full_reference_text

from .common import read_jsonl, sha256_text

VERDICT = re.compile(r"VERDICT:\s*(PASS|FAIL)", re.I)
CACHE = RUNS / "judge_cache.jsonl"


def judge_path(version: str):
    return EVALS / f"judge_{version}.txt"


def latest_judge() -> str:
    return "v2" if judge_path("v2").exists() else "v1"


def render(version: str, case: dict, answer: str) -> tuple:
    """(system, user). The reference docs sit in the cached system block."""
    template = judge_path(version).read_text(encoding="utf-8")
    head, _, tail = template.partition("Reference documentation:\n<<REFERENCE>>")
    system = [{"type": "text", "cache_control": {"type": "ephemeral"},
               "text": head.replace("<<EXAMPLES>>", "")
                       + "Reference documentation:\n" + full_reference_text()}]
    user = (tail.replace("<<API_VERSION>>", case["api_version"])
                .replace("<<QUESTION>>", case["question"])
                .replace("<<ANSWER>>", answer or "(empty answer)"))
    return system, user


def _cache() -> dict:
    return {(r["judge"], r["answer_sha"]): r for r in read_jsonl(CACHE)}


def judge(version: str, case: dict, answer: str) -> dict:
    key = (version, sha256_text(case["id"] + "\x00" + (answer or "")))
    hit = _cache().get(key)
    if hit:
        return hit
    system, user = render(version, case, answer)
    usage = llm.Usage()
    r = llm.create(usage, system=system, max_tokens=4000,
                   messages=[{"role": "user", "content": user}])
    text = llm.text_of(r)
    m = VERDICT.findall(text)
    row = {"judge": version, "answer_sha": key[1], "case_id": case["id"],
           "verdict": m[-1].upper() if m else "UNPARSED", "rationale": text[-1200:],
           "usage": usage.as_dict()}
    with CACHE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row
