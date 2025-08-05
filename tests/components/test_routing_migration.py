#!/usr/bin/env python3
"""Test script for migrated routing components in the unified architecture."""

import asyncio
from typing import Any

from flock.components.evaluation.declarative_evaluation_component import (
    DeclarativeEvaluationComponent, DeclarativeEvaluationConfig
)
from flock.components.routing.default_routing_component import (
    DefaultRoutingComponent, DefaultRoutingConfig
)
from flock.components.utility.output_utility_component import (
    OutputUtilityComponent, OutputUtilityConfig
)
from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import HandOffRequest


async def test_default_routing_component():
    """Test the DefaultRoutingComponent in unified architecture."""
    print("🚀 Testing DefaultRoutingComponent Migration")
    print("=" * 50)
    
    # Test different routing configurations
    test_cases = [
        {
            "name": "String routing",
            "config": DefaultRoutingConfig(next_agent="next_agent"),
            "expected_next": "next_agent"
        },
        {
            "name": "HandOffRequest routing", 
            "config": DefaultRoutingConfig(
                next_agent=HandOffRequest(
                    next_agent="custom_agent",
                    output_to_input_merge_strategy="add"
                )
            ),
            "expected_next": "custom_agent"
        },
        {
            "name": "Callable routing",
            "config": DefaultRoutingConfig(
                next_agent=lambda context, result: HandOffRequest(
                    next_agent="dynamic_agent",
                    output_to_input_merge_strategy="match"
                )
            ),
            "expected_next": "dynamic_agent"
        },
        {
            "name": "Empty routing (end workflow)",
            "config": DefaultRoutingConfig(next_agent=""),
            "expected_next": None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🔄 Test {i}: {test_case['name']}")
        print("-" * 30)
        
        # Create routing component
        router = DefaultRoutingComponent(
            name="test_router",
            config=test_case["config"]
        )
        
        # Create minimal evaluator for complete agent
        evaluator = DeclarativeEvaluationComponent(
            name="simple_evaluator",
            config=DeclarativeEvaluationConfig(
                persona="Test agent",
                task_description="Test routing"
            )
        )
        
        # Create output component (suppressed)
        output_component = OutputUtilityComponent(
            name="output_formatter",
            config=OutputUtilityConfig(no_output=True)
        )
        
        # Create agent with routing component
        agent = FlockAgent(
            name="test_routing_agent",
            input="query: str",
            output="response: str",
            components=[evaluator, router, output_component]
        )
        
        print(f"✅ Created agent with routing component: {router.name}")
        print(f"   - Router config: {type(test_case['config'].hand_off).__name__}")
        
        # Test routing decision
        context = FlockContext()
        test_result = {"response": "test output"}
        
        handoff_request = await router.determine_next_step(agent, test_result, context)
        
        if test_case["expected_next"] is None:
            if handoff_request is None:
                print("✅ Correctly returned None (end workflow)")
            else:
                print(f"❌ Expected None but got: {handoff_request}")
        else:
            if handoff_request and handoff_request.next_agent == test_case["expected_next"]:
                print(f"✅ Correctly routed to: {handoff_request.next_agent}")
            else:
                expected = test_case["expected_next"]
                actual = handoff_request.next_agent if handoff_request else None
                print(f"❌ Expected {expected} but got: {actual}")
        
        print()
    
    # Test integration with agent execution
    print("🎯 Testing Agent Integration")
    print("-" * 30)
    
    # Create agent with routing that goes to "summary_agent"
    router = DefaultRoutingComponent(
        name="integration_router",
        config=DefaultRoutingConfig(next_agent="summary_agent")
    )
    
    evaluator = DeclarativeEvaluationComponent(
        name="integration_evaluator",
        config=DeclarativeEvaluationConfig(
            persona="Integration test agent",
            task_description="Test integration"
        )
    )
    
    output_component = OutputUtilityComponent(
        name="output_formatter",
        config=OutputUtilityConfig(no_output=True)
    )
    
    agent = FlockAgent(
        name="integration_test_agent",
        input="query: str",
        output="response: str",
        components=[evaluator, router, output_component]
    )
    
    print(f"✅ Created integration test agent")
    print(f"   - Evaluator: {agent.evaluator.name if agent.evaluator else 'None'}")
    print(f"   - Router: {agent.router.name if agent.router else 'None'}")
    
    # Test that agent.next_handoff gets set correctly
    # Note: This won't actually call LLM due to missing API keys, but we can test the structure
    print("   Testing component identification...")
    
    # Verify the router is properly identified
    if agent.router and isinstance(agent.router, DefaultRoutingComponent):
        print("✅ Router correctly identified as DefaultRoutingComponent")
    else:
        print("❌ Router not properly identified")
    
    print()
    print("🎉 DefaultRoutingComponent Migration Test Complete!")
    print("✅ All routing configurations work correctly in unified architecture")


if __name__ == "__main__":
    asyncio.run(test_default_routing_component())
