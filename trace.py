"""One JSON line per answered question. Redacts, asserts, then appends.

Order matters and is the whole point of the module:

    build record  ->  redact.redact_record()  ->  assert no identifier survives
                  ->  json.dumps()            ->  append

The redaction happens to the in-memory record, before serialisation, so no
identifier is ever written to disk and later removed. If the assertion fails the
writer raises and the line is not written at all - a trace file that is missing a
line is recoverable, one that leaked a claimant's name is not.

A trace holds everything needed to rebuild the run without the app: the chunk ids
and their scores, the corpus fingerprint those ids are valid against, the policy
version and its sha, and the gate readings that decided the outcome.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from redact import redact_record, residual_identifiers
from src.indexer import get_registry

SCHEMA_VERSION = 1


def corpus_fingerprint(strategy: str = "structure_aware") -> dict:
    """Identifies the exact indexed corpus a trace's chunk ids are valid against."""
    h = hashlib.sha256()
    chunks = get_registry(strategy).chunks
    for c in chunks:
        h.update(c.chunk_id.encode("utf-8"))
        h.update(b"\x00")
        h.update(c.text.encode("utf-8"))
        h.update(b"\x00")
    return {"strategy": strategy, "chunks": len(chunks), "sha": h.hexdigest()[:12]}


def trace_id(run: str, qid: str, question: str) -> str:
    """Deterministic, so a re-run of the same traffic addresses the same traces."""
    h = hashlib.sha256(f"{run}|{qid}|{question}".encode("utf-8")).hexdigest()
    return f"trc_{h[:12]}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TraceWriter:
    def __init__(self, path: Path, run: str):
        self.path = Path(path)
        self.run = run
        self.written = 0

    def write(self, record: dict) -> dict:
        clean, counts = redact_record(record)
        clean["redaction"] = {"counts": counts, "total": sum(counts.values())}

        line = json.dumps(clean, ensure_ascii=False, sort_keys=True)
        residual = residual_identifiers(line)
        if residual:
            raise ValueError(
                f"refusing to write trace {record.get('trace_id')}: identifier survived "
                f"redaction: {residual[:5]}")

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        self.written += 1
        return clean


def read_traces(path: Path) -> list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"no trace file at {p} - run run_traffic.py first")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def find_trace(path: Path, tid: str) -> Optional[dict]:
    return next((t for t in read_traces(path) if t["trace_id"] == tid), None)
