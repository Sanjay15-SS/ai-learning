# AI Engineering — Complete Reference (Weeks 1–10)

A unified reference covering foundational LLM concepts, prompting, RAG, evals, agents, MCP, and multi-agent systems.

## Table of Contents

- [Week 1 — How a Language Model Actually Works](#week-1--how-a-language-model-actually-works)
- [Week 2 — Prompting, Structured Output & Tool Calling](#week-2--prompting-structured-output--tool-calling)
- [Week 3 — Retrieval-Augmented Generation, From Parts](#week-3--retrieval-augmented-generation-from-parts)
- [Week 4 — Retrieval, Search & Context Engineering (Q01–Q10)](#week-4--retrieval-search--context-engineering)
- [Week 5 — Output Contracts, Structured Generation & Assertions (Q11–Q20)](#week-5--output-contracts-structured-generation--assertions)
- [Week 6 — LLM-as-a-Judge, Blind Protocols & Evals (Q21–Q30)](#week-6--llm-as-a-judge-blind-protocols--evals)
- [Week 7 — Hand-Built Agent Loops, Tool Calling & Budgets (Q31–Q40)](#week-7--hand-built-agent-loops-tool-calling--budgets)
- [Week 8 — Trajectory Evaluations & Outcome-vs-Trajectory Gap (Q41–Q50)](#week-8--trajectory-evaluations--outcome-vs-trajectory-gap)
- [Week 9 — Model Context Protocol (MCP) & Zero-Diff Discovery (Q51–Q60)](#week-9--model-context-protocol-mcp--zero-diff-discovery)
- [Week 10 — Multi-Agent Squads, Orchestration & A2A (Q61–Q70)](#week-10--multi-agent-squads-orchestration--a2a)

---

## Week 1 — How a Language Model Actually Works

### Q1. What does a large language model actually do?

It predicts the next token, over and over. Given a sequence of tokens, it outputs a probability distribution over its vocabulary. One token is sampled from it, appended to the input, and the process repeats. Everything it "knows" comes from patterns learned in training. It does not look anything up at inference time unless you give it context (which is what RAG does).

---

### Q2. What is a token, and why is "a token is a word" wrong?

A token is a sub-word unit produced by a tokenizer (e.g. BPE). Common words are often one token, but rare words, code, JSON, numbers and non-English text split into many. Roughly 1 token ≈ 4 English characters ≈ 0.75 words. This matters because you are billed per token, and context limits are counted in tokens. The same meaning in code or Tamil can cost 2–3× more tokens than in English.

---

### Q3. Why do LLMs hallucinate, and why do they sound confident when they're wrong?

The model is trained to produce *likely* text, not *true* text. It has no built-in "I don't know" signal. A fluent wrong answer and a fluent right answer look the same to the sampling process. Confidence in tone is a property of the language, not of the facts. Mitigations: ground the model in retrieved context (RAG), force refusals when the context doesn't contain the answer, and verify with evals.

---

### Q4. How do you calculate the cost of an LLM call?

```
cost = (input_tokens × input_price + output_tokens × output_price) / 1,000,000
```

Prices are usually quoted per million tokens. Output tokens are typically 3–5× more expensive than input. In multi-turn chats and agents, the *whole* history is re-sent every turn, so input tokens grow every step. You have to sum tokens across every call, not just the last one.

---

### Q5. What is temperature? Does temperature 0 guarantee identical outputs?

Temperature scales the probability distribution before sampling. Low temperature makes the top token almost always win, while high temperature flattens the distribution so less likely tokens get picked.

| Use case | Recommended temperature |
|---|---|
| Extraction, classification, routing, evals | 0 |
| Creative drafting | ~0.7 |

Temperature 0 means *greedy*, not *deterministic*. Batching, floating-point differences on GPUs and model updates can still change outputs.

---

### Q6. What is top-p (nucleus) sampling and how does it differ from temperature?

Top-p samples only from the smallest set of tokens whose cumulative probability is ≥ p (e.g. 0.9), cutting off the long tail. Temperature reshapes the whole distribution; top-p truncates it. You normally tune one of them, not both.

---

### Q7. What is an embedding?

A fixed-length vector of numbers that represents the meaning of a piece of text. Texts with similar meaning land close together in vector space. Embedding models (e.g. `all-MiniLM-L6-v2`, 384 dimensions) are separate from generation models: they're cheaper, often run locally, and are the basis of semantic search.

---

### Q8. What is cosine similarity, and what does a high score NOT tell you?

The cosine of the angle between two vectors. It ranges from −1 to 1 and is usually 0 to 1 for text embeddings. `cosine_distance = 1 − similarity`. A high score means the two texts *use similar language*. It does **not** mean the chunk is relevant to the question, and relevant does not mean true. Two near-identical exclusion clauses from different policy editions will score almost the same.

---

### Q9. What is a context window, and what is "lost in the middle"?

The context window is the maximum number of tokens (prompt + output) the model can attend to in one call. "Lost in the middle" (Liu et al. 2023) shows that models use information at the start and end of long contexts better than information buried in the middle. So stuffing more into the context is not free: it costs money, adds latency, and can lower accuracy.

---

### Q10. What is prompt caching and when does it matter?

If the beginning of your prompt (system prompt, few-shot examples, a fixed document) is identical across calls, the provider can cache it and bill it at a reduced rate with lower latency. It's usually one config change and the highest-leverage cost optimisation available. It matters most with long, stable system prompts at high volume. To benefit, put stable content first and variable content last.

---

## Week 2 — Prompting, Structured Output & Tool Calling

### Q1. What makes a good system prompt?

Clear role, explicit task, hard constraints stated as rules (not suggestions), the output format, and what to do in edge cases (e.g. "if the answer isn't in the context, reply starting with `REFUSAL:`"). Be specific and testable. Avoid soft escape hatches like "use your best judgement", which give the model permission to invent.

---

### Q2. Zero-shot vs few-shot prompting — when do you use few-shot?

Zero-shot gives instructions only. Few-shot adds worked input→output examples. Use few-shot when the format or judgement is hard to describe in words but easy to show: tricky classification boundaries, a specific output style, or the edge cases a judge keeps getting wrong. Downsides: more tokens, and the model may copy surface features of the examples.

---

### Q3. What is chain-of-thought prompting? Any risks?

Asking the model to reason step by step before answering. It improves multi-step reasoning (Wei et al. 2022). Risks: more output tokens (cost and latency), reasoning that sounds right but isn't faithful to how the answer was produced, and leaking reasoning into outputs that must be machine-parsed. Keep reasoning in a separate field or use a reasoning model.

---

### Q4. Why use structured output (JSON) instead of free text?

Downstream code has to parse it. Structured output gives you a contract: known fields and types that you can validate. Free text breaks parsers silently. Use JSON mode or schema-constrained decoding, then validate with a schema library (Pydantic, or `instructor` on top of it) and retry on validation failure.

---

### Q5. How do you handle an LLM returning invalid JSON?

1. Use provider structured-output or JSON mode when it exists.
2. Validate against a schema (Pydantic).
3. On failure, retry and include the validation error in the prompt.
4. Cap retries, then fail loudly instead of passing garbage downstream.

Never "fix" it with a regex hack you can't test.

---

### Q6. What is tool (function) calling and how does it work?

You describe tools to the model (name, description, JSON-schema parameters). The model doesn't execute anything: it returns a structured request saying "call tool X with args Y". *Your code* runs the tool, sends the result back as a tool message, and the model continues. The model chooses; the application executes.

---

### Q7. What makes a good tool description?

One job per tool, stated clearly. Say when to use it *and when not to*. Use typed parameters, enums for closed sets (e.g. claim status), and examples of valid formats (e.g. `CLM-YYYY-NNNNN`). No overlap with other tools' descriptions. The description is a prompt: if two tools sound alike, the model will thrash between them.

---

### Q8. Why use enums in tool parameters?

They limit the model to valid values, which removes a whole class of invented arguments ("pending-ish"). They also document the domain and make validation trivial. Any parameter with a known finite set of values should be an enum.

---

### Q9. What is prompt injection?

Input that changes the model's instructions, like "ignore previous instructions and…". Direct injection comes from the user. Indirect injection is hidden in content the model reads: documents, web pages, tool outputs. The model cannot reliably tell instructions apart from data, so prompts alone are not a defence.

---

### Q10. How do you choose a model for a task?

Start from the task's needs: accuracy on *your* eval set, latency, cost per call, context length, tool-calling or structured-output support, and data or privacy constraints. Use the smallest or cheapest model that passes your eval, and keep stronger models for the hard cases. Choose with your own eval numbers, not leaderboard rankings.

---

## Week 3 — Retrieval-Augmented Generation, From Parts

### Q1. What is RAG and why use it instead of fine-tuning?

Retrieve relevant chunks from your own documents, put them in the prompt, and have the model answer from that context.

| RAG | Fine-tuning |
|---|---|
| Knowledge you can update by re-indexing (no retraining) | Changes behaviour or style |
| Citations and provenance | Cannot cite sources |
| Less hallucination | Poor way to add facts that change |
| Access control per document | — |

---

### Q2. Walk through a RAG pipeline end to end.

```
Ingest → parse → chunk → attach metadata → embed → store in vector DB
                                                          ↓
Query time: embed query → similarity search (optionally filtered) → top-k chunks
                                                          ↓
              build grounded prompt → generate with citations → refuse if unsupported
```

---

### Q3. What is the chunking tension?

Small chunks retrieve precisely but often lack the context needed to answer completely (e.g. an exclusion row stripped of the definitions clause it depends on). Large chunks carry more context but blur the embedding, so retrieval gets less precise. There is no universal "right size" — pick it by measuring hit-rate on known-answer questions.

---

### Q4. Fixed-size vs structure-aware chunking?

| Strategy | How | Best for |
|---|---|---|
| Fixed-size | Split every N tokens/chars with overlap | Simple, generic text |
| Structure-aware | Split on headings, clause IDs, table boundaries | Policies, contracts, manuals |

Structure-aware keeps each chunk meaningful and preserves its header. For structured documents it usually wins — prove it with a number.

---

### Q5. What is chunk overlap and why use it?

Neighbouring chunks share some text (e.g. 10–20%), so a sentence cut at a boundary still appears whole in one of them. It reduces boundary losses but increases index size and creates near-duplicate results.

---

### Q6. Why attach metadata to every chunk?

For provenance (which source document, form or edition), citations, filtering (e.g. only `policy_line = HO`), access control, and debugging. A chunk without a source can't be cited or audited — treat it as a failed ingest.

---

### Q7. What does a metadata filter do, and when does it change results?

It limits the search to chunks matching a condition before ranking (pre-filter) or after ranking (post-filter). It changes results when semantically similar chunks exist in *other* categories — for example the same exclusion wording in a different policy line or edition. Filtering removes those distractors so the correct chunk becomes top-1.

---

### Q8. How do you make citations verifiable?

Give each chunk a stable unique ID (also its primary key in the vector store), show the IDs in the context, and require the model to cite them per claim. Then check programmatically that every cited ID exists *and* that the cited chunk actually contains the claim. A citation that doesn't resolve is a hallucination with a footnote.

---

### Q9. How do you make a RAG system refuse instead of inventing?

Make refusal a hard rule in the system prompt with a fixed, machine-detectable format (e.g. the reply must start with `REFUSAL:`). Detect it in code and test it with out-of-corpus questions you know the corpus can't answer. Use temperature 0. Never use "use your best judgement if context is insufficient". For high-stakes domains, an invented answer is worse than no answer.

---

### Q10. How do you evaluate retrieval separately from generation, and why?

Write known-answer questions from the source documents *before* running retrieval, then measure hit-in-top-k (was the correct chunk retrieved?) with no LLM call at all. That isolates the retriever as the only variable. End-to-end accuracy hides which half is broken. Change one thing at a time (chunker *or* embedding model, never both) or you can't tell what moved the number.

---

## Week 4 — Retrieval, Search & Context Engineering

### Q01. How do you prevent version contamination in multi-version technical documentation retrieval?

- **Concept**: Scoped retrieval vs un-scoped global search.
- **Answer**: When documentation contains breaking changes across versions (e.g. Ledgerline v2 vs v3), an un-scoped semantic search will often return older, deprecated endpoints that have higher lexical or cosine similarity with the query. To prevent this, retrieval must be strictly partitioned or filtered using metadata tags (e.g., `api_version: "v3"`). The assistant should first detect or default the target version, and enforce hard metadata filters at the retrieval boundary so obsolete content cannot enter the prompt context.

---

### Q02. What is the trade-off between dense semantic search (embeddings) and sparse lexical search (BM25) in developer docs?

- **Concept**: Exact keyword matching vs conceptual understanding.
- **Answer**: Sparse lexical search (BM25) excels at exact matches for API tokens, error codes, HTTP status codes, and exact parameter names (e.g., `Idempotency-Key` or `pm_card_visa`), which dense embeddings often smear into generic vector representations. Dense embeddings excel at intent matching (e.g. mapping "how do I take money from a card" to "payment intents"). A production docs system uses hybrid search (Reciprocal Rank Fusion or cross-encoder re-ranking) combining sparse exact matches with dense semantic similarity.

---

### Q03. Why is naive sliding-window text chunking dangerous for OpenAPI specifications and code references?

- **Concept**: AST-aware and document structure chunking.
- **Answer**: Fixed character or token windows slice through YAML/JSON structures, severing an endpoint path from its required headers, request body schema, and response codes. For API documentation, chunking must be semantic: each chunk should represent an atomic OpenAPI operation (`method + path + parameters + responses`) or a complete, executable code example with its explanatory docstring.

---

### Q04. How do you handle local LLM inference constraints (e.g., Qwen-2.5-3B on MLX/Apple Silicon) without sacrificing quality?

- **Concept**: Quantization, context limits, and deterministic sampling.
- **Answer**: For local edge inference, 4-bit quantization (e.g., AWQ, MLX 4-bit) preserves ~95%+ of model reasoning while reducing memory footprint to under 2GB. To ensure test reproducibility and eliminate variance in evals, greedy decoding (`temperature=0.0`) is enforced. Context windows must be budgeted conservatively to avoid out-of-memory crashes and quadratic attention latency degradation.

---

### Q05. What is "Lost in the Middle" phenomenon, and how do you mitigate it when ordering retrieved docs?

- **Concept**: Attention distribution in long context windows.
- **Answer**: LLMs recall information best when it appears at the very beginning (primacy effect) or the very end (recency effect) of the context window. Information placed in the middle of a large prompt suffers high drop-off rates. Mitigation: sort retrieved documentation chunks so that highest-relevance snippets are placed either right before the user question or immediately following system instructions, rather than burying them in the middle of long reference texts.

---

### Q06. How do you distinguish between an unanswerable developer question and a retrieval failure?

- **Concept**: Refusal grounding vs hallucination prevention.
- **Answer**: A retrieval failure occurs when relevant docs exist in the corpus but fail to rank in top-k. An unanswerable query asks for features not supported by the platform (e.g., "GraphQL support" or "Rust SDK"). To distinguish them, establish a verified corpus boundary with deterministic refusal assertions: the system prompt instructs the model to refuse if the retrieved context lacks explicit documentation, rather than attempting to interpolate or hallucinate outside the corpus.

---

### Q07. Why should query re-writing precede document retrieval in developer assistants?

- **Concept**: Query expansion and synonym mapping.
- **Answer**: Developers frequently formulate queries with colloquial terminology or legacy habits (e.g. "charge a card" when the v3 API uses "confirm payment intent"). A lightweight query re-writing layer decomposes the user query, expands domain synonyms, and extracts required filters (e.g. target language: Python, target version: v3) before querying the vector store or index.

---

### Q08. How do you measure retrieval recall and precision independently of model answer generation?

- **Concept**: Retrieval-only metrics vs end-to-end evaluation.
- **Answer**: By decoupling the retriever from the generator: curate a golden dataset mapping each query to the ground-truth document chunk IDs. Then measure Hit Rate@K, Mean Reciprocal Rank (MRR), and NDCG@K. If Hit Rate@3 is 95%, answer errors stem from generator reasoning; if Hit Rate@3 is 50%, generator failures are downstream of retrieval starvation.

---

### Q09. What is context stuffing and why does providing full reference manuals degrade reasoning?

- **Concept**: Signal-to-noise ratio in attention layers.
- **Answer**: Dumping whole API manuals into the prompt floods attention heads with thousands of irrelevant tokens. This creates distraction paths, increases cost and time-to-first-token linearly or quadratically, and increases the likelihood of cross-version hallucination. Bounded retrieval providing only the 1–3 most relevant operations dramatically outperforms whole-spec stuffing.

---

### Q10. How do you design an effective fallback strategy when no relevant documents are retrieved above the similarity threshold?

- **Concept**: Graceful degradation and guardrails.
- **Answer**: When cosine similarity or BM25 scores fall below a calibrated confidence cutoff, the system triggers a fallback rule: (1) attempt query relaxation (remove strict filters), (2) check the platform changelog or deprecation index, and (3) if still empty, emit a structured refusal stating that the requested feature is not documented in the selected API version, providing links to the general index.

---

## Week 5 — Output Contracts, Structured Generation & Assertions

### Q11. What is an "Output Contract" and why is it preferred over free-form natural language generation?

- **Concept**: Deterministic machine-readable guarantees.
- **Answer**: An output contract specifies the exact lexical structure, required headers, metadata lines, and code block formats that the LLM must generate. Contracts eliminate ambiguity, allow downstream programmatic parsers to validate and ingest responses, and enable deterministic automated testing.

---

### Q12. How do deterministic assertions differ from LLM-based evaluation criteria?

- **Concept**: Unit testing vs probabilistic scoring.
- **Answer**: Deterministic assertions are pure Python functions that test objective, binary truths without calling an LLM (e.g., `ast.parse` to ensure code compiles, regex to check that endpoint paths exist in the OpenAPI spec, checking that `v2` endpoints do not appear in `v3` code). They run in microseconds, cost $0, and never hallucinate. LLM criteria are reserved for subjective usability and tone.

---

### Q13. Why is `ast.parse` essential in evaluating generated code samples?

- **Concept**: Syntactic correctness verification.
- **Answer**: LLMs frequently produce code with subtle syntax errors: unclosed brackets, incorrect indentation, invalid string escapes, or malformed decorators. Running `ast.parse(code_snippet)` guarantees that any Python code delivered to the user is syntactically valid before any behavioral assertions or human reviews take place.

---

### Q14. How do you enforce that a model never emits a legacy endpoint (e.g., v2) when responding to a current (v3) user?

- **Concept**: Negative assertions and regex guards.
- **Answer**: Implement a deterministic negative assertion (e.g., `no_v2_in_v3_code`). It parses the generated code and text against an exhaustive list of deprecated endpoints and parameters (e.g., `/v2/charges`, `source=tok_`, `/v2/webhooks`). If any v2 pattern matches while the target version is v3, the assertion immediately fails the response.

---

### Q15. What is the role of JSON Schema in modern function calling / structured outputs?

- **Concept**: Constrained decoding and type safety.
- **Answer**: JSON Schema defines the explicit types, required properties, enums, and nested structures expected from the model. Modern inference engines use grammar-based constrained decoding (logits masking) to mathematically prevent the model from generating tokens that violate the schema, guaranteeing 100% syntactically valid JSON.

---

### Q16. How do you design an assertion that verifies idempotency guarantees in payment APIs?

- **Concept**: Critical API header assertion.
- **Answer**: For state-mutating requests (such as `POST /v3/payment_intents`), the assertion extracts the HTTP headers in the generated snippet and verifies that `Idempotency-Key` is present and assigned a dynamic value (e.g. `str(uuid.uuid4())`), failing any sample that omits the header or hardcodes a static duplicate string.

---

### Q17. What is the risk of asking an LLM to self-evaluate its own output contract adherence?

- **Concept**: Self-preference bias and blind spots.
- **Answer**: An LLM that makes a reasoning or formatting error during generation will usually rationalize its error during self-evaluation due to shared activation weights and self-preference bias. Contract compliance must always be verified by external deterministic code assertions or an independent, differently-prompted judge.

---

### Q18. How do you design a "refusal assertion" to verify that an agent declined an unsupported question?

- **Concept**: Out-of-domain guardrail verification.
- **Answer**: A refusal assertion inspects questions flagged with `expect_refusal=True`. It asserts that: (1) no runnable code blocks were generated, and (2) the response contains standard refusal markers (e.g., "does not support", "not covered in the documentation", "unsupported") while avoiding hallucinated speculative endpoints.

---

### Q19. What is a "Must Include" assertion and how does it balance precision and flexibility?

- **Concept**: Keyword and entity presence checks.
- **Answer**: A `must_include` assertion takes a list of essential technical tokens (e.g., `["/v3/refunds", "payment_intent"]`) that must appear in the text or code. It verifies that the critical architectural concepts are explicitly communicated without overfitting to exact sentence phrasing.

---

### Q20. When should you use Instructor / Pydantic vs raw prompt formatting for structured outputs?

- **Concept**: Library abstraction vs low-level control.
- **Answer**: Use Pydantic/Instructor when building internal application data pipelines that require automatic retries on validation errors and Python object deserialization. Use raw prompt formatting and custom validators when testing fundamental model capabilities, minimizing library overhead, or running lightweight local models that lack native function-calling fine-tuning.

---

## Week 6 — LLM-as-a-Judge, Blind Protocols & Evals

### Q21. What is a "Blind Evaluation Protocol" and why is it mandatory when evaluating LLM judges?

- **Concept**: Preventing annotator contamination and confirmation bias.
- **Answer**: In a blind protocol, human baseline labels (`labels.json`) must be authored, validated, and committed to version control *before* the LLM judge is ever executed. If an engineer sees the judge's verdict first, they subconsciously alter their own labels to match the judge. A blind protocol proves the judge is calibrated against fixed human ground truth rather than post-hoc rationalization.

---

### Q22. What criteria should be removed from an LLM judge prompt and moved into deterministic code?

- **Concept**: Prompt slimming and objective vs subjective separation.
- **Answer**: Anything that can be objectively checked by a compiler or regex must be removed from the judge prompt:
  1. `code_parses` → Python `ast.parse`
  2. `endpoints_exist` → OpenAPI spec dictionary lookup
  3. `version_stated` → regex check for `API version: vX`
  4. `deprecations_noted` → string search in changelog

  The judge should be left with exactly ONE subjective criterion: `CORRECT_AND_USABLE` (binary PASS/FAIL).

---

### Q23. How do you calculate Judge Agreement and what score constitutes a reliable judge?

- **Concept**: Inter-rater reliability metrics.
- **Answer**: Agreement = (cases where judge verdict == human label) / total labeled cases. Cohen's Kappa further adjusts for chance agreement. In production docs evals, an agreement rate below 80% (κ < 0.60) indicates an unreliable judge that cannot be trusted for automated deployment gating; target agreement is ≥ 88%.

---

### Q24. What is "Few-Shot Calibration via Real Disagreements"?

- **Concept**: Iterative judge prompt refinement.
- **Answer**: When Judge v1 disagrees with human labels on specific cases, analyze the root cause. Select 2 representative disagreement cases and insert them into Judge v2's prompt as few-shot exemplars with explicit chain-of-thought rationale explaining *why* the human verdict was correct. Then measure Judge v2 on the remaining unseen cases to verify that agreement improved without over-fitting.

---

### Q25. Why must a prediction be written and timestamped before running Judge v2?

- **Concept**: Pre-registration of hypotheses to prevent p-hacking.
- **Answer**: Before running Judge v2, the engineer commits a one-sentence prediction (e.g., "Agreement will increase on deprecation questions because few-shot examples explicitly penalize omitting migration steps"). This scientific pre-registration ensures improvements are causal rather than random statistical noise or post-hoc cherry-picking.

---

### Q26. What is a Regression Case in an eval set, and how should it be harvested?

- **Concept**: Traffic harvesting and regression testing.
- **Answer**: A regression case is an eval test case created directly from a real production user trace that resulted in a user bug report or failed assertion. It must be copied verbatim (exact developer prompt, no synthetic cleaning) to ensure that the exact linguistic and semantic quirk that broke the system is permanently locked into the regression suite.

---

### Q27. What is the "Judge Alignment Gap" and what causes it?

- **Concept**: Systematic discrepancy between human preference and model scoring.
- **Answer**: The alignment gap is the delta between human evaluation standards and model evaluation. Primary causes:
  1. **Verbosity bias**: The judge prefers long, chatty answers even if they contain errors.
  2. **Self-enhancement bias**: The judge scores answers generated by its own model family higher.
  3. **Superficial formatting**: The judge passes code that looks neat but calls non-existent parameters.

---

### Q28. How do you structure an Evaluation Taxonomy for an API documentation assistant?

- **Concept**: Failure mode classification.
- **Answer**: Categorize failure modes into mutually exclusive classes:
  1. `version_confusion`: Giving v2 advice to a v3 user.
  2. `deprecated_no_migration`: Mentioning deprecation without providing replacement.
  3. `hallucinated_endpoint`: Inventing a non-existent URL or parameter.
  4. `broken_sample`: Emitting code that fails to compile or crashes at runtime.
  5. `unanswerable`: Failing to refuse questions out of scope.
  6. `conceptual`: Misexplaining core architecture.

---

### Q29. Why should an evaluation harness run with `--no-judge` during rapid development loops?

- **Concept**: Eval cost, speed, and iteration cycles.
- **Answer**: Deterministic assertions run locally in milliseconds for $0. Running an LLM judge on every code edit adds latency (10–60s) and API cost while introducing stochastic noise. Fast feedback loops rely on assertions; the full judge is invoked only at milestone gates and pull request merges.

---

### Q30. What is the "Strict Binary Verdict" rule in LLM-as-a-judge design?

- **Concept**: Eliminating ambiguous 1–5 Likert scales.
- **Answer**: 1–5 scoring scales suffer from severe calibration drift: different models (and humans) assign different meanings to "3" vs "4". Forcing a strict binary verdict (`PASS` or `FAIL`) accompanied by a mandatory one-sentence justification eliminates middle-ground ambiguity and produces clear, actionable pass-rate metrics.

---

## Week 7 — Hand-Built Agent Loops, Tool Calling & Budgets

### Q31. Walk through the core components of a ReAct (Reasoning + Acting) hand-built agent loop.

- **Concept**: Autonomous loop mechanics.
- **Answer**:
  1. **Prompt assembly**: System instructions + tool schemas + conversation history.
  2. **Model inference**: Model emits text or a `tool_use` stop reason with tool arguments.
  3. **Stop condition evaluation**: If `end_turn` or final answer, return.
  4. **Budget checks**: Check tokens, cost, iterations, and wall-clock time.
  5. **Tool execution**: Dispatch call to local function, capturing output or errors.
  6. **Context update**: Append `tool_use` block and `tool_result` block to messages list.
  7. **Recurse / Loop**: Return to Step 2 until finished or budget exhausted.

---

### Q32. What four budgets must be enforced on every autonomous agent loop, and why?

- **Concept**: Multi-dimensional safety boundaries.
- **Answer**:
  1. **Max iterations (laps)**: Prevents infinite ping-pong loops (e.g., limit = 5–8 laps).
  2. **Max total tokens**: Protects against explosive context window expansion and quadratic cost.
  3. **Max cost (USD)**: Hard financial ceiling preventing runaway spend.
  4. **Max wall-clock time (seconds)**: Protects client HTTP connections from hanging indefinitely.

  All four must be checked *both before and after* every model invocation and tool dispatch.

---

### Q33. When does a multi-turn agent outperform a fixed DAG workflow, and when does it lose?

- **Concept**: Dynamic branching vs deterministic pipelines.
- **Answer**: An agent outperforms a fixed workflow when the solution path is dynamic and non-linear—e.g. when Step 2 reveals that an endpoint is deprecated, requiring a conditional lookup of a replacement endpoint before fetching its spec. Conversely, for linear single-lookup tasks, an agent loses: it incurs higher latency, redundant reasoning tokens, and potential tool mis-dispatch.

---

### Q34. What is "Tool Overlap" and how does it degrade agent performance?

- **Concept**: Tool description ambiguity.
- **Answer**: Tool overlap occurs when two or more tools have descriptions with blurry boundaries. The model gets confused, flips a coin, or calls both tools in redundant succession. The fix is description sharpening: give each tool an exclusive, non-overlapping responsibility.

---

### Q35. How should tool errors be returned to the agent: raise an exception or return a message?

- **Concept**: In-band recoverable errors vs out-of-band crashes.
- **Answer**: Tool errors must be returned *in-band* as a standard `tool_result` message containing structured error details and recovery hints (e.g., `{"error": "Path /charges not found in v3", "suggestion": "Try /payment_intents"}`). Raising an unhandled Python exception terminates the process; returning an informative error enables the model to self-correct in its next turn.

---

### Q36. Why should you avoid giving an agent destructive or redundant tools in early laps?

- **Concept**: Principle of least privilege and tool scoping.
- **Answer**: Providing broad toolkits increases prompt token overhead and expands the hallucination surface. In early laps of information gathering, an agent should only access read-only, high-precision tools. Specialized or write-capable tools should be injected conditionally based on state or user authorization.

---

### Q37. How do you calculate agent step efficiency?

- **Concept**: Trajectory optimization metrics.
- **Answer**: `Step Efficiency = Minimum Necessary Steps / max(Minimum Necessary Steps, Actual Steps Taken)`. If an answer can be found in 2 steps but the agent took 4 steps, its efficiency is 2 / 4 = 0.50 (50%).

---

### Q38. What causes an agent to get stuck in an "infinite tool repetition" loop, and how do you break it?

- **Concept**: Identical state repetition and loop detection.
- **Answer**: Causes: The tool returns the exact same non-helpful output on repeated calls, or the model's temperature is 0 and it generates identical tool arguments. Mitigation: maintain a tool-call hash history; if the exact same `(tool_name, args)` tuple executes twice with identical results, inject a system warning prompting the model to try an alternate approach.

---

### Q39. Why is pricing agent runs using reference API list rates important even when running local models for free?

- **Concept**: Cost-parity benchmarking.
- **Answer**: Running local models (like Qwen on MLX) incurs $0 out-of-pocket spend. However, evaluating architectural efficiency requires knowing what the workload *would* cost in production on enterprise APIs. Pricing token counts at standard rates converts token consumption into business-critical dollars-per-question metrics.

---

### Q40. What is the "Prompt-as-Tool-Constraint" pattern?

- **Concept**: Constraining tool inputs via docstring prompt engineering.
- **Answer**: Rather than writing passive documentation, write the tool docstring as an active instruction to the LLM: specify exact allowed parameter combinations, warn about common traps, and explain what the tool does NOT do. The model reads this description as part of its system prompt and adheres to it.

---

## Week 8 — Trajectory Evaluations & Outcome-vs-Trajectory Gap

### Q41. What is the "Outcome-vs-Trajectory Gap" and why is it dangerous in production agents?

- **Concept**: Fluke successes vs repeatable processes.
- **Answer**: The gap = Outcome Pass Rate − Trajectory Pass Rate. A positive gap (e.g. 80% outcome pass vs 30% trajectory pass = 50% gap) means the agent is "getting the right answer for the wrong reason"—memorized knowledge or guessing. In production, when the underlying API changes, memorized knowledge fails silently.

---

### Q42. What four trajectory metrics should be reported in an agent evaluation suite?

- **Concept**: Comprehensive trajectory scorecard.
- **Answer**:
  1. **Tool-Choice Accuracy**: Fraction of dispatched tools that belonged to the set of legitimate tools for the task.
  2. **Argument Validity Rate**: Fraction of tool calls whose arguments were semantically and structurally valid.
  3. **Step Efficiency**: Ratio of theoretical minimum steps to actual steps taken.
  4. **Cost Variance (p50 vs max cost)**: The financial spread between a smooth run and a pathologically wandering trajectory.

---

### Q43. How do you evaluate an agent trajectory when multiple valid paths exist?

- **Concept**: Non-deterministic valid trajectories.
- **Answer**: Do not hardcode a single rigid sequence. Define `EXPECTED_TRAJECTORIES` as a list of acceptable path permutations. A trajectory passes if the agent's executed sequence matches *any* pre-approved valid sequence and all tool arguments passed validation.

---

### Q44. What is an "Argument Validity Failure" and give an example from API documentation?

- **Concept**: Hallucinated parameters in tool execution.
- **Answer**: An argument validity failure occurs when the agent selects the correct tool (`get_openapi_spec`), but passes a hallucinated or invalid argument (e.g. `path: "/v3/charges"` when that path does not exist in v3). The tool fails or returns an error, proving the agent did not know the real schema and guessed the path based on v2 habits.

---

### Q45. What is the "Right Answer, Wrong Path" failure mode?

- **Concept**: Un-grounded correct generation.
- **Answer**: The agent produces an answer that satisfies all textual assertions, but its trajectory log reveals it never queried the OpenAPI spec for the endpoint. It fabricated the code from pre-training memory. If the API had private extensions or subtle differences, the code would be broken in production.

---

### Q46. How do you design an offline mock client to test agent trajectory evaluators deterministically?

- **Concept**: Fast, repeatable eval testing without API costs.
- **Answer**: Implement a mock client conforming to the provider interface. The simulator inspects the input message history, matches question IDs, and emits scripted `tool_use` and `text` responses simulating both baseline failure paths (skipping tools, bad args) and mitigated paths. This allows the evaluation suite to run in CI in seconds.

---

### Q47. What is the "One Mitigation Rule" in evaluation engineering?

- **Concept**: Controlled scientific intervention.
- **Answer**: When evals reveal multiple failure modes, implement exactly ONE mitigation at a time. Measure before vs after on the exact same eval set. Applying multiple changes simultaneously confounds the experiment, making it impossible to know which change helped or hurt.

---

### Q48. What is the "Price Paid" metric when improving agent trajectories?

- **Concept**: Cost of increased guardrails.
- **Answer**: Mitigations that eliminate trajectory failures inevitably increase the workload. The "Price Paid" measures this delta in added tokens per question, added cost per question, and added latency. A senior engineer reports the accuracy gain alongside the price paid.

---

### Q49. How do you detect an "Inefficient Loop" failure mode in agent trajectories?

- **Concept**: Redundant and wandering steps.
- **Answer**: An inefficient loop occurs when an agent takes significantly more steps than necessary (e.g., step efficiency < 0.50), repeatedly re-searching docs with slightly altered queries or ping-ponging between tools without extracting new information.

---

### Q50. How do trajectory evals protect against silent regressions during prompt refactoring?

- **Concept**: Regression testing beyond binary accuracy.
- **Answer**: An agent prompt change might maintain an overall 90% answer pass rate while quietly doubling the average number of tool calls and increasing cost by 80%. Outcome-only evals miss this degradation; trajectory evals catch the step inflation and cost spike immediately.

---

## Week 9 — Model Context Protocol (MCP) & Zero-Diff Discovery

### Q51. What is the Model Context Protocol (MCP) and what problem does it solve?

- **Concept**: Open standard for tool and resource integration.
- **Answer**: MCP is an open, standardized protocol developed by Anthropic that decouples LLM applications from external tools and data sources. Instead of hardcoding bespoke tool wrappers inside every agent codebase, tools are hosted on standalone MCP servers communicating over JSON-RPC 2.0 (via stdio or SSE/HTTP). Any MCP-compliant client can dynamically discover and invoke tools from any server.

---

### Q52. What is "Zero-Diff Agent Extension" and why is it architecturally significant?

- **Concept**: Decoupled tool extensibility.
- **Answer**: Zero-diff extension means adding, updating, or removing tool capabilities without modifying a single line of code in the host agent module (`git diff agent.py` shows 0 lines). The agent dynamically queries configured servers at startup via `tools/list` and binds them to its model context. New servers are added solely by modifying a configuration file (`mcpServers.json`).

---

### Q53. Walk through the three fundamental phases of the MCP JSON-RPC lifecycle.

- **Concept**: Protocol handshake and execution phases.
- **Answer**:
  1. **Initialization Handshake**: Client sends `initialize` request with protocol version and capabilities; server responds with its info; client sends `notifications/initialized`.
  2. **Tool Discovery**: Client sends `tools/list` request; server returns array of available tools with their names, descriptions, and JSON Schemas.
  3. **Tool Invocation**: Client sends `tools/call` with tool name and arguments; server executes the tool and returns output content blocks and `isError` boolean.

---

### Q54. Where does the LLM model call physically take place in an MCP architecture?

- **Concept**: Protocol boundary and executor independence.
- **Answer**: The model call happens ONLY inside the host agent between `tools/list` (where discovered schemas are passed to the model) and `tools/call` (where the model decides which tool to call). The MCP server is a standalone deterministic JSON-RPC executor that NEVER invokes an LLM.

---

### Q55. Why do JSON-RPC notifications (e.g. `notifications/initialized`) omit the `id` field?

- **Concept**: JSON-RPC 2.0 specification compliance.
- **Answer**: Notifications are fire-and-forget one-way messages that do NOT expect or permit a response. Including an `id` turns a notification into a request, which violates the specification and causes spec-compliant servers to error.

---

### Q56. What is the difference between an unrecoverable tool error and a recoverable error in MCP?

- **Concept**: Actionable error design for agent self-correction.
- **Answer**: An unrecoverable error returns a cryptic failure. A recoverable error returns rich, actionable guidance (e.g., `{"error": "v4 unreleased", "latest_published_version": "v3.2", "recovery_hint": "Query v3.2 for current endpoints"}`), enabling the model to autonomously correct its path in the next lap.

---

### Q57. What are the primary supply-chain and security risks introduced by connecting third-party MCP servers?

- **Concept**: Security boundaries and prompt injection in MCP.
- **Answer**:
  1. **Tool Shadowing & Squatting**: A third-party server could advertise tools with descriptions engineered to override primary system tools.
  2. **Data Exfiltration**: Tool outputs could contain indirect prompt injections instructing the model to leak context or credentials to the server.
  3. **Over-privileged Access**: A compromised server token could reach internal networks, databases, or cloud infrastructure.

  Mitigation: Sandboxing, read-only least-privilege tokens, human approval for sensitive tools, and outbound egress filtering.

---

### Q58. How does MCP handle schema updates when tools change on the server (`listChanged`)?

- **Concept**: Dynamic capability notification.
- **Answer**: When an MCP server adds or updates tools dynamically, it can emit a `notifications/tools/list_changed` notification to the host agent (provided `capabilities.tools.listChanged: true` was negotiated during initialization). Upon receiving this notification, the host agent re-issues a `tools/list` request and updates its active tool definitions.

---

### Q59. Why is stdio used as a primary transport for local MCP servers instead of HTTP REST?

- **Concept**: Local process security and lifecycle management.
- **Answer**: Stdio transport allows the client to spawn the server directly as a child subprocess. It avoids opening network ports on `localhost`, inherits security isolation from the OS process model, and guarantees automatic cleanup when the parent agent exits (closing stdin terminates the child).

---

### Q60. How do you design an MCP Gateway to aggregate multiple downstream servers into a single interface?

- **Concept**: Gateway routing and auditing.
- **Answer**: An MCP Gateway acts as a proxy: to the host agent, it appears as a single MCP server. Under the hood, it maintains connections to multiple downstream servers, merges their `tools/list` catalogs, routes incoming `tools/call` requests to the correct server based on namespace or name, and provides a centralized audit log and rate limiter.

---

## Week 10 — Multi-Agent Squads, Orchestration & A2A

### Q61. What is the "Context Re-Send Multiplier" in multi-agent architectures, and how is it calculated?

- **Concept**: Token duplication cost in multi-agent orchestration.
- **Answer**: `Multiplier = Total Multi-Agent Tokens / Total Single-Agent Tokens`. Because each delegation hop re-sends the original prompt, target schemas, and intermediate findings across separate context windows, multi-agent architectures routinely exhibit a 2.0x to 4.0x token penalty.

---

### Q62. What is the single largest token sink in a multi-agent delegation pipeline?

- **Concept**: Hand-off token attribution.
- **Answer**: The hand-off from the Orchestrator to the second worker is almost always the single largest token sink (often 35%–45% of all tokens). This is because it must re-send the original user question, the target API version, and the full text or structured JSON emitted by the first worker.

---

### Q63. When does a multi-agent squad actually beat a single agent, and when is it "fashion over evidence"?

- **Concept**: Architectural ROI analysis.
- **Answer**: A multi-agent squad wins when tasks require strictly compartmentalized context, distinct security boundaries, or parallelizable subtasks. It is "fashion over evidence" when applied to sequential, moderate-context tasks where a single agent with all tools achieves identical accuracy at half the cost and one-third the latency.

---

### Q64. What is Sunk-Cost Bias in agent engineering, and how should engineering teams combat it?

- **Concept**: Objective evaluation vs architectural attachment.
- **Answer**: Sunk-cost bias occurs when a team refuses to accept empirical eval data showing that a simple single agent performs equally well at lower cost. Combat it by pre-committing to evaluation metrics, running blind head-to-head races, and explicitly naming the bias before making keep/kill decisions.

---

### Q65. When a specialized worker returns an HTTP 500 error, what are the three possible orchestrator behaviors?

- **Concept**: Fault tolerance and degradation modes.
- **Answer**:
  1. **Retry**: Re-attempts the worker call with exponential backoff.
  2. **Degrade to a partial answer**: Catches the error and proceeds, explicitly informing the user of what could not be verified.
  3. **Lie (Fabricate)**: Continues silently without the worker's output and hallucinates unverified claims.

  A production orchestrator must choose graceful degradation over fabrication.

---

### Q66. What is an AgentCard in Agent-to-Agent (A2A) protocols?

- **Concept**: Standardized agent capability discovery.
- **Answer**: An AgentCard is a machine-readable JSON metadata manifest advertised by an agent. It specifies the agent's name, version, protocol version, authentication requirements, input/output MIME modes, supported interactive states, and a list of callable skills with their respective input and output JSON Schemas. It allows external orchestrators to discover and bind agent capabilities dynamically.

---

### Q67. How does the A2A task lifecycle handle a worker failure differently than standard REST?

- **Concept**: Stateful task lifecycle vs synchronous failure.
- **Answer**: In plain REST, a worker failure triggers an immediate HTTP 500 status code, dropping the connection. In A2A protocols, tasks follow a stateful lifecycle (`submitted` → `working` → `input-required` / `paused` → `completed` / `failed`). Instead of abruptly terminating, the agent transitions to an `input-required` state, prompting the caller for missing parameters or clarification.

---

### Q68. What does A2A buy you over a plain REST call to a worker?

- **Concept**: Key advantages of A2A protocol.
- **Answer**:
  1. **Asynchronous stateful lifecycle**: A2A natively supports pausing tasks in an `input-required` state across long-running human-in-the-loop interventions without tying up HTTP sockets.
  2. **Standardized capability negotiation**: A2A provides machine-readable capability cards and cryptographic delegation tokens so agents negotiate schemas and sub-task contracts dynamically.

---

### Q69. Why is multi-agent latency (p50 and p99) significantly worse than single-agent latency?

- **Concept**: Multi-hop sequential latency.
- **Answer**: In a single agent, reasoning and tool calls occur within a single rolling context with few round-trips. In a multi-agent squad, each worker invocation requires a separate sequential network round-trip, prompt tokenization, queue time, model prefill, and generation. Latencies compound additively across hops, causing p50 to double and p99 tail latency to multiply.

---

### Q70. How do you design a "Keep or Kill" review for an experimental agent architecture?

- **Concept**: Production readiness gates.
- **Answer**: A senior engineering review requires:
  1. **Identical Benchmark Set**: Race both arms on the exact same regression cases with the same judge.
  2. **Four-Number Scorecard**: Measure Pass Rate, p50/p99 Latency, Total Tokens, and Cost per Question.
  3. **Failure Injection Proof**: Test resilience when components return 500 errors.
  4. **Strict Decision Rule**: If the multi-agent system does not produce a statistically significant increase in pass rate that offsets its token and latency penalties, the architecture must be **KILLED**.

---

### Interview Preparation Checklist

- [x] Week 1: Token prediction, tokenization, hallucination, cost, temperature, top-p, embeddings, cosine similarity, context windows, prompt caching.
- [x] Week 2: System prompts, zero/few-shot, chain-of-thought, structured output, invalid JSON, tool calling, tool descriptions, enums, prompt injection, model selection.
- [x] Week 3: RAG pipeline, chunking tension, fixed vs structure-aware chunking, overlap, metadata, filters, verifiable citations, refusals, retrieval-only evals.
- [x] Week 4: Retrieval, search, chunking, and local inference constraints.
- [x] Week 5: Output contracts, AST parsing, deterministic assertions.
- [x] Week 6: LLM-as-a-judge, blind protocols, Cohen's Kappa, and regression suites.
- [x] Week 7: ReAct agent loops, budgets, tool overlap, and workflow races.
- [x] Week 8: Trajectory evals, step efficiency, argument validity, and gap analysis.
- [x] Week 9: MCP architecture, JSON-RPC 2.0 stdio, zero-diff agents, and supply-chain risk.
- [x] Week 10: Multi-agent orchestrators, context re-send multipliers, A2A, and keep/kill verdicts.
