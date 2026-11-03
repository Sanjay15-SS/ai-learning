"""Quick verification script for Week 11 pipeline."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

from week11.run_task import run_full_week11, DRILL_MD, TRACE_JSON, COST_MD, TENX_MD, EVAL_CASE_PATH

r = run_full_week11()
red = r['red']
grn = r['green']
dr = r['drill']

print("=== WEEK 11 VERIFICATION ===")
print(f"Drill time-to-find : {dr['time_to_find_mmss']}")
print(f"Slice used         : {dr['slice_used']}")
print(f"Trace found        : {dr['trace_found']['trace_id']}")
print(f"Context IDs        : {dr['trace_found']['context_ids']}")
spans = dr['trace_found']['spans']
print(f"Spans              : retrieval={spans['retrieval_s']}s  llm={spans['llm_s']}s  total={spans['total_s']}s")
usage = dr['trace_found']['usage']
print(f"Tokens             : in={usage['input_tokens']} out={usage['output_tokens']} total={usage['total_tokens']}")
print(f"Cost               : ${usage['cost_usd']:.6f}")
cbs = dr['trace_found']['cost_by_stage']
print(f"Cost by stage      : retrieval=${cbs['retrieval_usd']:.6f} gen=${cbs['generation_usd']:.6f} tools=${cbs['tools_usd']:.6f}")
print()
print(f"Suite RED  (before fix): {red['passed']}/{red['total']} pass")
print(f"Suite GREEN (after fix): {grn['passed']}/{grn['total']} pass")
print()
print(f"Prompt version: {r['prompt_version_before']} -> {r['prompt_version_after']}")
print()
for p in [DRILL_MD, TRACE_JSON, COST_MD, TENX_MD, EVAL_CASE_PATH]:
    print(f"  {'OK' if p.exists() else 'MISSING'}: {p.name}")
