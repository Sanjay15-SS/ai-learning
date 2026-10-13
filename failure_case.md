# Injected Worker Failure — Case E07

## 1. Failure Injection Setup
- **Target Case**: `E07` ("Our v2 code sends source=tok_visa when charging. What do we send in v3?")
- **Failed Worker**: Version/Deprecation Worker
- **Injected Response**: `500 Internal Server Error: Deprecation registry service unavailable`

## 2. Orchestrator Actual Behavior (Recorded Honestly)
**One-Line Record**:
The orchestrator degraded to a partial answer (omitted deprecation verification due to worker 500).

### Detail:
Rather than crashing or halting the entire pipeline, the orchestrator caught the 500 status from the Version Worker. It fell back to generating code for PaymentIntents without formal changelog deprecation verification, resulting in a degraded answer that omitted deprecation notes.

```json
{
  "case_id": "E07",
  "injected_worker": "version_worker",
  "injected_error": "500 Internal Server Error",
  "orchestrator_behavior": "degraded to a partial answer (omitted deprecation verification due to worker 500)",
  "version_worker_output": "ERROR 500: Internal Server Error — Version & Deprecation registry service unavailable.",
  "status": "done"
}
```
