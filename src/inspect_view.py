"""The inspection view - the thing you open BEFORE labelling a retrieval failure.

For one question it puts three things side by side: every candidate the retriever
considered with the rank each stage gave it, where the known-correct chunk actually
landed, and what the answer step did with the context it got. A miss is then
labelled from evidence rather than from how wrong the answer text reads.

The labels:

    PASS      gold in the top-3 AND the answer was quoted from it
    R         retrieval failure - gold never reached the top-3
    G         generation failure - gold WAS in the top-3 and the answer step
              still missed it, either by reading only rank 1 (G-rank) or by
              refusing on a gate (G-refuse)
    NIC       not-in-corpus - no chunk is known to be correct, so a miss here
              is the right behaviour and is not counted against hit-rate@3

Keeping R and G apart is the whole point: they are fixed in different files, and
a change to the retriever cannot repair a G.
"""
import json
import re
from typing import Dict, List, Optional, Sequence

from . import CANDIDATES, GOLDEN_SET_PATH, RETRIEVAL_MODE
from .generator import answer, term_coverage
from .indexer import get_registry
from .retriever import search_explain

STAGE_ORDER = ("dense", "bm25", "rrf")
SNIPPET_CHARS = 87

# Identifiers a bi-encoder cannot see but an adjuster types anyway: exclusion codes
# (E-17), form numbers (HO-0304) and edition dates (03-24).
EXACT_TOKEN_RE = re.compile(r"\b(?:[A-Z]{1,2}-\d{2,4}|\d{2}-\d{2})\b")


def load_golden(path=GOLDEN_SET_PATH) -> List[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def exact_tokens(question: str) -> List[str]:
    """Exclusion code, then form number, then edition - the order an adjuster says them.

    Grouping by kind rather than by position keeps the token list comparable across
    questions that happen to word themselves the other way round.
    """
    buckets: Dict[int, List[str]] = {0: [], 1: [], 2: []}
    seen = set()
    for tok in EXACT_TOKEN_RE.findall(question):
        if tok in seen:
            continue
        seen.add(tok)
        if tok[0].isdigit():
            buckets[2].append(tok)                       # edition, e.g. 03-24
        elif len(tok.split("-")[0]) == 1:
            buckets[0].append(tok)                       # exclusion code, e.g. E-17
        else:
            buckets[1].append(tok)                       # form number, e.g. HO-0304
    return buckets[0] + buckets[1] + buckets[2]


def describe(chunk) -> str:
    """`HO-2199@02-24 E-33` - the form, the edition, and the row or clause."""
    m = chunk.metadata
    codes = m.get("exclusion_codes") or []
    what = codes[0] if codes else (m.get("clause") or "?")
    return f"{m.get('form_number')}@{m.get('edition_date')} {what}"


def snippet(chunk) -> str:
    """The last line of the chunk - for a table row, the row itself."""
    lines = [ln.strip() for ln in chunk.text.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.startswith("Form ")] or lines
    line = " ".join(body[-1].split())
    return line[:SNIPPET_CHARS] + ("..." if len(line) > SNIPPET_CHARS else "")


def _stage_tags(cand, mode: str) -> List[str]:
    tags = []
    for st in STAGE_ORDER:
        if st == "rrf" and mode == "dense":
            continue
        if st == "bm25" and mode == "dense":
            continue
        r = cand.stages.get(st)
        tags.append(f"{st}#{r[0]}({r[1]:.3f})" if r else f"{st}#-")
    return tags


def _present_tags(cand) -> str:
    return ", ".join(f"{st}#{cand.stages[st][0]}({cand.stages[st][1]:.3f})"
                     for st in STAGE_ORDER if st in cand.stages)


def inspect(question: str, gold_chunk_id: Optional[str] = None,
            strategy: str = "structure_aware", mode: str = RETRIEVAL_MODE,
            top_k: int = 3) -> dict:
    cands = search_explain(question, strategy=strategy, mode=mode, candidates=CANDIDATES)
    top = cands[:top_k]
    top_ids = [c.chunk.chunk_id for c in top]

    gold_pos = next((i for i, c in enumerate(cands) if c.chunk.chunk_id == gold_chunk_id), None)
    gold_rank = None if gold_chunk_id is None or gold_pos is None else gold_pos + 1
    hit = gold_chunk_id is not None and gold_chunk_id in top_ids

    res = answer(question, strategy=strategy, top_k=top_k, mode=mode)
    cited = res["citations"][0]["chunk_id"] if res["citations"] else None
    answer_ok = bool(gold_chunk_id) and cited == gold_chunk_id
    coverage, missing = term_coverage(question)

    tokens = exact_tokens(question)
    carrying = sum(1 for c in top
                   if all(t.lower() in c.chunk.text.lower() for t in tokens)) if tokens else 0
    top_desc = ", ".join(describe(c.chunk) for c in top)

    if gold_chunk_id is None:
        label = cause = "NIC"
        chunks = get_registry(strategy).chunks
        n_carry = sum(1 for c in chunks
                      if tokens and all(t.lower() in c.text.lower() for t in tokens))
        evidence = (f"no chunk_id is known to be correct; {n_carry} of {len(chunks)} indexed "
                    f"chunks carry all of {tokens}; top-3 = {top_desc}")
    elif hit and answer_ok:
        label = cause = "PASS"
        evidence = f"gold at {mode} rank {gold_rank}; quoted from it"
    elif hit and res["refused"]:
        label, cause = "G", "G-refuse"
        why = res["reason"].replace("Refused without composing an answer.", "").strip(" .")
        evidence = (f"gold `{gold_chunk_id}` IS in the top-3 at rank {gold_rank}, but the "
                    f"answer step REFUSED (gate={res['gate']}: {why})")
    elif hit:
        label, cause = "G", "G-rank"
        cited_c = next((c for c in cands if c.chunk.chunk_id == cited), None)
        cited_desc = describe(cited_c.chunk) if cited_c else "?"
        evidence = (f"gold `{gold_chunk_id}` IS in the top-3 at rank {gold_rank}, but the "
                    f"answer step reads ONLY rank 1 and quoted `{cited}` ({cited_desc})")
    else:
        label = cause = "R"
        if gold_pos is None:
            where = f"below rank {CANDIDATES} [-]"
        else:
            where = f"rank {gold_rank} [{_present_tags(cands[gold_pos])}]"
        evidence = f"gold `{gold_chunk_id}` at {mode} {where}; top-3 = {top_desc}"
        if tokens:
            evidence += f"; {carrying}/3 of the top-3 carry {tokens}"

    return {"question": question, "gold": gold_chunk_id, "mode": mode, "strategy": strategy,
            "candidates": cands, "top_ids": top_ids, "gold_rank": gold_rank, "hit": hit,
            "answer_ok": answer_ok, "cited": cited, "refused": res["refused"],
            "gate": res["gate"], "reason": res["reason"],
            "coverage": round(coverage, 3), "missing_terms": missing,
            "tokens": tokens, "carrying": carrying,
            "label": label, "cause": cause, "evidence": evidence}


def render(v: dict, show: int = 5) -> str:
    out = [f"Q: {v['question']}",
           f"mode={v['mode']}  gold={v['gold']}  gold_rank={v['gold_rank']}  "
           f"hit@3={v['hit']}  answer_ok={v['answer_ok']}  label={v['label']} ({v['cause']})"]
    if v["tokens"]:
        out.append(f"exact tokens in question: {v['tokens']}  "
                   f"(top-3 chunks carrying all of them: {v['carrying']}/3)")
    out.append("candidates (final order):")

    cands: Sequence = v["candidates"]
    shown = list(range(min(show, len(cands))))
    gold_pos = None if v["gold_rank"] is None else v["gold_rank"] - 1
    if gold_pos is not None and gold_pos not in shown:
        out_gold = True
    else:
        out_gold = False

    for i in shown:
        out += _cand_lines(cands[i], i + 1, v)
    if out_gold:
        out.append("  ...")
        out += _cand_lines(cands[gold_pos], gold_pos + 1, v)
    if v["gold"] is not None and v["gold_rank"] is None:
        out.append(f"  gold {v['gold']} not within the {CANDIDATES} candidates")

    out.append(f"answer quoted from: {v['cited']}")
    out.append(f"evidence: {v['evidence']}")
    return "\n".join(out)


def _cand_lines(cand, rank: int, v: dict) -> List[str]:
    tags = "  ".join(_stage_tags(cand, v["mode"]))
    mark = "  <-- GOLD" if cand.chunk.chunk_id == v["gold"] else ""
    m = cand.chunk.metadata
    return [f"{rank:>4}. {tags}  {cand.chunk.chunk_id}{mark}",
            f"      {m.get('form_number')} ed.{m.get('edition_date')} {m.get('clause')}: "
            f"{snippet(cand.chunk)}"]
