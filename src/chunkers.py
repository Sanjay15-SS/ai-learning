"""Two chunking strategies over the same 6 endorsements, same embedding model.

Strategy 1 (baseline)         - the Week 3 chunker: fixed-width character windows with overlap.
                    Structure-blind, so an exclusion row can be cut away from its
                    table header and from the form number that scopes it.

Strategy 2 (structure_aware)  - splits on form/clause headers, and emits ONE CHUNK PER
                    EXCLUSION ROW, each carrying the form number, edition date,
                    policy line, clause title and the table's header row. An
                    exclusion row is never separated from its table header or its
                    form number.
"""
import re
from typing import List, Optional

from . import Chunk, Document

CLAUSE_RE = re.compile(r"^##\s+(.*)$", re.M)
CLAUSE_ID_RE = re.compile(r"(Clause\s+\d+)", re.I)
EXCL_CODE_RE = re.compile(r"\b(E-\d{2})\b")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def _base_meta(doc: Document, strategy: str) -> dict:
    """Requirement 1 metadata, stamped on every chunk from either strategy."""
    return {
        "source_file": doc.source_file,
        "form_number": doc.form_number,
        "policy_line": doc.policy_line,
        "edition_date": doc.edition_date,
        "effective_date": doc.effective_date,
        "title": doc.title,
        "strategy": strategy,
    }


# --------------------------------------------------------------------------
# Strategy A - baseline (structure-blind fixed windows)
# --------------------------------------------------------------------------

def _clause_at(text: str, pos: int) -> str:
    """Best-effort: the clause heading most recently preceding this offset."""
    last = ""
    for m in CLAUSE_RE.finditer(text):
        if m.start() > pos:
            break
        last = m.group(1).strip()
    cid = CLAUSE_ID_RE.search(last)
    return cid.group(1).title() if cid else (last or "Header")


def baseline_chunks(doc: Document, size: int, overlap: int,
                    strategy: str = "baseline") -> List[Chunk]:
    text = doc.text
    step = max(1, size - overlap)
    chunks: List[Chunk] = []
    for start in range(0, len(text), step):
        piece = text[start:start + size]
        if not piece.strip():
            continue
        idx = len(chunks)
        meta = _base_meta(doc, strategy)
        meta.update({
            "clause": _clause_at(text, start),
            "exclusion_codes": sorted(set(EXCL_CODE_RE.findall(piece))),
            "chunk_index": idx,
            "char_start": start,
            "char_end": min(start + size, len(text)),
        })
        chunks.append(Chunk(f"{strategy}::{doc.form_number}@{doc.edition_date}::{idx:03d}", piece.strip(), meta))
        if start + size >= len(text):
            break
    return chunks


# --------------------------------------------------------------------------
# Strategy B - structure-aware (header/clause split, one chunk per exclusion row)
# --------------------------------------------------------------------------

def _split_sections(text: str):
    """Yield (heading, body) pairs. Text before the first '##' is the Header section."""
    matches = list(CLAUSE_RE.finditer(text))
    if not matches:
        return [("Header", text)]
    out = [("Header", text[: matches[0].start()].strip())]
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1).strip(), text[m.end():end].strip()))
    return [(h, b) for h, b in out if b]


def _split_table(body: str):
    """Return (prose_lines, tables) where each table is (header_line, [row_lines])."""
    prose, tables = [], []
    cur_header, cur_rows, in_table = None, [], False
    for line in body.splitlines():
        if TABLE_ROW_RE.match(line):
            if TABLE_SEP_RE.match(line):
                in_table = True
                continue
            if not in_table and cur_header is None:
                cur_header = line.strip()
            elif in_table:
                cur_rows.append(line.strip())
            else:
                cur_header = line.strip()
        else:
            if cur_header is not None:
                tables.append((cur_header, cur_rows))
                cur_header, cur_rows, in_table = None, [], False
            prose.append(line)
    if cur_header is not None:
        tables.append((cur_header, cur_rows))
    return prose, tables


def _context_header(doc: Document, clause: str) -> str:
    """The provenance stamp that travels with every structure-aware chunk."""
    return (f"Form {doc.form_number} (ed. {doc.edition_date}) — {doc.title} — "
            f"Policy Line {doc.policy_line} — {clause}")


def _paragraph_pack(paragraphs, max_chars: int):
    out, cur = [], ""
    for p in paragraphs:
        if cur and len(cur) + len(p) + 2 > max_chars:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        out.append(cur)
    return out


def structure_aware_chunks(doc: Document, max_chars: int,
                           strategy: str = "structure_aware") -> List[Chunk]:
    chunks: List[Chunk] = []

    def add(text: str, clause: str, kind: str,
            code: Optional[str] = None, table_header: Optional[str] = None):
        idx = len(chunks)
        meta = _base_meta(doc, strategy)
        cid = CLAUSE_ID_RE.search(clause)
        meta.update({
            "clause": cid.group(1).title() if cid else clause,
            "clause_heading": clause,
            "kind": kind,
            "exclusion_codes": [code] if code else sorted(set(EXCL_CODE_RE.findall(text))),
            "table_header": table_header,
            "chunk_index": idx,
        })
        chunks.append(Chunk(f"{strategy}::{doc.form_number}@{doc.edition_date}::{idx:03d}", text.strip(), meta))

    for clause, body in _split_sections(doc.text):
        prose_lines, tables = _split_table(body)
        header = _context_header(doc, clause)

        prose = "\n".join(prose_lines).strip()
        if prose:
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
            for packed in _paragraph_pack(paragraphs, max_chars):
                add(f"{header}\n\n{packed}", clause, "prose")

        # One chunk per table row. The row always ships with the form number,
        # the clause it sits under, and the table's own header row.
        for table_header, rows in tables:
            for row in rows:
                code_m = EXCL_CODE_RE.search(row)
                add(f"{header}\n\n{table_header}\n{row}", clause, "table_row",
                    code_m.group(1) if code_m else None, table_header)

    return chunks


def chunk_document(doc: Document, strategy: str, **kw) -> List[Chunk]:
    if strategy == "baseline":
        return baseline_chunks(doc, kw["size"], kw["overlap"])
    if strategy == "structure_aware":
        return structure_aware_chunks(doc, kw["max_chars"])
    raise ValueError(f"unknown strategy {strategy}")
