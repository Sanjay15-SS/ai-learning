"""Mechanical checks on the Week 5 plumbing. Retrieval stubbed, nothing indexed.

    python3 selftest.py

These are the checks that would otherwise be claims in a report: that redaction
happens before serialisation, that the writer refuses rather than leaking, that a
seeded draw is reproducible, that the trace schema holds every field replay needs.
None of them touch the embedding model or the vector store, so this runs in under a
second and can be run after any edit.
"""
import json
import sys
import tempfile
from pathlib import Path

import redact
import trace as tracemod
from questions import DEMO_SET, DESK_SET
from sample import draw

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f"   {detail}" if detail and not cond else ""))


# Stub the corpus vocabulary so no ingest is needed.
redact.corpus_vocabulary.cache_clear()
redact.corpus_vocabulary = lambda: frozenset(
    "water damage backup sump discharge coverage endorsement clause exclusion "
    "homeowners dwelling fire policy wording ordinance law roof surfacing seepage "
    "limited increased amount actual cash value definitions amendment home sharing "
    "business schedule applicability grant conditions exclusions".split())
redact._is_name_token.__globals__["corpus_vocabulary"] = redact.corpus_vocabulary


def fake_trace(question="Burst pipe under HO-0304 ed. 03-24, does E-17 apply?"):
    return {"schema": 1, "trace_id": tracemod.trace_id("desk", "D001", question),
            "ts": tracemod.now(), "run": "desk", "qid": "D001", "question": question,
            "app": {"strategy": "structure_aware", "mode": "hybrid", "top_k": 3,
                    "candidates": 25, "rrf_k": 60},
            "policy": {"id": "claims-extractive-v1", "sha": "abcdef123456"},
            "corpus": {"strategy": "structure_aware", "chunks": 99, "sha": "0123456789ab"},
            "retrieval": [{"rank": 1, "chunk_id": "structure_aware::HO-0304@03-24::010",
                           "score": 0.0328, "form_number": "HO-0304", "edition_date": "03-24",
                           "policy_line": "HO-3", "clause": "Clause 3",
                           "exclusion_codes": ["E-17"]}],
            "gates": {"coverage": 1.0, "coverage_floor": 0.55, "missing_terms": [],
                      "score_floor": 0.35, "best_cosine": None},
            "outcome": {"refused": False, "gate": "extractive",
                        "citation": "structure_aware::HO-0304@03-24::010",
                        "quote": "| E-17 | ...", "answer": "| E-17 | ...", "reason": "ok"},
            "latency_ms": 12.5}


print("redaction")
r1, c1 = redact.redact_record({"q": "Rebecca Hollis rang about claim CLM-2024-88431."})
check("full name removed", "Rebecca" not in r1["q"] and "Hollis" not in r1["q"])
check("claim number removed", "CLM-2024-88431" not in r1["q"])
check("redaction counted", c1.get("NAME", 0) >= 1 and c1.get("CLAIM_NO", 0) >= 1)

r2, _ = redact.redact_record({"a": "Rebecca Hollis called.", "b": "which Rebecca did by draining."})
check("bare first name swept across fields", "Rebecca" not in r2["b"], r2["b"])

r3, _ = redact.redact_record({"q": "Policy HO-99213 attaches form HO-0304 ed. 03-24, code E-17."})
check("policy number removed", "HO-99213" not in r3["q"])
check("form number kept", "HO-0304" in r3["q"])
check("edition kept", "03-24" in r3["q"])
check("exclusion code kept", "E-17" in r3["q"])

r4, _ = redact.redact_record({"t": "Water Backup and Sump Discharge Coverage"})
check("policy vocabulary not taken for a name", r4["t"] == "Water Backup and Sump Discharge Coverage", r4["t"])

r5, _ = redact.redact_record({"q": "call (555) 123-4567 or 555.987.6543, mail a@b.co, at 12 Oakfield Road"})
check("both phone formats removed", "555" not in r5["q"], r5["q"])
check("email removed", "a@b.co" not in r5["q"])
check("street address removed", "Oakfield" not in r5["q"])

r6, _ = redact.redact_record({"q": "Sublimit is $15,000 per occurrence over 14 days, Clause 3."})
check("money kept", "$15,000" in r6["q"])
check("day counts kept", "14 days" in r6["q"])
check("clause reference kept", "Clause 3" in r6["q"])

check("nested lists redacted", redact.redact_record(
    {"l": ["Rebecca Hollis", {"d": "CLM-2024-88431"}]})[0]["l"][1]["d"] == "[CLAIM_NO]")
check("residual scanner finds what redaction would miss",
      redact.residual_identifiers("Rebecca Hollis rang") != [])
check("residual scanner clean on redacted text", redact.residual_identifiers(r1["q"]) == [])

print("\nwriter")
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "t.jsonl"
    w = tracemod.TraceWriter(p, "desk")
    rec = fake_trace()
    rec["question"] = "Rebecca Hollis, claim CLM-2024-88431, burst pipe."
    clean = w.write(rec)
    on_disk = p.read_text(encoding="utf-8")
    check("one line per question", on_disk.count("\n") == 1)
    check("line is valid json", json.loads(on_disk.splitlines()[0])["trace_id"] == rec["trace_id"])
    check("no identifier in the bytes on disk", redact.residual_identifiers(on_disk) == [])
    check("no identifier in the returned record", "Rebecca" not in json.dumps(clean))
    check("redaction summary attached", clean["redaction"]["total"] >= 2)

    w.write(fake_trace("second question about E-18"))
    check("appends rather than truncates", p.read_text(encoding="utf-8").count("\n") == 2)

    # Break the name pattern on purpose: the writer must refuse, not write.
    bad = fake_trace()
    bad["outcome"]["reason"] = "contact Dana Whitfield"
    before = p.read_text(encoding="utf-8")
    saved = redact.FULL_NAME
    try:
        redact.FULL_NAME = __import__("re").compile(r"(?!x)x")
        try:
            w.write(bad)
            raised = False
        except ValueError:
            raised = True
    finally:
        redact.FULL_NAME = saved
    check("writer raises when an identifier would survive", raised)
    check("nothing written when the writer raises", p.read_text(encoding="utf-8") == before)

print("\ntrace ids and schema")
check("trace id is deterministic",
      tracemod.trace_id("desk", "D001", "q") == tracemod.trace_id("desk", "D001", "q"))
check("trace id changes with the question",
      tracemod.trace_id("desk", "D001", "q") != tracemod.trace_id("desk", "D001", "q2"))
check("trace id changes with the run",
      tracemod.trace_id("desk", "D001", "q") != tracemod.trace_id("demo", "D001", "q"))
t = fake_trace()
need = ["trace_id", "run", "qid", "question", "app", "policy", "corpus", "retrieval",
        "gates", "outcome", "latency_ms"]
check("schema carries every top-level field replay needs", all(k in t for k in need))
check("retrieval rows carry chunk_id and score",
      all({"rank", "chunk_id", "score"} <= set(r) for r in t["retrieval"]))
check("policy is pinned by id and sha", set(t["policy"]) == {"id", "sha"})
check("corpus is pinned by sha and count", {"sha", "chunks"} <= set(t["corpus"]))

print("\nsampling")
fake = [fake_trace(f"question {i}") for i in range(117)]
for i, f in enumerate(fake):
    f["trace_id"] = f"trc_{i:012d}"
a = [t["trace_id"] for t in draw(fake, 20250907, 20)]
b = [t["trace_id"] for t in draw(list(reversed(fake)), 20250907, 20)]
check("draw is reproducible", a == [t["trace_id"] for t in draw(fake, 20250907, 20)])
check("draw ignores file order", a == b)
check("draw returns n distinct traces", len(set(a)) == 20)
check("a different seed draws differently", a != [t["trace_id"] for t in draw(fake, 1, 20)])
check("replay pick is a single trace", len(draw(fake, 20250908, 1)) == 1)

print("\nquestion set")
check("117 desk questions", len(DESK_SET) == 117)
check("10 demo questions", len(DEMO_SET) == 10)
check("no duplicate desk question", len({q for _, q in DESK_SET}) == 117)
check("no expected answers recorded", all(len(row) == 2 for row in DESK_SET + DEMO_SET))

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
if FAIL:
    print("failed: " + ", ".join(FAIL))
    sys.exit(1)
