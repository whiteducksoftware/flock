# Flock Agent Serialization: Implementation Strategy

**Date**: 2025-10-13
**Target Version**: v0.2+
**Implementation Timeline**: 2-3 weeks (3 phases)

---

## 🎯 Executive Summary

This document provides a **step-by-step implementation roadmap** for adding agent serialization to Flock using the **YAML + Pydantic + Function Registry** pattern.

**Goals**:
- ✅ Secure serialization (no pickle vulnerabilities)
- ✅ Human-readable YAML configuration
- ✅ Cross-machine portability
- ✅ Backward compatibility (non-breaking changes)

**Timeline**: 3 phases over 2-3 weeks

---

## 📋 Phase 1: Basic Serialization (Week 1)

### Goals
- Add `to_dict()` / `from_dict()` methods
- Handle simple attributes
- Type registry integration
- Round-trip testing

---

### Task 1.1: Define Pydantic Schemas (1 day)

**Create**: `src/flock/serialization.py` (NEW file)

```python
"""Agent serialization schemas and utilities."""

from pydantic import BaseModel, Field
from typing import Any


class VisibilityConfig(BaseModel):
    """Serializable visibility configuration."""
    kind: str
    agents: list[str] | None = None
    required_labels: list[str] | None = None
    tenant_id: str | None = None
    ttl_seconds: float | None = None
    then: "VisibilityConfig | None" = None


class SubscriptionConfig(BaseModel):
    """Serializable subscription configuration."""
    types: list[str]  # Type names from registry
    from_agents: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    where: list[str] = Field(default_factory=list)  # Function names
    tags: list[str] = Field(default_factory=list)
    join: dict[str, Any] | None = None  # JoinSpec serialization
    batch: dict[str, Any] | None = None  # BatchSpec serialization


class AgentOutputConfig(BaseModel):
    """Serializable agent output configuration."""
    type: str  # Type name from registry
    channel: str | None = None
    visibility: VisibilityConfig | None = None


class ComponentConfig(BaseModel):
    """Generic component configuration."""
    type: str  # Component class name
    config: dict[str, Any]  # Component-specific config


class AgentConfig(BaseModel):
    """Complete agent configuration for serialization."""
    # Core identity
    name: str
    description: str | None = None
    model: str | None = None

    # Subscriptions and outputs
    subscriptions: list[SubscriptionConfig] = Field(default_factory=list)
    outputs: list[AgentOutputConfig] = Field(default_factory=list)

    # Configuration
    best_of_n: int = 1
    max_concurrency: int = 2
    prevent_self_trigger: bool = False

    # RBAC
    labels: list[str] = Field(default_factory=list)
    tenant_id: str | None = None

    # MCP integration
    mcp_server_names: list[str] = Field(default_factory=list)
    mcp_server_mounts: dict[str, list[str]] = Field(default_factory=dict)
    tool_whitelist: list[str] | None = None

    # Components
    engines: list[ComponentConfig] = Field(default_factory=list)
    utilities: list[ComponentConfig] = Field(default_factory=list)

    # Metadata
    warnings: list[str] = Field(default_factory=list)


class FlockConfig(BaseModel):
    """Complete orchestrator configuration."""
    agents: list[AgentConfig]
    mcp_servers: dict[str, dict[str, Any]]
    version: str = "0.2.0"
```

**Tests**: `tests/test_serialization_schemas.py`

```python
def test_agent_config_schema():
    """Test AgentConfig Pydantic schema."""
    config = AgentConfig(
        name="test_agent",
        description="A test agent",
        model="openai/gpt-4",
        subscriptions=[
            SubscriptionConfig(types=["TestType"], channels=["test"])
        ],
    )

    # Should serialize to dict
    data = config.model_dump()
    assert data["name"] == "test_agent"

    # Should deserialize from dict
    config2 = AgentConfig(**data)
    assert config2.name == "test_agent"
```

---

### Task 1.2: Implement `Agent.to_dict()` (2 days)

**Modify**: `src/flock/agent.py`

```python
from flock.serialization import AgentConfig, SubscriptionConfig, AgentOutputConfig, ComponentConfig
from flock.registry import type_registry, function_registry


class Agent:
    # ... existing code ...

    def to_dict(self, include_warnings: bool = True) -> dict[str, Any]:
        """
        Serialize agent to dictionary.

        Args:
            include_warnings: Whether to include warnings about non-serializable elements

        Returns:
            Dictionary representation of agent configuration

        Example:
            >>> agent = Agent(name="my_agent", description="Test agent")
            >>> config = agent.to_dict()
            >>> print(config["name"])
            'my_agent'
        """
        warnings = []

        # Serialize subscriptions
        subscription_configs = []
        for sub in self.subscriptions:
            sub_config = self._serialize_subscription(sub, warnings)
            subscription_configs.append(sub_config)

        # Serialize outputs
        output_configs = []
        for output in self.outputs:
            output_config = self._serialize_output(output, warnings)
            output_configs.append(output_config)

        # Serialize engines
        engine_configs = []
        for engine in self.engines:
            engine_config = ComponentConfig(
                type=engine.__class__.__name__,
                config=engine.model_dump(exclude={"name"})
            )
            engine_configs.append(engine_config)

        # Serialize utilities
        utility_configs = []
        for utility in self.utilities:
            utility_config = ComponentConfig(
                type=utility.__class__.__name__,
                config=utility.model_dump(exclude={"name"})
            )
            utility_configs.append(utility_config)

        # Create AgentConfig
        config = AgentConfig(
            name=self.name,
            description=self.description,
            model=self.model,
            subscriptions=[s.model_dump() for s in subscription_configs],
            outputs=[o.model_dump() for o in output_configs],
            best_of_n=self.best_of_n,
            max_concurrency=self.max_concurrency,
            prevent_self_trigger=self.prevent_self_trigger,
            labels=list(self.labels),
            tenant_id=self.tenant_id,
            mcp_server_names=list(self.mcp_server_names),
            mcp_server_mounts=dict(self.mcp_server_mounts),
            tool_whitelist=self.tool_whitelist,
            engines=[e.model_dump() for e in engine_configs],
            utilities=[u.model_dump() for u in utility_configs],
            warnings=warnings if include_warnings else [],
        )

        return config.model_dump()

    def _serialize_subscription(
        self, sub: Subscription, warnings: list[str]
    ) -> SubscriptionConfig:
        """Serialize a single subscription."""
        # Convert types to names
        type_names = []
        for type_cls in sub.types:
            try:
                name = type_registry.get_name(type_cls)
                type_names.append(name)
            except KeyError:
                warnings.append(f"Type {type_cls.__name__} not registered")

        # Convert predicates to function names
        where_names = []
        if sub.where:
            for predicate in sub.where:
                if callable(predicate):
                    try:
                        # Try to get function name
                        name = predicate.__name__
                        if name == "<lambda>":
                            warnings.append(
                                "Lambda predicate not serializable - "
                                "requires re-registration"
                            )
                            where_names.append("__lambda__")
                        else:
                            where_names.append(name)
                    except AttributeError:
                        warnings.append("Predicate has no __name__ attribute")

        # Handle JoinSpec
        join_config = None
        if sub.join:
            join_config = {
                "within_seconds": sub.join.within.total_seconds()
                if isinstance(sub.join.within, timedelta)
                else sub.join.within
            }
            # Lambda in 'by' cannot be serialized
            warnings.append(
                "JoinSpec correlation key (by) not serializable - "
                "requires re-registration"
            )

        # Handle BatchSpec
        batch_config = None
        if sub.batch:
            batch_config = {
                "size": sub.batch.size,
                "timeout_seconds": sub.batch.timeout.total_seconds()
                if sub.batch.timeout
                else None,
            }

        return SubscriptionConfig(
            types=type_names,
            from_agents=list(sub.from_agents),
            channels=list(sub.channels),
            where=where_names,
            tags=list(sub.tags),
            join=join_config,
            batch=batch_config,
        )

    def _serialize_output(
        self, output: AgentOutput, warnings: list[str]
    ) -> AgentOutputConfig:
        """Serialize a single output."""
        # Get type name
        try:
            type_name = type_registry.get_name(output.spec.type)
        except KeyError:
            warnings.append(f"Output type {output.spec.type.__name__} not registered")
            type_name = output.spec.type.__name__

        # Serialize visibility
        visibility_config = None
        if output.visibility:
            visibility_config = VisibilityConfig(
                **output.visibility.model_dump(mode="json")
            )

        return AgentOutputConfig(
            type=type_name,
            channel=output.channel,
            visibility=visibility_config,
        )
```

**Tests**: `tests/test_agent_serialization.py`

```python
def test_agent_to_dict_basic():
    """Test basic agent serialization."""
    agent = Agent(
        name="test_agent",
        description="Test description",
        model="openai/gpt-4",
    )

    config = agent.to_dict()

    assert config["name"] == "test_agent"
    assert config["description"] == "Test description"
    assert config["model"] == "openai/gpt-4"


def test_agent_to_dict_with_subscriptions():
    """Test agent serialization with subscriptions."""
    @flock_type("TestType")
    class TestType(BaseModel):
        value: str

    agent = Agent(name="test").consumes(TestType, channels=["test"])

    config = agent.to_dict()

    assert len(config["subscriptions"]) == 1
    assert config["subscriptions"][0]["types"] == ["TestType"]
    assert config["subscriptions"][0]["channels"] == ["test"]


def test_agent_to_dict_with_lambda_warning():
    """Test that lambdas generate warnings."""
    @flock_type("TestType")
    class TestType(BaseModel):
        value: int

    agent = Agent(name="test").consumes(
        TestType, where=lambda x: x.value > 10
    )

    config = agent.to_dict()

    assert any("lambda" in w.lower() for w in config["warnings"])
```

---

### Task 1.3: Implement `Agent.from_dict()` (2 days)

**Modify**: `src/flock/agent.py`

```python
class Agent:
    # ... existing code ...

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        orchestrator: Flock | None = None,
        strict: bool = False,
    ) -> "Agent":
        """
        Deserialize agent from dictionary.

        Args:
            data: Dictionary representation from to_dict()
            orchestrator: Optional orchestrator to inject
            strict: If True, raise errors for missing functions/types

        Returns:
            Reconstructed Agent instance

        Raises:
            SerializationError: If strict=True and required elements missing

        Example:
            >>> config = {"name": "my_agent", "description": "Test"}
            >>> agent = Agent.from_dict(config)
            >>> print(agent.name)
            'my_agent'
        """
        # Validate with Pydantic
        config = AgentConfig(**data)

        # Create base agent
        agent = cls(
            name=config.name,
            description=config.description,
            model=config.model,
            best_of_n=config.best_of_n,
            max_concurrency=config.max_concurrency,
            prevent_self_trigger=config.prevent_self_trigger,
            labels=set(config.labels),
            tenant_id=config.tenant_id,
            tool_whitelist=config.tool_whitelist,
        )

        # Deserialize subscriptions
        for sub_config in config.subscriptions:
            subscription = cls._deserialize_subscription(sub_config, strict)
            agent.subscriptions.append(subscription)

        # Deserialize outputs
        for output_config in config.outputs:
            output = cls._deserialize_output(output_config, strict)
            agent.outputs.append(output)

        # Deserialize engines
        for engine_config in config.engines:
            engine = cls._deserialize_component(engine_config, strict)
            if engine:
                agent.engines.append(engine)

        # Deserialize utilities
        for utility_config in config.utilities:
            utility = cls._deserialize_component(utility_config, strict)
            if utility:
                agent.utilities.append(utility)

        # MCP integration
        agent.mcp_server_names = set(config.mcp_server_names)
        agent.mcp_server_mounts = dict(config.mcp_server_mounts)

        # Re-inject orchestrator
        if orchestrator:
            agent._orchestrator = orchestrator

        # Recreate semaphore
        agent._semaphore = asyncio.Semaphore(agent.max_concurrency)

        return agent

    @classmethod
    def _deserialize_subscription(
        cls, sub_config: SubscriptionConfig, strict: bool
    ) -> Subscription:
        """Deserialize a single subscription."""
        # Resolve types
        types = []
        for type_name in sub_config.types:
            try:
                type_cls = type_registry.resolve(type_name)
                types.append(type_cls)
            except KeyError:
                if strict:
                    raise SerializationError(f"Type '{type_name}' not registered")
                logger.warning(f"Type '{type_name}' not registered, skipping")

        # Resolve predicates
        where = []
        for func_name in sub_config.where:
            if func_name == "__lambda__":
                logger.warning("Lambda predicate requires manual re-registration")
                continue
            try:
                func = function_registry.resolve(func_name)
                where.append(func)
            except KeyError:
                if strict:
                    raise SerializationError(f"Function '{func_name}' not registered")
                logger.warning(f"Function '{func_name}' not registered, skipping")

        # Reconstruct JoinSpec
        join = None
        if sub_config.join:
            logger.warning("JoinSpec correlation key requires manual re-registration")
            # Can only partially reconstruct
            join = JoinSpec(
                by=lambda x: None,  # Placeholder
                within=timedelta(seconds=sub_config.join["within_seconds"]),
            )

        # Reconstruct BatchSpec
        batch = None
        if sub_config.batch:
            batch = BatchSpec(
                size=sub_config.batch["size"],
                timeout=timedelta(seconds=sub_config.batch["timeout_seconds"])
                if sub_config.batch.get("timeout_seconds")
                else None,
            )

        return Subscription(
            types=types,
            from_agents=sub_config.from_agents,
            channels=sub_config.channels,
            where=where if where else None,
            tags=sub_config.tags,
            join=join,
            batch=batch,
        )

    @classmethod
    def _deserialize_output(
        cls, output_config: AgentOutputConfig, strict: bool
    ) -> AgentOutput:
        """Deserialize a single output."""
        # Resolve type
        try:
            type_cls = type_registry.resolve(output_config.type)
        except KeyError:
            if strict:
                raise SerializationError(f"Type '{output_config.type}' not registered")
            logger.warning(f"Type '{output_config.type}' not registered")
            type_cls = BaseModel  # Fallback

        # Deserialize visibility
        visibility = None
        if output_config.visibility:
            visibility = cls._deserialize_visibility(output_config.visibility)

        return AgentOutput(
            spec=ArtifactSpec(type=type_cls),
            channel=output_config.channel,
            visibility=visibility,
        )

    @classmethod
    def _deserialize_visibility(cls, vis_config: VisibilityConfig) -> Visibility:
        """Deserialize visibility policy."""
        kind = vis_config.kind

        if kind == "Public":
            return PublicVisibility()
        elif kind == "Private":
            return PrivateVisibility(agents=set(vis_config.agents or []))
        elif kind == "Labelled":
            return LabelledVisibility(
                required_labels=set(vis_config.required_labels or [])
            )
        elif kind == "Tenant":
            return TenantVisibility(tenant_id=vis_config.tenant_id)
        elif kind == "After":
            then_vis = cls._deserialize_visibility(vis_config.then)
            return AfterVisibility(
                ttl=timedelta(seconds=vis_config.ttl_seconds), then=then_vis
            )
        else:
            raise SerializationError(f"Unknown visibility kind: {kind}")

    @classmethod
    def _deserialize_component(
        cls, comp_config: ComponentConfig, strict: bool
    ) -> AgentComponent | None:
        """Deserialize a component instance."""
        # TODO: Implement component registry
        logger.warning(f"Component deserialization not yet implemented: {comp_config.type}")
        return None
```

**Tests**: `tests/test_agent_deserialization.py`

```python
def test_agent_from_dict_basic():
    """Test basic agent deserialization."""
    config = {
        "name": "test_agent",
        "description": "Test description",
        "model": "openai/gpt-4",
    }

    agent = Agent.from_dict(config)

    assert agent.name == "test_agent"
    assert agent.description == "Test description"
    assert agent.model == "openai/gpt-4"


def test_agent_round_trip():
    """Test agent serialization round-trip."""
    @flock_type("TestType")
    class TestType(BaseModel):
        value: str

    agent1 = Agent(name="test", description="Test agent")
    agent1.consumes(TestType, channels=["test"])

    config = agent1.to_dict()
    agent2 = Agent.from_dict(config)

    assert agent2.name == agent1.name
    assert agent2.description == agent1.description
    assert len(agent2.subscriptions) == len(agent1.subscriptions)
```

---

## 📋 Phase 2: YAML Support (Week 2)

### Task 2.1: Add YAML Methods (1 day)

**Modify**: `src/flock/agent.py`

```python
import yaml


class Agent:
    # ... existing code ...

    def to_yaml(self, file_path: str | None = None) -> str:
        """
        Serialize agent to YAML format.

        Args:
            file_path: Optional path to save YAML file

        Returns:
            YAML string representation

        Example:
            >>> agent = Agent(name="my_agent")
            >>> yaml_str = agent.to_yaml("agent.yaml")
            >>> print(yaml_str)
            name: my_agent
            ...
        """
        data = self.to_dict()
        yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)

        if file_path:
            with open(file_path, "w") as f:
                f.write(yaml_content)

        return yaml_content

    @classmethod
    def from_yaml(
        cls,
        yaml_content: str | None = None,
        file_path: str | None = None,
        orchestrator: Flock | None = None,
        strict: bool = False,
    ) -> "Agent":
        """
        Deserialize agent from YAML format.

        Args:
            yaml_content: YAML string (if not using file_path)
            file_path: Path to YAML file (if not using yaml_content)
            orchestrator: Optional orchestrator to inject
            strict: If True, raise errors for missing functions/types

        Returns:
            Reconstructed Agent instance

        Example:
            >>> agent = Agent.from_yaml(file_path="agent.yaml")
            >>> print(agent.name)
            'my_agent'
        """
        if file_path:
            with open(file_path) as f:
                yaml_content = f.read()

        if yaml_content is None:
            raise ValueError("Must provide either yaml_content or file_path")

        # Use safe_load to prevent code injection
        data = yaml.safe_load(yaml_content)

        return cls.from_dict(data, orchestrator=orchestrator, strict=strict)
```

**Tests**: `tests/test_yaml_serialization.py`

```python
def test_agent_to_yaml():
    """Test agent YAML serialization."""
    agent = Agent(name="test_agent", description="Test")

    yaml_str = agent.to_yaml()

    assert "name: test_agent" in yaml_str
    assert "description: Test" in yaml_str


def test_agent_from_yaml_file(tmp_path):
    """Test agent deserialization from YAML file."""
    yaml_content = """
name: test_agent
description: Test agent
model: openai/gpt-4
labels: [chef, food]
    """

    file_path = tmp_path / "agent.yaml"
    file_path.write_text(yaml_content)

    agent = Agent.from_yaml(file_path=str(file_path))

    assert agent.name == "test_agent"
    assert agent.model == "openai/gpt-4"
    assert "chef" in agent.labels


def test_yaml_round_trip(tmp_path):
    """Test YAML round-trip."""
    agent1 = Agent(name="test", description="Test", model="gpt-4")

    file_path = tmp_path / "agent.yaml"
    agent1.to_yaml(file_path=str(file_path))

    agent2 = Agent.from_yaml(file_path=str(file_path))

    assert agent2.name == agent1.name
    assert agent2.model == agent1.model
```

---

### Task 2.2: Environment Variable Substitution (1 day)

**Create**: `src/flock/serialization_utils.py`

```python
"""Utilities for serialization."""

import os
import re
from pathlib import Path


def resolve_env_vars(value: str) -> str:
    """
    Resolve environment variables in string.

    Supports formats:
    - ${VAR_NAME}
    - ${VAR_NAME:-default_value}

    Example:
        >>> os.environ["WORKSPACE"] = "/home/user/workspace"
        >>> resolve_env_vars("${WORKSPACE}/data")
        '/home/user/workspace/data'
    """
    def replacer(match):
        var_expr = match.group(1)

        # Handle default values: ${VAR:-default}
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.environ.get(var_name, default)
        else:
            return os.environ.get(var_expr, match.group(0))

    return re.sub(r"\$\{([^}]+)\}", replacer, value)


def resolve_paths(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively resolve environment variables in all string values.

    Example:
        >>> data = {"mcp_server_mounts": {"fs": ["${WORKSPACE}/data"]}}
        >>> resolved = resolve_paths(data)
        >>> print(resolved["mcp_server_mounts"]["fs"][0])
        '/home/user/workspace/data'
    """
    if isinstance(data, dict):
        return {k: resolve_paths(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_paths(item) for item in data]
    elif isinstance(data, str):
        return resolve_env_vars(data)
    else:
        return data
```

**Modify**: `Agent.from_dict()` to use `resolve_paths()`

```python
@classmethod
def from_dict(cls, data: dict[str, Any], ...) -> "Agent":
    # Resolve environment variables
    from flock.serialization_utils import resolve_paths
    data = resolve_paths(data)

    # ... rest of deserialization
```

**Tests**: `tests/test_serialization_utils.py`

```python
def test_resolve_env_vars():
    """Test environment variable resolution."""
    os.environ["TEST_VAR"] = "/test/path"

    result = resolve_env_vars("${TEST_VAR}/data")

    assert result == "/test/path/data"


def test_resolve_env_vars_with_default():
    """Test environment variable with default value."""
    result = resolve_env_vars("${NONEXISTENT_VAR:-/default/path}")

    assert result == "/default/path"


def test_resolve_paths_recursive():
    """Test recursive path resolution."""
    os.environ["WORKSPACE"] = "/workspace"

    data = {
        "mcp_server_mounts": {
            "filesystem": ["${WORKSPACE}/data", "${WORKSPACE}/cache"]
        }
    }

    resolved = resolve_paths(data)

    assert resolved["mcp_server_mounts"]["filesystem"][0] == "/workspace/data"
    assert resolved["mcp_server_mounts"]["filesystem"][1] == "/workspace/cache"
```

---

### Task 2.3: Function Registry Enhancements (2 days)

**Modify**: `src/flock/registry.py`

```python
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


@dataclass
class FunctionMetadata:
    """Metadata for registered functions."""
    name: str
    description: str
    parameters: dict[str, type]
    return_type: type
    tags: list[str]


class EnhancedFunctionRegistry:
    """Enhanced function registry with metadata."""

    _functions: dict[str, tuple[Callable, FunctionMetadata]] = {}

    @classmethod
    def register(
        cls,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """
        Register a function with metadata.

        Can be used as decorator:
            @register(description="My function")
            def my_func(x: int) -> bool:
                return x > 0

        Or directly:
            register(my_func, description="My function")
        """
        def decorator(f: Callable):
            func_name = name or f.__name__
            hints = get_type_hints(f) if hasattr(f, "__annotations__") else {}

            metadata = FunctionMetadata(
                name=func_name,
                description=description,
                parameters={k: v for k, v in hints.items() if k != "return"},
                return_type=hints.get("return", Any),
                tags=tags or [],
            )

            cls._functions[func_name] = (f, metadata)
            return f

        if func is None:
            return decorator
        else:
            return decorator(func)

    @classmethod
    def resolve(cls, func_name: str) -> Callable:
        """Resolve function by name."""
        if func_name not in cls._functions:
            raise KeyError(f"Function '{func_name}' not registered")
        return cls._functions[func_name][0]

    @classmethod
    def get_metadata(cls, func_name: str) -> FunctionMetadata:
        """Get function metadata."""
        if func_name not in cls._functions:
            raise KeyError(f"Function '{func_name}' not registered")
        return cls._functions[func_name][1]

    @classmethod
    def list_functions(cls, tag: str | None = None) -> list[str]:
        """List all registered functions, optionally filtered by tag."""
        if tag is None:
            return list(cls._functions.keys())
        return [
            name
            for name, (_, metadata) in cls._functions.items()
            if tag in metadata.tags
        ]


# Create global instance
function_registry = EnhancedFunctionRegistry()


# Convenience decorator
def flock_predicate(name: str | None = None, description: str = ""):
    """
    Decorator to register a predicate function.

    Example:
        @flock_predicate("high_confidence", "Filters high-confidence results")
        def high_confidence(x: Result) -> bool:
            return x.confidence > 0.8

        # Usage:
        .consumes(Result, where="high_confidence")
    """
    return function_registry.register(name=name, description=description, tags=["predicate"])
```

**Tests**: `tests/test_function_registry.py`

```python
def test_function_registry_decorator():
    """Test function registry with decorator."""
    @flock_predicate("test_pred", "A test predicate")
    def test_pred(x: int) -> bool:
        return x > 0

    func = function_registry.resolve("test_pred")
    assert func(10) is True
    assert func(-5) is False


def test_function_metadata():
    """Test function metadata retrieval."""
    @flock_predicate("test_pred", "A test predicate")
    def test_pred(x: int) -> bool:
        return x > 0

    metadata = function_registry.get_metadata("test_pred")
    assert metadata.name == "test_pred"
    assert metadata.description == "A test predicate"
    assert "predicate" in metadata.tags


def test_list_functions_by_tag():
    """Test listing functions by tag."""
    @flock_predicate("pred1")
    def pred1(x: int) -> bool:
        return True

    @function_registry.register(tags=["tool"])
    def tool1():
        pass

    predicates = function_registry.list_functions(tag="predicate")
    assert "pred1" in predicates
    assert "tool1" not in predicates
```

---

## 📋 Phase 3: Migration & Polish (Week 3)

### Task 3.1: Migration CLI Tool (2 days)

**Create**: `src/flock/cli/migrate.py`

```python
"""Migration tool for Flock v0.4 to v0.2+ serialization."""

import click
import yaml
from pathlib import Path


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option("--force", is_flag=True, help="Overwrite output file if exists")
def migrate(input_file: str, output_file: str, force: bool):
    """
    Migrate Flock v0.4 agent YAML to v0.2+ format.

    This tool converts pickle-based serialization to Pydantic-based format.

    Example:
        flock-migrate old_agent.yaml new_agent.yaml
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    if output_path.exists() and not force:
        click.echo(f"Error: {output_path} already exists. Use --force to overwrite.")
        return

    click.echo(f"Migrating {input_path} → {output_path}")

    try:
        # Load old format (UNSAFE - only for migration)
        with open(input_path) as f:
            old_data = yaml.unsafe_load(f)  # ⚠️ Required for pickle

        # Extract serializable data
        new_data = extract_serializable(old_data)

        # Save new format
        with open(output_path, "w") as f:
            yaml.dump(new_data, f, default_flow_style=False)

        click.echo(f"✅ Migration complete!")

        # Print warnings
        if new_data.get("warnings"):
            click.echo("\n⚠️  Manual steps required:")
            for warning in new_data["warnings"]:
                click.echo(f"  - {warning}")

    except Exception as e:
        click.echo(f"❌ Migration failed: {e}")


def extract_serializable(old_data: dict) -> dict:
    """Extract serializable data from v0.4 format."""
    warnings = []

    # Basic fields
    new_data = {
        "name": old_data.get("name"),
        "description": old_data.get("description"),
        "model": old_data.get("model"),
    }

    # Warn about tools
    if "_tools" in old_data:
        warnings.append("Tools not migrated - requires re-registration")

    # Warn about predicates
    if "_predicates" in old_data:
        warnings.append("Predicates not migrated - requires re-registration")

    new_data["warnings"] = warnings
    return new_data


if __name__ == "__main__":
    migrate()
```

**Setup**: Add to `pyproject.toml`

```toml
[project.scripts]
flock-migrate = "flock.cli.migrate:migrate"
```

---

### Task 3.2: Documentation (1 day)

**Create**: `docs/guides/agent-serialization.md`

```markdown
# Agent Serialization Guide

## Overview

Flock supports serializing agents to YAML format for cross-machine portability.

## Basic Usage

### Save Agent to YAML

\`\`\`python
from flock import Agent

agent = Agent(name="pizza_chef", description="Creates pizza recipes")
agent.to_yaml("pizza_chef.yaml")
\`\`\`

### Load Agent from YAML

\`\`\`python
agent = Agent.from_yaml("pizza_chef.yaml")
\`\`\`

## Advanced Features

### Environment Variables

Use `${VAR_NAME}` syntax for portability:

\`\`\`yaml
mcp_server_mounts:
  filesystem:
    - ${WORKSPACE}/data
    - ${HOME}/.cache/flock
\`\`\`

### Function Registry

Register predicates for serialization:

\`\`\`python
from flock.registry import flock_predicate

@flock_predicate("high_confidence")
def high_confidence(result: Result) -> bool:
    return result.confidence > 0.8

# Usage:
agent.consumes(Result, where="high_confidence")
\`\`\`

## Migration from v0.4

Use the migration tool:

\`\`\`bash
flock-migrate old_agent.yaml new_agent.yaml
\`\`\`

## Limitations

- Lambda functions cannot be serialized (use `@flock_predicate` instead)
- JoinSpec correlation keys must be re-registered
- Custom components require component registry
\`\`\`

---

### Task 3.3: Examples (2 days)

**Create**: `examples/serialization/01_basic.py`

```python
"""Basic agent serialization example."""

from flock import Agent, Flock, flock_type
from pydantic import BaseModel


@flock_type("Greeting")
class Greeting(BaseModel):
    message: str


def main():
    # Create agent
    agent = Agent(name="greeter", description="Greets users")
    agent.consumes(Greeting)

    # Save to YAML
    agent.to_yaml("greeter.yaml")
    print("✅ Agent saved to greeter.yaml")

    # Load from YAML
    loaded_agent = Agent.from_yaml("greeter.yaml")
    print(f"✅ Agent loaded: {loaded_agent.name}")

    # Use in Flock
    flock = Flock("gpt-4")
    flock.add_agent(loaded_agent)
    print("✅ Agent added to orchestrator")


if __name__ == "__main__":
    main()
```

**Create**: `examples/serialization/02_with_predicates.py`

```python
"""Agent serialization with predicates."""

from flock import Agent, flock_type
from flock.registry import flock_predicate
from pydantic import BaseModel


@flock_type("Result")
class Result(BaseModel):
    value: float
    confidence: float


@flock_predicate("high_confidence", "Filters high-confidence results")
def high_confidence(result: Result) -> bool:
    return result.confidence > 0.8


def main():
    # Create agent with predicate
    agent = Agent(name="analyzer")
    agent.consumes(Result, where="high_confidence")

    # Save to YAML
    yaml_str = agent.to_yaml("analyzer.yaml")
    print("YAML output:")
    print(yaml_str)

    # Load from YAML
    loaded_agent = Agent.from_yaml("analyzer.yaml")
    print(f"✅ Agent loaded with {len(loaded_agent.subscriptions)} subscriptions")


if __name__ == "__main__":
    main()
```

---

## ✅ Success Criteria

### Phase 1 Complete When:
- [ ] `to_dict()` / `from_dict()` methods implemented
- [ ] Round-trip serialization works (agent → dict → agent)
- [ ] Type registry integration working
- [ ] 80%+ test coverage for serialization module
- [ ] All existing tests still pass

### Phase 2 Complete When:
- [ ] `to_yaml()` / `from_yaml()` methods implemented
- [ ] Environment variable substitution working
- [ ] Function registry enhanced with metadata
- [ ] Cross-machine portability tested
- [ ] 85%+ test coverage for serialization

### Phase 3 Complete When:
- [ ] Migration CLI tool working
- [ ] Documentation complete
- [ ] 3+ examples created
- [ ] Migration guide for v0.4 users
- [ ] All tests passing (including integration tests)

---

## 🎯 Testing Strategy

### Unit Tests
- [ ] Schema validation (AgentConfig, SubscriptionConfig, etc.)
- [ ] to_dict() for all agent attributes
- [ ] from_dict() for all agent attributes
- [ ] Round-trip serialization
- [ ] Warning generation for non-serializable elements

### Integration Tests
- [ ] YAML file I/O
- [ ] Environment variable resolution
- [ ] Function registry resolution
- [ ] Cross-machine simulation (different paths)

### End-to-End Tests
- [ ] Create agent → save → load → use in Flock
- [ ] Migration v0.4 → v0.2
- [ ] Multiple agents in single YAML
- [ ] Complex subscriptions with predicates

---

## 📊 Progress Tracking

| Phase | Task | Status | Owner | ETA |
|-------|------|--------|-------|-----|
| 1 | Define schemas | ⏳ | TBD | Day 1 |
| 1 | to_dict() | ⏳ | TBD | Day 2-3 |
| 1 | from_dict() | ⏳ | TBD | Day 4-5 |
| 2 | YAML methods | ⏳ | TBD | Day 6 |
| 2 | Env vars | ⏳ | TBD | Day 7 |
| 2 | Registry | ⏳ | TBD | Day 8-9 |
| 3 | Migration CLI | ⏳ | TBD | Day 10-11 |
| 3 | Documentation | ⏳ | TBD | Day 12 |
| 3 | Examples | ⏳ | TBD | Day 13-14 |

---

## 🚀 Next Steps

1. **Review this strategy** with team
2. **Assign owners** for each phase
3. **Create GitHub issues** for each task
4. **Set up project board** for tracking
5. **Start Phase 1** implementation

---

**Last Updated**: 2025-10-13
**Status**: Ready for Implementation
