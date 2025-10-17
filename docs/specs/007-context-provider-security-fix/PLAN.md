# Implementation Plan: Context Provider Security Fix

## Validation Checklist
- [x] Context Ingestion section complete with all required specs
- [x] Implementation phases logically organized
- [x] Each phase starts with test definition (TDD approach)
- [x] Dependencies between phases identified
- [x] Parallel execution marked where applicable
- [x] Multi-component coordination identified (if applicable)
- [x] Final validation phase included
- [x] No placeholder content remains

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific security research sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all security requirements are met

### Deviation Protocol

If implementation cannot follow specification exactly:
1. Document the deviation and reason
2. Get approval before proceeding
3. Update security analysis if the deviation is an improvement
4. Never deviate without documentation

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

---

## Context Priming

*GATE: You MUST fully read all files mentioned in this section before starting any implementation.*

**Security Research Reference**:

- `.flock/flock-research/context-provider/SECURITY_ANALYSIS.md` - **PRIMARY REFERENCE** - Complete security vulnerability analysis with 3 critical findings
- `.flock/flock-research/context-provider/README.md` - Original Context Provider blueprint with security status header
- `.flock/flock-research/context-provider/DRIFT_ANALYSIS.md` - Technical drift analysis showing current vs proposed architecture

**Critical Security Findings** `[ref: SECURITY_ANALYSIS.md; lines: 11-50]`:

**🔴 Vulnerability #1 (READ Bypass)**: Agents can access ANY artifact via `ctx.board.list()` - visibility not enforced at context level
**🔴 Vulnerability #2 (WRITE Bypass)**: Agents can call `ctx.board.publish()` directly - validation bypassed
**🔴 Vulnerability #3 (GOD MODE)**: Agents have unlimited `ctx.orchestrator` access - complete privilege escalation

**Root Cause** `[ref: runtime.py; lines: 247-252]`:
```python
class Context(BaseModel):
    board: Any          # ❌ Direct store access (agents have god mode)
    orchestrator: Any   # ❌ Unlimited orchestrator access
```

**Key Design Decisions** `[ref: SECURITY_ANALYSIS.md; lines: 263-360]`:

1. **Remove Infrastructure Access**: Delete `board` and `orchestrator` from `Context` - agents don't need direct access
2. **Add Security Boundary**: Context Provider enforces visibility filtering BEFORE agents see data
3. **Orchestrator Publishes**: Move publishing from `agent.py:632` up to orchestrator level - validation cannot be bypassed
4. **No Backward Compatibility**: Engines MUST fail if they try old patterns (`.list()`, `.publish()`) - fail fast to enforce security

**Implementation Context**:

- **NO backward compatibility warnings** - Engines using old patterns must fail immediately
- **Commands to run**: `pytest tests/` for security validation tests
- **Patterns to follow**: Context Provider pattern `[ref: SECURITY_ANALYSIS.md; lines: 364-415]`
- **Pluggability**: Global (`Flock(context_provider=...)`) and per-agent (`agent.with_context(...)`)
- **Default Provider**: `DefaultContextProvider` with mandatory visibility enforcement
- **Filtered Provider**: `FilteredContextProvider` wraps `FilterConfig` for declarative filtering

---

## Implementation Phases

### Phase 1: Security Foundation - Remove Infrastructure Access ✅ **COMPLETED**

**🎯 Deliverable**: Agents no longer have direct `board`/`orchestrator` access (breaks god mode)

- [x] **Prime Context**: Security analysis vulnerability documentation
    - [x] Read complete vulnerability analysis `[ref: SECURITY_ANALYSIS.md; lines: 11-229]`
    - [x] Understand current Context structure `[ref: runtime.py; lines: 247-260]`

- [x] **Write Tests**: Verify agents cannot access infrastructure `[activity: test-security]`
    - [x] Test that `Context` has no `board` attribute (AttributeError expected)
    - [x] Test that `Context` has no `orchestrator` attribute (AttributeError expected)
    - [x] Test that agents trying to access `ctx.board.list()` fail immediately
    - [x] Test that agents trying to call `ctx.board.publish()` fail immediately
    - [x] Test location: `tests/test_context_security.py::test_context_no_infrastructure_access`

- [x] **Implement**: Remove dangerous fields from Context `[activity: refactor-security]`
    - [x] Open `src/flock/runtime.py` and modify `Context` class (lines 247-260)
    - [x] Remove `board: Any` field
    - [x] Remove `orchestrator: Any` field
    - [x] Keep `correlation_id`, `task_id`, `state`, `is_batch` (safe fields)
    - [x] **Expected breakage**: All engines using `ctx.board` or `ctx.orchestrator` will fail (INTENDED)

- [x] **Validate**: Ensure security gates work `[activity: run-tests]`
    - [x] Run `pytest tests/test_context_security.py -v`
    - [x] Verify AttributeError when accessing `ctx.board`
    - [x] Verify AttributeError when accessing `ctx.orchestrator`

**Results**: ✅ 8 security tests passing | GOD MODE broken | Agents have ZERO infrastructure access

---

### Phase 2: Context Provider Protocol & Default Implementation ✅ **COMPLETED**

**🎯 Deliverable**: Security boundary enforcing visibility filtering

- [x] **Prime Context**: Provider design and visibility enforcement
    - [x] Read provider architecture `[ref: SECURITY_ANALYSIS.md; lines: 364-415]`
    - [x] Review visibility system `[ref: src/flock/visibility.py; lines: 1-108]`
    - [x] Understand FilterConfig `[ref: src/flock/store.py; lines: 92-102]`

- [x] **Write Tests**: Provider protocol and visibility enforcement `[activity: test-security]`
    - [x] Test `ContextProvider` protocol is callable with `ContextRequest`
    - [x] Test `DefaultContextProvider` filters by visibility (agent can only see allowed artifacts)
    - [x] Test `DefaultContextProvider` respects `PrivateVisibility` (agent NOT in allowlist gets empty list)
    - [x] Test `DefaultContextProvider` respects `TenantVisibility` (different tenant gets empty list)
    - [x] Test `DefaultContextProvider` respects `LabelledVisibility` (missing label gets empty list)
    - [x] Test `DefaultContextProvider` respects correlation_id filtering
    - [x] Test location: `tests/test_context_provider.py::test_default_provider_security`

- [x] **Implement**: Create provider protocol `[activity: implement-security]`
    - [x] Create `src/flock/context_provider.py` (new file)
    - [x] Define `ContextRequest` dataclass with `agent: Agent`, `correlation_id: UUID`, `store: BlackboardStore`, `agent_identity: AgentIdentity`
    - [x] Define `ContextProvider` Protocol with `async def __call__(request: ContextRequest) -> list[dict[str, Any]]`
    - [x] **NO** advanced providers (CompositeProvider, RedactingProvider) - out of scope

- [x] **Implement**: Default provider with visibility enforcement `[activity: implement-security]`
    - [x] Implement `DefaultContextProvider` class in `src/flock/context_provider.py`
    - [x] In `__call__`: query artifacts using `FilterConfig(correlation_id=str(request.correlation_id))`
    - [x] **CRITICAL**: Filter results by `artifact.visibility.allows(request.agent_identity)` - THIS IS THE SECURITY FIX
    - [x] Return list of dicts: `[{"type": a.type, "payload": a.payload, "produced_by": a.produced_by, ...}]`
    - [x] Include docstring explaining security enforcement

- [x] **Validate**: Provider enforces security `[activity: run-tests]`
    - [x] Run `pytest tests/test_context_provider.py -v`
    - [x] Verify agents can ONLY see artifacts they're allowed to see
    - [x] Verify private/tenant/label visibility is enforced

**Results**: ✅ 11 security tests passing | Security boundary enforced | Visibility filtering mandatory | READ bypass vulnerability FIXED

---

### Phase 3: Pluggable Providers - Global & Per-Agent ✅ **COMPLETED**

**🎯 Deliverable**: Users can configure custom providers globally or per-agent

- [x] **Component A**: Global provider configuration `[parallel: true]` `[component: orchestrator]`

    - [x] **Prime Context**: Orchestrator initialization
        - [x] Read orchestrator structure `[ref: src/flock/orchestrator.py; lines: 1-100]`

    - [x] **Write Tests**: Global provider configuration `[activity: test-integration]`
        - [x] Test `Flock(context_provider=MyProvider())` sets global provider
        - [x] Test agents use global provider if no per-agent provider configured
        - [x] Test location: `tests/test_context_provider.py::test_global_provider`

    - [x] **Implement**: Add provider to Flock `[activity: implement-integration]`
        - [x] Add `context_provider: ContextProvider | None = None` parameter to `Flock.__init__()` in `src/flock/orchestrator.py`
        - [x] Store as `self._default_context_provider`
        - [x] When creating Context for agent execution, pass provider to agents (mechanism TBD in Phase 7)

    - [x] **Validate**: Global provider works `[activity: run-tests]`
        - [x] Run `pytest tests/test_context_provider.py::test_global_provider -v`

- [x] **Component B**: Per-agent provider configuration `[parallel: true]` `[component: agent]`

    - [x] **Prime Context**: Agent builder API
        - [x] Read agent builder `[ref: src/flock/agent.py; lines: 799-1425]`

    - [x] **Write Tests**: Per-agent provider configuration `[activity: test-integration]`
        - [x] Test `agent.with_context(MyProvider())` sets agent-specific provider
        - [x] Test agent-specific provider overrides global provider
        - [x] Test location: `tests/test_context_provider.py::test_per_agent_provider`

    - [x] **Implement**: Add with_context to AgentBuilder `[activity: implement-integration]`
        - [x] Add `with_context(self, provider: ContextProvider) -> AgentBuilder` method to `AgentBuilder` in `src/flock/agent.py`
        - [x] Store as `self._agent.context_provider`
        - [x] Return `self` for fluent chaining

    - [x] **Validate**: Per-agent provider works `[activity: run-tests]`
        - [x] Run `pytest tests/test_context_provider.py::test_per_agent_provider -v`

**Results**: ✅ 7 configuration tests passing | Global provider supported | Per-agent provider supported | Provider override priority working

---

### Phase 4: FilteredContextProvider - Declarative Filtering ✅ **COMPLETED**

**🎯 Deliverable**: Ergonomic provider wrapping FilterConfig

- [x] **Prime Context**: FilterConfig and query API
    - [x] Read FilterConfig structure `[ref: src/flock/store.py; lines: 92-102]`
    - [x] Review query_artifacts API `[ref: src/flock/store.py; lines: 161-170]`

- [x] **Write Tests**: FilteredContextProvider functionality `[activity: test-integration]`
    - [x] Test `FilteredContextProvider(FilterConfig(tags={"important"}))` filters by tags
    - [x] Test `FilteredContextProvider(FilterConfig(type_names={"Task"}))` filters by type
    - [x] Test `FilteredContextProvider` still enforces visibility on top of filters
    - [x] Test `FilteredContextProvider(limit=10)` respects artifact limit
    - [x] Test location: `tests/test_context_provider.py::TestFilteredContextProvider`

- [x] **Implement**: FilteredContextProvider class `[activity: implement-integration]`
    - [x] Add `FilteredContextProvider` class to `src/flock/context_provider.py`
    - [x] Constructor: `__init__(self, filter_config: FilterConfig, limit: int = 50)`
    - [x] In `__call__`: query using `store.query_artifacts(self.filter_config, limit=self.limit)`
    - [x] **CRITICAL**: Still filter by `artifact.visibility.allows(agent_identity)` - visibility is ALWAYS enforced
    - [x] Return filtered artifact dicts

- [x] **Validate**: FilteredContextProvider works `[activity: run-tests]`
    - [x] Run `pytest tests/test_context_provider.py::TestFilteredContextProvider -v`
    - [x] Verify declarative filtering + visibility enforcement

**Results**: ✅ 6 declarative filtering tests passing | Tag filtering working | Type filtering working | Visibility enforcement on top of filters (CRITICAL SECURITY) | Limit respected | Format validated | Total: 24 tests passing (2 protocol + 9 DefaultContextProvider + 7 pluggable + 6 FilteredContextProvider)

---

### Phase 5: Engine Integration - Remove Direct Store Access ✅ **COMPLETED**

**🎯 Deliverable**: Engines use provider instead of `ctx.board.list()`

- [x] **Prime Context**: Engine architecture and current fetch_conversation_context
    - [x] Read EngineComponent `[ref: src/flock/components.py; lines: 156-205]`
    - [x] Identify current inefficient pattern (uses `list()` instead of `query_artifacts`)

- [x] **Write Tests**: Engine context fetching via provider `[activity: test-integration]`
    - [x] Test `EngineComponent.fetch_conversation_context()` uses provider (no direct `ctx.board` access)
    - [x] Test engine receives only visible artifacts (respects visibility)
    - [x] Test engine receives correlation-filtered artifacts by default
    - [x] Test engine respects context_exclude_types configuration
    - [x] Test engine respects context_max_artifacts limit
    - [x] Test custom provider works with engine (FilteredContextProvider)
    - [x] Test engine returns correct output format
    - [x] Test location: `tests/test_engine_context.py::TestEngineUsesProvider`

- [x] **Implement**: Update EngineComponent.fetch_conversation_context `[activity: implement-security]`
    - [x] Modify `src/flock/components.py` lines 156-249
    - [x] **REMOVED**: `all_artifacts = await ctx.board.list()` line (THIS WAS THE VULNERABILITY)
    - [x] **ADDED**: Get provider from context with fail-fast: `provider = getattr(ctx, "provider", None)`
    - [x] **ADDED**: Agent parameter to fetch_conversation_context signature (needed for visibility)
    - [x] Create `ContextRequest(agent=agent, correlation_id=target_correlation_id, store=store, agent_identity=agent.identity)`
    - [x] Call `context_items = await provider(request)` to get FILTERED context
    - [x] Apply `context_max_artifacts` limit if configured
    - [x] Apply `context_exclude_types` filtering
    - [x] Return filtered context with event_number field
    - [x] **NO FALLBACK** to `ctx.board` - engines fail fast if provider missing

- [x] **Validate**: Engines secure `[activity: run-tests]`
    - [x] Run `pytest tests/test_engine_context.py::TestEngineUsesProvider -v`
    - [x] Verify engines cannot bypass visibility (untrusted agents see nothing)
    - [x] Verify engines use provider not ctx.board

**Results**: ✅ 7 engine integration tests passing | Vulnerable ctx.board.list() REMOVED | Provider-based context fetching implemented | Visibility enforcement at engine level | Fail-fast behavior verified | READ bypass vulnerability at engine level FIXED

---

### Phase 6+7: Orchestrator Publishing + Context Injection (COMBINED SPRINT) ✅ **COMPLETED**

**🎯 Deliverable**: Orchestrator validates & publishes + injects provider (agents return data only)

- [x] **Prime Context**: Current agent publishing flow and orchestrator execution
    - [x] Read agent execute flow `[ref: src/flock/agent.py; lines: 195-246]`
    - [x] Read _make_outputs_for_group `[ref: src/flock/agent.py; lines: 514-634]`
    - [x] Identify current `await ctx.board.publish(artifact)` calls (lines 491, 634)
    - [x] Read orchestrator execution logic `[ref: src/flock/orchestrator.py; lines: 604, 969, 1337]`
    - [x] Understand how Context is created for agents

- [x] **Write Tests**: Orchestrator-controlled publishing + Provider injection `[activity: test-security]`
    - [x] Test orchestrator injects provider + store into Context (Phase 7)
    - [x] Test orchestrator removes board/orchestrator from Context (Phase 1 fix)
    - [x] Test provider resolution: per-agent > global > DefaultContextProvider (Phase 7)
    - [x] Test agents return `EvalResult` with artifacts (NO direct publishing) (Phase 6)
    - [x] Test orchestrator publishes artifacts after agent.execute() (Phase 6)
    - [x] Test orchestrator respects publish_outputs flag (Phase 6)
    - [x] Test end-to-end security boundary (Phase 6+7 integration)
    - [x] Test visibility enforcement with provider injection (Phase 6+7 integration)
    - [x] Test location: `tests/test_orchestrator_context_injection.py` (13 comprehensive tests)

- [x] **Implement**: Remove publishing from Agent class `[activity: implement-security]`
    - [x] Modify `src/flock/agent.py::_make_outputs` (line 491)
    - [x] **REMOVED**: `await ctx.board.publish(artifact)` call at line 491
    - [x] Modify `src/flock/agent.py::_make_outputs_for_group` (line 634)
    - [x] **REMOVED**: `await ctx.board.publish(artifact)` call at line 634
    - [x] **RESULT**: Agents now return `produced` list WITHOUT publishing

- [x] **Implement**: Add publishing to Orchestrator + Inject Provider `[activity: implement-security]`
    - [x] Modify `src/flock/orchestrator.py::direct_invoke` (line 604)
      - [x] Add provider resolution: `provider = getattr(agent, "context_provider", None) or self._default_context_provider or DefaultContextProvider()`
      - [x] Create Context with provider + store (NO board/orchestrator)
      - [x] Orchestrator already publishes outputs (line 603)
    - [x] Modify `src/flock/orchestrator.py::invoke` (line 969)
      - [x] Add provider resolution
      - [x] Create Context with provider + store (NO board/orchestrator)
      - [x] Add publishing after agent.execute(): `for output in outputs: await self._persist_and_schedule(output)`
    - [x] Modify `src/flock/orchestrator.py::_run_agent_task` (line 1337)
      - [x] Add provider resolution
      - [x] Create Context with provider + store (NO board/orchestrator)
      - [x] Add publishing after agent.execute(): `for output in outputs: await self._persist_and_schedule(output)`
    - [x] **RESULT**: All Context creation points inject provider + store, orchestrator publishes all outputs

- [x] **Validate**: Publishing security + Provider injection works `[activity: run-tests]`
    - [x] Run `pytest tests/test_orchestrator_context_injection.py -v` (13/13 tests passing)
    - [x] Verify agents cannot publish (no `ctx.board.publish()`)
    - [x] Verify orchestrator handles publishing
    - [x] Verify global provider is used
    - [x] Verify per-agent provider overrides
    - [x] Verify DefaultContextProvider fallback
    - [x] Run `pytest tests/test_context_provider.py tests/test_engine_context.py -v` (31/31 existing tests still passing)

**Results**: ✅ 13 Phase 6+7 tests passing + 31 existing tests still passing | WRITE bypass vulnerability FIXED (agents can't publish) | Context injection complete (provider + store) | Provider resolution working (per-agent > global > default) | End-to-end security boundary operational | Total implementation time: ~2 hours (combined sprint)

---

### Integration & End-to-End Validation

**🎯 Deliverable**: All security vulnerabilities fixed, system works correctly

- [ ] **Security Validation**: All three vulnerabilities patched `[activity: test-security]`
    - [ ] ✅ **Vulnerability #1 (READ)**: Agents CANNOT access `ctx.board.list()` (AttributeError)
    - [ ] ✅ **Vulnerability #2 (WRITE)**: Agents CANNOT call `ctx.board.publish()` (AttributeError)
    - [ ] ✅ **Vulnerability #3 (GOD MODE)**: Agents CANNOT access `ctx.orchestrator` (AttributeError)
    - [ ] Test private artifact visibility: Agent without permission gets empty context
    - [ ] Test tenant isolation: Agent from tenant A cannot see tenant B data
    - [ ] Test label-based RBAC: Agent without required label cannot see classified data
    - [ ] Test location: `tests/test_security_fixes.py` (comprehensive security test suite)

- [ ] **Integration Tests**: Provider system works end-to-end `[activity: test-integration]`
    - [ ] Test full workflow: publish → agent triggered → provider filters context → agent processes → orchestrator publishes result
    - [ ] Test global provider configuration works
    - [ ] Test per-agent provider configuration works
    - [ ] Test FilteredContextProvider with various FilterConfig options
    - [ ] Test provider receives correct store and agent identity
    - [ ] Test location: `tests/test_context_provider_integration.py`

- [ ] **Compatibility Tests**: Old engines fail fast (NO backward compatibility) `[activity: test-security]`
    - [ ] Test engine using `ctx.board.list()` raises AttributeError immediately
    - [ ] Test engine using `ctx.board.publish()` raises AttributeError immediately
    - [ ] Test engine using `ctx.orchestrator` raises AttributeError immediately
    - [ ] **EXPECTED BEHAVIOR**: Old engines MUST fail (enforces migration to secure pattern)
    - [ ] Test location: `tests/test_no_backward_compatibility.py`

- [ ] **Performance Validation**: Verify query optimization `[activity: test-performance]`
    - [ ] Verify DefaultContextProvider uses `query_artifacts()` not `list()` (fixes performance bug)
    - [ ] Test with 10,000 artifacts: verify O(log N) query time (indexed query)
    - [ ] Compare memory usage: old (`list()` = O(N)) vs new (provider = O(M) where M = visible artifacts)
    - [ ] Test location: `tests/test_context_provider_performance.py`

- [ ] **Example Validation**: Update existing examples `[activity: update-docs]`
    - [ ] Identify examples using `ctx.board` (will break)
    - [ ] Update to use provider pattern OR accept context as-is from engine
    - [ ] Verify all examples still work after security fix
    - [ ] Examples location: `examples/` directory

- [ ] **Documentation**: Security fix guide `[activity: update-docs]`
    - [ ] Create `docs/migration/context-provider-security-fix.md`
    - [ ] Document the three vulnerabilities that were fixed
    - [ ] Explain new Context Provider pattern
    - [ ] Show before/after code examples
    - [ ] Explain why NO backward compatibility (security fix)
    - [ ] Document global vs per-agent provider configuration
    - [ ] Document FilteredContextProvider usage

- [ ] **Test Coverage**: Ensure comprehensive security coverage `[activity: run-tests]`
    - [ ] Run `pytest tests/ --cov=src/flock --cov-report=term-missing`
    - [ ] Verify >90% coverage for `context_provider.py`, `runtime.py`, `components.py`, `agent.py`, `orchestrator.py`
    - [ ] Verify all security test scenarios pass

- [ ] **Final Security Audit**: Independent validation `[activity: review-security]`
    - [ ] Review all code changes for security implications
    - [ ] Verify no other code paths allow direct store access
    - [ ] Verify visibility enforcement cannot be bypassed
    - [ ] Verify orchestrator is sole publisher (agents cannot forge artifacts)
    - [ ] Confirm attack scenarios from SECURITY_ANALYSIS.md are no longer possible

- [ ] **Build Verification**: System builds and runs `[activity: run-tests]`
    - [ ] Run `pytest tests/ -v` (all tests pass)
    - [ ] Run any project-specific build commands
    - [ ] Verify no runtime errors in examples
    - [ ] Verify orchestrator starts correctly with new architecture

---

## Implementation Notes

### Critical Security Requirements

1. **NO Backward Compatibility**: Engines using old patterns (`ctx.board.list()`, `ctx.board.publish()`, `ctx.orchestrator`) MUST fail immediately with AttributeError
2. **Mandatory Visibility**: Context Providers MUST ALWAYS filter by visibility - this cannot be optional or bypassable
3. **Orchestrator Publishing**: ONLY the orchestrator can publish to the store - agents return data only
4. **Fail Fast**: If provider is missing or misconfigured, system should fail immediately, not fall back to insecure pattern

### Test-Driven Development Approach

- **Red-Green-Refactor**: Write failing test → Implement minimal code to pass → Refactor
- **Security-First**: Security tests drive implementation (agents CANNOT access infrastructure)
- **No Mocking Security**: Test real visibility enforcement, not mocked behavior
- **Integration Tests**: Test full workflow end-to-end with real store and visibility system

### Parallel Execution Strategy

- **Phase 3 Component A & B**: Can run in parallel (orchestrator and agent changes are independent)
- **All other phases**: Must run sequentially (each phase depends on previous)

### Reference Architecture

**Before** (INSECURE):
```
Agent → ctx.board.list() → Store (NO FILTERING!)
Agent → ctx.board.publish() → Store (NO VALIDATION!)
Agent → ctx.orchestrator.* → (GOD MODE!)
```

**After** (SECURE):
```
Agent → provider(request) → [Visibility Filter] → Filtered Context
Agent → return EvalResult → Orchestrator validates → Orchestrator publishes
Agent → ctx.orchestrator REMOVED → (NO GOD MODE!)
```

### Key Files Modified

- `src/flock/runtime.py`: Remove `board`, `orchestrator` from Context; add `provider`
- `src/flock/context_provider.py`: NEW FILE - Provider protocol and implementations
- `src/flock/components.py`: Update `fetch_conversation_context` to use provider
- `src/flock/agent.py`: Remove `ctx.board.publish()` calls
- `src/flock/orchestrator.py`: Add provider injection, handle publishing
- `tests/test_context_security.py`: NEW FILE - Security validation tests
- `tests/test_context_provider.py`: NEW FILE - Provider tests
- `tests/test_security_fixes.py`: NEW FILE - Comprehensive security test suite

### Success Criteria

✅ All three vulnerabilities FIXED (agents cannot bypass security)
✅ Visibility enforced at context level (mandatory, cannot be bypassed)
✅ Validation enforced at orchestrator level (agents cannot forge artifacts)
✅ NO backward compatibility (old patterns fail immediately)
✅ Provider system pluggable (global and per-agent configuration)
✅ FilteredContextProvider works with FilterConfig
✅ All tests pass (security, integration, performance)
✅ Documentation complete (migration guide)

### Total Estimated Effort

- **Phase 1**: 3 hours (remove infrastructure access)
- **Phase 2**: 4 hours (provider protocol + default implementation)
- **Phase 3**: 3 hours (pluggable providers, parallel execution)
- **Phase 4**: 2 hours (FilteredContextProvider)
- **Phase 5**: 3 hours (engine integration)
- **Phase 6**: 4 hours (orchestrator publishing)
- **Phase 7**: 3 hours (context injection)
- **Integration**: 4 hours (end-to-end validation)

**Total**: ~26 hours (~3-4 days with testing and validation)

---

## References

- **Primary**: `.flock/flock-research/context-provider/SECURITY_ANALYSIS.md` - Complete security vulnerability analysis
- **Blueprint**: `.flock/flock-research/context-provider/README.md` - Original Context Provider design
- **Drift Analysis**: `.flock/flock-research/context-provider/DRIFT_ANALYSIS.md` - Current vs proposed architecture
