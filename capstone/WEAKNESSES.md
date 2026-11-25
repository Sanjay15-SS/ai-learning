# Top 3 known weaknesses

**Written Wednesday 2026-11-25, before the full eval numbers came in and before anyone asked.**
Not edited after the run. Where the run confirmed or contradicted a point, that is in
EVAL_REPORT.md, not here.

## 1. The code check trusts a symbol table we wrote, not the SDK

`codecheck.py` proves a sample matches `sdk_spec.py`. It does not prove the sample runs against
a real `pip install ledgerline==2.4.1`. If the table drifts from the release (v3.1 ships next
month with two more deprecations), every check stays green and is confidently wrong. Mitigation
today: selftest #9 goes red when a deprecated symbol has no eval case. It does NOT catch a
symbol that is missing from the table entirely. The real fix is to generate the table from the
released wheel (`inspect` over the installed package) in CI on every release.

## 2. The agent mostly doesn't verify; the guards do

The 3B local model often answers straight from the retrieved context without calling
`symbol_exists` / `check_code`. When an answer comes out right, it is usually because the
deterministic code check and one repair call rescued it, not because the agent reasoned
correctly. Expect low tool-choice accuracy and a large outcome-minus-trajectory gap. That also
makes the repair call the most common extra cost and the biggest latency hit.

## 3. Version resolution is a regex over the question

A caller who doesn't state a version is assumed to be on 3.0 and gets v3 code with one
"Assuming SDK 3.0" line. For ~40% of integrators (still on 2.x) that is the wrong default. Mixed
signals ("we upgraded staging to 3.0 but prod is on 2.4") resolve to whichever pattern matches
first. In-IDE, the version should come from the lockfile / `pip freeze` the IDE already has, not
from the prose.
