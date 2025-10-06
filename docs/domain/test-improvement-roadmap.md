# Test Improvement Roadmap: 58% → 80% Coverage

**Analysis Date:** 2025-10-05
**Current Coverage:** 58% (56.81% precise)
**Target Coverage:** 80%
**Gap:** 22% coverage increase needed

## Executive Summary

This roadmap provides a complete battle plan to achieve 80% test coverage while fixing test/implementation drift and eliminating code smells. The analysis identified three interconnected problems that must be addressed together:

1. **Coverage Gaps**: 35 untested source files, critical modules at <30% coverage
2. **API Drift**: 52 instances of deprecated/legacy API usage in tests
3. **Code Smells**: Real LLM connections, broken mocks, massive duplication

**Key Insight:** Simply adding tests won't work - we must fix drift and smells FIRST, then add coverage. Otherwise, we're building on a broken foundation.

---

## The Three-Phase Strategy

### Phase 1: Foundation Repair (Week 1)
**Goal:** Fix drift and smells so new tests use correct patterns
**Effort:** 12-16 hours
**Coverage Impact:** +0% (but prevents future drift)

### Phase 2: Critical Coverage (Weeks 2-3)
**Goal:** Test the untested critical infrastructure
**Effort:** 50-70 hours
**Coverage Impact:** +15-18%

### Phase 3: Dashboard & Polish (Week 4)
**Goal:** Fill remaining gaps to cross 80% threshold
**Effort:** 20-30 hours
**Coverage Impact:** +4-6%

**Total Timeline:** 4 weeks
**Total Effort:** 82-116 hours
**Expected Final Coverage:** 76-81% ✅

---

## Phase 1: Foundation Repair (Week 1)

### 1.1 Fix Production Code Drift (CRITICAL - 2 hours)

**File:** `/home/ara/work/flock-flow/src/flock/service.py:37`

```python
# BEFORE (Deprecated API)
await orchestrator.publish_external(type_name=type_name, payload=payload)

# AFTER (Current API)
artifact_dict = {"type": type_name, **payload}
await orchestrator.publish(artifact_dict)
```

**Why First:** Production API endpoint must use current API before we update tests.

---

### 1.2 Update Test Fixtures (CRITICAL - 4 hours)

**File:** `/home/ara/work/flock-flow/tests/conftest.py`

**Changes Required:**

```python
# Line 30: Remove LLM model from orchestrator fixture
@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test."""
    # BEFORE: return Flock(model="gpt-4o-mini")
    return Flock()  # AFTER: No model needed for tests

# Lines 51-59: Fix or remove unused mock_llm fixture
# OPTION 1: Make it auto-use
@pytest.fixture(autouse=True)
def mock_llm(mocker):
    """Auto-mock all LLM calls in tests."""
    mock_lm = Mock()
    mock_lm.return_value = "mocked output"
    mocker.patch("dspy.LM", return_value=mock_lm)
    return mock_lm

# OPTION 2: Remove it entirely if not needed
# (Delete lines 51-59)

# NEW: Add collector fixture (eliminate 12 duplicates)
@pytest.fixture
def collector():
    """Create DashboardEventCollector instance."""
    return DashboardEventCollector()

# NEW: Add specialized orchestrator fixture
@pytest.fixture
def orchestrator_with_collector(collector):
    """Orchestrator with dashboard collector attached."""
    orch = Flock()
    orch._dashboard_collector = collector
    return orch
```

**Removes 7 duplicate fixtures** across these files:
- `tests/e2e/test_critical_scenarios.py:41`
- `tests/test_dashboard_service.py:17`
- `tests/test_dashboard_collector.py:45`
- `tests/integration/test_orchestrator_dashboard.py:14`
- `tests/test_dashboard_api.py:78`
- `tests/integration/test_websocket_protocol.py:30`

---

### 1.3 Fix High-Priority Test Drift (6-10 hours)

**Affected Files (by priority):**

#### 1️⃣ `/home/ara/work/flock-flow/tests/test_orchestrator.py` (23 issues)

**Lines with `publish_external` (19 instances):**
92, 115, 138, 162, 213, 216, 242, 266-272, 292, 310, 334-335, 444, 462, 469, 511

**Lines with `arun` (2 instances):**
18, 52

**Lines with `direct_invoke` (2 instances):**
382, 397

**Migration Pattern:**
```python
# BEFORE: publish_external
await orchestrator.publish_external(
    type_name="OrchestratorMovie",
    payload={"title": "Test", "runtime": 120}
)

# AFTER: publish with dict
await orchestrator.publish({
    "type": "OrchestratorMovie",
    "title": "Test",
    "runtime": 120
})

# OR AFTER: publish with model (preferred)
movie = OrchestratorMovie(title="Test", runtime=120)
await orchestrator.publish(movie)

# BEFORE: arun
outputs = await orchestrator.arun(agents["movie"], idea)

# AFTER: invoke
outputs = await orchestrator.invoke(agents["movie"], idea)
await orchestrator.run_until_idle()

# BEFORE: direct_invoke (internal API)
await orchestrator.direct_invoke(agent.agent, [dict_input])

# AFTER: invoke (public API)
await orchestrator.invoke(agent, dict_input)
```

#### 2️⃣ `/home/ara/work/flock-flow/tests/test_agent.py` (13 issues)

**Lines with `publish_external` (2 instances):**
435, 474

**Lines with `arun` (11 instances):**
124, 155, 181-182, 209, 237, 271, 304, 330, 360, 386

**Also replace 11 inline `Flock()` creations with fixture usage.**

#### 3️⃣ `/home/ara/work/flock-flow/tests/integration/test_collector_orchestrator.py` (8 issues)

**Lines with `arun` (8 instances):**
88, 142, 176, 212, 252-253, 282, 328

---

### 1.4 Fix Critical Code Smells (2-4 hours)

#### Remove LLM Model Strings

**File:** `/home/ara/work/flock-flow/tests/test_version_endpoint.py`

```python
# Lines 16, 48: BEFORE
orchestrator = Flock("openai/gpt-4o-mini")

# AFTER
orchestrator = Flock()  # Or use fixture parameter
```

#### Fix Broken Mock Test

**File:** `/home/ara/work/flock-flow/tests/test_engines.py:28-64`

```python
# BEFORE (Lines 61-64) - Always passes!
except Exception:
    # Mock may not match exact DSPy API, but test validates mocking approach
    # This is acceptable for a mock-based test
    assert True

# AFTER - Proper mock or remove test
@pytest.mark.asyncio
async def test_dspy_engine_with_proper_mock(orchestrator, mocker):
    """Test DSPy engine with properly mocked LM."""

    # Create proper mock that matches DSPy API
    mock_lm = Mock()
    mock_response = Mock()
    mock_response.response = "mocked output"
    mock_lm.return_value = mock_response

    mocker.patch("dspy.LM", return_value=mock_lm)

    agent = (
        orchestrator.agent("test")
        .consumes(EngineInput)
        .publishes(EngineOutput)
        .with_engines(DSPyEngine(stream=False))
    )

    input_artifact = EngineInput(prompt="test")
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Verify mock was called
    assert mock_lm.called

    # Verify artifacts published
    artifacts = await orchestrator.store.list()
    assert len(artifacts) > 0
```

#### Replace Inline Object Creation with Fixtures (2 hours)

**Pattern Found 39 Times:**
```python
# BEFORE
@pytest.mark.asyncio
async def test_something():
    orchestrator = Flock()
    # ...

# AFTER
@pytest.mark.asyncio
async def test_something(orchestrator):  # Use fixture parameter
    # ...
```

**Files to update:**
- `tests/test_orchestrator.py` (7 instances)
- `tests/test_agent.py` (11 instances)
- `tests/test_components.py` (4 instances)
- `tests/test_engines.py` (2 instances)
- Others (15 instances)

---

## Phase 2: Critical Coverage (Weeks 2-3)

### 2.1 Priority 1: DSPy Engine Tests (+8-10% coverage)

**Create:** `tests/test_dspy_engine.py`

**Current Coverage:** 25.43% (301 missing lines)
**Target Coverage:** 80%+
**Impact:** Highest coverage gain potential

**Test Scenarios Needed:**

```python
# 1. Basic Signature Execution (Lines 211-256)
async def test_dspy_signature_execution():
    """Test basic DSPy signature creation and execution."""
    # Cover: build_dspy_signature(), _execute_signature()

# 2. Streaming Output (Lines 480-600)
async def test_streaming_output_generation():
    """Test streaming token generation."""
    # Cover: stream=True path, _stream_output()

# 3. Non-Streaming Output (Lines 600-700)
async def test_non_streaming_output():
    """Test regular (non-streaming) output."""
    # Cover: stream=False path, _generate_output()

# 4. MCP Tool Integration (Lines 782-847)
async def test_mcp_tool_integration():
    """Test MCP tool assignment to DSPy engine."""
    # Cover: assign_mcp_tools(), tool execution

# 5. Error Handling (Lines 700-776)
async def test_error_handling_in_engine():
    """Test engine error handling and recovery."""
    # Cover: try/except blocks, error artifact creation

# 6. Rich Live Patching (Lines 74-105)
async def test_rich_live_patch():
    """Test Rich Live display patching for streaming."""
    # Cover: _patch_rich_live()

# 7. Context Variable Handling (Lines 400-450)
async def test_context_variables():
    """Test proper context propagation through engine."""
    # Cover: context variable access in signatures

# 8. Multiple Input Artifacts (Lines 320-400)
async def test_multiple_input_handling():
    """Test engine with multiple consumed artifacts."""
    # Cover: multiple artifact consumption pattern
```

**Key Testing Patterns:**
- Use `mock_llm` fixture for all tests
- Test with `stream=True` and `stream=False`
- Mock MCP client for tool integration tests
- Use `DSPyEngine(model="test")` with mocked backend

---

### 2.2 Priority 2: MCP Client Tests (+3-4% coverage)

**Create:** `tests/test_mcp_client.py`

**Current Coverage:** 18.88% (203 missing lines)
**Target Coverage:** 80%+

**Test Scenarios Needed:**

```python
# 1. Client Initialization (Lines 159-220)
async def test_client_initialization():
    """Test MCPClientWrapper initialization."""
    # Cover: __init__, lazy connection setup

# 2. Tool Listing & Caching (Lines 241-324)
async def test_tool_listing_with_cache():
    """Test tool list retrieval and caching."""
    # Cover: list_tools(), caching logic

async def test_tool_cache_invalidation():
    """Test cache invalidation on reconnect."""

# 3. Tool Execution (Lines 357-402)
async def test_tool_execution():
    """Test calling MCP tools."""
    # Cover: call_tool()

async def test_tool_execution_errors():
    """Test error handling during tool calls."""

# 4. Resource Operations (Lines 411-475)
async def test_resource_operations():
    """Test resource read/list operations."""
    # Cover: read_resource(), list_resources()

# 5. Connection Management (Lines 479-559)
async def test_connection_lifecycle():
    """Test connect/disconnect/reconnect."""
    # Cover: connect(), disconnect(), _ensure_connected()

async def test_lazy_connection():
    """Test lazy connection establishment."""

# 6. Prompt Operations (Lines 566-633)
async def test_prompt_operations():
    """Test prompt listing and retrieval."""
    # Cover: list_prompts(), get_prompt()
```

**Mock Strategy:**
```python
@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for testing wrapper."""
    mock = AsyncMock()
    mock.list_tools.return_value = [
        {"name": "test_tool", "description": "A test tool"}
    ]
    return mock
```

---

### 2.3 Priority 3: Telemetry Tests (+1.5-2% coverage)

**Create:** `tests/test_telemetry.py`

**Current Coverage:** 0.00% (entire file untested)
**Target Coverage:** 80%+

**Test Scenarios Needed:**

```python
# 1. TelemetryConfig (Lines 10-50)
def test_telemetry_config_creation():
    """Test telemetry configuration."""
    # Cover: TelemetryConfig model

# 2. Tracer Setup (Lines 60-120)
def test_setup_tracer():
    """Test tracer initialization."""
    # Cover: setup_tracer()

def test_tracer_with_custom_config():
    """Test custom telemetry config."""

# 3. Exporters (Lines 130-170)
def test_console_exporter():
    """Test console exporter setup."""

def test_otlp_exporter():
    """Test OTLP exporter configuration."""

# 4. Environment Handling (Lines 180-193)
def test_environment_variables():
    """Test env var-based configuration."""
```

---

### 2.4 Priority 4: MCP Manager Tests (+1-1.5% coverage)

**Create:** `tests/test_mcp_manager.py`

**Current Coverage:** 21.15% (57 missing lines)

**Test Scenarios Needed:**

```python
# 1. Manager Initialization
async def test_manager_initialization():
    """Test MCPClientManager setup."""

# 2. Server Registration
async def test_server_registration():
    """Test registering MCP servers."""

# 3. Client Lifecycle
async def test_client_lifecycle():
    """Test client start/stop."""

# 4. Multiple Servers
async def test_multiple_servers():
    """Test managing multiple MCP servers."""
```

---

### 2.5 Priority 5: MCP Config Tests (+1.5-2% coverage)

**Create:** `tests/test_mcp_config.py`

**Current Coverage:** 39.06% (91 missing lines)

**Test Scenarios Needed:**

```python
# 1. Configuration Parsing (Lines 182-244)
def test_config_parsing():
    """Test FlockMCPConfiguration parsing."""

# 2. Transport Types (Lines 249-290)
def test_stdio_transport():
    """Test stdio transport configuration."""

def test_sse_transport():
    """Test SSE transport configuration."""

# 3. Validation (Lines 291-431)
def test_config_validation():
    """Test configuration validation rules."""

def test_invalid_config():
    """Test handling of invalid configs."""
```

---

## Phase 3: Dashboard & Polish (Week 4)

### 3.1 Expand Dashboard Service Tests (+3-4% coverage)

**File:** `tests/test_dashboard_service.py`

**Current Coverage:** 39.29% (115 missing lines)
**Target Coverage:** 80%+

**Uncovered Endpoints (Lines 170-493):**

```python
# 1. /api/artifact-types (Lines 170-181)
async def test_artifact_types_endpoint():
    """Test artifact type listing endpoint."""

# 2. /api/agents (Lines 199-210)
async def test_agents_endpoint():
    """Test agent listing endpoint."""

# 3. /api/control/publish (Lines 247-300)
async def test_control_publish_endpoint():
    """Test publishing artifacts via API."""

async def test_control_publish_validation():
    """Test publish input validation."""

# 4. /api/control/invoke (Lines 319-376)
async def test_control_invoke_endpoint():
    """Test invoking agents via API."""

async def test_control_invoke_validation():
    """Test invoke input validation."""

# 5. Theme Endpoints (Lines 449-493)
async def test_theme_endpoints():
    """Test theme CRUD operations."""
```

---

### 3.2 Expand WebSocket Tests (+1-2% coverage)

**File:** `tests/test_websocket_manager.py`

**Current Coverage:** 67.19%

**Add Edge Case Tests:**

```python
# 1. Connection Errors
async def test_websocket_connection_errors():
    """Test handling of connection failures."""

# 2. Heartbeat Timeout
async def test_heartbeat_timeout():
    """Test client disconnection on heartbeat timeout."""

# 3. Concurrent Connections
async def test_concurrent_connections():
    """Test multiple simultaneous connections."""

# 4. Message Ordering
async def test_message_ordering():
    """Test that events are delivered in order."""
```

---

## Coverage Projection

### Current State
- **Coverage:** 56.81%
- **Statements:** 4,137 total, 1,587 missed

### After Phase 1 (Foundation Repair)
- **Coverage:** 56.81% (no change - but prevents future drift)
- **Statements:** Same
- **Value:** Clean foundation for new tests

### After Phase 2 (Critical Coverage)
- **Coverage:** 71.81% - 74.81%
- **Coverage Gain:** +15-18%
- **New Tests:** 5 major test files created
- **Impact:** Most critical infrastructure tested

### After Phase 3 (Dashboard & Polish)
- **Coverage:** 75.81% - 80.81% ✅
- **Coverage Gain:** +4-6%
- **Total Gain:** +19-24%
- **Target Met:** YES (80% threshold achieved)

---

## Quick Reference: API Migration Guide

### Deprecated → Current API

| Pattern | Deprecated (Don't Use) | Current (Use This) |
|---------|----------------------|-------------------|
| Publish artifact | `publish_external(type_name, payload)` | `publish(obj)` or `publish(dict)` |
| Direct invocation | `arun(agent, input)` | `invoke(agent, input)` |
| Batch publish | N/A | `publish_many([objs])` |
| Internal call | `direct_invoke(agent, [inputs])` | `invoke(agent, input)` |

### Code Examples

```python
# ❌ DEPRECATED: publish_external
await orchestrator.publish_external(
    type_name="Movie",
    payload={"title": "Test", "runtime": 120}
)

# ✅ CURRENT: publish with dict
await orchestrator.publish({
    "type": "Movie",
    "title": "Test",
    "runtime": 120
})

# ✅ CURRENT: publish with model (preferred)
movie = Movie(title="Test", runtime=120)
await orchestrator.publish(movie)

# ❌ LEGACY: arun
outputs = await orchestrator.arun(agent, input_obj)

# ✅ CURRENT: invoke
outputs = await orchestrator.invoke(agent, input_obj)
await orchestrator.run_until_idle()

# ❌ INTERNAL: direct_invoke
await orchestrator.direct_invoke(agent.agent, [input])

# ✅ PUBLIC: invoke
await orchestrator.invoke(agent, input)
```

---

## Testing Best Practices

### 1. Always Use Fixtures

```python
# ❌ DON'T
@pytest.mark.asyncio
async def test_something():
    orchestrator = Flock()
    collector = DashboardEventCollector()
    # ...

# ✅ DO
@pytest.mark.asyncio
async def test_something(orchestrator, collector):
    # Fixtures provide consistent setup
```

### 2. Mock External Dependencies

```python
# ❌ DON'T: Use real LLM
orchestrator = Flock("openai/gpt-4o-mini")

# ✅ DO: Use mocked LLM
@pytest.mark.asyncio
async def test_with_mock(orchestrator, mock_llm):
    # All LLM calls are mocked
```

### 3. Test One Thing Per Test

```python
# ❌ DON'T: Test multiple unrelated things
async def test_everything():
    # Tests initialization
    # Tests execution
    # Tests error handling
    # Tests cleanup
    pass  # Too much!

# ✅ DO: Focused tests
async def test_initialization():
    # Only test initialization

async def test_execution():
    # Only test execution

async def test_error_handling():
    # Only test errors
```

### 4. Use Descriptive Test Names

```python
# ❌ DON'T
async def test_agent():
    pass

# ✅ DO
async def test_agent_publishes_output_after_successful_execution():
    pass
```

---

## Effort Estimates

| Phase | Tasks | Estimated Hours |
|-------|-------|----------------|
| **Phase 1: Foundation** | Fix drift, smells, fixtures | 12-16 |
| **Phase 2: Critical Coverage** | Create 5 major test files | 50-70 |
| **Phase 3: Dashboard & Polish** | Expand existing tests | 20-30 |
| **TOTAL** | | **82-116 hours** |

**Timeline:** 4 weeks (assuming 20-30 hours/week)

**Risk:** MEDIUM
- Most time in Phase 2 (new test files)
- Phase 1 has dependencies (must complete before Phase 2)
- Phase 3 can start after Phase 2 modules complete

---

## Success Metrics

### Coverage Metrics
- [ ] Overall coverage ≥ 80%
- [ ] dspy_engine.py ≥ 80%
- [ ] mcp/client.py ≥ 80%
- [ ] telemetry.py ≥ 80%
- [ ] dashboard/service.py ≥ 80%

### Quality Metrics
- [ ] Zero uses of deprecated `publish_external()`
- [ ] Zero uses of legacy `arun()`
- [ ] Zero uses of internal `direct_invoke()`
- [ ] Zero real LLM model strings in tests
- [ ] All fixtures consolidated in conftest.py
- [ ] Zero inline `Flock()` / `DashboardEventCollector()` creation

### Drift Metrics
- [ ] All tests use current API (`publish`, `invoke`)
- [ ] Production code uses current API
- [ ] Test patterns match implementation patterns

---

## Appendix: Detailed Coverage Analysis

### Modules Below 80% Coverage (23 total)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|--------------|----------|
| engines/dspy_engine.py | 25.43% | 301 | CRITICAL |
| mcp/client.py | 18.88% | 203 | CRITICAL |
| dashboard/service.py | 39.29% | 115 | HIGH |
| logging/telemetry.py | 0.00% | 85 | CRITICAL |
| mcp/config.py | 39.06% | 91 | HIGH |
| mcp/types/handlers.py | 14.05% | 84 | HIGH |
| logging/logging.py | 49.33% | 76 | MEDIUM |
| mcp/manager.py | 21.15% | 57 | HIGH |
| utility/output_utility_component.py | 41.14% | 59 | MEDIUM |
| utilities.py | 61.94% | 62 | MEDIUM |

*(Top 10 shown - see full analysis for all 23 modules)*

---

## Questions & Answers

**Q: Can I just add tests without fixing drift?**
A: No. New tests would use deprecated APIs, making the problem worse. Fix drift first.

**Q: Why not aim for 90% coverage?**
A: 80% is the GitHub pipeline requirement. Additional coverage can come later.

**Q: Can I skip Phase 1?**
A: No. Phase 1 fixes the foundation. Without it, new tests will be inconsistent and drift-prone.

**Q: What if I only have time for Phase 2?**
A: Do Phase 1 first (only 12-16 hours). Phase 2 without Phase 1 creates technical debt.

**Q: Can phases overlap?**
A: Phase 2 tests can be written in parallel after Phase 1 completes. Phase 3 can overlap with Phase 2.

---

**Generated:** 2025-10-05
**Analysis Tool:** Claude Code (Sonnet 4.5)
**Repository:** /home/ara/work/flock-flow
**Branch:** feat/quality-gates
