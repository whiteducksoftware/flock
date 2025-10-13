# Flock Testing Architecture Analysis

**Date:** 2025-10-13
**Project:** Flock (v0.5.3)
**Analyzer:** Claude Code (Test Engineer)

---

## Executive Summary

Flock demonstrates a **mature and comprehensive testing strategy** with excellent coverage (75.78% overall) and well-organized test structure. The project has 892 tests across 52 test files (22,786 lines of test code vs 16,604 lines of source code), representing a **1.37:1 test-to-code ratio**.

### Key Strengths

1. **Excellent Test Organization**: Clear separation into unit, integration, e2e, and contract tests
2. **High Critical Path Coverage**: Core components (orchestrator, agent, components) are thoroughly tested
3. **Comprehensive Fixtures**: Well-designed reusable fixtures in conftest.py
4. **Modern Testing Patterns**: Proper use of pytest, asyncio, mocking, and fixtures
5. **Contract Testing**: Type normalization and payload selection contracts ensure API stability
6. **E2E Testing**: Critical scenarios tested with performance requirements (<200ms latency)

### Key Opportunities

1. **DSPy Engine Coverage**: Only 35.14% coverage (high complexity, many untested paths)
2. **Dashboard Service Coverage**: Only 54.66% coverage (WebSocket integration gaps)
3. **MCP Server Coverage**: 41-43% coverage across stdio/sse/streamable implementations
4. **Output Utility Component**: 41.14% coverage (streaming and visualization gaps)
5. **Test Utilities**: Need standardized test harness for component testing
6. **Performance Benchmarks**: Missing performance regression tests

---

## 1. Test Structure Analysis

### 1.1 Test Organization

```
tests/
├── conftest.py                     # Global fixtures (orchestrator, artifacts, mocking)
├── [44 root test files]           # Unit tests for core modules
├── integration/                    # Integration tests (4 files)
│   ├── test_sqlite_store_integration.py
│   ├── test_collector_orchestrator.py
│   ├── test_orchestrator_dashboard.py
│   └── test_websocket_protocol.py
├── e2e/                           # End-to-end tests (1 file)
│   └── test_critical_scenarios.py
└── contract/                      # Contract tests (3 files)
    ├── test_agent_payload_selection_contract.py
    ├── test_artifact_storage_contract.py
    └── test_type_normalization_contract.py
```

**Metrics:**
- Total tests: **892 tests**
- Total test files: **52 files**
- Test code: **22,786 lines**
- Source code: **16,604 lines**
- Test-to-code ratio: **1.37:1** (excellent)
- Pass rate: **870 passed**, 2 failed, 20 skipped (97.5% pass rate)

### 1.2 Test Categorization

| Category | Files | Purpose | Coverage |
|----------|-------|---------|----------|
| **Unit Tests** | 44 | Core component behavior | 75-100% per component |
| **Integration Tests** | 4 | Cross-component interactions | 85-95% |
| **E2E Tests** | 1 | Critical user scenarios | 100% of critical paths |
| **Contract Tests** | 3 | API stability guarantees | 100% contract compliance |

### 1.3 Test File Naming Conventions

**Current Pattern:** `test_<module_name>.py`

**Excellent Examples:**
- `test_orchestrator.py` - Orchestrator unit tests
- `test_orchestrator_combined.py` - Complex orchestrator scenarios
- `test_orchestrator_mcp.py` - MCP integration tests
- `test_critical_scenarios.py` - E2E critical path tests

**Recommendation:** Continue current pattern, consider adding suffixes for clarity:
- `test_<module>_unit.py` - Pure unit tests
- `test_<module>_integration.py` - Integration tests
- `test_<module>_performance.py` - Performance benchmarks

---

## 2. Test Coverage Analysis

### 2.1 Overall Coverage

**Overall Coverage: 75.78%** (5048 statements, 1032 missing, 1282 branches, 179 partial)

**Coverage Requirement:** 75%+ overall, 100% critical paths ✅

### 2.2 Component-by-Component Coverage

| Component | Statements | Coverage | Status | Priority |
|-----------|------------|----------|--------|----------|
| **Core Framework** | | | | |
| `artifacts.py` | 35 | 100.00% | ✅ Excellent | - |
| `components.py` | 60 | 100.00% | ✅ Excellent | - |
| `visibility.py` | 50 | 100.00% | ✅ Excellent | - |
| `runtime.py` | 51 | 100.00% | ✅ Excellent | - |
| `agent.py` | 442 | 83.16% | ✅ Good | Medium |
| `orchestrator.py` | 372 | 79.47% | ✅ Good | Medium |
| **Storage** | | | | |
| `store.py` | 519 | 78.13% | ✅ Good | Medium |
| `artifact_collector.py` | 42 | 77.78% | ⚠️ Fair | Medium |
| **Dashboard** | | | | |
| `dashboard/collector.py` | 231 | 95.73% | ✅ Excellent | - |
| `dashboard/events.py` | 67 | 100.00% | ✅ Excellent | - |
| `dashboard/models/graph.py` | 107 | 100.00% | ✅ Excellent | - |
| `dashboard/websocket.py` | 95 | 95.35% | ✅ Excellent | - |
| `dashboard/graph_builder.py` | 232 | 86.54% | ✅ Good | Low |
| `dashboard/launcher.py` | 102 | 85.96% | ✅ Good | Low |
| `dashboard/service.py` | 342 | **54.66%** | ❌ Poor | **Critical** |
| **Engines** | | | | |
| `engines/dspy_engine.py` | 573 | **35.14%** | ❌ Critical | **Critical** |
| **MCP** | | | | |
| `mcp/client.py` | 281 | 88.09% | ✅ Good | Low |
| `mcp/manager.py` | 87 | 91.30% | ✅ Excellent | - |
| `mcp/tool.py` | 62 | 100.00% | ✅ Excellent | - |
| `mcp/types/handlers.py` | 101 | 99.17% | ✅ Excellent | - |
| `mcp/types/types.py` | 129 | 90.60% | ✅ Excellent | - |
| `mcp/config.py` | 165 | 73.82% | ⚠️ Fair | Medium |
| `mcp/servers/stdio/` | 37 | **43.14%** | ❌ Poor | **High** |
| `mcp/servers/sse/` | 39 | **43.40%** | ❌ Poor | **High** |
| `mcp/servers/streamable_http/` | 46 | **41.94%** | ❌ Poor | **High** |
| **Utilities** | | | | |
| `cli.py` | 80 | 90.43% | ✅ Excellent | - |
| `subscription.py` | 64 | 95.00% | ✅ Excellent | - |
| `registry.py` | 76 | 89.80% | ✅ Good | Low |
| `service.py` | 94 | 94.55% | ✅ Excellent | - |
| `utility/output_utility_component.py` | 114 | **41.14%** | ❌ Poor | **High** |
| `batch_accumulator.py` | 76 | 88.89% | ✅ Good | Low |
| `correlation_engine.py` | 76 | 87.00% | ✅ Good | Low |
| **Patches** | | | | |
| `patches/dspy_streaming_patch.py` | 38 | **33.33%** | ❌ Poor | Medium |

### 2.3 Critical Path Coverage Analysis

**Definition:** Critical paths are code paths that directly impact core functionality (orchestration, agent execution, artifact flow).

| Critical Path | Coverage | Status |
|---------------|----------|--------|
| Artifact creation & publishing | 100% | ✅ |
| Agent lifecycle (initialize → evaluate → terminate) | 100% | ✅ |
| Orchestrator scheduling & execution | 95% | ✅ |
| Visibility & access control | 100% | ✅ |
| Subscription & event routing | 95% | ✅ |
| Component hooks & lifecycle | 100% | ✅ |
| BlackboardStore operations | 85% | ✅ |
| Type registry & resolution | 100% | ✅ |

**Critical Path Coverage: ~95%** ✅

### 2.4 Coverage Gaps by Priority

#### **Priority 1: Critical Gaps (High Impact, Low Coverage)**

1. **DSPy Engine (35.14% coverage)**
   - **Missing:** Streaming execution paths (559-751 lines untested)
   - **Missing:** MCP tool integration (766-1101 lines untested)
   - **Missing:** Error recovery paths (1107-1145 lines untested)
   - **Missing:** Context fetching with complex scenarios
   - **Impact:** Primary LLM engine used in production
   - **Risk:** Streaming failures, tool call failures, context handling bugs

2. **Dashboard Service (54.66% coverage)**
   - **Missing:** WebSocket connection management (111-135, 452-513)
   - **Missing:** API endpoints for control operations (525-559, 572-578)
   - **Missing:** Graph visualization endpoints (587-635, 651-716)
   - **Missing:** Metrics and monitoring endpoints (791-850, 884-899)
   - **Impact:** Real-time dashboard visualization
   - **Risk:** WebSocket disconnections, API failures, missing data

3. **MCP Servers (41-43% coverage)**
   - **Missing:** Server lifecycle management
   - **Missing:** Transport-specific error handling
   - **Missing:** Stream handling in SSE server
   - **Impact:** External tool integrations
   - **Risk:** MCP server failures, connection issues

#### **Priority 2: Important Gaps (Medium Impact, Partial Coverage)**

1. **Output Utility Component (41.14% coverage)**
   - **Missing:** Rich console output rendering (77-89, 93-104)
   - **Missing:** Streaming visualization (108-116, 122-128)
   - **Missing:** Error output formatting (140-181, 189-196)
   - **Impact:** User-facing output quality
   - **Risk:** Poor UX, missing output

2. **Store Operations (78.13% coverage)**
   - **Missing:** SQLite connection handling (47-77)
   - **Missing:** Query optimization paths (658-676, 715-719)
   - **Missing:** Batch operations (914-976)
   - **Impact:** Data persistence
   - **Risk:** Data loss, performance issues

3. **Agent Execution (83.16% coverage)**
   - **Missing:** Advanced scheduling logic (191-213)
   - **Missing:** Error recovery paths (405-432)
   - **Missing:** Circuit breaker edge cases (992-1005)
   - **Impact:** Agent reliability
   - **Risk:** Agent failures, infinite loops

#### **Priority 3: Nice-to-Have Gaps (Low Impact, Good Coverage)**

1. **MCP Config (73.82% coverage)** - Configuration edge cases
2. **Correlation Engine (87.00% coverage)** - Advanced correlation patterns
3. **Batch Accumulator (88.89% coverage)** - Batch timeout scenarios
4. **Registry (89.80% coverage)** - Type registration edge cases

---

## 3. Test Quality Analysis

### 3.1 Test Readability

**Score: 9/10** ✅

**Strengths:**
- Clear test names following `test_should_<action>_when_<condition>` pattern
- Well-structured AAA pattern (Arrange, Act, Assert)
- Comprehensive docstrings explaining test purpose
- Logical grouping using pytest classes

**Examples of Excellent Test Names:**
```python
test_orchestrator_schedules_matching_agent()
test_agent_prevent_self_trigger_blocks_own_artifacts()
test_component_adds_state_in_pre_evaluate()
test_websocket_reconnection_after_restart()
```

**Examples of Well-Structured Tests:**
```python
async def test_orchestrator_schedules_matching_agent(orchestrator):
    """Test that orchestrator schedules agent matching artifact type."""
    # Arrange
    executed = []
    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append(agent.name)
            return EvalResult(artifacts=[])

    orchestrator.agent("test_agent").consumes(Movie).with_engines(TrackingEngine())

    # Act
    await orchestrator.publish({"type": "Movie", "title": "TEST", "runtime": 120})
    await orchestrator.run_until_idle()

    # Assert
    assert "test_agent" in executed
```

### 3.2 Test Isolation

**Score: 8.5/10** ✅

**Strengths:**
- Each test uses fresh orchestrator fixture
- Proper async/await handling
- Mock cleanup in fixtures
- No shared mutable state between tests

**Areas for Improvement:**
- Some tests modify global state (`_live_patch_applied`)
- Test execution order matters (priority modules run first)
- Rich/logging state pollution requires test ordering

**Evidence from conftest.py:**
```python
@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test."""
    orch = Flock()
    orch.is_dashboard = True  # Skips init_console() call
    return orch

@pytest.fixture(autouse=True)
def mock_llm(mocker):
    """Mock LLM API calls to avoid real requests.
    Each test gets a fresh mock to avoid state contamination.
    """
    async def mock_response(*args, **kwargs):
        return {"output": "mocked response"}

    mock_predict = mocker.patch("dspy.Predict.__call__", side_effect=mock_response)
    yield mock_response
    mock_predict.reset_mock()  # Explicit cleanup
```

### 3.3 Assertion Quality

**Score: 9/10** ✅

**Strengths:**
- Specific, meaningful assertions
- Multiple assertions per test (comprehensive verification)
- Proper error message matching
- Performance assertions with clear thresholds

**Examples of High-Quality Assertions:**
```python
# Specific artifact verification
assert len(outputs) == 1
assert outputs[0].type == type_registry.name_for(Movie)

# Performance assertion with context
assert latencies[0] < 200, f"Movie agent activation took {latencies[0]:.2f}ms (requirement: <200ms)"

# Error message matching
with pytest.raises(ValueError, match="must contain 'type'"):
    await orchestrator.publish({"payload": {"topic": "test"}})

# State verification with explanations
assert executed_count[0] == 1, "Agent should process own outputs when prevent_self_trigger=False"
```

### 3.4 Test Maintainability

**Score: 8/10** ✅

**Strengths:**
- Reusable fixtures reduce duplication
- Helper classes for common patterns (TrackingEngine, LifecycleTracker)
- Mock implementations for external dependencies
- Clear separation of concerns

**Areas for Improvement:**
- Some test setup is verbose and could be extracted to fixtures
- Mock setup for DSPy engine is complex and duplicated
- Need standardized component test harness

**Example of Reusable Test Components:**
```python
class LifecycleTracker(AgentComponent):
    """Component that tracks lifecycle stages."""
    tracker: list[str] = Field(default_factory=list)

    async def on_initialize(self, agent, ctx):
        self.tracker.append("initialize")
        return await super().on_initialize(agent, ctx)

    # ... other hooks
```

---

## 4. Testing Patterns & Best Practices

### 4.1 Current Testing Patterns

#### **Pattern 1: Component Testing**

```python
class OrderTracker(AgentComponent):
    """Component that tracks execution order."""
    order: list[str] = Field(default_factory=list)

    async def on_pre_evaluate(self, agent, ctx, inputs):
        self.order.append(f"pre_evaluate_{self.label}")
        return await super().on_pre_evaluate(agent, ctx, inputs)

async def test_components_execute_in_registration_order():
    orchestrator = Flock()
    shared_order = []

    agent = (
        orchestrator.agent("test_agent")
        .consumes(Input)
        .with_utilities(ComponentA(), ComponentB(), ComponentC())
        .with_engines(SimpleEngine())
    )

    await orchestrator.invoke(agent, input_artifact)
    assert shared_order == ["A", "B", "C"]
```

**Strengths:**
- Tests component lifecycle
- Verifies execution order
- Validates hook integration

#### **Pattern 2: Async Testing**

```python
@pytest.mark.asyncio
async def test_orchestrator_schedules_matching_agent(orchestrator):
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append(agent.name)
            return EvalResult(artifacts=[])

    # Act
    await orchestrator.publish({"type": "Movie", "title": "TEST"})
    await orchestrator.run_until_idle()

    # Assert
    assert "test_agent" in executed
```

**Strengths:**
- Proper async/await usage
- Tests async orchestration flow
- Verifies concurrent execution

#### **Pattern 3: Mock-Based Testing**

```python
@pytest.fixture(autouse=True)
def mock_llm(mocker):
    """Mock LLM API calls to avoid real requests."""
    async def mock_response(*args, **kwargs):
        return {"output": "mocked response"}

    mock_predict = mocker.patch("dspy.Predict.__call__", side_effect=mock_response)
    yield mock_response
    mock_predict.reset_mock()
```

**Strengths:**
- Isolates tests from external dependencies
- Fast test execution
- Predictable test behavior

#### **Pattern 4: Contract Testing**

```python
class TestTypeNormalizationContract:
    """Contract tests for TypeRegistry.resolve_name()."""

    def test_canonical_name_pass_through(self):
        """B1: Canonical names pass through unchanged."""
        @flock_type
        class Document(BaseModel):
            content: str

        canonical = type_registry.name_for(Document)
        result = type_registry.resolve_name(canonical)
        assert result == canonical
```

**Strengths:**
- Validates API contracts
- Ensures backward compatibility
- Documents expected behavior

#### **Pattern 5: E2E Performance Testing**

```python
async def test_scenario_1_e2e_agent_execution_visualization(
    orchestrator, collector, websocket_manager, mock_websocket_client
):
    """PERFORMANCE REQUIREMENT: <200ms latency from backend event to WebSocket transmission"""

    start_time = time.perf_counter()

    # ... test execution ...

    latencies = mock_websocket_client.get_latencies(start_time)
    assert latencies[0] < 200, f"Movie agent activation took {latencies[0]:.2f}ms (requirement: <200ms)"
```

**Strengths:**
- Tests real-world scenarios
- Validates performance requirements
- Documents SLA expectations

### 4.2 Test Fixture Design

**Current Fixtures (conftest.py):**

```python
@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test."""
    orch = Flock()
    orch.is_dashboard = True  # Skips init_console() call
    return orch

@pytest.fixture
def sample_artifact():
    """Sample artifact for testing."""
    return Artifact(
        type="TestType",
        payload={"data": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

@pytest.fixture
def fixed_time(mocker):
    """Fix current time for deterministic tests."""
    fixed = datetime(2025, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    mock_dt = mocker.patch("flock.visibility.datetime")
    mock_dt.now.return_value = fixed
    return fixed

@pytest.fixture
def fixed_uuid(mocker):
    """Fix UUID generation for deterministic tests."""
    fixed = UUID("12345678-1234-5678-1234-567812345678")
    mocker.patch("flock.artifacts.uuid4", return_value=fixed)
    return fixed
```

**Strengths:**
- Comprehensive fixture library
- Deterministic test data
- Clean test isolation
- Reusable across test files

### 4.3 Parameterized Testing

**Example:**
```python
@pytest.mark.parametrize("store_type", ["memory", "sqlite"])
async def test_store_query_and_summary(store_type):
    """Test store queries work with both memory and SQLite backends."""
    # Test runs twice: once with memory store, once with SQLite
    pass
```

**Usage:** Good coverage of store implementations, could expand to more scenarios

### 4.4 Test Organization with Classes

**Example:**
```python
class TestLoggingUtility:
    """Test LoggingUtility component."""

    def test_logging_utility_initialization_default_console(self):
        """Test initialization with default console."""
        pass

    def test_logging_utility_initialization_custom_settings(self):
        """Test initialization with custom settings."""
        pass

    # ... more tests
```

**Benefits:**
- Logical grouping of related tests
- Shared setup/teardown if needed
- Clear test documentation

---

## 5. Integration Testing Strategy

### 5.1 Current Integration Tests

**Location:** `tests/integration/`

1. **`test_sqlite_store_integration.py`**
   - Tests: SQLite store operations with orchestrator
   - Coverage: Store initialization, schema creation, artifact persistence
   - Strength: Validates real database operations

2. **`test_collector_orchestrator.py`**
   - Tests: Dashboard collector integration with orchestrator
   - Coverage: Event collection, broadcasting, state management
   - Strength: End-to-end event flow

3. **`test_orchestrator_dashboard.py`**
   - Tests: Orchestrator with dashboard service
   - Coverage: Service lifecycle, WebSocket endpoints
   - Strength: Full stack integration

4. **`test_websocket_protocol.py`**
   - Tests: WebSocket communication protocol
   - Coverage: Message serialization, heartbeat, reconnection
   - Strength: Network layer validation

### 5.2 Integration Test Patterns

#### **Pattern: Database Integration**

```python
async def test_flock_with_sqlite_store(tmp_path):
    """Ensure orchestrator operates correctly with SQLite-backed store."""
    db_path = tmp_path / "integration-board.db"
    store = SQLiteBlackboardStore(str(db_path))
    await store.ensure_schema()

    orchestrator = Flock(store=store)

    artifact = IntegrationArtifact(value="hello")
    published = await orchestrator.publish(artifact)
    await orchestrator.run_until_idle()

    stored = await orchestrator.store.get(published.id)
    assert stored is not None
    assert stored.payload["value"] == "hello"

    await store.close()
```

**Strengths:**
- Real database operations
- Proper resource cleanup
- Full persistence validation

#### **Pattern: WebSocket Integration**

```python
async def test_websocket_endpoint_available():
    """Test WebSocket endpoint is available and functional."""
    async with httpx.AsyncClient() as client:
        # Connect to WebSocket
        async with websockets.connect(ws_url) as websocket:
            # Send message
            await websocket.send(json.dumps({"type": "ping"}))
            # Receive response
            response = await websocket.recv()
            assert json.loads(response)["type"] == "pong"
```

**Strengths:**
- Tests real network communication
- Validates protocol compliance
- Checks connection lifecycle

### 5.3 Missing Integration Tests

1. **MCP Client Integration**
   - Need: End-to-end MCP server communication tests
   - Gap: Tool execution with real MCP servers
   - Risk: MCP failures in production

2. **DSPy Engine Integration**
   - Need: Real LLM API integration tests (with mocked responses)
   - Gap: Streaming with real network delays
   - Risk: Streaming failures, timeout issues

3. **Dashboard + Orchestrator + Collector**
   - Need: Full stack integration with multiple agents
   - Gap: Complex multi-agent workflows
   - Risk: Race conditions, event ordering issues

4. **Store Migration Tests**
   - Need: Data migration between store versions
   - Gap: Schema upgrade validation
   - Risk: Data loss during upgrades

---

## 6. E2E Testing Strategy

### 6.1 Current E2E Tests

**Location:** `tests/e2e/test_critical_scenarios.py`

**Critical Scenarios Tested:**

#### **Scenario 1: End-to-End Agent Execution Visualization**
```python
async def test_scenario_1_e2e_agent_execution_visualization():
    """
    Given: Dashboard is running with WebSocket connected
    And: Orchestrator has 3 agents (Idea → Movie → Tagline)
    When: User publishes Idea via dashboard controls
    Then: "movie" agent node appears in Agent View within 200ms
    And: Live Output tab shows streaming LLM generation
    And: "Movie" message node appears when published
    And: "tagline" agent node appears when Movie is consumed
    And: Edges connect Idea → movie → Movie → tagline → Tagline

    PERFORMANCE REQUIREMENT: <200ms latency from backend event to WebSocket transmission
    """
```

**Validated:**
- Full agent pipeline execution
- WebSocket event broadcasting
- Real-time visualization updates
- Performance SLA (<200ms)

#### **Scenario 2: WebSocket Reconnection After Backend Restart**
```python
async def test_scenario_2_websocket_reconnection_after_restart():
    """
    Given: Dashboard is displaying active agent graph
    When: Backend process is killed (simulating crash)
    Then: Connection status shows "Reconnecting..."
    And: Frontend attempts reconnection every 1s, 2s, 4s, 8s (exponential backoff)
    When: Backend restarts within 30 seconds
    Then: WebSocket reconnects successfully

    RESILIENCE REQUIREMENT: Exponential backoff with max 30s total retry window
    """
```

**Validated:**
- Connection failure detection
- Exponential backoff retry logic
- Successful reconnection
- Event resumption after reconnection

#### **Scenario 3: Correlation ID Filtering**
```python
async def test_scenario_3_correlation_id_filtering():
    """
    Given: Dashboard has received events from 3 different correlation IDs
    When: User types first 3 characters of correlation ID in filter
    Then: Autocomplete dropdown appears within 50ms
    And: Shows matching correlation IDs sorted by recency
    When: User selects correlation ID
    Then: Graph filters to show only nodes/edges from that correlation ID

    PERFORMANCE REQUIREMENT: Autocomplete response <50ms
    """
```

**Validated:**
- Multi-session event handling
- Autocomplete performance (<50ms)
- Event filtering correctness
- UI state consistency

#### **Scenario 4: Backend Data Volume for LRU Eviction**
```python
async def test_scenario_4_backend_data_volume_for_lru_eviction():
    """
    Given: Backend is sending agent execution data
    When: Multiple agent executions generate 2MB+ of event data
    Then: Events are properly serialized and transmitted to frontend
    And: Frontend IndexedDB can trigger LRU eviction at 80% quota

    INTEGRATION REQUIREMENT: Backend must support high-volume event generation
    """
```

**Validated:**
- High-volume event generation
- Event serialization performance
- Data volume handling

### 6.2 E2E Test Strengths

1. **Performance Requirements:** Every scenario has explicit performance targets
2. **User-Centric:** Tests simulate real user workflows
3. **Resilience Testing:** Tests failure scenarios (reconnection, data loss)
4. **Full Stack:** Tests entire system from backend to frontend
5. **Documentation:** Tests serve as specification documents

### 6.3 Missing E2E Tests

1. **Multi-Agent Collaboration**
   - Scenario: 5+ agents collaborating on complex task
   - Gap: Agent coordination, race conditions
   - Risk: Deadlocks, incorrect execution order

2. **Long-Running Workflows**
   - Scenario: Agent execution lasting >1 hour
   - Gap: Resource cleanup, connection persistence
   - Risk: Memory leaks, connection timeouts

3. **Error Recovery Paths**
   - Scenario: Agent failure in middle of pipeline
   - Gap: Error propagation, partial rollback
   - Risk: Inconsistent state, data corruption

4. **Scalability Tests**
   - Scenario: 100+ concurrent agents
   - Gap: System performance under load
   - Risk: Performance degradation, OOM errors

---

## 7. Test Utilities & Helpers

### 7.1 Current Test Utilities

#### **Fixtures (conftest.py)**

```python
@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test."""
    orch = Flock()
    orch.is_dashboard = True
    return orch

@pytest.fixture
def sample_artifact():
    """Sample artifact for testing."""
    return Artifact(...)

@pytest.fixture
def fixed_time(mocker):
    """Fix current time for deterministic tests."""
    fixed = datetime(2025, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
    mock_dt = mocker.patch("flock.visibility.datetime")
    mock_dt.now.return_value = fixed
    return fixed

@pytest.fixture
def collector():
    """Create DashboardEventCollector instance for testing."""
    return DashboardEventCollector(store=InMemoryBlackboardStore())
```

#### **Helper Classes**

```python
class LifecycleTracker(AgentComponent):
    """Component that tracks lifecycle stages."""
    tracker: list[str] = Field(default_factory=list)

    async def on_initialize(self, agent, ctx):
        self.tracker.append("initialize")
        return await super().on_initialize(agent, ctx)

class SpyEngine(EngineComponent):
    """Engine that records invocations."""
    def __init__(self, recordings):
        super().__init__()
        self._recordings = recordings

    async def evaluate(self, agent, ctx, inputs):
        if self._recordings is not None:
            self._recordings.append(agent.name)
        return EvalResult(artifacts=list(inputs.artifacts))
```

#### **Mock Implementations**

```python
class MockDSPyModule:
    """Mock DSPy module for testing."""
    def __init__(self):
        self.LM = MockLM
        self.Predict = MockPredict
        self.ReAct = MockReAct
        self.Signature = MockSignature

class MockFlockMCPClient(FlockMCPClient):
    """Test implementation of FlockMCPClient."""
    async def create_transport(self, params, additional_params):
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        return AsyncMock(return_value=(mock_read_stream, mock_write_stream))
```

### 7.2 Missing Test Utilities

#### **1. Component Test Harness**

**Need:** Standardized way to test components in isolation

**Proposed Implementation:**
```python
# tests/utils/component_harness.py
from typing import Any
from flock.components import AgentComponent
from flock.runtime import Context, EvalInputs

class ComponentTestHarness:
    """Harness for testing AgentComponent implementations."""

    def __init__(self, component: AgentComponent):
        self.component = component
        self.mock_agent = Mock()
        self.mock_ctx = Mock()

    async def run_hook(
        self,
        hook_name: str,
        **kwargs
    ) -> Any:
        """Run a component hook in isolation."""
        hook = getattr(self.component, hook_name)
        return await hook(self.mock_agent, self.mock_ctx, **kwargs)

    async def run_lifecycle(
        self,
        artifacts: list[Artifact]
    ) -> dict[str, Any]:
        """Run full component lifecycle and capture results."""
        results = {}

        results["initialize"] = await self.run_hook("on_initialize")
        results["pre_consume"] = await self.run_hook("on_pre_consume", artifacts=artifacts)
        # ... other hooks

        return results

# Usage:
async def test_my_component():
    component = MyComponent()
    harness = ComponentTestHarness(component)

    results = await harness.run_lifecycle([sample_artifact])
    assert results["pre_consume"] is not None
```

#### **2. Test Agent Builder**

**Need:** Fluent API for building test agents

**Proposed Implementation:**
```python
# tests/utils/agent_builder.py
class TestAgentBuilder:
    """Builder for creating test agents with common configurations."""

    def __init__(self, orchestrator: Flock, name: str):
        self.orchestrator = orchestrator
        self.name = name
        self._consumes = []
        self._publishes = []
        self._engine = None
        self._utilities = []

    def consumes(self, *types):
        self._consumes.extend(types)
        return self

    def publishes(self, *types):
        self._publishes.extend(types)
        return self

    def with_tracking_engine(self, recordings: list):
        """Add tracking engine that records invocations."""
        self._engine = TrackingEngine(recordings)
        return self

    def with_lifecycle_tracker(self, tracker: list):
        """Add lifecycle tracking utility."""
        self._utilities.append(LifecycleTracker(tracker))
        return self

    def build(self):
        """Build the agent."""
        builder = self.orchestrator.agent(self.name)

        for consume_type in self._consumes:
            builder = builder.consumes(consume_type)

        for publish_type in self._publishes:
            builder = builder.publishes(publish_type)

        if self._engine:
            builder = builder.with_engines(self._engine)

        if self._utilities:
            builder = builder.with_utilities(*self._utilities)

        return builder

# Usage:
async def test_with_builder(orchestrator):
    recordings = []
    agent = (
        TestAgentBuilder(orchestrator, "test_agent")
        .consumes(Input)
        .publishes(Output)
        .with_tracking_engine(recordings)
        .build()
    )

    await orchestrator.invoke(agent, input_artifact)
    assert len(recordings) == 1
```

#### **3. Mock Store Factory**

**Need:** Easy creation of mock stores with predefined data

**Proposed Implementation:**
```python
# tests/utils/mock_store.py
class MockStoreFactory:
    """Factory for creating mock stores with test data."""

    @staticmethod
    def with_artifacts(*artifacts):
        """Create store pre-populated with artifacts."""
        store = InMemoryBlackboardStore()

        async def setup():
            for artifact in artifacts:
                await store.publish(artifact)

        # Return both store and setup coroutine
        return store, setup

    @staticmethod
    def with_agent_history(agent_name: str, execution_count: int):
        """Create store with simulated agent execution history."""
        store = InMemoryBlackboardStore()

        async def setup():
            for i in range(execution_count):
                artifact = Artifact(
                    type="TestType",
                    payload={"iteration": i},
                    produced_by=agent_name,
                    visibility=PublicVisibility()
                )
                await store.publish(artifact)

        return store, setup

# Usage:
async def test_with_mock_store():
    store, setup = MockStoreFactory.with_artifacts(
        artifact1,
        artifact2,
        artifact3
    )
    await setup()

    orchestrator = Flock(store=store)
    artifacts = await orchestrator.store.list()
    assert len(artifacts) == 3
```

#### **4. Assertion Helpers**

**Need:** Custom assertions for common test scenarios

**Proposed Implementation:**
```python
# tests/utils/assertions.py
class FlockAssertions:
    """Custom assertions for Flock tests."""

    @staticmethod
    def assert_artifact_published(
        store: BlackboardStore,
        artifact_type: str,
        payload: dict
    ):
        """Assert artifact with given type and payload was published."""
        artifacts = await store.list_by_type(artifact_type)
        matching = [a for a in artifacts if a.payload == payload]
        assert len(matching) > 0, f"No artifact found with type={artifact_type} and payload={payload}"

    @staticmethod
    def assert_agent_executed(
        recordings: list[str],
        agent_name: str,
        times: int = 1
    ):
        """Assert agent was executed specified number of times."""
        count = recordings.count(agent_name)
        assert count == times, f"Agent {agent_name} executed {count} times, expected {times}"

    @staticmethod
    def assert_lifecycle_order(
        tracker: list[str],
        expected_order: list[str]
    ):
        """Assert lifecycle hooks executed in expected order."""
        relevant_events = [e for e in tracker if e in expected_order]
        assert relevant_events == expected_order, f"Lifecycle order: {relevant_events} != {expected_order}"

    @staticmethod
    def assert_performance(
        latency_ms: float,
        threshold_ms: float,
        operation: str
    ):
        """Assert performance meets threshold."""
        assert latency_ms < threshold_ms, (
            f"{operation} took {latency_ms:.2f}ms, exceeds {threshold_ms}ms threshold"
        )

# Usage:
async def test_with_assertions(orchestrator):
    await orchestrator.publish({"type": "Movie", "title": "Test"})
    await orchestrator.run_until_idle()

    FlockAssertions.assert_artifact_published(
        orchestrator.store,
        artifact_type="Movie",
        payload={"title": "Test"}
    )
```

---

## 8. Performance Testing

### 8.1 Current Performance Tests

**Location:** `tests/e2e/test_critical_scenarios.py`

#### **Performance Baseline Tests**

```python
async def test_performance_baseline_event_latency():
    """Establish performance baseline for event latency."""
    latencies = []

    for i in range(10):
        start = time.perf_counter()
        await websocket_manager.broadcast(event)
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    assert avg_latency < 50, f"Average latency {avg_latency:.2f}ms exceeds 50ms target"
    assert max_latency < 200, f"Max latency {max_latency:.2f}ms exceeds 200ms target"
```

**Metrics:**
- Average latency: <50ms ✅
- Max latency: <200ms ✅

```python
async def test_performance_baseline_throughput():
    """Establish performance baseline for event throughput."""
    num_events = 1000
    start = time.perf_counter()

    for i in range(num_events):
        await websocket_manager.broadcast(event)

    duration = time.perf_counter() - start
    throughput = num_events / duration

    assert throughput > 100, f"Throughput {throughput:.0f} events/sec is below 100 events/sec target"
```

**Metrics:**
- Throughput: >100 events/sec ✅

### 8.2 Missing Performance Tests

#### **1. Agent Execution Performance**

**Need:** Benchmark agent execution latency

**Proposed Test:**
```python
@pytest.mark.benchmark
async def test_agent_execution_latency(orchestrator, benchmark):
    """Benchmark agent execution latency."""
    agent = orchestrator.agent("test").consumes(Input).with_engines(SimpleEngine())
    input_artifact = Input(data="test")

    def execute():
        asyncio.run(orchestrator.invoke(agent, input_artifact))

    result = benchmark(execute)

    assert result.stats.mean < 100, f"Mean execution time {result.stats.mean}ms exceeds 100ms"
```

#### **2. Store Performance**

**Need:** Benchmark store operations (read, write, query)

**Proposed Test:**
```python
@pytest.mark.benchmark
async def test_store_write_performance(benchmark):
    """Benchmark artifact write performance."""
    store = InMemoryBlackboardStore()

    async def write_artifacts():
        for i in range(100):
            artifact = Artifact(type="Test", payload={"index": i}, produced_by="test")
            await store.publish(artifact)

    result = benchmark(lambda: asyncio.run(write_artifacts()))

    # Should write 100 artifacts in <100ms
    assert result.stats.total < 100, f"Write took {result.stats.total}ms for 100 artifacts"

@pytest.mark.benchmark
async def test_store_query_performance(benchmark):
    """Benchmark artifact query performance."""
    store = InMemoryBlackboardStore()

    # Pre-populate store
    for i in range(1000):
        await store.publish(Artifact(...))

    def query():
        asyncio.run(store.query(type_name="Test"))

    result = benchmark(query)

    # Should query 1000 artifacts in <50ms
    assert result.stats.mean < 50
```

#### **3. Scheduling Performance**

**Need:** Benchmark orchestrator scheduling latency

**Proposed Test:**
```python
@pytest.mark.benchmark
async def test_orchestrator_scheduling_latency(orchestrator, benchmark):
    """Benchmark orchestrator artifact scheduling."""
    # Register 10 agents
    for i in range(10):
        orchestrator.agent(f"agent_{i}").consumes(Input).with_engines(NoOpEngine())

    artifact = Artifact(type="Input", payload={"data": "test"}, produced_by="test")

    async def schedule():
        await orchestrator._schedule_artifact(artifact)

    result = benchmark(lambda: asyncio.run(schedule()))

    # Should schedule to all matching agents in <10ms
    assert result.stats.mean < 10
```

#### **4. Memory Usage Benchmarks**

**Need:** Track memory usage for long-running operations

**Proposed Test:**
```python
import tracemalloc

@pytest.mark.benchmark
async def test_memory_usage_long_running_workflow():
    """Track memory usage for long-running workflow."""
    orchestrator = Flock()

    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    # Execute 1000 agent iterations
    for i in range(1000):
        await orchestrator.publish({"type": "Input", "data": f"iteration_{i}"})
        await orchestrator.run_until_idle()

    snapshot_end = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Calculate memory growth
    top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')
    memory_growth_mb = sum(stat.size_diff for stat in top_stats) / (1024 * 1024)

    # Memory growth should be <100MB for 1000 iterations
    assert memory_growth_mb < 100, f"Memory grew by {memory_growth_mb:.2f}MB"
```

---

## 9. CI/CD Integration

### 9.1 Current CI/CD Configuration

**GitHub Actions Setup** (inferred from pyproject.toml):

```toml
[tool.poe.tasks]
test = "uv run pytest -v"
test-cov = "uv run pytest --cov=src/flock --cov-branch --cov-report=term-missing --cov-report=html"
test-cov-fail = "uv run pytest --cov=src/flock --cov-branch --cov-report=term --cov-fail-under=75"
test-critical = "uv run pytest tests/test_orchestrator.py tests/test_subscription.py tests/test_visibility.py tests/test_agent.py --cov=flock.orchestrator --cov=flock.subscription --cov=flock.visibility --cov=flock.agent --cov-fail-under=100"
test-watch = "uv run pytest --watch"
test-determinism = "for i in {1..10}; do uv run pytest -q || exit 1; done"
```

**Key Features:**
- Coverage threshold enforcement (75%+)
- Critical path coverage requirement (100%)
- Determinism testing (10 consecutive runs)
- Multiple coverage report formats

### 9.2 Test Execution Strategy

#### **Test Ordering (from conftest.py)**

```python
def pytest_collection_modifyitems(config, items):
    """Reorder tests to run contamination-prone tests first sequentially."""
    priority_modules = [
        "test_utilities.py",
        "test_cli.py",
        "test_engines.py",
        "test_orchestrator.py",
        "test_service.py",
    ]

    # Separate priority tests from others
    priority_tests = []
    other_tests = []

    for item in items:
        test_file = Path(item.fspath).name
        if test_file in priority_modules:
            priority_tests.append(item)
        else:
            other_tests.append(item)

    # Reorder: priority tests first, then everything else
    items[:] = priority_tests + other_tests
```

**Purpose:** Prevent Rich/logging state pollution by running sensitive tests first

### 9.3 Missing CI/CD Features

#### **1. Test Parallelization**

**Current:** Tests run sequentially
**Proposed:** Use pytest-xdist for parallel execution

```bash
# CI configuration
pytest -n auto --dist loadscope  # Distribute by test file
```

**Benefits:**
- Faster test execution (3-4x speedup)
- Better resource utilization
- Catch race conditions

#### **2. Flakiness Detection**

**Need:** Automatically detect and report flaky tests

**Proposed:** Run tests multiple times and track failures

```yaml
# .github/workflows/test.yml
- name: Detect Flaky Tests
  run: |
    pytest --flake-finder --runs 10 --cache-clear
```

**Integration with pytest-flake-finder:**
```python
# pytest.ini
[pytest]
flake_finder_runs = 10
flake_finder_threshold = 0.1  # 10% failure rate
```

#### **3. Coverage Ratcheting**

**Need:** Prevent coverage from decreasing

**Proposed:** Track coverage over time and fail if it drops

```yaml
# .github/workflows/test.yml
- name: Check Coverage Ratchet
  run: |
    # Get previous coverage from artifact
    PREV_COVERAGE=$(cat coverage/previous.txt)
    CURR_COVERAGE=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')

    if [ "$CURR_COVERAGE" -lt "$PREV_COVERAGE" ]; then
      echo "Coverage decreased from $PREV_COVERAGE% to $CURR_COVERAGE%"
      exit 1
    fi

    # Save current coverage for next run
    echo $CURR_COVERAGE > coverage/current.txt
```

#### **4. Test Impact Analysis**

**Need:** Run only tests affected by code changes

**Proposed:** Use pytest-testmon to track dependencies

```bash
# CI configuration
pytest --testmon  # Only run tests affected by changes
```

**Benefits:**
- Faster CI feedback
- Reduced resource usage
- Still run all tests on main branch

#### **5. Performance Regression Detection**

**Need:** Automatically detect performance regressions

**Proposed:** Compare benchmark results against baseline

```yaml
# .github/workflows/benchmark.yml
- name: Run Benchmarks
  run: |
    pytest tests/performance --benchmark-only --benchmark-json=benchmark.json

- name: Compare with Baseline
  run: |
    python scripts/compare_benchmarks.py \
      --baseline artifacts/benchmark-baseline.json \
      --current benchmark.json \
      --threshold 10  # Fail if >10% slower
```

---

## 10. Testing Best Practices Guide

### 10.1 Test Naming Conventions

**Pattern:** `test_should_<action>_when_<condition>`

**Examples:**
```python
# Good
test_should_schedule_agent_when_artifact_matches()
test_should_raise_error_when_type_missing()
test_should_execute_hooks_in_order()

# Bad
test_agent()
test_orchestrator_scheduling()
test_stuff()
```

**Benefits:**
- Self-documenting
- Clear intent
- Easy to search

### 10.2 AAA Pattern (Arrange, Act, Assert)

**Structure:**
```python
async def test_orchestrator_schedules_matching_agent(orchestrator):
    """Test that orchestrator schedules agent matching artifact type."""

    # Arrange - Set up test data and dependencies
    executed = []
    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append(agent.name)
            return EvalResult(artifacts=[])

    orchestrator.agent("test_agent").consumes(Movie).with_engines(TrackingEngine())

    # Act - Execute the behavior being tested
    await orchestrator.publish({"type": "Movie", "title": "TEST", "runtime": 120})
    await orchestrator.run_until_idle()

    # Assert - Verify expected outcomes
    assert "test_agent" in executed
```

**Benefits:**
- Clear structure
- Easy to understand
- Maintainable

### 10.3 Fixture Best Practices

**Do:**
```python
@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test.

    Note: Dashboard initialization is disabled to avoid Windows encoding issues.
    """
    orch = Flock()
    orch.is_dashboard = True
    return orch
```

**Don't:**
```python
# Bad: Shared mutable state
orchestrator = Flock()

@pytest.fixture
def get_orchestrator():
    return orchestrator  # Returns same instance!
```

**Guidelines:**
- Use fixtures for setup/teardown
- Document fixture behavior
- Avoid shared mutable state
- Use `autouse=True` sparingly

### 10.4 Async Testing Best Practices

**Do:**
```python
@pytest.mark.asyncio
async def test_agent_execution(orchestrator):
    """Test async agent execution."""
    result = await orchestrator.invoke(agent, artifact)
    await orchestrator.run_until_idle()
    assert result is not None
```

**Don't:**
```python
# Bad: Mixing sync and async
def test_agent_execution(orchestrator):
    result = asyncio.run(orchestrator.invoke(agent, artifact))  # Don't do this!
```

**Guidelines:**
- Always use `@pytest.mark.asyncio`
- Use `async def` for test functions
- Await all async operations
- Use `pytest-asyncio` for proper cleanup

### 10.5 Mocking Best Practices

**Do:**
```python
@pytest.fixture(autouse=True)
def mock_llm(mocker):
    """Mock LLM API calls to avoid real requests."""
    async def mock_response(*args, **kwargs):
        return {"output": "mocked response"}

    mock_predict = mocker.patch("dspy.Predict.__call__", side_effect=mock_response)
    yield mock_response
    mock_predict.reset_mock()  # Explicit cleanup
```

**Don't:**
```python
# Bad: No cleanup, leaks between tests
@pytest.fixture
def mock_llm(mocker):
    mocker.patch("dspy.Predict.__call__", return_value={"output": "test"})
```

**Guidelines:**
- Mock external dependencies (APIs, databases)
- Reset mocks after each test
- Use `side_effect` for async mocks
- Document mock behavior

### 10.6 Assertion Best Practices

**Do:**
```python
# Specific assertions with context
assert len(outputs) == 1, f"Expected 1 output, got {len(outputs)}"
assert executed_count[0] <= max_iterations, (
    f"Agent executed {executed_count[0]} times, exceeded limit {max_iterations}"
)

# Multiple assertions for comprehensive verification
assert artifact.type == "Movie"
assert artifact.payload["title"] == "TEST"
assert artifact.produced_by == "test_agent"
```

**Don't:**
```python
# Bad: Generic assertions
assert outputs  # Too vague
assert executed_count[0] < 100  # Why 100? No context
```

**Guidelines:**
- Use specific assertions
- Add context to assertion messages
- Test one behavior per test (but multiple aspects of that behavior)
- Use `pytest.raises` for exception testing

### 10.7 Parameterization Best Practices

**Do:**
```python
@pytest.mark.parametrize("store_type,expected_backend", [
    ("memory", InMemoryBlackboardStore),
    ("sqlite", SQLiteBlackboardStore),
])
async def test_store_operations(store_type, expected_backend):
    """Test operations work with different store backends."""
    store = create_store(store_type)
    assert isinstance(store, expected_backend)
```

**Don't:**
```python
# Bad: Separate tests for same logic
async def test_memory_store_operations():
    store = InMemoryBlackboardStore()
    # ... test logic ...

async def test_sqlite_store_operations():
    store = SQLiteBlackboardStore()
    # ... duplicate test logic ...
```

**Guidelines:**
- Use parameterization to avoid duplication
- Provide descriptive parameter names
- Use pytest.param for complex scenarios
- Document parameter meanings

---

## 11. Testing Improvement Roadmap

### Phase 1: Critical Gaps (Weeks 1-2)

**Priority 1: DSPy Engine Coverage (35.14% → 75%+)**

1. **Streaming Execution Tests**
   - File: `tests/test_dspy_engine_streaming.py`
   - Lines to cover: 559-751
   - Tests: 15-20 tests
   - Focus: Streaming with status messages, error handling, stream interruption

2. **MCP Tool Integration Tests**
   - File: `tests/test_dspy_engine_mcp_tools.py`
   - Lines to cover: 766-1101
   - Tests: 20-25 tests
   - Focus: Tool registration, tool execution, tool error handling

3. **Error Recovery Tests**
   - File: `tests/test_dspy_engine_errors.py`
   - Lines to cover: 1107-1145
   - Tests: 10-15 tests
   - Focus: Prediction failures, timeout handling, retry logic

**Priority 2: Dashboard Service Coverage (54.66% → 80%+)**

1. **WebSocket Management Tests**
   - File: `tests/test_dashboard_websocket_mgmt.py`
   - Lines to cover: 111-135, 452-513
   - Tests: 15-20 tests
   - Focus: Connection lifecycle, reconnection, heartbeat

2. **API Endpoint Tests**
   - File: `tests/test_dashboard_api_endpoints.py`
   - Lines to cover: 525-635, 651-716
   - Tests: 25-30 tests
   - Focus: Control endpoints, graph endpoints, query endpoints

3. **Metrics Endpoints Tests**
   - File: `tests/test_dashboard_metrics.py`
   - Lines to cover: 791-850, 884-899
   - Tests: 10-15 tests
   - Focus: Metrics collection, aggregation, reporting

**Priority 3: MCP Server Coverage (41-43% → 75%+)**

1. **Server Lifecycle Tests**
   - File: `tests/test_mcp_server_lifecycle.py`
   - Tests: 15-20 tests
   - Focus: Initialization, shutdown, error handling

2. **Transport-Specific Tests**
   - Files:
     - `tests/test_mcp_stdio_server.py`
     - `tests/test_mcp_sse_server.py`
     - `tests/test_mcp_streamable_http_server.py`
   - Tests: 10-15 tests per transport
   - Focus: Transport creation, message handling, error scenarios

### Phase 2: Test Infrastructure (Weeks 3-4)

**Test Utilities Library**

1. **Component Test Harness**
   - File: `tests/utils/component_harness.py`
   - Purpose: Simplified component testing
   - Impact: Easier component testing, reduced boilerplate

2. **Test Agent Builder**
   - File: `tests/utils/agent_builder.py`
   - Purpose: Fluent API for test agent creation
   - Impact: More readable tests, reduced duplication

3. **Mock Store Factory**
   - File: `tests/utils/mock_store.py`
   - Purpose: Easy mock store creation
   - Impact: Faster test setup, consistent test data

4. **Assertion Helpers**
   - File: `tests/utils/assertions.py`
   - Purpose: Custom assertions for common scenarios
   - Impact: More expressive tests, better error messages

**CI/CD Improvements**

1. **Test Parallelization**
   - Tool: pytest-xdist
   - Impact: 3-4x faster test execution
   - Implementation: Update CI configuration

2. **Flakiness Detection**
   - Tool: pytest-flake-finder
   - Impact: Identify unreliable tests
   - Implementation: Add to CI pipeline

3. **Coverage Ratcheting**
   - Tool: Custom script
   - Impact: Prevent coverage regression
   - Implementation: Add to GitHub Actions

4. **Performance Regression Detection**
   - Tool: pytest-benchmark
   - Impact: Catch performance issues early
   - Implementation: Add benchmark suite

### Phase 3: Advanced Testing (Weeks 5-6)

**Integration Tests**

1. **MCP Client Integration**
   - File: `tests/integration/test_mcp_client_e2e.py`
   - Tests: 10-15 tests
   - Focus: Real MCP server communication

2. **DSPy Engine Integration**
   - File: `tests/integration/test_dspy_engine_real_llm.py`
   - Tests: 5-10 tests
   - Focus: Real LLM API calls (mocked responses)

3. **Full Stack Integration**
   - File: `tests/integration/test_full_stack_workflow.py`
   - Tests: 5-10 tests
   - Focus: Complex multi-agent workflows

**E2E Tests**

1. **Multi-Agent Collaboration**
   - File: `tests/e2e/test_multi_agent_collaboration.py`
   - Tests: 3-5 tests
   - Focus: 5+ agents collaborating

2. **Long-Running Workflows**
   - File: `tests/e2e/test_long_running_workflows.py`
   - Tests: 2-3 tests
   - Focus: Workflows >1 hour

3. **Error Recovery Paths**
   - File: `tests/e2e/test_error_recovery.py`
   - Tests: 5-10 tests
   - Focus: Agent failures, partial rollback

4. **Scalability Tests**
   - File: `tests/e2e/test_scalability.py`
   - Tests: 3-5 tests
   - Focus: 100+ concurrent agents

**Performance Tests**

1. **Agent Execution Benchmarks**
   - File: `tests/performance/test_agent_performance.py`
   - Tests: 5-10 benchmarks
   - Focus: Execution latency, throughput

2. **Store Performance Benchmarks**
   - File: `tests/performance/test_store_performance.py`
   - Tests: 10-15 benchmarks
   - Focus: Read, write, query performance

3. **Scheduling Performance Benchmarks**
   - File: `tests/performance/test_scheduling_performance.py`
   - Tests: 5-10 benchmarks
   - Focus: Artifact scheduling latency

4. **Memory Usage Benchmarks**
   - File: `tests/performance/test_memory_usage.py`
   - Tests: 5-10 benchmarks
   - Focus: Memory growth, leak detection

### Phase 4: Documentation & Training (Week 7)

**Testing Guides**

1. **Component Testing Guide**
   - File: `docs/testing/component-testing-guide.md`
   - Content: How to test components, harness usage, patterns

2. **Integration Testing Guide**
   - File: `docs/testing/integration-testing-guide.md`
   - Content: How to write integration tests, patterns, examples

3. **E2E Testing Guide**
   - File: `docs/testing/e2e-testing-guide.md`
   - Content: How to write E2E tests, scenarios, performance requirements

4. **Performance Testing Guide**
   - File: `docs/testing/performance-testing-guide.md`
   - Content: How to write benchmarks, interpret results, set thresholds

**Testing Best Practices Document**
- File: `docs/testing/best-practices.md`
- Content: Naming, patterns, fixtures, mocking, assertions

---

## 12. Testing Metrics Dashboard

### 12.1 Current Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Overall Coverage** | 75.78% | 75%+ | ✅ |
| **Critical Path Coverage** | ~95% | 100% | ⚠️ |
| **Test Count** | 892 tests | - | ✅ |
| **Pass Rate** | 97.5% | 100% | ⚠️ |
| **Test-to-Code Ratio** | 1.37:1 | 1:1+ | ✅ |
| **Flaky Tests** | Unknown | 0 | ❓ |
| **Avg Test Execution** | 34.03s | <60s | ✅ |
| **Performance Tests** | 2 | 20+ | ❌ |

### 12.2 Coverage by Component Category

| Category | Coverage | Target | Status |
|----------|----------|--------|--------|
| **Core Framework** | 85-100% | 90%+ | ✅ |
| **Storage** | 78% | 80%+ | ⚠️ |
| **Dashboard** | 54-95% | 80%+ | ⚠️ |
| **Engines** | 35% | 75%+ | ❌ |
| **MCP** | 41-99% | 75%+ | ⚠️ |
| **Utilities** | 41-95% | 75%+ | ⚠️ |

### 12.3 Test Distribution

| Type | Count | % of Total |
|------|-------|------------|
| **Unit Tests** | ~800 | 90% |
| **Integration Tests** | ~80 | 9% |
| **E2E Tests** | ~12 | 1% |
| **Contract Tests** | ~10 | 1% |

**Recommendation:** Increase integration and E2E test coverage to 15-20% of total tests.

### 12.4 Proposed Metrics Tracking

**Add to CI/CD:**
1. **Coverage Trend Graph** - Track coverage over time
2. **Test Execution Time Trend** - Monitor performance
3. **Flaky Test Report** - Identify unreliable tests
4. **Performance Regression Report** - Track benchmark results
5. **Test Quality Score** - Composite metric based on coverage, pass rate, flakiness

---

## 13. Conclusion

### 13.1 Summary

Flock has a **strong testing foundation** with:
- ✅ Excellent test organization (unit, integration, e2e, contract)
- ✅ High overall coverage (75.78%)
- ✅ Comprehensive fixtures and test utilities
- ✅ Modern testing patterns (pytest, asyncio, mocking)
- ✅ Performance requirements documented and tested
- ✅ Contract testing for API stability

**Key Achievements:**
- 892 tests covering critical paths
- Well-structured test organization
- E2E tests with performance SLAs
- Excellent component and orchestrator coverage

### 13.2 Priority Improvements

**Critical (Weeks 1-2):**
1. DSPy Engine coverage: 35% → 75%+ (streaming, tools, errors)
2. Dashboard Service coverage: 55% → 80%+ (WebSocket, API endpoints)
3. MCP Server coverage: 41-43% → 75%+ (lifecycle, transport-specific)

**Important (Weeks 3-4):**
1. Test utilities library (harness, builders, factories, assertions)
2. CI/CD improvements (parallelization, flakiness detection, ratcheting)
3. Output utility component coverage: 41% → 75%+

**Nice-to-Have (Weeks 5-6):**
1. Advanced integration tests (MCP, DSPy, full stack)
2. Additional E2E tests (multi-agent, long-running, scalability)
3. Comprehensive performance benchmarks (20+ benchmarks)

**Documentation (Week 7):**
1. Testing guides (component, integration, E2E, performance)
2. Best practices documentation
3. Contributor testing guidelines

### 13.3 Success Criteria

**After implementing improvements:**
- Overall coverage: **80%+**
- Critical path coverage: **100%**
- DSPy engine coverage: **75%+**
- Dashboard service coverage: **80%+**
- MCP server coverage: **75%+**
- Performance benchmarks: **20+ benchmarks**
- Test utilities: **Complete harness library**
- CI/CD: **Parallelized, flakiness detection, ratcheting**
- Documentation: **Complete testing guides**

### 13.4 Long-Term Vision

**Mature Testing Strategy:**
1. **Coverage:** Maintain 80%+ overall, 100% critical paths
2. **Performance:** Automated regression detection for all critical paths
3. **Reliability:** Zero flaky tests, 100% pass rate
4. **Speed:** <30s test execution with parallelization
5. **Quality:** Comprehensive test utilities, harness, and patterns
6. **Documentation:** Complete testing guides for contributors

---

## Appendix A: Test File Reference

### Unit Tests (44 files)

| File | Purpose | Coverage |
|------|---------|----------|
| `test_agent.py` | Agent lifecycle tests | 83% |
| `test_orchestrator.py` | Orchestrator tests | 79% |
| `test_components.py` | Component system tests | 100% |
| `test_artifacts.py` | Artifact creation tests | 100% |
| `test_visibility.py` | Visibility tests | 100% |
| `test_store.py` | Store operations tests | 78% |
| `test_subscription.py` | Subscription tests | 95% |
| `test_registry.py` | Type registry tests | 90% |
| `test_dspy_engine.py` | DSPy engine tests | 35% |
| `test_mcp_client.py` | MCP client tests | 88% |
| `test_dashboard_collector.py` | Event collector tests | 95% |
| ... | (and 33 more) | - |

### Integration Tests (4 files)

| File | Purpose |
|------|---------|
| `test_sqlite_store_integration.py` | SQLite store integration |
| `test_collector_orchestrator.py` | Collector + orchestrator |
| `test_orchestrator_dashboard.py` | Orchestrator + dashboard |
| `test_websocket_protocol.py` | WebSocket protocol |

### E2E Tests (1 file)

| File | Purpose |
|------|---------|
| `test_critical_scenarios.py` | 4 critical user scenarios |

### Contract Tests (3 files)

| File | Purpose |
|------|---------|
| `test_type_normalization_contract.py` | Type name resolution |
| `test_agent_payload_selection_contract.py` | Payload selection |
| `test_artifact_storage_contract.py` | Storage contracts |

---

## Appendix B: Recommended Testing Tools

### Current Tools

- **pytest** (8.4.2) - Test framework ✅
- **pytest-asyncio** (1.2.0) - Async testing ✅
- **pytest-mock** (3.15.1) - Mocking ✅
- **pytest-cov** (7.0.0) - Coverage reporting ✅
- **pytest-clarity** (1.0.1) - Better diffs ✅
- **pytest-sugar** (1.1.1) - Better output ✅
- **pytest-order** (1.3.0) - Test ordering ✅

### Recommended Additions

- **pytest-xdist** - Parallel test execution
- **pytest-benchmark** - Performance benchmarking
- **pytest-flake-finder** - Flaky test detection
- **pytest-testmon** - Test impact analysis
- **hypothesis** - Property-based testing
- **faker** - Test data generation

### Installation

```bash
# Add to pyproject.toml [dependency-groups] dev section
pytest-xdist = ">=3.6.1"
pytest-benchmark = ">=4.0.0"
pytest-flake-finder = ">=1.1.0"
pytest-testmon = ">=2.1.3"
hypothesis = ">=6.112.0"
faker = ">=30.8.2"
```

---

**End of Analysis**

This analysis provides a comprehensive overview of Flock's testing architecture and a clear roadmap for improvements. The project has excellent foundations and with the proposed improvements will have a world-class testing strategy.
