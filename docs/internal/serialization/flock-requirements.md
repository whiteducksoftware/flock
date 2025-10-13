# Flock Serialization Requirements Analysis

**Date**: 2025-10-13
**Codebase Version**: Analyzed from main branch
**Analysis Scope**: Complete Agent structure and dependencies

---

## Executive Summary

The Flock framework has **excellent serialization foundations** (Pydantic everywhere, type registry, function registry) but faces challenges with:

1. **Lambda functions** (31+ usages in predicates, correlation keys, scoring)
2. **Runtime state** (semaphores, connections, orchestrator references)
3. **Component instances** (engines, utilities)

**Recommendation**: Three-tier serialization (core + extended + runtime) with graceful degradation for lambdas.

---

## 1. Agent Anatomy - Complete Attribute Inventory

### 1.1 Simple Serializable Attributes (✅ Direct Serialization)

**Location**: `src/flock/agent.py:87-116`

| Attribute | Type | Line | Purpose | Serialization Method |
|-----------|------|------|---------|---------------------|
| `name` | `str` | 94 | Agent identifier | Direct |
| `description` | `str \| None` | 95 | LLM instructions | Direct |
| `model` | `str \| None` | 109 | Default LLM model | Direct |
| `best_of_n` | `int` | 101 | Multiple evaluation runs | Direct |
| `max_concurrency` | `int` | 103 | Parallel execution limit | Direct |
| `labels` | `set[str]` | 107 | Role-based tags | `list(labels)` |
| `tenant_id` | `str \| None` | 108 | Multi-tenancy isolation | Direct |
| `prevent_self_trigger` | `bool` | 110 | Loop prevention flag | Direct |
| `tool_whitelist` | `list[str] \| None` | 115 | Tool filtering | Direct |

**Total**: 9 attributes, all Pydantic-serializable

---

### 1.2 Complex Serializable Attributes (⚠️ Custom Logic Required)

#### A. Subscriptions (`subscriptions: list[Subscription]`)

**Location**: `src/flock/subscription.py:94-167`

**Structure**:
```python
@dataclass
class Subscription:
    types: Sequence[type[BaseModel]] = ()  # ⚠️ Type references
    from_agents: Sequence[str] = ()  # ✅ Strings
    channels: Sequence[str] = ()  # ✅ Strings
    where: Sequence[Predicate] | None = None  # ❌ Lambdas
    join: JoinSpec | None = None  # ❌ Contains lambda
    batch: BatchSpec | None = None  # ✅ Serializable
    tags: Sequence[str] = ()  # ✅ Strings
```

**Challenges**:
1. **types**: Type references → Must use type registry to convert to strings
2. **where**: Predicates can be lambdas (31+ occurrences)
3. **join**: JoinSpec contains lambda for correlation key

**Example**:
```python
# From examples/01-cli/09_debate_club.py:48
.consumes(DebateVerdict, where=lambda r: "contra" in r.winner)
```

**Serialization Strategy**:
```python
{
    "types": ["DebateVerdict"],  # Type registry name
    "where": ["__lambda__"],  # Special marker for lambdas
    "warnings": ["Predicate contains lambda - requires re-registration"]
}
```

---

#### B. Outputs (`outputs: list[AgentOutput]`)

**Location**: `src/flock/output_utility.py:24-72`

**Structure**:
```python
@dataclass
class AgentOutput:
    spec: ArtifactSpec  # ⚠️ Contains type reference
    channel: str | None = None  # ✅ String
    visibility: Visibility | None = None  # ⚠️ Pydantic model
```

**ArtifactSpec Structure**:
```python
@dataclass
class ArtifactSpec:
    type: type[BaseModel]  # ⚠️ Type reference
    payload: BaseModel | None = None  # ⚠️ Instance
```

**Serialization Strategy**:
```python
{
    "type": "Recipe",  # Type registry name
    "channel": "recipes",
    "visibility": {"kind": "Public"}  # Pydantic model_dump()
}
```

---

#### C. MCP Server References

**Attributes**:
- `mcp_server_names: set[str]` ✅ Direct
- `mcp_server_mounts: dict[str, list[str]]` ⚠️ Requires path validation
- `mcp_mount_points: list[str]` (deprecated) ⚠️ Legacy

**Example**:
```python
agent.connect_to_mcp_servers(
    ["filesystem"],
    mounts={"filesystem": ["/workspace/data"]}
)
```

**Cross-Machine Challenge**: Paths like `/workspace/data` may not exist on target machine

**Serialization Strategy**:
```python
{
    "mcp_server_names": ["filesystem"],
    "mcp_server_mounts": {
        "filesystem": ["${WORKSPACE}/data"]  # Environment variable
    }
}
```

---

#### D. Engines (`engines: list[EngineComponent]`)

**Location**: `src/flock/engines/dspy_engine.py:113-154`

**DSPyEngine Configuration**:
```python
class DSPyEngine(EngineComponent):
    name: str | None = "dspy"
    model: str | None = None
    instructions: str | None = None
    temperature: float = 1.0
    max_tokens: int = 32000
    max_tool_calls: int = 10
    max_retries: int = 0
    stream: bool = Field(default_factory=...)  # ⚠️ Factory function
    theme: str = "afterglow"
    enable_cache: bool = False
```

**Challenge**: `stream` uses factory function (line 128)

**Serialization Strategy**: All engines inherit from Pydantic BaseModel → use `model_dump()`

```python
{
    "type": "DSPyEngine",  # Component type
    "config": {
        "name": "dspy",
        "model": "openai/gpt-4.1",
        "temperature": 0.7,
        "max_tokens": 32000,
        "stream": false  # Resolved at serialization time
    }
}
```

---

#### E. Utilities (`utilities: list[AgentComponent]`)

**Location**: `src/flock/components.py:51-90`

**Base Class**:
```python
class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    name: str | None = None
    config: AgentComponentConfig = Field(default_factory=AgentComponentConfig)

    # Lifecycle hooks (NOT serializable):
    async def on_initialize(...): pass
    async def on_pre_consume(...): pass
    async def on_pre_evaluate(...): pass
    async def on_post_evaluate(...): pass
    async def on_post_publish(...): pass
    async def on_error(...): pass
    async def on_terminate(...): pass
```

**Serialization Strategy**: Store component type + config, hooks are not serialized

```python
{
    "type": "OutputUtility",
    "config": {
        "name": "output_utility",
        "default_channel": "recipes"
    }
}
```

---

### 1.3 Non-Serializable Runtime Attributes (❌ Recreate on Load)

| Attribute | Type | Line | Purpose | Recreation Strategy |
|-----------|------|------|---------|---------------------|
| `_orchestrator` | `Flock` | 96 | Parent reference | Re-inject on `from_dict()` |
| `_semaphore` | `asyncio.Semaphore` | 104 | Concurrency control | `asyncio.Semaphore(max_concurrency)` |
| `best_of_score` | `Callable \| None` | 102 | Scoring function | Function registry lookup or `None` |
| `calls_func` | `Callable \| None` | 105 | Callback function | Function registry lookup or `None` |
| `tools` | `set[Callable]` | 106 | Tool functions | Function registry resolution |

**Total**: 5 runtime attributes that must be recreated

---

## 2. The Lambda Problem - Detailed Analysis

### 2.1 Lambda Usage Inventory

We found **31+ lambda usages** across the codebase:

#### Location 1: Subscription Predicates (`where=lambda`)

**File**: `examples/01-cli/09_debate_club.py`

**Examples**:
```python
# Line 48:
.consumes(DebateVerdict, where=lambda r: "contra" in r.winner)

# Line 62:
.consumes(DebateVerdict, where=lambda r: "pro" in r.winner)

# Line 76:
.consumes(Opinion, where=lambda o: o.stance == "pro")

# Line 90:
.consumes(Opinion, where=lambda o: o.stance == "contra")
```

**Count**: 20+ occurrences in examples

---

#### Location 2: Correlation Keys (`JoinSpec.by=lambda`)

**File**: `src/flock/subscription.py:29-57`

**Structure**:
```python
@dataclass
class JoinSpec:
    by: Callable[[BaseModel], Any]  # ❌ Lambda
    within: timedelta | int  # ✅ Serializable
```

**Example**:
```python
JoinSpec(
    by=lambda x: x.correlation_id,
    within=timedelta(minutes=5)
)
```

**Count**: 5+ occurrences

---

#### Location 3: Scoring Functions (`best_of_score=lambda`)

**File**: `src/flock/agent.py:102`

**Example**:
```python
agent = Agent(
    name="evaluator",
    best_of_n=5,
    best_of_score=lambda result: result.confidence_score
)
```

**Count**: 3+ occurrences

---

#### Location 4: Callbacks (`calls_func=lambda`)

**File**: `src/flock/agent.py:105`

**Example**:
```python
agent = Agent(
    name="notifier",
    calls_func=lambda artifact: send_notification(artifact)
)
```

**Count**: 3+ occurrences

---

### 2.2 Why Lambdas Are Hard to Serialize

#### Option 1: Pickle (❌ Security Risk)

```python
import pickle
import base64

# Serialize lambda
lambda_func = lambda x: x.id
pickled = base64.b64encode(pickle.dumps(lambda_func)).decode()

# Problem: Arbitrary code execution
class Exploit:
    def __reduce__(self):
        return (os.system, ('rm -rf /',))

pickled_exploit = pickle.dumps(Exploit())  # ❌ RCE on unpickle
```

**CVE-2025-1716**: Pickle bypass vulnerability allows remote code execution

---

#### Option 2: Source Code Inspection (⚠️ Limited)

```python
import inspect

# Works for defined functions:
def my_predicate(x):
    return x.id > 10

source = inspect.getsource(my_predicate)  # ✅ Works

# Fails for lambdas:
lambda_func = lambda x: x.id > 10
source = inspect.getsource(lambda_func)  # ❌ Raises OSError
```

**Limitation**: `inspect.getsource()` only works if source file is available

---

#### Option 3: AST Preservation (⚠️ Security Risk)

```python
import ast

# Store lambda as code string:
lambda_code = "lambda x: x.id > 10"

# Deserialize:
lambda_func = eval(lambda_code)  # ❌ Arbitrary code execution

# Example exploit:
malicious = "lambda x: __import__('os').system('rm -rf /')"
eval(malicious)  # ❌ RCE
```

**Risk**: `eval()` is as dangerous as pickle

---

#### Option 4: Function Registry (✅ Recommended)

```python
# Registry pattern:
@flock_predicate("high_confidence")
def high_confidence(x):
    return x.confidence > 0.8

# Usage:
.consumes(Result, where="high_confidence")

# Serializes as:
{"where": ["high_confidence"]}

# Deserializes:
predicate = function_registry.resolve("high_confidence")
```

**Benefits**:
- ✅ Secure (no code execution)
- ✅ Cross-machine portable
- ✅ Human-readable

**Limitation**: Requires refactoring lambdas to named functions

---

### 2.3 Recommended Lambda Handling Strategy

**Three-Tier Approach**:

**Tier 1**: Named functions with `@flock_predicate` decorator
```python
@flock_predicate("contra_winner")
def contra_winner(r: DebateVerdict) -> bool:
    return "contra" in r.winner

.consumes(DebateVerdict, where="contra_winner")  # ✅ Serializable
```

**Tier 2**: Module path references
```python
.consumes(DebateVerdict, where="myapp.predicates.contra_winner")  # ✅ Import path
```

**Tier 3**: Graceful degradation for lambdas
```python
.consumes(DebateVerdict, where=lambda r: "contra" in r.winner)

# Serializes with warning:
{
    "where": ["__lambda__"],
    "warnings": ["Predicate contains lambda - requires re-registration"]
}

# Deserializes:
subscription = Subscription(
    types=[DebateVerdict],
    where=None  # ⚠️ Predicate lost
)
# User must call: agent.add_predicate("contra_winner", lambda r: "contra" in r.winner)
```

---

## 3. Existing Serialization Patterns in Flock

### 3.1 Pydantic Model Serialization

**Usage**: Framework uses Pydantic extensively

**Example**: `src/flock/store.py:456-527`

```python
# Serialize artifact visibility
visibility_json = json.dumps(artifact.visibility.model_dump(mode="json"))

# Deserialize
from flock.visibility import PublicVisibility, PrivateVisibility
visibility_data = json.loads(visibility_json)
if visibility_data["kind"] == "Public":
    visibility = PublicVisibility()
elif visibility_data["kind"] == "Private":
    visibility = PrivateVisibility(**visibility_data)
```

**Lesson**: Use `model_dump(mode="json")` for Pydantic serialization

---

### 3.2 MCP Configuration Pattern (Reference Implementation)

**Location**: `src/flock/mcp/config.py:340-422`

**Best Practice Example**:

```python
class FlockMCPConfiguration(BaseModel):
    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Serialize the object to a dict."""
        # Step 1: Use Pydantic for simple fields
        exclude = ["connection_config", "caching_config"]
        data = self.model_dump(exclude=exclude, mode="json")

        # Step 2: Custom serialization for complex fields
        data["connection_config"] = self.connection_config.to_dict(path_type)
        data["caching_config"] = self.caching_config.to_dict()

        # Step 3: Handle environment variables
        if self.env:
            data["env"] = {k: v for k, v in self.env.items()}

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialize from dict."""
        # Step 1: Deserialize nested objects
        connection_config = FlockMCPConnectionConfiguration.from_dict(
            data["connection_config"]
        )
        caching_config = FlockMCPCachingConfiguration.from_dict(
            data.get("caching_config", {})
        )

        # Step 2: Reconstruct main object
        return cls(
            connection_config=connection_config,
            caching_config=caching_config,
            env=data.get("env"),
        )
```

**Key Insights**:
1. Use Pydantic `model_dump()` as base
2. Custom logic for non-serializable fields
3. `to_dict()` / `from_dict()` symmetry
4. Support options (e.g., `path_type="relative"`)

---

### 3.3 Type Registry Pattern

**Location**: `src/flock/registry.py:19-88`

**Implementation**:

```python
class TypeRegistry:
    _by_name: dict[str, type[BaseModel]] = {}
    _by_cls: dict[type[BaseModel], str] = {}

    @classmethod
    def register(cls, name: str, type_cls: type[BaseModel]):
        cls._by_name[name] = type_cls
        cls._by_cls[type_cls] = name

    @classmethod
    def resolve(cls, type_name: str) -> type[BaseModel]:
        return cls._by_name[type_name]

    @classmethod
    def get_name(cls, type_cls: type[BaseModel]) -> str:
        return cls._by_cls[type_cls]
```

**Usage for Serialization**:

```python
# Serialize type reference:
type_name = type_registry.get_name(DebateVerdict)  # "DebateVerdict"

# Deserialize:
type_cls = type_registry.resolve("DebateVerdict")  # <class 'DebateVerdict'>
```

**Lesson**: Already have name-to-type mapping for serialization

---

### 3.4 Function Registry Pattern

**Location**: `src/flock/registry.py:90-112`

**Implementation**:

```python
class FunctionRegistry:
    _by_name: dict[str, Callable[..., Any]] = {}

    @classmethod
    def register(cls, func: Callable[..., Any]):
        cls._by_name[func.__name__] = func

    @classmethod
    def resolve(cls, func_name: str) -> Callable[..., Any]:
        return cls._by_name[func_name]
```

**Current Limitation**: No metadata (no description, parameters, etc.)

**Recommended Enhancement**:

```python
@dataclass
class FunctionMetadata:
    name: str
    description: str
    parameters: dict[str, type]
    return_type: type

class EnhancedFunctionRegistry:
    _functions: dict[str, tuple[Callable, FunctionMetadata]] = {}

    @classmethod
    def register(cls, func: Callable, description: str = ""):
        metadata = FunctionMetadata(
            name=func.__name__,
            description=description,
            parameters=get_type_hints(func),
            return_type=get_type_hints(func).get("return", Any)
        )
        cls._functions[func.__name__] = (func, metadata)
```

---

## 4. Requirements Matrix

### 4.1 MUST Serialize (Core Functionality) - 100% Lossless

| Category | Attributes | Serialization Method | Priority |
|----------|-----------|---------------------|----------|
| **Identity** | `name`, `description` | Direct | CRITICAL |
| **Model** | `model` | Direct | CRITICAL |
| **Subscriptions** | `types`, `from_agents`, `channels`, `tags` | Type names + strings | CRITICAL |
| **Outputs** | `type`, `channel`, `visibility` | Type names + Pydantic | CRITICAL |
| **RBAC** | `labels`, `tenant_id` | Direct | HIGH |
| **MCP** | `mcp_server_names`, `mcp_server_mounts` | Strings + path resolution | HIGH |
| **Config** | `best_of_n`, `max_concurrency`, `prevent_self_trigger` | Direct | MEDIUM |

**Success Criteria**: Agent can be reconstructed with identical behavior (except lambdas)

---

### 4.2 SHOULD Serialize (Configuration) - Lossy with Warnings

| Category | Attributes | Degradation Behavior | Warning Message |
|----------|-----------|---------------------|----------------|
| **Engines** | `engines` | Use default DSPyEngine | "Custom engines not serialized" |
| **Utilities** | `utilities` | Skip utilities | "Custom utilities not serialized" |
| **Tool Whitelist** | `tool_whitelist` | All tools available | "Tool whitelist not applied" |

**Success Criteria**: Agent runs with default configuration

---

### 4.3 COULD Serialize (Lossy/Warning) - Graceful Degradation

| Category | Attributes | Strategy | Warning |
|----------|-----------|----------|---------|
| **Predicates** | `subscription.where` | Function names or drop | "Predicates require re-registration" |
| **Correlation** | `join.by` | Drop with warning | "Correlation key not serialized" |
| **Scoring** | `best_of_score` | Drop with warning | "Scoring function not serialized" |
| **Callbacks** | `calls_func` | Drop with warning | "Callback not serialized" |
| **Tools** | `tools` | Function names | "Tools require re-registration" |

**Success Criteria**: Agent loads without errors, user receives clear warnings

---

### 4.4 CANNOT Serialize (Runtime Only) - Recreate on Load

| Attribute | Recreation Strategy |
|-----------|---------------------|
| `_orchestrator` | Re-inject via `agent._orchestrator = orchestrator` |
| `_semaphore` | `asyncio.Semaphore(max_concurrency)` |
| MCP connections | Lazy-load on first tool use |

**Success Criteria**: Runtime state fully restored after first use

---

## 5. Cross-Machine Portability Requirements

### 5.1 Environment-Specific Elements

#### Challenge 1: File Paths in MCP Mounts

**Problem**:
```python
mcp_server_mounts = {
    "filesystem": ["/home/user/workspace/data"]  # ❌ Machine-specific
}
```

**Solution**: Environment variable substitution
```python
mcp_server_mounts = {
    "filesystem": ["${WORKSPACE}/data"]  # ✅ Portable
}

# On load:
import os
resolved = path.replace("${WORKSPACE}", os.environ["WORKSPACE"])
```

---

#### Challenge 2: MCP Server Availability

**Problem**:
```yaml
mcp_server_names: [filesystem, postgres, custom_server]
```

**Solution**: Graceful degradation
```python
# On load:
for server_name in config["mcp_server_names"]:
    try:
        orchestrator.register_mcp_server(server_name)
    except MCPServerNotFound:
        warnings.append(f"MCP server '{server_name}' not available")
```

---

#### Challenge 3: Model Availability

**Problem**:
```yaml
model: openai/gpt-4.1  # May not be available on target machine
```

**Solution**: Fail with clear error
```python
# On load:
try:
    validate_model_availability(config["model"])
except ModelNotAvailable as e:
    raise SerializationError(
        f"Model '{config['model']}' not available. "
        f"Available models: {list_available_models()}"
    )
```

---

### 5.2 Dependency Requirements

**Required for Deserialization**:
```yaml
dependencies:
  flock_version: "0.2.0"
  pydantic_version: "2.x"
  python_version: "3.12"
  optional:
    - dspy  # For DSPyEngine
    - mcp  # For MCP integration
```

**Validation on Load**:
```python
def validate_dependencies(config: dict) -> list[str]:
    warnings = []

    if config["flock_version"] != __version__:
        warnings.append(f"Config for v{config['flock_version']}, running v{__version__}")

    if "dspy" in config["optional"] and not is_dspy_available():
        warnings.append("DSPy not installed - engines may not work")

    return warnings
```

---

### 5.3 Security Considerations

#### Risk 1: Code Injection via Lambdas

**Mitigation**: Never eval/exec deserialized code

```python
# ❌ NEVER DO THIS:
lambda_code = config["predicate"]
predicate = eval(lambda_code)  # Code injection vulnerability

# ✅ DO THIS:
predicate_name = config["predicate"]
predicate = function_registry.resolve(predicate_name)  # Safe
```

---

#### Risk 2: Path Traversal in MCP Mounts

**Mitigation**: Validate mount paths against allowlist

```python
ALLOWED_MOUNT_ROOTS = ["/workspace", "/data", "/tmp"]

def validate_mount_path(path: str) -> bool:
    resolved = os.path.realpath(path)
    return any(resolved.startswith(root) for root in ALLOWED_MOUNT_ROOTS)
```

---

#### Risk 3: Credential Leakage in Model Strings

**Mitigation**: Strip credentials from model strings

```python
# ❌ NEVER SERIALIZE:
model = "openai/gpt-4:sk-1234567890abcdef"

# ✅ SERIALIZE:
model = "openai/gpt-4"

# Credentials via environment:
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
```

---

## 6. Recommended Serialization Architecture

### 6.1 Three-Tier Approach

**Tier 1: Core Configuration** (Always serialize, 100% lossless)

```yaml
name: pizza_chef
description: Creates pizza recipes
model: openai/gpt-4.1
labels: [chef, food]
tenant_id: restaurant-123
prevent_self_trigger: true
```

---

**Tier 2: Extended Configuration** (Serialize with warnings)

```yaml
subscriptions:
  - types: [Idea]
    from_agents: [customer]
    where: [is_valid_idea]  # ⚠️ Function registry reference
    channels: [pizza_requests]

outputs:
  - type: Recipe
    channel: recipes
    visibility:
      kind: Public

engines:
  - type: DSPyEngine
    config:
      model: openai/gpt-4.1
      temperature: 0.7

utilities:
  - type: OutputUtility
    config:
      default_channel: recipes
```

---

**Tier 3: Runtime References** (Don't serialize, recreate)

```python
# Not in serialized format:
# - _orchestrator (injected on load)
# - _semaphore (recreated from max_concurrency)
# - MCP connections (lazy-loaded on demand)
```

---

### 6.2 Serialization API Design

#### Method 1: `to_dict()` / `from_dict()`

```python
class Agent:
    def to_dict(self, include_warnings: bool = True) -> dict[str, Any]:
        """Serialize agent to dictionary."""
        data = {
            "name": self.name,
            "description": self.description,
            "model": self.model,
            # ... core attributes
        }

        # Serialize subscriptions
        data["subscriptions"] = [
            self._serialize_subscription(sub)
            for sub in self.subscriptions
        ]

        # Add warnings for non-serializable elements
        if include_warnings:
            data["warnings"] = self._collect_warnings()

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], orchestrator: Flock | None = None) -> Agent:
        """Deserialize agent from dictionary."""
        # Reconstruct agent
        agent = cls(
            name=data["name"],
            description=data["description"],
            model=data["model"],
            # ... core attributes
        )

        # Deserialize subscriptions
        for sub_data in data.get("subscriptions", []):
            agent.subscriptions.append(
                cls._deserialize_subscription(sub_data)
            )

        # Re-inject orchestrator
        if orchestrator:
            agent._orchestrator = orchestrator

        return agent
```

---

#### Method 2: `to_yaml()` / `from_yaml()`

```python
import yaml

class Agent:
    def to_yaml(self, file_path: str | None = None) -> str:
        """Serialize agent to YAML."""
        data = self.to_dict()
        yaml_content = yaml.dump(data, default_flow_style=False)

        if file_path:
            with open(file_path, "w") as f:
                f.write(yaml_content)

        return yaml_content

    @classmethod
    def from_yaml(cls, yaml_content: str | None = None, file_path: str | None = None) -> Agent:
        """Deserialize agent from YAML."""
        if file_path:
            with open(file_path) as f:
                yaml_content = f.read()

        data = yaml.safe_load(yaml_content)  # ✅ Safe from code injection
        return cls.from_dict(data)
```

---

### 6.3 Migration from v0.4 (Pickle-Based)

**Create Migration Tool**: `flock-migrate`

```python
def migrate_v04_to_v02(old_yaml_path: str, new_yaml_path: str):
    """Migrate Flock v0.4 YAML to v0.2+ format."""
    # Step 1: Load old format (with pickle)
    with open(old_yaml_path) as f:
        old_data = yaml.unsafe_load(f)  # ⚠️ Unsafe for old format

    # Step 2: Extract serializable data
    new_data = {
        "name": old_data["name"],
        "description": old_data["description"],
        # ... extract what we can
    }

    # Step 3: Add warnings for lost data
    new_data["warnings"] = [
        "Tools not migrated - requires re-registration",
        "Predicates not migrated - requires re-registration"
    ]

    # Step 4: Save new format
    with open(new_yaml_path, "w") as f:
        yaml.dump(new_data, f)

    print(f"✅ Migrated {old_yaml_path} → {new_yaml_path}")
    print(f"⚠️  Manual steps required: {new_data['warnings']}")
```

---

## 7. Implementation Checklist

### Phase 1: Basic Serialization (Core Attributes)
- [ ] Implement `Agent.to_dict()` method
- [ ] Implement `Agent.from_dict()` class method
- [ ] Handle type registry name resolution
- [ ] Test round-trip serialization (agent → dict → agent)

### Phase 2: Complex Types (Subscriptions, Outputs)
- [ ] Custom serialization for `Subscription` (handle lambdas)
- [ ] Custom serialization for `AgentOutput` (ArtifactSpec)
- [ ] Visibility policy serialization
- [ ] Test subscription matching after deserialization

### Phase 3: Components (Engines, Utilities)
- [ ] Component type registry (DSPyEngine, OutputUtility, etc.)
- [ ] Serialize component configuration
- [ ] Handle default components
- [ ] Test component lifecycle after deserialization

### Phase 4: YAML Support
- [ ] Implement `to_yaml()` / `from_yaml()` convenience methods
- [ ] Environment variable substitution
- [ ] Path resolution (relative/absolute)
- [ ] Test cross-machine portability

### Phase 5: Migration Tools
- [ ] Create `flock-migrate` CLI tool
- [ ] Deprecation warnings for pickle usage
- [ ] Documentation: "Migrating from v0.4"
- [ ] Convert examples to new format

### Phase 6: Testing
- [ ] Unit tests: Round-trip serialization
- [ ] Integration tests: Cross-machine transfer
- [ ] Edge cases: Missing dependencies, lambdas
- [ ] Security tests: Code injection attempts

---

## 8. Conclusion

The Flock framework has **excellent serialization foundations**:
- ✅ Pydantic everywhere
- ✅ Type registry for name resolution
- ✅ Function registry for tool resolution
- ✅ MCP config pattern as reference

**Main Challenges**:
- ⚠️ Lambda functions (31+ usages)
- ⚠️ Runtime state (semaphores, connections)
- ⚠️ Cross-machine dependencies (MCP servers, models)

**Recommended Strategy**: Three-tier serialization (core + extended + runtime) with graceful degradation for lambdas, following the MCP config `to_dict()` / `from_dict()` pattern.

**Timeline**: 2-3 weeks for complete implementation (Phase 1-4)

---

**Next Steps**:
1. Review this analysis with team
2. Decide on lambda handling strategy
3. Implement Phase 1 (basic serialization)
4. Test cross-machine portability
