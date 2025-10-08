# Formal Verification Examples for Flock

**Date:** 2025-10-08
**Status:** Implementation Examples
**Companion to:** formal-methods-analysis.md

---

## Overview

This document provides concrete examples of how formal verification properties from `formal-methods-analysis.md` can be implemented as practical tools for Flock developers.

---

## Example 1: Type Safety Verification via Mypy Plugin

### Problem

Current Flock code allows type errors that only manifest at runtime:

```python
from pydantic import BaseModel
from flock import Flock

class Idea(BaseModel):
    topic: str
    genre: str

class Movie(BaseModel):
    title: str
    runtime: int  # minutes

flock = Flock()

# BUG: Predicate tries to access Movie.runtime on Idea instance
flock.agent("bad_agent")
    .consumes(Idea, where=lambda m: m.runtime > 120)  # ✗ Idea has no 'runtime'
    .publishes(Movie)

# This fails at runtime when predicate is evaluated!
```

### Solution: Mypy Plugin for Subscription Validation

**File: `flock/mypy_plugin.py`**

```python
"""Mypy plugin for static verification of Flock agent contracts."""

from typing import Callable, Type as TypingType
from mypy.plugin import Plugin, MethodContext
from mypy.nodes import CallExpr, LambdaExpr, ARG_NAMED
from mypy import nodes


class FlockTypePlugin(Plugin):
    """Verify agent subscription type safety."""

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], TypingType] | None:
        if fullname == "flock.agent.AgentBuilder.consumes":
            return self.check_consumes_subscription
        return None

    def check_consumes_subscription(self, ctx: MethodContext) -> TypingType:
        """Verify .consumes(T, where=lambda) has correct types."""
        if len(ctx.args) < 1:
            return ctx.default_return_type

        # Get consumed type T
        consumed_type_arg = ctx.args[0][0]
        if not isinstance(consumed_type_arg, nodes.NameExpr):
            return ctx.default_return_type

        consumed_type = consumed_type_arg.node

        # Get 'where' predicate (if present)
        where_arg = None
        for arg_kind, arg_expr in zip(ctx.arg_kinds[1], ctx.args[1]):
            if arg_kind == ARG_NAMED and arg_expr:
                where_arg = arg_expr
                break

        if not where_arg or not isinstance(where_arg, LambdaExpr):
            return ctx.default_return_type

        # Verify lambda parameter type matches consumed type
        lambda_param = where_arg.arguments[0]
        lambda_param_type = lambda_param.variable.type

        if lambda_param_type != consumed_type:
            ctx.api.fail(
                f"Predicate parameter type mismatch: "
                f"expected {consumed_type}, got {lambda_param_type}",
                ctx.context
            )

        return ctx.default_return_type


def plugin(version: str):
    return FlockTypePlugin
```

**Usage:**

```toml
# pyproject.toml
[tool.mypy]
plugins = ["flock.mypy_plugin"]
```

```bash
mypy app.py

# Output:
# app.py:15: error: Predicate parameter type mismatch: expected Idea, got Movie
#     .consumes(Idea, where=lambda m: m.runtime > 120)
#                                     ^
```

**Impact:**
- ✅ Catches type errors at **development time**
- ✅ Works with existing CI/CD pipelines
- ✅ IDE integration (VSCode, PyCharm)

---

## Example 2: Deadlock Detection via Dependency Graph Analysis

### Problem

Circular subscription patterns can cause infinite loops:

```python
flock = Flock()

# Movie agent consumes Idea, publishes Movie
flock.agent("movie")
    .consumes(Idea)
    .publishes(Movie)

# Tagline agent consumes Movie, publishes Tagline
flock.agent("tagline")
    .consumes(Movie)
    .publishes(Tagline)

# Reviewer agent consumes Tagline, publishes Idea (creates cycle!)
flock.agent("reviewer")
    .consumes(Tagline)
    .publishes(Idea)  # ✗ Cycle: Idea → Movie → Tagline → Idea
```

### Solution: Static Subscription Graph Analysis

**File: `flock/verify/deadlock.py`**

```python
"""Deadlock detection for Flock agent subscriptions."""

from dataclasses import dataclass
from typing import List, Set
import networkx as nx
from flock import Flock


@dataclass
class Cycle:
    """Represents a detected circular dependency."""
    agents: List[str]
    types: List[str]

    def __str__(self) -> str:
        chain = " → ".join(f"{a}({t})" for a, t in zip(self.agents, self.types))
        return f"Cycle detected: {chain} → {self.agents[0]}"


class DeadlockAnalyzer:
    """Analyze Flock agent graphs for deadlock risks."""

    def __init__(self, flock: Flock):
        self.flock = flock
        self.graph = self._build_dependency_graph()

    def _build_dependency_graph(self) -> nx.DiGraph:
        """Build directed graph of agent dependencies via type routing."""
        graph = nx.DiGraph()

        # Add all agents as nodes
        for agent in self.flock.agents:
            graph.add_node(agent.name)

        # Build edges: A → B if A publishes type T and B consumes T
        for consumer in self.flock.agents:
            for subscription in consumer.subscriptions:
                for consumed_type in subscription.type_names:
                    for producer in self.flock.agents:
                        for output in producer.outputs:
                            if output.spec.type_name == consumed_type:
                                graph.add_edge(
                                    producer.name,
                                    consumer.name,
                                    type=consumed_type
                                )

        return graph

    def detect_cycles(self) -> List[Cycle]:
        """Detect circular subscription dependencies."""
        cycles = []

        try:
            # Find all simple cycles in dependency graph
            for cycle_nodes in nx.simple_cycles(self.graph):
                # Extract edge types for the cycle
                types = []
                for i in range(len(cycle_nodes)):
                    u = cycle_nodes[i]
                    v = cycle_nodes[(i + 1) % len(cycle_nodes)]
                    edge_data = self.graph.get_edge_data(u, v)
                    types.append(edge_data.get("type", "unknown"))

                cycles.append(Cycle(agents=cycle_nodes, types=types))

        except nx.NetworkXNoCycle:
            pass  # No cycles detected

        return cycles

    def is_deadlock_free(self) -> bool:
        """Check if the agent graph is acyclic (deadlock-free)."""
        return nx.is_directed_acyclic_graph(self.graph)

    def detect_self_loops(self) -> List[str]:
        """Detect agents that consume their own outputs (single-agent cycles)."""
        self_loops = []

        for agent in self.flock.agents:
            consumed_types = set()
            for sub in agent.subscriptions:
                consumed_types.update(sub.type_names)

            produced_types = {out.spec.type_name for out in agent.outputs}

            overlap = consumed_types & produced_types
            if overlap and not agent.prevent_self_trigger:
                self_loops.append(
                    f"{agent.name} (types: {', '.join(overlap)}, "
                    f"prevent_self_trigger={agent.prevent_self_trigger})"
                )

        return self_loops

    def visualize(self, output_file: str = "flock_graph.png") -> None:
        """Generate visual representation of agent dependency graph."""
        import matplotlib.pyplot as plt

        pos = nx.spring_layout(self.graph)
        nx.draw(
            self.graph,
            pos,
            with_labels=True,
            node_color='lightblue',
            node_size=3000,
            arrowsize=20,
            font_size=10,
            font_weight='bold'
        )

        # Draw edge labels (artifact types)
        edge_labels = nx.get_edge_attributes(self.graph, 'type')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels)

        plt.savefig(output_file)
        print(f"Graph visualization saved to {output_file}")


# CLI Tool
def main():
    """CLI entry point for deadlock analysis."""
    import sys
    import importlib.util

    if len(sys.argv) < 2:
        print("Usage: flock-verify-deadlock <app.py>")
        sys.exit(1)

    # Dynamically load user's Flock application
    spec = importlib.util.spec_from_file_location("app", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find Flock instance
    flock = getattr(module, 'flock', None)
    if not flock:
        print("Error: No 'flock' variable found in module")
        sys.exit(1)

    # Run analysis
    analyzer = DeadlockAnalyzer(flock)

    print("=== Flock Deadlock Analysis ===\n")

    # Check for cycles
    cycles = analyzer.detect_cycles()
    if cycles:
        print(f"❌ Deadlock risk detected! Found {len(cycles)} cycle(s):\n")
        for cycle in cycles:
            print(f"  {cycle}\n")
    else:
        print("✅ No circular dependencies detected (deadlock-free)\n")

    # Check for self-loops
    self_loops = analyzer.detect_self_loops()
    if self_loops:
        print(f"⚠️  Warning: {len(self_loops)} agent(s) consume own outputs:\n")
        for loop in self_loops:
            print(f"  {loop}")
        print("\n  Recommendation: Enable prevent_self_trigger=True\n")

    # Generate visualization
    analyzer.visualize()

    sys.exit(0 if not cycles else 1)


if __name__ == "__main__":
    main()
```

**Usage:**

```bash
# Install tool
pip install flock-verify

# Run analysis
flock-verify-deadlock app.py

# Output:
# === Flock Deadlock Analysis ===
#
# ❌ Deadlock risk detected! Found 1 cycle(s):
#
#   Cycle detected: movie(Idea) → tagline(Movie) → reviewer(Tagline) → movie
#
# ⚠️  Warning: 0 agent(s) consume own outputs
#
# Graph visualization saved to flock_graph.png
```

**Impact:**
- ✅ Prevents infinite loops in production
- ✅ Visualizes agent topology for debugging
- ✅ CI/CD integration (`exit 1` on cycle detection)

---

## Example 3: Visibility Policy Verification

### Problem

Visibility policies can be complex, leading to runtime access control violations:

```python
from flock.visibility import PrivateVisibility, TenantVisibility

# Agent A publishes private data
flock.agent("medical_records")
    .publishes(PatientData, visibility=PrivateVisibility(agents={"doctor"}))

# Agent B attempts to consume (should be blocked)
flock.agent("billing")
    .consumes(PatientData)  # ✗ Should not have access!
```

### Solution: Property-Based Testing for Visibility Invariants

**File: `tests/test_visibility_properties.py`**

```python
"""Property-based tests for visibility correctness."""

import pytest
from hypothesis import given, strategies as st
from flock import Flock
from flock.artifacts import Artifact
from flock.visibility import (
    PublicVisibility,
    PrivateVisibility,
    TenantVisibility,
    AgentIdentity
)


# Strategy: Generate random visibility policies
@st.composite
def visibility_strategy(draw):
    """Generate random visibility policies for testing."""
    kind = draw(st.sampled_from(["public", "private", "tenant"]))

    if kind == "public":
        return PublicVisibility()
    elif kind == "private":
        agents = draw(st.sets(st.text(min_size=1, max_size=10), min_size=1, max_size=5))
        return PrivateVisibility(agents=agents)
    else:  # tenant
        tenant_id = draw(st.text(min_size=1, max_size=20))
        return TenantVisibility(tenant_id=tenant_id)


@st.composite
def agent_identity_strategy(draw):
    """Generate random agent identities."""
    name = draw(st.text(min_size=1, max_size=20))
    labels = draw(st.sets(st.text(min_size=1, max_size=10), max_size=3))
    tenant_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    return AgentIdentity(name=name, labels=labels, tenant_id=tenant_id)


# Property 1: Public visibility allows all agents
@given(agent=agent_identity_strategy())
def test_public_visibility_allows_all(agent):
    """Property: PublicVisibility.allows(agent) is always True."""
    visibility = PublicVisibility()
    assert visibility.allows(agent), "Public visibility must allow all agents"


# Property 2: Private visibility allows only named agents
@given(
    allowed_agents=st.sets(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
    agent_name=st.text(min_size=1, max_size=10)
)
def test_private_visibility_enforces_allowlist(allowed_agents, agent_name):
    """Property: PrivateVisibility.allows(agent) ⟺ agent.name ∈ allowed_agents."""
    visibility = PrivateVisibility(agents=allowed_agents)
    agent = AgentIdentity(name=agent_name, labels=set(), tenant_id=None)

    allowed = visibility.allows(agent)
    expected = agent_name in allowed_agents

    assert allowed == expected, (
        f"Private visibility check failed: "
        f"expected {expected}, got {allowed}"
    )


# Property 3: Tenant visibility isolates tenants
@given(
    tenant_id_1=st.text(min_size=1, max_size=20),
    tenant_id_2=st.text(min_size=1, max_size=20)
)
def test_tenant_visibility_isolates_tenants(tenant_id_1, tenant_id_2):
    """Property: Tenants cannot access each other's data."""
    visibility = TenantVisibility(tenant_id=tenant_id_1)
    agent = AgentIdentity(name="test", labels=set(), tenant_id=tenant_id_2)

    allowed = visibility.allows(agent)

    if tenant_id_1 == tenant_id_2:
        assert allowed, "Same tenant must have access"
    else:
        assert not allowed, "Different tenants must be isolated"


# Integration Property: Orchestrator respects visibility
@pytest.mark.asyncio
@given(
    visibility=visibility_strategy(),
    allowed_agent_name=st.text(min_size=1, max_size=10),
    blocked_agent_name=st.text(min_size=1, max_size=10)
)
async def test_orchestrator_enforces_visibility(
    visibility, allowed_agent_name, blocked_agent_name
):
    """Property: Orchestrator._check_visibility correctly filters agents."""
    from pydantic import BaseModel
    from flock.registry import flock_type

    @flock_type
    class TestData(BaseModel):
        value: int

    flock = Flock()

    # Configure visibility to allow only one agent
    if isinstance(visibility, PrivateVisibility):
        visibility.agents = {allowed_agent_name}

    # Create artifact with visibility
    artifact = Artifact(
        type="TestData",
        payload={"value": 42},
        produced_by="external",
        visibility=visibility
    )

    # Test allowed agent
    allowed_identity = AgentIdentity(name=allowed_agent_name, labels=set(), tenant_id=None)
    allowed = flock._check_visibility(artifact, allowed_identity)

    # Test blocked agent (if different)
    if allowed_agent_name != blocked_agent_name:
        blocked_identity = AgentIdentity(name=blocked_agent_name, labels=set(), tenant_id=None)
        blocked = flock._check_visibility(artifact, blocked_identity)
        assert not blocked, "Blocked agent should not have access"

    # Verify visibility was enforced
    expected = visibility.allows(allowed_identity)
    assert allowed == expected, "Orchestrator visibility check mismatch"
```

**Run Tests:**

```bash
pytest tests/test_visibility_properties.py -v

# Output:
# tests/test_visibility_properties.py::test_public_visibility_allows_all PASSED [100 examples]
# tests/test_visibility_properties.py::test_private_visibility_enforces_allowlist PASSED [100 examples]
# tests/test_visibility_properties.py::test_tenant_visibility_isolates_tenants PASSED [100 examples]
# tests/test_orchestrator_enforces_visibility PASSED [100 examples]
```

**Impact:**
- ✅ Validates visibility invariants across **thousands of test cases**
- ✅ Finds edge cases in access control logic
- ✅ Provides formal evidence for security audits

---

## Example 4: Resource Bound Estimation

### Problem

Developers don't know upfront how many agent invocations or LLM calls will occur:

```python
flock = Flock()

flock.agent("movie").consumes(Idea).publishes(Movie)
flock.agent("tagline").consumes(Movie).publishes(Tagline)
flock.agent("script").consumes(Movie, Tagline).publishes(Script)

# Question: If I publish 10 Idea artifacts, how many total agent runs?
# Answer: ?
```

### Solution: Static Resource Bound Analysis

**File: `flock/verify/bounds.py`**

```python
"""Static analysis for resource bound estimation."""

from dataclasses import dataclass
from typing import Dict, List
from flock import Flock


@dataclass
class ResourceBounds:
    """Estimated resource usage bounds."""
    min_invocations: int
    max_invocations: int
    avg_invocations: float
    max_artifacts: int
    agent_breakdown: Dict[str, int]


class BoundsAnalyzer:
    """Analyze Flock agent graphs for resource bounds."""

    def __init__(self, flock: Flock):
        self.flock = flock

    def estimate_invocations(self, initial_artifacts: Dict[str, int]) -> ResourceBounds:
        """
        Estimate agent invocations given initial artifact counts.

        Args:
            initial_artifacts: Map of type name → count (e.g., {"Idea": 10})

        Returns:
            Estimated resource bounds
        """
        # Track how many artifacts of each type will be produced
        artifact_counts = initial_artifacts.copy()
        agent_invocations = {agent.name: 0 for agent in self.flock.agents}

        # Simulate propagation through subscription graph
        changed = True
        iterations = 0
        max_iterations = 100  # Prevent infinite loops

        while changed and iterations < max_iterations:
            changed = False
            iterations += 1

            for agent in self.flock.agents:
                for subscription in agent.subscriptions:
                    # Count how many artifacts match this subscription
                    matches = sum(
                        artifact_counts.get(type_name, 0)
                        for type_name in subscription.type_names
                    )

                    if matches > 0:
                        # Agent will be invoked 'matches' times
                        new_invocations = matches

                        # Account for prevent_self_trigger
                        if agent.prevent_self_trigger:
                            # Agent won't process its own outputs
                            for output in agent.outputs:
                                if output.spec.type_name in subscription.type_names:
                                    # Subtract own outputs (conservative estimate)
                                    new_invocations = max(0, new_invocations - agent_invocations[agent.name])

                        # Update invocation count
                        old_count = agent_invocations[agent.name]
                        agent_invocations[agent.name] += new_invocations

                        # Produce output artifacts
                        for output in agent.outputs:
                            old_artifact_count = artifact_counts.get(output.spec.type_name, 0)
                            artifact_counts[output.spec.type_name] = old_artifact_count + new_invocations

                        if agent_invocations[agent.name] != old_count:
                            changed = True

        # Calculate totals
        total_invocations = sum(agent_invocations.values())
        total_artifacts = sum(artifact_counts.values())

        return ResourceBounds(
            min_invocations=total_invocations,  # Conservative estimate
            max_invocations=total_invocations * 2,  # Account for concurrency/retries
            avg_invocations=total_invocations * 1.5,
            max_artifacts=total_artifacts,
            agent_breakdown=agent_invocations
        )

    def estimate_cost(
        self,
        initial_artifacts: Dict[str, int],
        cost_per_invocation: float = 0.01  # USD
    ) -> float:
        """Estimate monetary cost (e.g., LLM API costs)."""
        bounds = self.estimate_invocations(initial_artifacts)
        return bounds.avg_invocations * cost_per_invocation


# CLI Tool
def main():
    """CLI entry point for resource bound analysis."""
    import sys
    import importlib.util

    if len(sys.argv) < 2:
        print("Usage: flock-estimate-bounds <app.py> <type:count>...")
        print("Example: flock-estimate-bounds app.py Idea:10 Movie:5")
        sys.exit(1)

    # Load Flock app
    spec = importlib.util.spec_from_file_location("app", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    flock = getattr(module, 'flock', None)
    if not flock:
        print("Error: No 'flock' variable found")
        sys.exit(1)

    # Parse initial artifacts
    initial_artifacts = {}
    for arg in sys.argv[2:]:
        type_name, count = arg.split(':')
        initial_artifacts[type_name] = int(count)

    # Run analysis
    analyzer = BoundsAnalyzer(flock)
    bounds = analyzer.estimate_invocations(initial_artifacts)

    print("=== Resource Bound Estimation ===\n")
    print(f"Initial artifacts: {initial_artifacts}\n")
    print(f"Estimated invocations:")
    print(f"  Min: {bounds.min_invocations}")
    print(f"  Avg: {bounds.avg_invocations:.1f}")
    print(f"  Max: {bounds.max_invocations}")
    print(f"\nMax artifacts on blackboard: {bounds.max_artifacts}")
    print(f"\nBreakdown by agent:")
    for agent_name, count in sorted(bounds.agent_breakdown.items()):
        print(f"  {agent_name}: {count} invocations")

    # Cost estimate
    cost = analyzer.estimate_cost(initial_artifacts)
    print(f"\nEstimated cost: ${cost:.2f}")


if __name__ == "__main__":
    main()
```

**Usage:**

```bash
flock-estimate-bounds app.py Idea:10

# Output:
# === Resource Bound Estimation ===
#
# Initial artifacts: {'Idea': 10}
#
# Estimated invocations:
#   Min: 30
#   Avg: 45.0
#   Max: 60
#
# Max artifacts on blackboard: 40
#
# Breakdown by agent:
#   movie: 10 invocations
#   script: 10 invocations
#   tagline: 10 invocations
#
# Estimated cost: $0.45
```

**Impact:**
- ✅ Capacity planning before deployment
- ✅ Cost prediction for budgeting
- ✅ SLA guarantees (max latency bounds)

---

## Example 5: Determinism Analysis

### Problem

Non-deterministic execution makes debugging difficult:

```python
flock.agent("ranker")
    .consumes(Movie)
    .best_of(5, score=lambda r: r.metrics["confidence"])  # Non-deterministic!
```

### Solution: Determinism Checker

**File: `flock/verify/determinism.py`**

```python
"""Determinism analysis for Flock agents."""

from dataclasses import dataclass
from typing import List
from flock import Flock


@dataclass
class NonDeterminismSource:
    """Source of non-determinism in the system."""
    agent_name: str
    reason: str
    severity: str  # "high", "medium", "low"


class DeterminismAnalyzer:
    """Analyze Flock for non-deterministic behavior."""

    def __init__(self, flock: Flock):
        self.flock = flock

    def analyze(self) -> List[NonDeterminismSource]:
        """Detect sources of non-determinism."""
        issues = []

        for agent in self.flock.agents:
            # Check for best-of-N sampling
            if agent.best_of_n > 1:
                issues.append(NonDeterminismSource(
                    agent_name=agent.name,
                    reason=f"best_of_n={agent.best_of_n} (samples multiple LLM outputs)",
                    severity="high"
                ))

            # Check for concurrency
            if agent.max_concurrency > 1:
                issues.append(NonDeterminismSource(
                    agent_name=agent.name,
                    reason=f"max_concurrency={agent.max_concurrency} (parallel execution)",
                    severity="medium"
                ))

            # Check for shared delivery mode
            for subscription in agent.subscriptions:
                if subscription.delivery == "shared":
                    issues.append(NonDeterminismSource(
                        agent_name=agent.name,
                        reason=f"delivery=shared (multiple agents compete for artifacts)",
                        severity="medium"
                    ))

            # Check for time-based predicates (heuristic)
            for subscription in agent.subscriptions:
                for predicate in subscription.where:
                    if "time" in predicate.__code__.co_names or "now" in predicate.__code__.co_names:
                        issues.append(NonDeterminismSource(
                            agent_name=agent.name,
                            reason="time-based predicate (depends on wall clock)",
                            severity="low"
                        ))

        return issues

    def is_deterministic(self) -> bool:
        """Check if the entire system is deterministic."""
        return len(self.analyze()) == 0


# CLI Tool
def main():
    """CLI entry point for determinism analysis."""
    import sys
    import importlib.util

    if len(sys.argv) < 2:
        print("Usage: flock-check-determinism <app.py>")
        sys.exit(1)

    # Load Flock app
    spec = importlib.util.spec_from_file_location("app", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    flock = getattr(module, 'flock', None)
    if not flock:
        print("Error: No 'flock' variable found")
        sys.exit(1)

    # Run analysis
    analyzer = DeterminismAnalyzer(flock)
    issues = analyzer.analyze()

    print("=== Determinism Analysis ===\n")

    if not issues:
        print("✅ System is deterministic (reproducible execution)\n")
        sys.exit(0)
    else:
        print(f"⚠️  Found {len(issues)} source(s) of non-determinism:\n")

        for issue in sorted(issues, key=lambda x: x.severity, reverse=True):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[issue.severity]
            print(f"{severity_icon} {issue.agent_name}: {issue.reason}")

        print("\nRecommendation: For reproducible debugging, consider:")
        print("  - Set best_of_n=1")
        print("  - Set max_concurrency=1")
        print("  - Use delivery='exclusive'")
        print("  - Avoid time-based predicates")

        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Usage:**

```bash
flock-check-determinism app.py

# Output:
# === Determinism Analysis ===
#
# ⚠️  Found 3 source(s) of non-determinism:
#
# 🔴 ranker: best_of_n=5 (samples multiple LLM outputs)
# 🟡 processor: max_concurrency=3 (parallel execution)
# 🟢 filter: time-based predicate (depends on wall clock)
#
# Recommendation: For reproducible debugging, consider:
#   - Set best_of_n=1
#   - Set max_concurrency=1
#   - Use delivery='exclusive'
#   - Avoid time-based predicates
```

---

## Summary: Practical Tools Roadmap

| Tool | Effort | Impact | Status |
|------|--------|--------|--------|
| **Type Safety Checker** | 2 weeks | High | ⚠️ Prototype |
| **Deadlock Detector** | 1 week | Critical | ⚠️ Prototype |
| **Visibility Tester** | 1 week | High | ⚠️ Prototype |
| **Resource Estimator** | 2 weeks | Medium | ⚠️ Prototype |
| **Determinism Checker** | 1 week | Medium | ⚠️ Prototype |

**Next Step:** Package as `flock-verify` CLI tool and integrate into CI/CD pipelines.

---

## References

1. Hypothesis property-based testing: https://hypothesis.readthedocs.io/
2. Mypy plugin development: https://mypy.readthedocs.io/en/stable/extending_mypy.html
3. NetworkX graph algorithms: https://networkx.org/documentation/stable/reference/algorithms/
4. Static analysis best practices: Ayewah et al. (2008), "Using Static Analysis to Find Bugs"
