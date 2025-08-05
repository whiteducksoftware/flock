# Refactor Plan: Flock Orchestrator

## Current Issues Analysis

### 1. **Massive Single Responsibility Violations**
- Flock class is 974 lines with 8+ major responsibilities
- Orchestration + Execution + Batch Processing + Evaluation + Server Management + CLI + Web API + Configuration
- Violates SRP at every level - should be focused on orchestration only

### 2. **Complex Initialization & Side Effects**
- `__init__` method does too much: registry discovery, opik setup, server registration, banner display
- Side effects scattered throughout initialization
- Hard to test due to many external dependencies
- Banner display and configuration setup mixed with core logic

### 3. **Execution Logic Issues**
- Temporal vs Local execution logic mixed in main orchestrator
- Complex `run_async` method handles agent resolution, context setup, server management, execution
- Sync wrapper methods duplicate async logic with `_run_sync`
- No clear separation between execution engines

### 4. **Mixed Concerns Throughout**
- Server management (`_mgr`, `add_server`) mixed with agent orchestration
- Batch processing and evaluation logic embedded in main class
- CLI and Web API startup methods in orchestrator
- Configuration and execution state mixed together

### 5. **Testing & Maintenance Issues**
- Hard to mock due to tight coupling
- Difficult to test individual concerns in isolation
- Complex state management with multiple runtime dictionaries
- No clear interfaces for different responsibilities

## Proposed Refactoring Strategy

### Phase 1: Apply Composition Pattern (High Priority)

Following the successful FlockAgent refactoring, split Flock into specialized composition helpers:

#### 1.1 Core Flock (Minimal Orchestrator)
```python
class Flock(BaseModel, Serializable):
    """Minimal orchestrator focused on agent workflow coordination."""
    
    # Core data (keep in main class)
    name: str
    model: str | None
    description: str | None
    enable_temporal: bool
    _agents: dict[str, FlockAgent]
    _servers: dict[str, FlockMCPServerBase]
    
    # Composition helpers (lazy-loaded)
    @property
    def _execution(self) -> FlockExecution:
        """Handle run/run_async logic."""
    
    @property  
    def _server_manager(self) -> FlockServerManager:
        """Handle server lifecycle and management."""
    
    @property
    def _batch_processor(self) -> FlockBatchProcessor:
        """Handle batch execution logic."""
    
    @property
    def _evaluator(self) -> FlockEvaluator:
        """Handle evaluation workflows."""
    
    @property
    def _web_server(self) -> FlockWebServer:
        """Handle web API and UI serving."""
    
    @property
    def _initialization(self) -> FlockInitialization:
        """Handle complex initialization logic."""
```

#### 1.2 Specialized Composition Classes
```
FlockExecution           - run/run_async logic, context setup, workflow coordination
FlockServerManager       - Server registration, lifecycle, MCP management  
FlockBatchProcessor      - Batch execution, parallel processing
FlockEvaluator          - Dataset evaluation, metrics, reporting
FlockWebServer          - REST API, UI serving, endpoint management
FlockInitialization     - Setup logic, configuration, side effects
```

### Phase 2: Extract Execution Engines (Medium Priority)

#### 2.1 Separate Execution Strategies
```python
class ExecutionEngine(Protocol):
    """Interface for different execution strategies."""
    async def execute(self, context: FlockContext) -> dict[str, Any]:
        ...

class LocalExecutionEngine:
    """Handles local execution workflow."""
    async def execute(self, context: FlockContext) -> dict[str, Any]:
        # Current local execution logic
        
class TemporalExecutionEngine:
    """Handles Temporal workflow execution."""
    async def execute(self, context: FlockContext) -> dict[str, Any]:
        # Current temporal execution logic
```

#### 2.2 Clean Execution Delegation
```python
class FlockExecution:
    """Handles execution coordination with pluggable engines."""
    
    def __init__(self, flock: Flock):
        self.flock = flock
        self._local_engine = LocalExecutionEngine()
        self._temporal_engine = TemporalExecutionEngine()
    
    def _get_engine(self) -> ExecutionEngine:
        """Select appropriate execution engine."""
        return self._temporal_engine if self.flock.enable_temporal else self._local_engine
    
    async def run_async(self, start_agent, input, **kwargs) -> dict[str, Any]:
        """Main execution logic delegated to appropriate engine."""
        # Setup context, resolve agents, then delegate to engine
        engine = self._get_engine()
        return await engine.execute(context)
```

### Phase 3: Configuration & State Management (Low Priority)

#### 3.1 Centralized Configuration
```python
class FlockConfig(BaseModel):
    """Centralized configuration for Flock instance."""
    
    # Core settings
    name: str
    model: str | None = DEFAULT_MODEL
    description: str | None = None
    
    # Execution settings  
    enable_temporal: bool = False
    temporal_config: TemporalWorkflowConfig | None = None
    temporal_start_in_process_worker: bool = True
    
    # Feature flags
    enable_opik: bool = False
    show_flock_banner: bool = True
    
    # Benchmark settings
    benchmark_agent_name: str | None = None
    benchmark_eval_field: str | None = None  
    benchmark_input_field: str | None = None
```

#### 3.2 State Management Separation
```python
class FlockState:
    """Manages runtime state separately from configuration."""
    
    def __init__(self):
        self.agents: dict[str, FlockAgent] = {}
        self.servers: dict[str, FlockMCPServerBase] = {}
        self.start_agent_name: str | None = None
        self.start_input: dict = {}
```

## Detailed Implementation Plan

### New File Structure
```
src/flock/core/
├── flock.py                    # Minimal orchestrator (200-300 lines)
├── execution/
│   ├── __init__.py
│   ├── flock_execution.py      # Main execution coordination
│   ├── local_engine.py         # Local execution strategy
│   ├── temporal_engine.py      # Temporal execution strategy
│   └── execution_context.py    # Execution context management
├── management/
│   ├── __init__.py  
│   ├── flock_server_manager.py # Server lifecycle management
│   ├── flock_batch_processor.py # Batch processing logic
│   ├── flock_evaluator.py     # Evaluation workflows
│   └── flock_initialization.py # Setup and initialization
├── web/
│   ├── __init__.py
│   ├── flock_web_server.py     # Web serving logic
│   └── flock_cli_manager.py    # CLI management
└── config/
    ├── __init__.py
    ├── flock_config.py         # Configuration classes
    └── flock_state.py          # State management
```

### Key Architectural Changes

#### 1. Minimal Flock Orchestrator
```python
class Flock(BaseModel, Serializable):
    """Focused orchestrator for agent workflow coordination."""
    
    # Core configuration and state
    config: FlockConfig
    _state: FlockState = Field(exclude=True)
    
    def __init__(self, **kwargs):
        """Simplified initialization."""
        config = FlockConfig(**kwargs)
        super().__init__(config=config)
        self._state = FlockState()
        
        # Delegate complex initialization
        self._initialization.setup(config, self._state)
    
    # --- Agent Management (keep in main class) ---
    def add_agent(self, agent: FlockAgent) -> FlockAgent:
        """Add agent to workflow."""
        # Simplified logic, delegate complex operations
        
    def add_server(self, server: FlockMCPServerBase) -> FlockMCPServerBase:
        """Add server - delegate to server manager."""
        return self._server_manager.add_server(server)
    
    # --- Execution (delegate to execution helper) ---
    def run(self, **kwargs) -> Box | dict:
        """Synchronous execution."""
        return self._execution.run(**kwargs)
    
    async def run_async(self, **kwargs) -> Box | dict:
        """Asynchronous execution."""  
        return await self._execution.run_async(**kwargs)
    
    # --- Batch Processing (delegate) ---
    def run_batch(self, **kwargs):
        """Delegate to batch processor."""
        return self._batch_processor.run_batch(**kwargs)
    
    # --- Evaluation (delegate) ---
    def evaluate(self, **kwargs):
        """Delegate to evaluator."""
        return self._evaluator.evaluate(**kwargs)
    
    # --- Web & CLI (delegate) ---
    def serve(self, **kwargs):
        """Delegate to web server."""
        return self._web_server.serve(**kwargs)
    
    def start_cli(self, **kwargs):
        """Delegate to CLI manager."""
        return self._web_server.start_cli(**kwargs)
```

#### 2. Focused Execution Helper
```python
class FlockExecution:
    """Handles all execution logic and coordination."""
    
    def __init__(self, flock: Flock):
        self.flock = flock
        self.local_engine = LocalExecutionEngine(flock)
        self.temporal_engine = TemporalExecutionEngine(flock)
    
    def run(self, **kwargs) -> Box | dict:
        """Synchronous wrapper."""
        return self.flock._run_sync(self.run_async(**kwargs))
    
    async def run_async(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        **kwargs
    ) -> Box | dict:
        """Main execution logic."""
        # 1. Resolve start agent
        start_agent_name = self._resolve_start_agent(start_agent)
        
        # 2. Setup execution context
        run_context = self._setup_context(context, start_agent_name, input, **kwargs)
        
        # 3. Select and run execution engine
        engine = self._select_engine()
        
        # 4. Execute with server management
        async with self.flock._server_manager:
            result = await engine.execute(run_context)
            
        # 5. Format result
        return self._format_result(result, kwargs.get('box_result', True))
    
    def _resolve_start_agent(self, start_agent) -> str:
        """Resolve start agent logic."""
        # Current complex agent resolution logic
        
    def _setup_context(self, context, start_agent_name, input, **kwargs) -> FlockContext:
        """Setup execution context."""
        # Current context setup logic
        
    def _select_engine(self) -> ExecutionEngine:
        """Select appropriate execution engine."""
        return self.temporal_engine if self.flock.config.enable_temporal else self.local_engine
```

#### 3. Server Management Helper
```python
class FlockServerManager:
    """Dedicated server lifecycle management."""
    
    def __init__(self, flock: Flock):
        self.flock = flock
        self._mgr = FlockServerManager()  # Internal manager
    
    def add_server(self, server: FlockMCPServerBase) -> FlockMCPServerBase:
        """Add and register server."""
        # Current add_server logic
        self.flock._state.servers[server.config.name] = server
        FlockRegistry.register_server(server)
        self._mgr.add_server_sync(server)
        return server
    
    async def __aenter__(self):
        """Start all managed servers."""
        return await self._mgr.__aenter__()
    
    async def __aexit__(self, *args):
        """Cleanup all managed servers."""
        return await self._mgr.__aexit__(*args)
```

#### 4. Initialization Helper
```python
class FlockInitialization:
    """Handles complex initialization logic."""
    
    def __init__(self, flock: Flock):
        self.flock = flock
    
    def setup(self, config: FlockConfig, state: FlockState):
        """Handle all initialization side effects."""
        # Banner display
        if config.show_flock_banner:
            init_console(clear_screen=True, show_banner=True)
        
        # Temporal configuration
        self._setup_temporal(config)
        
        # Session ID
        self._ensure_session_id()
        
        # Registry discovery
        FlockRegistry.discover_and_register_components()
        
        # Opik setup
        if config.enable_opik:
            self._setup_opik(config)
    
    def _setup_temporal(self, config: FlockConfig):
        """Setup temporal environment."""
        # Current temporal setup logic
        
    def _setup_opik(self, config: FlockConfig):
        """Setup Opik integration."""
        # Current Opik setup logic
```

## Benefits of This Refactoring

### 1. **Dramatically Improved Maintainability**
- Flock class reduced from 974 to ~300 lines
- Each helper has single, clear responsibility
- Much easier to test individual components
- Clear separation between orchestration and execution

### 2. **Better Testability**
- Can mock individual helpers easily
- Execution engines can be tested independently
- No more complex initialization side effects in tests
- Clear interfaces for all components

### 3. **Enhanced Extensibility**
- Easy to add new execution engines (e.g., Kubernetes, Docker)
- Pluggable batch processors and evaluators
- Can swap out server management strategies
- New web frameworks can be added easily

### 4. **Cleaner Architecture**
- Clear separation between configuration, state, and behavior
- Consistent composition pattern across all core classes
- No more mixed concerns in single methods
- Easier to understand and reason about

### 5. **Performance Benefits**
- Lazy loading of expensive components
- Can optimize individual helpers independently
- Reduced memory footprint for unused features
- Better resource management

## Migration Strategy

### Phase 1: Extract Execution Logic (2-3 days)
1. Create FlockExecution helper class
2. Extract run/run_async logic
3. Create execution engine interfaces
4. Migrate local and temporal execution

### Phase 2: Extract Management Helpers (2-3 days)
1. Create FlockServerManager
2. Extract batch processing logic
3. Extract evaluation logic
4. Create initialization helper

### Phase 3: Configuration Cleanup (1-2 days)
1. Create FlockConfig class
2. Separate state management
3. Clean up initialization
4. Update web/CLI delegation

### Phase 4: Testing & Integration (2-3 days)
1. Ensure all existing tests pass
2. Add tests for new helpers
3. Integration testing
4. Performance validation

### Phase 5: Documentation & Cleanup (1 day)
1. Update documentation
2. Clean up any remaining duplication
3. Final testing and validation

## Risk Assessment

### Low Risk
- Composition pattern already proven successful with FlockAgent
- Backward compatibility maintained through delegation
- Clear interfaces and separation of concerns

### Medium Risk
- Large amount of code to move
- Complex execution logic needs careful migration
- Server management lifecycle must be preserved exactly

### Mitigation Strategies
- Incremental migration with feature flags
- Extensive integration testing at each phase
- Keep original methods as compatibility wrappers initially
- Thorough testing of server lifecycle and execution flows

## Expected Outcomes

### Immediate Benefits
- 60-70% reduction in main Flock class size
- Much easier to test and maintain
- Clear separation of concerns
- Consistent architecture across all core classes

### Long-term Benefits
- Easy to add new execution engines
- Pluggable components for different use cases
- Better performance through lazy loading
- Foundation for advanced features (caching, monitoring, etc.)

This refactoring will bring Flock's architecture in line with modern software design principles while maintaining full backward compatibility and improving developer experience significantly.
