# Flock Flow Core Architecture Analysis

## Overview

Flock Flow is a sophisticated blackboard architecture system designed for multi-agent orchestration and event-driven coordination. The system implements a production-ready blackboard pattern with advanced features including subscription mechanisms, visibility controls, artifact lifecycle management, and MCP (Model Context Protocol) integration.

## Core Architectural Components

### 1. Blackboard Architecture (`orchestrator.py`)

The system implements a **Blackboard Pattern** with the following key components:

#### Flock (Main Orchestrator)
- **Purpose**: Central coordinator managing all agents and artifact scheduling
- **Key Responsibilities**:
  - Agent registration and lifecycle management
  - Artifact persistence and scheduling
  - MCP server management and tool orchestration
  - Circuit breaker protection against runaway agents
  - Metrics collection and monitoring

#### Key Classes:
```python
class Flock:
    """Main orchestrator implementing blackboard architecture"""
    - store: BlackboardStore  # Artifact persistence
    - _agents: dict[str, Agent]  # Registered agents
    - _tasks: set[Task]  # Active execution tasks
    - _processed: set[tuple[str, str]]  # Prevent duplicate processing
    - _mcp_configs: Dict[str, FlockMCPConfiguration]  # MCP server configs
    - max_agent_iterations: int  # Circuit breaker limit
```

#### BoardHandle
- **Purpose**: Interface exposed to agents for blackboard interaction
- **Methods**: `publish()`, `get()`, `list()`
- **Pattern**: Facade pattern providing clean agent API

#### Scheduling Mechanism
The orchestrator uses **event-driven scheduling** with these critical safeguards:

1. **Duplicate Prevention**: Tracks processed (artifact_id, agent_name) pairs
2. **Self-Trigger Protection**: Agents can be configured to prevent feedback loops
3. **Circuit Breaker**: Limits agent iterations to detect infinite loops
4. **Visibility Filtering**: Enforces access controls before scheduling
5. **Subscription Matching**: Complex predicate evaluation for artifact routing

### 2. Agent System (`agent.py`)

#### Agent Class
The core agent implementation follows a **component-based architecture**:

```python
class Agent:
    """Executable agent with lifecycle hooks and component support"""
    - subscriptions: List[Subscription]  # Input specifications
    - outputs: List[AgentOutput]  # Output declarations
    - utilities: List[AgentComponent]  # Cross-cutting concerns
    - engines: List[EngineComponent]  # Core processing logic
    - best_of_n: int  # Parallel execution strategy
    - max_concurrency: int  # Execution limits
    - prevent_self_trigger: bool  # Feedback loop prevention
    - mcp_server_names: Set[str]  # MCP tool assignments
```

#### Agent Lifecycle
The agent execution follows a **pipeline pattern** with these phases:

1. **Pre-Consume**: Input transformation and validation
2. **Pre-Evaluate**: Context preparation and state setup
3. **Engine Evaluation**: Core processing logic (supports parallel best-of-n)
4. **Post-Evaluate**: Result transformation and filtering
5. **Output Generation**: Artifact creation and publishing
6. **Post-Publish**: Cleanup and side effects
7. **Error Handling**: Comprehensive error propagation

#### AgentBuilder Pattern
Implements a **fluent builder pattern** for agent configuration:

```python
agent = flock.agent("movie-processor")
    .description("Processes movie ideas")
    .consumes(Idea, where=lambda i: i.genre == "comedy")
    .publishes(Movie, Tagline, visibility=PublicVisibility())
    .with_engines(MovieEngine())
    .with_utilities(LoggingUtility(), MetricsUtility())
    .max_concurrency(3)
    .best_of(5, score=lambda r: r.metrics.get("confidence", 0))
```

### 3. Artifact System (`artifacts.py`)

#### Artifact Class
Represents typed data objects on the blackboard:

```python
class Artifact:
    """Typed artifact with metadata and visibility controls"""
    - id: UUID  # Unique identifier
    - type: str  # Registered type name
    - payload: Dict[str, Any]  # Serialized data
    - produced_by: str  # Source agent
    - correlation_id: UUID  # Conversation tracking
    - partition_key: str  # Sharding hint
    - tags: set[str]  # Classification labels
    - visibility: Visibility  # Access control
    - version: int  # Version tracking
```

#### ArtifactSpec
Defines wiring contracts for type-safe artifact creation:

```python
class ArtifactSpec:
    """Type specification for artifact validation"""
    - type_name: str  # Registered type identifier
    - model: type[BaseModel]  # Pydantic model class
```

### 4. Subscription System (`subscription.py`)

#### Subscription Class
Implements sophisticated **event routing** with multiple matching criteria:

```python
class Subscription:
    """Agent subscription with complex matching logic"""
    - types: Sequence[type[BaseModel]]  # Type filters
    - where: Sequence[Predicate]  # Content predicates
    - text_predicates: Sequence[TextPredicate]  # Semantic matching
    - from_agents: Set[str]  # Source filtering
    - channels: Set[str]  # Tag-based routing
    - join: JoinSpec  # Temporal correlation
    - batch: BatchSpec  # Aggregation rules
    - delivery: str  # Delivery semantics ("exclusive", "shared")
    - mode: str  # Execution mode ("events", "direct", "both")
    - priority: int  # Scheduling priority
```

#### Advanced Features:
- **Text Predicates**: Semantic content matching with confidence thresholds
- **Join Specifications**: Temporal correlation of related artifacts
- **Batch Specifications**: Artifact aggregation with time windows
- **Delivery Modes**: Event-driven vs direct invocation
- **Priority Scheduling**: Ordered artifact processing

### 5. Visibility System (`visibility.py`)

#### Visibility Hierarchy
Implements **access control patterns** with multiple visibility levels:

```python
class Visibility:  # Base class
class PublicVisibility:  # Open access
class PrivateVisibility:  # Named agent access
class LabelledVisibility:  # Role-based access
class TenantVisibility:  # Multi-tenant isolation
class AfterVisibility:  # Time-based access control
```

#### AgentIdentity
```python
class AgentIdentity:
    """Agent identity for visibility checks"""
    - name: str  # Unique agent identifier
    - labels: Set[str]  # Role/attribute labels
    - tenant_id: str  # Multi-tenant identifier
```

### 6. Component Architecture (`components.py`)

#### AgentComponent
Base class for **cross-cutting concerns** with lifecycle hooks:

```python
class AgentComponent:
    """Base component with lifecycle hooks"""
    - on_initialize()  # Setup phase
    - on_pre_consume()  # Input preprocessing
    - on_pre_evaluate()  # Context preparation
    - on_post_evaluate()  # Result processing
    - on_post_publish()  # Output handling
    - on_error()  # Error handling
    - on_terminate()  # Cleanup
```

#### EngineComponent
Extends AgentComponent with **conversation context support**:

```python
class EngineComponent:
    """Processing engine with context awareness"""
    - enable_context: bool  # Context fetching
    - context_max_artifacts: int  # Context limits
    - context_exclude_types: set[str]  # Type filtering
    - fetch_conversation_context()  # Context retrieval
    - get_latest_artifact_of_type()  # Context queries
```

### 7. Runtime System (`runtime.py`)

#### EvalInputs
```python
class EvalInputs:
    """Inputs passed to agent engines"""
    - artifacts: List[Artifact]  # Input artifacts
    - state: Dict[str, Any]  # Agent state
    - first_as()  # Convenience extraction
    - all_as()  # Batch extraction
```

#### EvalResult
```python
class EvalResult:
    """Results returned by agent engines"""
    - artifacts: List[Artifact]  # Output artifacts
    - state: Dict[str, Any]  # Updated state
    - metrics: Dict[str, float]  # Performance metrics
    - logs: List[str]  # Execution logs
    - from_object()  # Factory methods
    - from_objects()  # Batch creation
```

#### Context
```python
class Context:
    """Execution context for agents"""
    - board: BoardHandle  # Blackboard interface
    - orchestrator: Flock  # System reference
    - correlation_id: UUID  # Conversation tracking
    - task_id: str  # Execution identifier
    - state: Dict[str, Any]  # Agent state
```

### 8. Storage System (`store.py`)

#### BlackboardStore
Abstract base for **artifact persistence**:

```python
class BlackboardStore:
    """Storage interface for artifacts"""
    - publish(artifact)  # Store artifact
    - get(artifact_id)  # Retrieve by ID
    - list()  # List all artifacts
    - list_by_type(type_name)  # Type-based queries
```

#### InMemoryBlackboardStore
Default implementation with **thread-safe access**:

```python
class InMemoryBlackboardStore:
    """In-memory storage for development and testing"""
    - _by_id: Dict[UUID, Artifact]  # Primary index
    - _by_type: Dict[str, List[Artifact]]  # Type index
    - _lock: Lock  # Thread safety
```

### 9. Registry System (`registry.py`)

#### TypeRegistry
Manages **type registration** and resolution:

```python
class TypeRegistry:
    """Registry for Pydantic model types"""
    - _by_name: Dict[str, type[BaseModel]]  # Name -> Class
    - _by_cls: Dict[type[BaseModel], str]  # Class -> Name
    - register(model, name)  # Type registration
    - resolve(type_name)  # Type resolution
    - resolve_name(type_name)  # Name canonicalization
```

## Key Architectural Patterns

### 1. Blackboard Pattern
- **Central Knowledge Source**: Artifacts stored in shared blackboard
- **Independent Agents**: Autonomous agents with specialized knowledge
- **Event-Driven Coordination**: Agents react to published artifacts
- **Emergent Behavior**: Complex results from simple agent interactions

### 2. Component-Based Architecture
- **Composable Design**: Agents built from reusable components
- **Separation of Concerns**: Utilities vs engines vs core logic
- **Lifecycle Management**: Standardized component lifecycle hooks
- **Dependency Injection**: Components receive dependencies via context

### 3. Publisher-Subscriber Pattern
- **Decoupled Communication**: Agents publish without knowing subscribers
- **Flexible Routing**: Complex subscription predicates and filters
- **Scalable Coordination**: Multiple agents can react to same events
- **Temporal Correlation**: Join and batch specifications for complex flows

### 4. Builder Pattern
- **Fluent Configuration**: Readable agent definition syntax
- **Validation at Build Time**: Early detection of configuration errors
- **Immutable Configuration**: Built agents cannot be modified
- **Chaining Support**: Method chaining for complex configurations

### 5. Strategy Pattern
- **Pluggable Storage**: Multiple storage backend implementations
- **Configurable Visibility**: Multiple access control strategies
- **Flexible Engines**: Different processing strategies per agent
- **Variable Delivery**: Event-driven vs direct execution modes

### 6. Observer Pattern
- **Component Hooks**: Components observe agent lifecycle events
- **Error Propagation**: Centralized error handling and logging
- **Metrics Collection**: Automatic performance monitoring
- **State Management**: Distributed state updates across components

### 7. Command Pattern
- **Direct Invocation**: Explicit agent execution commands
- **Encapsulated Requests**: Artifacts encapsulate execution requests
- **Undo/Redo Support**: Artifact versioning enables rollback
- **Transaction Boundaries**: Clear execution units with correlation IDs

## Critical Design Decisions

### AD001: Two-Level Architecture
- **Decision**: MCP servers registered at orchestrator level, assigned to agents
- **Rationale**: Efficient resource sharing and connection management
- **Trade-offs**: Centralized complexity vs distributed simplicity

### AD003: Tool Namespacing
- **Decision**: All MCP tools namespaced as {server}__{tool}
- **Rationale**: Prevent naming conflicts across servers
- **Trade-offs**: Longer names vs unambiguous tool references

### AD005: Lazy Connection Establishment
- **Decision**: MCP connections established on first use
- **Rationale**: Reduce startup overhead and resource usage
- **Trade-offs**: First-call latency vs always-ready connections

### AD007: Graceful Degradation
- **Decision**: MCP loading failures don't crash agents
- **Rationale**: System resilience and partial functionality
- **Trade-offs**: Reduced functionality vs total failure

## Safety and Reliability Features

### 1. Circuit Breaker Pattern
- **Iteration Limits**: Prevent infinite agent loops
- **Count Reset**: Automatic reset when system idle
- **Metrics Tracking**: Monitor agent execution patterns

### 2. Duplicate Prevention
- **Processed Tracking**: Prevent redundant artifact processing
- **Identity Keys**: Composite keys for unique processing
- **Memory Management**: Bounded tracking set size

### 3. Self-Trigger Protection
- **Feedback Prevention**: Agents can't trigger on own outputs
- **Configurable**: Per-agent self-trigger control
- **Override Options**: Explicit self-trigger when needed

### 4. Error Isolation
- **Agent Sandboxing**: Errors don't affect other agents
- **Component Error Handling**: Localized error recovery
- **Graceful Degradation**: Partial system operation on failures

### 5. Concurrency Control
- **Semaphore Limits**: Per-agent concurrency control
- **Async Task Management**: Proper task lifecycle management
- **Resource Cleanup**: Automatic resource reclamation

## Integration Patterns

### 1. MCP Integration
- **Server Registration**: Centralized server configuration
- **Tool Assignment**: Per-agent tool allocation
- **Namespacing**: Unambiguous tool references
- **Error Handling**: Graceful MCP failure handling

### 2. Type System Integration
- **Pydantic Models**: Strong typing for all artifacts
- **Registry Pattern**: Centralized type management
- **Validation**: Automatic artifact validation
- **Serialization**: Consistent data representation

### 3. Logging Integration
- **Structured Logging**: Consistent log format
- **Context Propagation**: Request-scoped logging context
- **Component Logging**: Component-specific log categories
- **Performance Monitoring**: Built-in performance metrics

## Usage Patterns

### 1. Simple Agent Definition
```python
agent = flock.agent("processor")
    .consumes(InputType)
    .publishes(OutputType)
    .with_engines(ProcessingEngine())
```

### 2. Complex Agent with Multiple Features
```python
agent = flock.agent("complex-agent")
    .description("Advanced processing agent")
    .consumes(Task, where=lambda t: t.priority > 5)
    .publishes(Result, visibility=PrivateVisibility(["supervisor"]))
    .with_engines(AdvancedEngine())
    .with_utilities(LoggingUtility(), MetricsUtility())
    .max_concurrency(3)
    .best_of(5, score=lambda r: r.metrics.get("accuracy", 0))
    .with_tools([custom_tool])
    .uses_mcp("server1", "server2")
```

### 3. Event-Driven Workflow
```python
# Define agents
collector = flock.agent("collector").consumes(RawData).publishes(ProcessedData)
analyzer = flock.agent("analyzer").consumes(ProcessedData).publishes(Analysis)
reporter = flock.agent("reporter").consumes(Analysis).publishes(Report)

# Trigger workflow
await flock.publish(RawData(content="..."))
await flock.run_until_idle()  # Process entire cascade
```

### 4. Direct Invocation Pattern
```python
# Bypass subscriptions for direct control
results = await flock.invoke(
    processor,
    Task(name="urgent", priority=10),
    publish_outputs=True  # Still allow downstream processing
)
```

## Performance Considerations

### 1. Memory Management
- **Artifact Storage**: Configurable storage backends
- **Processed Tracking**: Bounded memory for duplicate prevention
- **Component Caching**: Efficient component reuse

### 2. Concurrency
- **Async Execution**: Non-blocking agent processing
- **Parallel Best-of-N**: Concurrent execution with result selection
- **Semaphore Limits**: Controlled resource usage

### 3. Scheduling Efficiency
- **Subscription Matching**: Optimized predicate evaluation
- **Visibility Filtering**: Early access control checks
- **Task Management**: Efficient async task lifecycle

### 4. Network Considerations
- **MCP Connection Pooling**: Efficient connection reuse
- **Lazy Loading**: On-demand resource allocation
- **Timeout Management**: Proper timeout handling

## Extensibility Points

### 1. Storage Backends
- Implement `BlackboardStore` for custom storage
- Support for distributed storage systems
- Persistence and recovery mechanisms

### 2. Component Development
- Custom `AgentComponent` implementations
- Domain-specific `EngineComponent` classes
- Reusable utility components

### 3. Visibility Policies
- Custom `Visibility` implementations
- Complex access control rules
- Dynamic permission systems

### 4. Subscription Extensions
- Custom predicate types
- Advanced correlation mechanisms
- External event source integration

This architecture provides a robust, scalable foundation for multi-agent systems with sophisticated coordination patterns, strong safety guarantees, and extensive extensibility options.
