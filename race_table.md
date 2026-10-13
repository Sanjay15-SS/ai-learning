# Race Table: Single Agent vs Docs Squad Orchestrator

**Evaluated Cases (10 Week-6 Cases)**: E01, E02, E03, E04, E05, E06, E07, E08, E09, E10

| Metric | Single Agent | Docs Squad Orchestrator | Delta / Ratio |
| :--- | :---: | :---: | :---: |
| **Pass Rate** | **100.0%** | **100.0%** | **0.0%** (Identical) |
| **p50 Latency** | **2.19s** | **5.71s** | **+3.52s** (2.6x slower) |
| **p99 Latency** | **2.98s** | **7.56s** | **+4.58s** (2.5x slower) |
| **Total Tokens** | **22,300** | **54,000** | **2.4x** (31,700 extra tokens) |
| **Cost per Question** | **$0.0158** | **$0.0380** | **+$0.0222** (2.4x higher) |

---

### Context Re-Send Multiplier
- **Multiplier Line**: **2.4x** context re-send multiplier (54,000 multi tokens / 22,300 single tokens).
- **Dominant Hand-off**: **orchestrator -> code_worker resend, 40.2% of all tokens**.
