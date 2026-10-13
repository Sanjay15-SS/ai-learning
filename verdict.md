# Verdict: KILL the Orchestrator

We name the sunk-cost bias out loud: our team invested substantial effort engineering
orchestrator prompts, worker contracts, and hand-off schemas, creating a strong bias to preserve it.
However, the empirical numbers are decisive: the orchestrator incurred a 2.4x token penalty
(54,000 vs 22,300 tokens) and increased cost by 141%
($0.0380 vs $0.0158/q) while producing an identical 100% pass rate.
Adding multi-hop latency (5.71s vs 2.19s p50) and extra failure modes yields negative ROI.
We kill the multi-agent docs squad and retain the single agent.
