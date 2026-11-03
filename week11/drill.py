"""Week 11 — Drill: find the trace with a deprecated code sample in its *output*.

Usage:
    python -m week11.drill

The drill searches the structured trace log (traces/traces_w11.jsonl) for any
answer whose output_text contains a deprecated v2 symbol being used AS IF it
were valid in v3 code.  This is the hard case the Common Mistakes section warns
about: the deprecated call is in the *generated sample*, not in the question.

Search slices tried (in order):
  1. output_text grep for deprecated symbols from changelog
  2. assertions_pass == False AND assertions.deprecations_noted == False
  3. input_type == 'code_request' (narrows the log)
  4. cost_by_stage.total_usd outlier (> mean + 1 std)

Returns the first matching trace and reports time-to-find in mm:ss plus the
slice that found it.
"""
import json
import math
import re
import time
from pathlib import Path
from typing import Optional

from src.corpus import changelog
from week11.observability import read_traces, STRUCTURED_LOG

# Deprecated symbols pattern built from the changelog
_DEPRECATED_PATTERNS: Optional[list] = None


def _deprecated_patterns() -> list:
    global _DEPRECATED_PATTERNS
    if _DEPRECATED_PATTERNS is None:
        _DEPRECATED_PATTERNS = [re.compile(e["pattern"]) for e in changelog()]
    return _DEPRECATED_PATTERNS


def _mean_std(values: list) -> tuple:
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in values) / n)
    return mean, std


def drill(log_path: Path = STRUCTURED_LOG) -> dict:
    """Run the drill and return a result dict."""
    t_start = time.perf_counter()
    traces = read_traces(log_path)
    if not traces:
        return {"error": f"No traces found in {log_path}"}

    pats = _deprecated_patterns()

    def output_contains_deprecated(tr: dict) -> bool:
        output = tr.get("output_text", "") or ""
        if not output:
            return False
        # Only flag if the deprecated symbol appears inside a code block
        code_blocks = re.findall(r"```python(.*?)```", output, re.S)
        code = "\n".join(code_blocks)
        return any(p.search(code) for p in pats)

    # Slice 1: output_text grep for deprecated symbols in code blocks
    found = None
    slice_used = None

    candidates_slice1 = [tr for tr in traces if output_contains_deprecated(tr)]
    if candidates_slice1:
        # Prioritise traces where assertions.deprecations_noted is explicitly False
        flagged = [tr for tr in candidates_slice1
                   if tr.get("assertions", {}).get("deprecations_noted") is False]
        found = (flagged or candidates_slice1)[0]
        slice_used = "output_text (deprecated-symbol grep on code blocks)"
    else:
        # Slice 2: assertion failure on deprecations_noted
        slice2 = [tr for tr in traces
                  if tr.get("assertions", {}).get("deprecations_noted") is False
                  and tr.get("assertions_pass") is False]
        if slice2:
            found = slice2[0]
            slice_used = "assertions.deprecations_noted == False"
        else:
            # Slice 3: input_type == code_request + assertions_pass False
            slice3 = [tr for tr in traces
                      if tr.get("input_type") == "code_request"
                      and not tr.get("assertions_pass", True)]
            if slice3:
                found = slice3[0]
                slice_used = "input_type:code_request + assertions_pass:False"
            else:
                # Slice 4: cost outlier
                costs = [tr.get("cost_by_stage", {}).get("total_usd", 0.0) for tr in traces]
                mean, std = _mean_std(costs)
                threshold = mean + std
                outliers = [tr for tr, c in zip(traces, costs)
                            if c > threshold and not tr.get("assertions_pass", True)]
                if outliers:
                    found = sorted(outliers,
                                   key=lambda t: -t.get("cost_by_stage", {}).get("total_usd", 0))[0]
                    slice_used = "cost_outlier (> mean+1σ) + assertions_pass:False"

    elapsed_s = time.perf_counter() - t_start
    mm = int(elapsed_s // 60)
    ss = int(elapsed_s % 60)
    time_to_find = f"{mm:02d}:{ss:02d}"

    result: dict = {
        "time_to_find_mmss": time_to_find,
        "elapsed_s": round(elapsed_s, 3),
        "slice_used": slice_used,
        "trace_found": found,
        "total_traces_searched": len(traces),
    }

    if found is None:
        result["missing_log_field"] = (
            "output_text was not indexed (old traces lack this field).  "
            "Without output_text the search must fall back to assertion results, "
            "which requires that the prod pipeline actually ran assertions and stored them."
        )
    return result


def print_drill_report(result: dict) -> None:
    print("=" * 60)
    print("DRILL REPORT — Week 11 Failure Search")
    print("=" * 60)
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    print(f"Time-to-find : {result['time_to_find_mmss']}")
    print(f"Elapsed      : {result['elapsed_s']:.3f}s")
    print(f"Slice used   : {result['slice_used']}")
    print(f"Traces scanned: {result['total_traces_searched']}")
    if result.get("trace_found"):
        tr = result["trace_found"]
        print(f"\nFound trace  : {tr.get('trace_id')}")
        print(f"  timestamp  : {tr.get('ts')}")
        print(f"  question   : {tr.get('question')}")
        print(f"  prompt_ver : {tr.get('prompt_version')}")
        print(f"  input_type : {tr.get('input_type')}")
        print(f"  context_ids: {tr.get('context_ids')}")
        spans = tr.get("spans", {})
        print(f"  spans      : retrieval={spans.get('retrieval_s')}s  "
              f"llm={spans.get('llm_s')}s  total={spans.get('total_s')}s")
        usage = tr.get("usage", {})
        print(f"  tokens     : in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
              f"total={usage.get('total_tokens')}")
        cbs = tr.get("cost_by_stage", {})
        print(f"  cost/stage : retrieval=${cbs.get('retrieval_usd'):.6f}  "
              f"generation=${cbs.get('generation_usd'):.6f}  "
              f"tools=${cbs.get('tools_usd'):.6f}  "
              f"total=${cbs.get('total_usd'):.6f}")
        print(f"  assertions : {tr.get('assertions')}")
    else:
        print(f"\nNOT FOUND. Missing log field: {result.get('missing_log_field')}")
    print("=" * 60)


if __name__ == "__main__":
    from week11.plant import plant_bad_trace
    plant_bad_trace()          # ensure there is something to find
    result = drill()
    print_drill_report(result)
