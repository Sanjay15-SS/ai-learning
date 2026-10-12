# Model Error Handling Transcript — Before vs After

### BEFORE: Cryptic Error Path (Old Unrecoverable Error)

**Tool Docstring (Old)**:
```
get_openapi_spec: Get API reference information for an endpoint, including docs and details about the API.
```

**Conversation & Model Trace**:
- **User**: "Please inspect the OpenAPI spec for POST /v4/charges in api_version='v4'."
- **Model Turn 1**:
  - `tool_use`: `get_openapi_spec(method="POST", path="/v4/charges", api_version="v4")`
- **Tool Result (Server 1)**:
  ```json
  {
    "error": "Error 3: invalid version"
  }
  ```
- **Model Turn 2 (Halts / Hallucinates / Fails)**:
  > "I encountered 'Error 3: invalid version' when requesting the OpenAPI specification for version v4. The system does not recognize v4 or the endpoint is unavailable. Please check your parameters and try again later."

*(Failure mode: The model cannot determine whether v4 is not yet published, temporarily offline, or what versions exist. It cannot self-correct and gives up with an unhelpful error message).*


---

### AFTER: Recoverable Error Path (Docstring-as-Prompt + Actionable Error)

**Tool Docstring Rewritten as Prompt (New)**:
```
get_openapi_spec: Retrieve the exact OpenAPI operation specification for a method and path in the Ledgerline API. You must specify a valid API version ('v2' or 'v3') and an exact path. Note: Ledgerline API v4.x is unreleased; latest available is v3.2. If the user asks for v4, examine v3 endpoints or check changelog notes.
```

**Conversation & Model Trace**:
- **User**: "Please inspect the OpenAPI spec for POST /v4/charges in api_version='v4'."
- **Model Turn 1**:
  - `tool_use`: `get_openapi_spec(method="POST", path="/v4/charges", api_version="v4")`
- **Tool Result (Server 1 - Recoverable Prompt)**:
  ```json
  {
    "error": "no docs for v4.x: latest published is v3.2, deprecated methods listed under v3.2/migration",
    "latest_published_version": "v3.2",
    "valid_versions": ["v2", "v3"],
    "recovery_hint": "Ledgerline v4 does not exist. The latest published release is v3.2. Query get_openapi_spec with api_version='v3' or use search_docs with api_version='v3' and check_deprecation for migration details."
  }
  ```
- **Model Turn 2 (Autonomous Self-Correction & Recovery)**:
  - `tool_use`: `check_deprecation(symbol="POST /v2/charges", api_version="v3")`
- **Tool Result (Server 1)**:
  ```json
  {
    "symbol": "POST /v2/charges",
    "status": "deprecated",
    "since": "v3.0.0",
    "replacement": "POST /v3/payment_intents",
    "note": "Replaced by PaymentIntents API in v3"
  }
  ```
- **Model Turn 3 (Successful Grounded Answer)**:
  > "API version: v3
  > Ledgerline API v4.x is not published yet; the latest stable release is v3.2.
  > In v3, `POST /v2/charges` is deprecated and replaced by `POST /v3/payment_intents`.
  > To create a payment in v3, call `/v3/payment_intents` with `amount`, `currency`, and `payment_method`."

*(Success: The actionable error message informed the model of the latest version (v3.2) and valid versions, allowing immediate recovery in the next lap without human intervention).*

