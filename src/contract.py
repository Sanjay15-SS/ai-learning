"""The output contract every answerer in this folder obeys - the Week 6 app, the
Week 7 agent and the Week 7 workflow - so they can be scored by the same code."""
import re
from typing import Optional

NOT_COVERED = "Not covered in the Ledgerline docs."

CONTRACT = f"""\
Answer format - follow it exactly:
1. The first line is `API version: v2` or `API version: v3`: the version your answer targets.
   If the developer does not say which version they are on, target v3 (the current version).
2. A short, direct explanation.
3. If the answer involves calling the API, exactly one ```python code block using the
   `requests` library against https://api.ledgerline.example. Use only endpoints, fields and
   headers that exist in the stated version.
4. If you use or mention a v2 symbol while answering for v3, say that it is deprecated or
   removed and name what replaces it.
5. If the documentation does not answer the question, the explanation is exactly
   "{NOT_COVERED}" and nothing is guessed."""

VERSION_LINE = re.compile(r"^\s*\**API version:\**\s*`?(v[23])`?", re.I | re.M)
CODE_BLOCK = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.S)
ANY_BLOCK = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.S)


def stated_version(answer: str) -> Optional[str]:
    m = VERSION_LINE.search(answer or "")
    return m.group(1).lower() if m else None


def code_blocks(answer: str) -> list:
    return CODE_BLOCK.findall(answer or "")


def is_refusal(answer: str) -> bool:
    return NOT_COVERED.lower().rstrip(".") in (answer or "").lower()


def target_version(question: str) -> str:
    """What version the developer is on, read from the question. Default: current."""
    q = question.lower()
    on_v2 = re.search(r"\b(?:on|using|stay on|staying on|still on)\s+v2\b", q)
    if on_v2 and not re.search(r"\b(?:to|into|onto|for)\s+v3\b", q):
        return "v2"
    return "v3"
