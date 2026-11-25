"""Resolve the CALLER'S SDK version BEFORE retrieval. Order: explicit flag > pinned
requirement (ledgerline==2.4.1) > "I'm on 2.4" > a bare version mention > default 3.0
(flagged as assumed, and the answer says so)."""
import re
from typing import Optional

from . import sdk_spec as S

PIN = re.compile(r"ledgerline\s*(?:==|~=|>=|<=|@)\s*v?(\d+)\.(\d+)", re.I)
ON = re.compile(r"\b(?:i'?m|we'?re|i am|we are|still|stuck|currently|running|using|on)\s+"
                r"(?:on\s+|using\s+)?(?:ledgerline\s+|the\s+|sdk\s+)?v?(\d)(?:\.(\d+|x))?\b", re.I)
FROM = re.compile(r"\bfrom\s+v?(\d)(?:\.(\d+|x))?\s+to\s+v?(\d)", re.I)
BARE = re.compile(r"\b(?:v|version\s*|sdk\s*)(\d)(?:\.(\d+|x))?\b|\b(\d)\.(\d+|x)\b", re.I)

LATEST_MINOR = {2: 4, 3: 0}


def _clamp(major: int, minor: Optional[str]) -> Optional[str]:
    if major not in LATEST_MINOR:
        return None
    if minor in (None, "x", ""):
        m = LATEST_MINOR[major]
    else:
        m = min(int(minor), LATEST_MINOR[major])
    return f"{major}.{m}"


def resolve(question: str, explicit: Optional[str] = None) -> dict:
    if explicit:
        maj, mi = S.V(explicit)
        return {"version": _clamp(maj, str(mi)), "source": "flag", "assumed": False}
    q = question or ""
    m = PIN.search(q)
    if m:
        return {"version": _clamp(int(m.group(1)), m.group(2)), "source": "pinned_requirement",
                "assumed": False}
    m = FROM.search(q)
    if m:
        return {"version": _clamp(int(m.group(1)), m.group(2)), "source": "migrating_from",
                "assumed": False, "target": _clamp(int(m.group(3)), None)}
    m = ON.search(q)
    if m and _clamp(int(m.group(1)), m.group(2)):
        return {"version": _clamp(int(m.group(1)), m.group(2)), "source": "question",
                "assumed": False}
    m = BARE.search(q)
    if m:
        maj = int(m.group(1) or m.group(3))
        mi = m.group(2) if m.group(1) else m.group(4)
        v = _clamp(maj, mi)
        if v:
            return {"version": v, "source": "question_mention", "assumed": False}
    return {"version": S.CURRENT, "source": "default", "assumed": True}
