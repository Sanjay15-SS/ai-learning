"""The Week 6 docs assistant: retrieve pages, one model call, answer in the contract.

    app v1 - retrieval searches every version (what shipped)
    app v2 - retrieval is scoped to the version the developer is on (THE one change)

Nothing else differs between v1 and v2: same prompt, same model, same k.
"""
import time

from .contract import CONTRACT, target_version
from .corpus import search
from . import llm

SYSTEM = ("You answer developer questions about the Ledgerline payments API using ONLY the "
          "documentation pages supplied with each question.\n\n" + CONTRACT)

K = 4


def retrieve(question: str, app: str):
    version = target_version(question) if app == "v2" else None
    return search(question, api_version=version, k=K)


def answer(question: str, app: str = "v1") -> dict:
    t0 = time.perf_counter()
    hits = retrieve(question, app)
    context = "\n\n".join(f"<page id=\"{p.page_id}\" version=\"{p.api_version}\">\n"
                          f"{p.title}\n{p.body}\n</page>" for p in hits)
    usage = llm.Usage()
    r = llm.create(usage, system=SYSTEM, max_tokens=4000, messages=[{"role": "user", "content":
        f"Documentation:\n{context}\n\nDeveloper question: {question}"}])
    return {"app": app, "question": question, "answer": llm.text_of(r),
            "stop_reason": r.stop_reason, "retrieved": [p.page_id for p in hits],
            "latency_s": round(time.perf_counter() - t0, 3), "usage": usage.as_dict()}
