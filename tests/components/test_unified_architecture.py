#!/usr/bin/env python3
"""Test script for the unified component architecture."""

import asyncio
from typing import Any

from flock.core.component.agent_component_base import AgentComponent, AgentComponentConfig
from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.component.routing_component import RoutingModuleBase
from flock.core.component.utility_component import UtilityModuleBase
from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import HandOffRequest


# Example implementations for testing

class SimpleEvaluationConfig(AgentComponentConfig):
    response_template: str = "Processed: {input}"


class SimpleEvaluationComponent(EvaluationComponent):
    """Simple evaluation component for testing."""
    
    config: SimpleEvaluationConfig
    
    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        # Simple evaluation logic
        query = inputs.get('query', 'No query provided')
        result = self.config.response_template.format(input=query)
        return {'result': result}


class SimpleRoutingComponent(RoutingModuleBase):
    """Simple routing component for testing."""
    
    async def determine_next_step(
        self,
        agent: Any,
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> HandOffRequest | None:
        # Simple routing - end workflow
        return None  # No next step


class LoggingUtilityComponent(UtilityModuleBase):
    """Simple utility component that logs lifecycle events."""
    
    async def on_initialize(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None) -> None:
        print(f"[{self.name}] Initializing with inputs: {inputs}")
    
    async def on_pre_evaluate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None) -> dict[str, Any]:
        print(f"[{self.name}] Pre-evaluate: {inputs}")
        return inputs
    
    async def on_post_evaluate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        print(f"[{self.name}] Post-evaluate: {result}")
        return result
    
    async def on_terminate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        print(f"[{self.name}] Terminating with result: {result}")
        return result


async def test_unified_architecture():
    """Test the unified component architecture."""
    print("🚀 Testing Unified Component Architecture")
    print("=" * 50)
    
    # Create components
    evaluator = SimpleEvaluationComponent(
        name="simple_evaluator",
        config=SimpleEvaluationConfig(response_template="AI says: {input}")
    )
    
    router = SimpleRoutingComponent(
        name="simple_router",
        config=AgentComponentConfig()
    )
    
    logger = LoggingUtilityComponent(
        name="logger",
        config=AgentComponentConfig()
    )
    
    # Create unified agent
    agent = FlockAgent(
        name="test_agent",
        input="query: str",
        output="result: str", 
        components=[evaluator, router, logger]
    )
    
    print(f"✅ Created agent with {len(agent.components)} components")
    print(f"   - Evaluator: {agent.evaluator.name if agent.evaluator else 'None'}")
    print(f"   - Router: {agent.router.name if agent.router else 'None'}")
    print(f"   - Total components: {[c.name for c in agent.components]}")
    print()
    
    # Test execution
    print("🎯 Testing Agent Execution")
    print("-" * 30)
    
    result = await agent.run_async({"query": "Hello unified world!"})
    
    print()
    print(f"📊 Final Result: {result}")
    print(f"🔄 Next Handoff: {agent.next_handoff}")
    print()
    
    # Test component management
    print("🔧 Testing Component Management")
    print("-" * 30)
    
    # Add another component
    metrics = UtilityModuleBase(
        name="metrics",
        config=AgentComponentConfig()
    )
    
    agent.add_component(metrics)
    print(f"✅ Added metrics component. Total: {len(agent.components)}")
    
    # Remove a component
    agent.remove_component("logger")
    print(f"✅ Removed logger component. Total: {len(agent.components)}")
    
    # Test convenience properties still work
    print(f"📋 Evaluator: {agent.evaluator.name if agent.evaluator else 'None'}")
    print(f"📋 Router: {agent.router.name if agent.router else 'None'}")
    
    print()
    print("🎉 Unified Architecture Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_unified_architecture())
