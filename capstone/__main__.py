"""One entry point.

    python3 -m capstone ask "I'm on 2.4 - how do I paginate?" [--sdk-version 2.4] [--mode before]
    python3 -m capstone all                 # THE one command: corpus, demo, evals, report
    python3 -m capstone eval [--mode both] [--ids C01,C11] [--no-judge]
    python3 -m capstone report              # re-compute every number from runs/ (no model calls)
    python3 -m capstone trace <trace_id>    # one trace, engine spans + MCP-server spans joined
    python3 -m capstone promote <trace_id> --case C01   # failure -> permanent regression case
    python3 -m capstone loop                # the closed failure->test loop, live (red -> green)
    python3 -m capstone label               # hand-label the after-run answers (PASS/FAIL)
    python3 -m capstone mcp                 # run the MCP server on stdio for an outside client
"""
import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="capstone")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--sdk-version")
    p.add_argument("--mode", default="after", choices=["before", "after"])
    p = sub.add_parser("eval"); p.add_argument("--mode", default="both")
    p.add_argument("--ids"); p.add_argument("--no-judge", action="store_true")
    p.add_argument("--subset", action="store_true", help="the 12-case subset (~1 h on an 8 GB M1)")
    p.add_argument("--fresh", action="store_true", help="discard previous rows instead of resuming")
    sub.add_parser("report")
    p = sub.add_parser("trace"); p.add_argument("trace_id")
    p = sub.add_parser("promote"); p.add_argument("trace_id"); p.add_argument("--case", required=True)
    sub.add_parser("loop")
    sub.add_parser("label")
    sub.add_parser("mcp")
    sub.add_parser("demo")
    p = sub.add_parser("all"); p.add_argument("--no-judge", action="store_true")
    p.add_argument("--subset", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "mcp":
        from .mcp_server import build
        return build().run_stdio()
    from .build_corpus import build as build_corpus, OUT
    if not (OUT / "CHANGELOG.md").exists():
        print("building corpus:", build_corpus())
    if a.cmd == "ask":
        from .engine import answer, close_session
        try:
            r = answer(a.question, a.sdk_version, a.mode)
        finally:
            close_session()
        print(f"trace_id: {r['trace_id']}  version: {r['version']['version']} "
              f"(from {r['version']['source']})  cost: ${r['total_cost_usd']:.5f}  "
              f"latency: {r['total_latency_s']}s\n\n{r['answer']}")
    elif a.cmd == "eval":
        from . import evaluate as E
        ids = a.ids.split(",") if a.ids else (E.SUBSET if a.subset else None)
        for m in (["before", "after"] if a.mode == "both" else [a.mode]):
            print(f"== eval {m} ==")
            E.run(m, ids, use_judge=not a.no_judge and m == "after", fresh=a.fresh)
        from .report import write_report
        write_report()
    elif a.cmd == "report":
        from .report import write_report
        print(write_report())
    elif a.cmd == "trace":
        from .obs import full_trace
        print(json.dumps(full_trace(a.trace_id), indent=2))
    elif a.cmd == "promote":
        from .loop import promote
        print(json.dumps(promote(a.trace_id, a.case), indent=2))
    elif a.cmd == "loop":
        from .loop import closed_loop
        closed_loop()
    elif a.cmd == "label":
        from .loop import label
        label()
    elif a.cmd == "demo":
        from .loop import demo
        demo()
    elif a.cmd == "all":
        from .loop import demo, closed_loop
        from . import evaluate as E
        from .report import write_report
        demo()
        for m in ("before", "after"):
            print(f"== eval {m} ==")
            E.run(m, E.SUBSET if a.subset else None, use_judge=not a.no_judge and m == "after")
        closed_loop()
        print(write_report())


if __name__ == "__main__":
    sys.exit(main())
