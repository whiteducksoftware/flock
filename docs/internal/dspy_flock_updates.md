# DSPy × Flock — Upgrade Analysis and Recommendations

This document reviews how Flock currently integrates DSPy, highlights breaking and behavioral changes in the latest DSPy, and proposes concrete, incremental improvements to make Flock’s integration more elegant, robust, and capable. No code has been changed yet; this is a design and planning deliverable for review.

## Executive Summary

- Flock’s DSPy integration works but re-implements several things that DSPy now provides natively (signatures, tools, streaming, usage tracking). We can delete custom glue, reduce surface area, and gain features by leaning on the current DSPy APIs.
- The most impactful updates:
  - Replace custom signature builder with `dspy.Signature(...)` + `custom_types`, and use signature mutation helpers (append/with_updated_fields) instead of rewriting `agent.input` strings.
  - Modernize streaming: use `dspy.streamify` events and stream listeners instead of scraping OpenAI-style deltas; emit StatusMessage and per-field streaming cleanly.
  - Stop calling `dspy.settings.configure(...)` inside async flows; use `dspy.settings.context(...)` per-run. Use per-call `lm=` overrides where needed.
  - Use JSON/XML adapters for structured output instead of ad-hoc parsing. Add TwoStepAdapter defaults for reasoning models.
  - Replace homegrown MCP tool schema conversion with DSPy’s `Tool` helpers where feasible; at minimum reuse the provided converters.
  - Switch cost/usage accounting to DSPy’s usage tracker or token-usage helpers rather than assuming `lm.history[i]['cost']`.
- Additional opportunities: adopt `dspy.History` inputs for chat context, `dspy.ToolCalls` for modeling predicted tool-calls, `dspy.Code` for typed code outputs, and stream listeners for “answer”/“reasoning” fields.

## Where Flock Uses DSPy Today

- Evaluation component
  - `src/flock/components/evaluation/declarative_evaluation_component.py`
    - Creates a DSPy signature via `DSPyIntegrationMixin.create_dspy_signature_class(...)`.
    - Picks a module via `_select_task` (Predict/ReAct/CoT); supports tool/mcp tools.
    - Streaming path: `dspy.streamify(..., is_async_program=True)` and iterates chunks; tries to parse `chunk.choices[0].delta.content`.
    - Non-streaming path: awaits `agent_task.acall(**inputs)`, then `_process_result(...)`.

- Integration helpers
  - `src/flock/core/mixin/dspy_integration.py`
    - Custom string→type resolution and dynamic `type(dspy_..., (dspy.Signature,), ...)` builder.
    - Configures LM with `dspy.LM(...)` then `dspy.settings.configure(lm=...)`.
    - Task selection to `dspy.Predict`, `dspy.ReAct`, `dspy.ChainOfThought`.
    - Result shaping merges inputs + parsed prediction; computes “cost” from `settings.lm.history`.

- MCP tools
  - `src/flock/core/mcp/flock_mcp_tool.py` and `src/flock/core/mcp/flock_mcp_server.py`
    - Builds `dspy.Tool` instances by hand from MCP tool schemas and wraps server calls.

- Memory utility
  - `src/flock/components/utility/memory_utility_component.py`
    - Injects `context` into inputs; mutates `agent.input` string to advertise the field; calls `agent._configure_language_model(...)` and `_select_task(...)` for a quick extraction pass.

- Initialization
  - `src/flock/core/orchestration/flock_initialization.py`
    - Optional Opik: `dspy.settings.configure(callbacks=[OpikCallback(...)])`.

## What Changed in DSPy (2.6+ highlights relevant to Flock)

- Global settings are stricter and richer
  - `dspy.settings.configure(...)` may only be called by the original owner thread and async task. Use `dspy.settings.context(...)` for per-call overrides.
  - New knobs: `adapter`, `callbacks`, `send_stream`, `stream_listeners`, `usage_tracker`, `max_history_size`, `max_trace_size`, etc.

- Language model and adapters
  - `dspy.LM(model=..., model_type='chat'|'text'|'responses', use_developer_role=...)`. Reasoning models (e.g., `gpt-5`, `o1`, `o3`) enforce `temperature=1.0` and `max_tokens>=16000`.
  - Adapters: `ChatAdapter` (default), `JSONAdapter` (native structured outputs), `XMLAdapter`, `TwoStepAdapter` (reasoning model + smaller extractor LM).

- Signatures and fields
  - `dspy.Signature("in1: Type -> out1: Type", instructions)` or dict form; `custom_types` lets you pass your own type map. Helpers: `append`, `prepend`, `delete`, `with_updated_fields`.
  - Pydantic-type annotations are respected; built-in parsing handles `typing` generics, `Union`, `Optional`, dotted names, etc.

- Streaming
  - `dspy.streamify(program, ...)` yields three kinds of items: `ModelResponseStream` chunks, `StatusMessage`, and a final `dspy.Prediction` (configurable).
  - `StreamListener(signature_field_name=...)` can stream specific output fields (e.g., `answer`, `reasoning`) across nested programs; `streaming_response(...)` converts to OpenAI-style SSE.

- Tools
  - `dspy.Tool(callable)` infers schema from type hints; `Tool.from_mcp_tool(session, tool)` and JSON-schema converters provided.
  - `ToolCalls` and `History` typed adapters model tool-calls output and chat history, respectively.

- Usage/metrics
  - `dspy.utils.usage_tracker.track_usage()` context collects usage across requests; LM exposes `history` entries with token `usage` (not necessarily “cost”). Helpers to sum tokens exist.

## Gaps and Anti‑Patterns in Flock’s Current Integration

- Signature construction duplicates DSPy
  - We parse `"name: type | desc"` with custom `_resolve_type_string` and build a dynamic subclass of `dspy.Signature`. DSPy already parses these; we can use `dspy.Signature(...)` with `custom_types` instead and delete that logic.
  - Memory utility mutates `agent.input` strings to add fields; better to work with a Signature instance and call `Signature.append(...)` at runtime (or create a derived signature per evaluation) instead of in-band string editing.

- Streaming implementation is brittle
  - We assume `chunk.choices[0].delta.content`. `dspy.streamify` now emits `ModelResponseStream` chunks, `StatusMessage`, and a final `Prediction`. We also call `_process_result(chunk, ...)` for each chunk, which is incorrect until the final `Prediction` is received.
  - We don’t use stream listeners; so we cannot stream specific output fields reliably, and we ignore status updates.

- Global settings usage can conflict with new constraints
  - `_configure_language_model(...)` calls `dspy.settings.configure(lm=...)` inside async flows (e.g., memory extraction), which is disallowed if not in the owner async task/thread. Prefer `settings.context(lm=...)` or per-call `lm=` override.
  - Opik config via `settings.configure(callbacks=[...])` is fine during boot, but must not be repeated in other tasks.

- Module selection mismatches and limited coverage
  - `_select_task(...)` expects override literals like `"Predict"`, `"ReAct"`, `"ChainOfThought"`. In one call site we pass `"Completion"`, which falls back with a warning. We should sanitize the enum and consider exposing DSPy’s `Refine` (and related) modules as first-class options for self‑critique/advice loops.

- MCP tool glue re-implements DSPy
  - `FlockMCPTool._convert_input_schema_to_tool_args(...)` duplicates DSPy’s JSON-schema conversion. Also, DSPy already exposes `Tool.from_mcp_tool(...)`. Even if we must route through our `client_manager`, we can still reuse DSPy’s conversion util to stay aligned.

- Cost/usage accounting relies on non-portable fields
  - `_process_result(...)` sums `x['cost']` from `settings.lm.history`. New DSPy records `usage` details per interaction; cost is model/provider-specific and not guaranteed. We should pivot to token usage via `usage_tracker` or token helpers.

## Concrete Recommendations (No Code Yet)

1) Replace custom signature builder with native DSPy Signatures
   - Where: `DSPyIntegrationMixin.create_dspy_signature_class` and its call sites.
   - Approach:
     - Build Signatures with `dspy.Signature(f"{inputs} -> {outputs}", instructions, custom_types=...)`.
     - Provide `custom_types` using Flock’s TypeRegistry for non-builtin types.
     - For runtime field injection (e.g., memory `context`), avoid mutating `agent.input` strings; keep a base signature and produce a derived signature via `Signature.append("context", dspy.InputField(...), type_=list[str])` when needed.
   - Benefits: less code, fewer bugs (parsing generics, Literals), easier to evolve with DSPy.

2) Modernize streaming end-to-end
   - Where: `DeclarativeEvaluationComponent._execute_streaming`.
   - Approach:
     - Use `streamify(program, stream_listeners=[...])` with listeners for each string output field we want to stream (e.g., `answer`, `reasoning`).
     - Handle yields by type:
       - `ModelResponseStream`: either pass through to UI or feed to listeners; don’t parse `.choices` directly in our code.
       - `StatusMessage`: surface progress to console/Web UI.
       - Final `Prediction`: only here call `_process_result(prediction, inputs)`.
     - If we need OpenAI-compatible SSE for the web app, wrap the generator with `dspy.streaming.streaming_response(...)`.
   - Benefits: robust across providers, supports per-field streaming, removes brittle delta parsing, plugs naturally into UI.

3) Scope DSPy configuration correctly
   - Where: `_configure_language_model`, memory utility’s `_extract_concepts`, evaluator setup.
   - Approach:
     - Avoid `settings.configure(...)` inside async tasks; prefer `with dspy.settings.context(lm=LM(...), adapter=..., callbacks=...)` around the call, or pass `lm=LM(...)` to `program.acall(...)` as a per-call override.
     - For reasoning models (`gpt-5`, `o*`), auto-select `model_type='responses'`, enforce `temperature=1.0`, `max_tokens>=16000`, and consider `TwoStepAdapter` (see below).
   - Benefits: complies with DSPy’s threading/async ownership rules; reduces global state churn.

4) Adopt adapters for structured outputs
   - Where: evaluator setup path.
   - Approach:
     - If agent outputs are strongly typed (Pydantic or explicit types), configure `dspy.JSONAdapter()` to get native structured outputs. For models without native structured outputs support, DSPy transparently falls back to JSON mode.
     - For reasoning models, set `dspy.TwoStepAdapter(extraction_model=dspy.LM("openai/gpt-4o-mini"))` to improve structure fidelity.
   - Benefits: fewer parsing hacks, better determinism, improved snapshot stability.

5) Expand module selection and unify override semantics
   - Where: `_select_task` and component config.
   - Approach:
     - Normalize allowed values (e.g., `predict`, `react`, `cot`, `refine`) case-insensitively; map `completion`/`predict` to `dspy.Predict`.
     - Consider exposing `dspy.Refine` and `MultiChainComparison` to align with “self-correct” components.
   - Benefits: clarity for users; unlocks more DSPy primitives without custom loops.

6) Reuse DSPy’s tool schema utilities
   - Where: `FlockMCPTool` and MCP server tool plumbing.
   - Approach:
     - Replace `_convert_input_schema_to_tool_args(...)` with DSPy’s `convert_input_schema_to_tool_args` to generate args/arg_types/arg_desc.
     - If a direct `Tool.from_mcp_tool(session, tool)` is feasible in our architecture, use it; otherwise keep our async wrapper but rely on DSPy’s type parsing.
   - Benefits: removes duplicated schema logic; stays current with DSPy changes (e.g., nested Pydantic handling).

7) Switch to token/usage accounting
   - Where: `_process_result`.
   - Approach:
     - Prefer `with dspy.track_usage() as tracker: ...` around evaluation; after completion, `tracker.get_total_tokens()` yields per‑LM token usage.
     - Alternatively, use `dspy.teleprompt.utils.get_token_usage(settings.lm)` to compute totals from `lm.history`.
     - If we still want a cost estimate, introduce a small mapping hook (model→$ per token) as an optional layer outside DSPy.
   - Benefits: provider‑agnostic, robust, and testable.

8) Embrace typed chat history and tool-calls where appropriate
   - Where: agent input/output contracts.
   - Approach:
     - Use `dspy.History` as an input field for chat‑style multi-turn interactions (instead of ad‑hoc `context` strings), letting adapters format history correctly.
     - When predicting a tool plan rather than executing tools live, use `dspy.ToolCalls` as an output field to model function selection and args deterministically.
   - Benefits: better structure and correctness for interactive agents; aligns with DSPy’s adapters.

9) Minor cleanups
   - Replace manual merging of `inputs` into outputs in `_process_result` with returning the DSPy `Prediction` fields only; let callers choose whether to merge.
   - Ensure `include_reasoning/include_thought_process` post-filters operate on `Prediction.items(include_dspy=False)`.
   - Avoid mutating `agent.input`/`agent.output` strings at runtime; use signature instances.
   - Use `program.update_config(...)` for per‑program defaults instead of rebuilding modules when only config changes.

## Suggested Migration Path (Safe, Incremental)

- Phase 1 — Internals parity (no behavior change)
  - Swap signature builder to `dspy.Signature(...)` with `custom_types` and keep current evaluator API.
  - Replace `_process_result` usage math with token usage; keep returning dicts to preserve snapshots.
  - Normalize evaluator override types; fix `"Completion"` → `Predict` mapping.

- Phase 2 — Streaming & settings hygiene
  - Update streaming loop to typed yields (StatusMessage/ModelResponseStream/Prediction) and stream listeners.
  - Replace in‑flow `settings.configure(...)` with `settings.context(...)` or per‑call `lm=...`.

- Phase 3 — Adapters and extras
  - Introduce `JSONAdapter` as an opt‑in on agents with structured outputs; add `TwoStepAdapter` for reasoning models.
  - Adopt `History` input and optional `ToolCalls` outputs for suitable agents.

- Phase 4 — MCP tool cleanup
  - Replace schema conversion with DSPy’s converter; evaluate feasibility of `Tool.from_mcp_tool(...)` for a direct path.

## Testing Implications

- Add p0 tests for:
  - Streaming: ensure `_execute_streaming` processes only on final `Prediction`; verify per-field streaming with a `StreamListener` stub.
  - Signature builder: dict/string forms produce expected `Signature.fields` and instructions; remove dependence on custom `_resolve_type_string`.
  - Usage tracking: prediction inside `dspy.track_usage()` yields stable token counts in tests (use DummyLM or cached responses).
  - Settings/threading: calling evaluator in async contexts uses `settings.context(...)` without `configure(...)` errors.
  - MCP tools: converter parity between our wrapper and DSPy’s conversion for a tiny JSON schema.

## Open Questions for Review

- Do we want `JSONAdapter` on by default when output is a Pydantic model? It improves determinism but can be stricter; proposal is making it opt‑in per agent or auto‑on for compatible providers.
- Should we expose DSPy modules (`Refine`, etc.) directly as component flags, or keep them behind a “strategy” sub-config?
- For web streaming, do we want to adopt `streaming_response(...)` and SSE end‑to‑end semantics now or after console parity lands?
- Is it acceptable to standardize on token usage reporting (and drop “cost”) in core API responses? If not, we can implement a pluggable cost estimator.

## Summary of Proposed Code Changes (future PRs)

- Replace `create_dspy_signature_class` with thin wrapper around `dspy.Signature` + `custom_types` and signature mutation helpers.
- Update `_execute_streaming` to handle typed yields and use stream listeners; process `Prediction` only at the end.
- Replace `_configure_language_model` global `configure(...)` with per-call `settings.context(...)` or `lm=` argument; audit all call sites.
- Introduce adapter configuration on `DeclarativeEvaluationConfig` (e.g., `adapter: 'chat'|'json'|'xml'|'two_step'` + optional extractor LM).
- Normalize evaluator type mapping and consider adding `refine`.
- Swap MCP tool schema conversion to DSPy’s utility; consider `Tool.from_mcp_tool` where feasible.
- Replace “cost” with token usage (tracker or helpers) in `_process_result` return metadata.
- Optional: add `History` to default chat agents and `ToolCalls` for planning-style outputs.

If approved, I can break this into small, reviewable PRs following the testing strategy and markers (p0 first, then integration).

