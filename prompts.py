"""The answering policy, under a version id, so a trace can be replayed after an edit.

This app has no model and therefore no system prompt. What it has instead is a
policy: a fixed set of rules that turn retrieved chunks into an answer or a refusal.
Those rules are what a prompt would have been, so they are versioned the same way.

`policy_sha()` is a hash of the rules AND of the constants they name. Change the
coverage floor and the sha moves, which is the point: a trace written under
`claims-extractive-v1 / <sha>` can only be replayed by code that still means the
same thing by those words. `replay.py` refuses when the sha has moved.
"""
import hashlib

from src import COVERAGE_FLOOR, RETRIEVAL_MODE, SCORE_FLOOR, CANDIDATES, RRF_K

POLICY_ID = "claims-extractive-v1"

POLICY_TEXT = f"""\
Answering policy for the endorsement desk assistant.

RETRIEVAL
  mode              = {RETRIEVAL_MODE}
  candidates        = {CANDIDATES} per stage before fusion
  rrf_k             = {RRF_K}
  the answer step reads the top-ranked chunk only.

GATE 1 - TERM COVERAGE
  Take the content words of the question, drop stopwords, and test each against the
  full text of the indexed endorsements. If fewer than {COVERAGE_FLOOR:.0%} of them
  appear anywhere in the corpus, refuse before retrieval is consulted.

GATE 2 - SCORE FLOOR
  If no retrieved chunk has a dense cosine of at least {SCORE_FLOOR}, refuse.

ANSWERING
  Quote the answer verbatim from the top-ranked chunk. Never compose, never
  paraphrase, never combine two chunks. For a table-row chunk, quote the column
  header together with the row. Cite the chunk_id the quote came from.

REFUSING
  A refusal names its gate and says nothing about coverage.
"""


def policy_sha() -> str:
    return hashlib.sha256(POLICY_TEXT.encode("utf-8")).hexdigest()[:12]


def policy_record() -> dict:
    return {"id": POLICY_ID, "sha": policy_sha()}
