"""Strip claimant identifiers on the way IN to the trace writer.

Not a cleanup pass over a file that already exists. `trace.write()` calls this
before `json.dumps`, so an identifier is never serialised in the first place and
there is no window in which the trace file holds one. Nothing in this module opens
a trace file, by design.

What it removes, and what it must not:

  removes   claimant names, claim numbers, policy numbers, phone numbers, email
            addresses, street addresses
  keeps     form numbers (HO-0304), exclusion codes (E-17), edition dates (03-24),
            money amounts, day counts, clause numbers

The second list is the hard half. An over-eager redactor that turns
"Water Backup and Sump Discharge Coverage" into "[NAME] Coverage" destroys the
trace it was meant to protect, so the stoplist that protects policy vocabulary is
derived from the corpus itself rather than typed out by hand.

Names are sweept in two passes. Pass one finds full names, "Rebecca Hollis". Pass
two takes every token of every name it found and sweeps those single tokens through
every field, because the assistant echoes a claimant back mid-sentence by first name
alone and a two-word rule never sees it.
"""
import re
from functools import lru_cache
from typing import Dict, List, Tuple

from src import DATA_DIR

# --------------------------------------------------------------------------
# Vocabulary the corpus owns - never redacted
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def corpus_vocabulary() -> frozenset:
    """Every capitalised word that occurs in the endorsements, lowercased.

    Derived, not hand-written: a new endorsement adds its own vocabulary the moment
    it is dropped into data/, with no edit here.
    """
    words = set()
    for p in sorted(DATA_DIR.iterdir()):
        if p.suffix.lower() in {".md", ".txt"}:
            for w in re.findall(r"\b[A-Z][a-z]{2,}\b", p.read_text(encoding="utf-8")):
                words.add(w.lower())
    return frozenset(words)


# Words that open a sentence or a heading and would otherwise look like a surname.
GRAMMAR_WORDS = frozenset("""
the this that these those and but for with from into over under per each any all
does did was were are is has have had will would could should may might must
insured insureds claimant policyholder adjuster desk file note loss claim policy
water damage roof business seepage vacancy vacant coverage exclusion endorsement
yes no none where when what which how much many do we our their his her they
""".split())

# --------------------------------------------------------------------------
# Structured identifiers - matched first, because they are unambiguous
# --------------------------------------------------------------------------

PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL",     re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("CLAIM_NO",  re.compile(r"\bCLM[-\s]?\d{4}[-\s]?\d{4,6}\b", re.I)),
    # A policy number is a form-style prefix with FIVE or more digits. A form number
    # has four (HO-0304) and must survive.
    ("POLICY_NO", re.compile(r"\b[A-Z]{2}-\d{5,}\b")),
    ("PHONE",     re.compile(r"(?<![\w-])(?:\(\d{3}\)\s?|\d{3}[-.\s])\d{3}[-.\s]\d{4}(?![\w-])")),
    ("ADDRESS",   re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
                             r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Court|Ct|"
                             r"Place|Pl|Way|Terrace|Boulevard|Blvd)\b")),
]

# "Rebecca Hollis", "Mrs Alvarez", "Mr. J. Okafor"
TITLE_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+(?:[A-Z]\.\s*)?[A-Z][a-z]+\b")
FULL_NAME = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


def _is_name_token(word: str) -> bool:
    low = word.lower()
    return low not in corpus_vocabulary() and low not in GRAMMAR_WORDS


class Redactor:
    """One redactor per trace record, so the names found in one field can be swept
    through the others."""

    def __init__(self) -> None:
        self.counts: Dict[str, int] = {}
        self.name_tokens: set = set()

    def _bump(self, kind: str, n: int = 1) -> None:
        if n:
            self.counts[kind] = self.counts.get(kind, 0) + n

    # -- pass 1 -----------------------------------------------------------
    def scan(self, text: str) -> None:
        """Collect name tokens without changing anything."""
        for m in TITLE_NAME.finditer(text):
            for w in re.findall(r"[A-Z][a-z]+", m.group(0))[1:]:
                if _is_name_token(w):
                    self.name_tokens.add(w)
        for m in FULL_NAME.finditer(text):
            a, b = m.group(0).split()
            if _is_name_token(a) and _is_name_token(b):
                self.name_tokens.update((a, b))

    # -- pass 2 -----------------------------------------------------------
    def apply(self, text: str) -> str:
        for kind, pat in PATTERNS:
            text, n = pat.subn(f"[{kind}]", text)
            self._bump(kind, n)
        text, n = TITLE_NAME.subn("[NAME]", text)
        self._bump("NAME", n)
        def _full(m):
            if all(_is_name_token(w) for w in m.group(0).split()):
                self._bump("NAME")
                return "[NAME]"
            return m.group(0)

        text = FULL_NAME.sub(_full, text)
        for tok in sorted(self.name_tokens, key=len, reverse=True):
            text, n = re.subn(rf"\b{re.escape(tok)}\b", "[NAME]", text)
            self._bump("NAME", n)
        text = re.sub(r"(?:\[NAME\]\s*){2,}", "[NAME] ", text)
        return text


def redact_record(obj):
    """Redact every string anywhere in a nested record. Returns (clean, counts)."""
    r = Redactor()

    def walk(o, fn):
        if isinstance(o, str):
            return fn(o)
        if isinstance(o, dict):
            return {k: walk(v, fn) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [walk(v, fn) for v in o]
        return o

    walk(obj, lambda s: (r.scan(s), s)[1])          # pass 1: find names everywhere
    clean = walk(obj, r.apply)                      # pass 2: remove them everywhere
    return clean, dict(r.counts)


# --------------------------------------------------------------------------
# The check the writer runs before it is allowed to append
# --------------------------------------------------------------------------

RESIDUAL = [(kind, pat) for kind, pat in PATTERNS] + [
    ("NAME", TITLE_NAME), ("NAME", FULL_NAME)]


def residual_identifiers(text: str) -> List[str]:
    """Anything a redacted string still should not contain."""
    found = []
    for kind, pat in RESIDUAL:
        for m in pat.finditer(text):
            if kind == "NAME" and not all(_is_name_token(w)
                                          for w in re.findall(r"[A-Z][a-z]+", m.group(0))):
                continue
            found.append(f"{kind}:{m.group(0)}")
    return found
