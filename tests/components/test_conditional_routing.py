#!/usr/bin/env python3
"""Test script for ConditionalRoutingComponent migration."""

import asyncio
from flock.components.routing.conditional_routing_component import (
    ConditionalRoutingComponent, ConditionalRoutingConfig
)
from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


async def test_conditional_routing():
    """Test ConditionalRoutingComponent functionality."""
    print("Testing ConditionalRoutingComponent Migration")
    print("=" * 50)
    
    # Test different condition types
    test_cases = [
        {
            "name": "String equals condition",
            "config": ConditionalRoutingConfig(
                condition_context_key="test_key",
                expected_string="success",
                success_agent="next_agent",
                failure_agent="error_agent"
            ),
            "context_value": "success",
            "expected_next": "next_agent"
        },
        {
            "name": "Boolean condition",
            "config": ConditionalRoutingConfig(
                condition_context_key="test_bool",
                expected_bool=True,
                success_agent="success_path",
                failure_agent="failure_path"
            ),
            "context_value": True,
            "expected_next": "success_path"
        },
        {
            "name": "Number comparison",
            "config": ConditionalRoutingConfig(
                condition_context_key="test_number",
                expected_number=10,
                number_mode=">=",
                success_agent="greater_path",
                failure_agent="lesser_path"
            ),
            "context_value": 15,
            "expected_next": "greater_path"
        },
        {
            "name": "Existence check - exists",
            "config": ConditionalRoutingConfig(
                condition_context_key="test_exists",
                check_exists=True,
                success_agent="found_agent",
                failure_agent="not_found_agent"
            ),
            "context_value": "any_value",
            "expected_next": "found_agent"
        },
        {
            "name": "Failure case with retry",
            "config": ConditionalRoutingConfig(
                condition_context_key="test_retry",
                expected_string="correct",
                success_agent="success_agent",
                failure_agent="final_failure",
                retry_on_failure=True,
                max_retries=2
            ),
            "context_value": "wrong",
            "expected_next": "mock_agent"  # Should retry back to same agent
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print("-" * 30)
        
        # Create routing component
        router = ConditionalRoutingComponent(
            name="test_conditional_router",
            config=test_case["config"]
        )
        
        # Create mock agent
        mock_agent = FlockAgent(
            name="mock_agent",
            input="query: str",
            output="response: str",
            components=[]
        )
        
        # Create context with test value
        context = FlockContext()
        context.set_variable(test_case["config"].condition_context_key, test_case["context_value"])
        
        # Test routing decision
        test_result = {"response": "test output"}
        handoff_request = await router.determine_next_step(mock_agent, test_result, context)
        
        if handoff_request:
            actual_next = handoff_request.next_agent
            print(f"Routed to: {actual_next}")
        else:
            actual_next = None
            print("Ended workflow (returned None)")
        
        if actual_next == test_case["expected_next"]:
            print("PASSED")
        else:
            print(f"FAILED: Expected {test_case['expected_next']}, got {actual_next}")
        
        print()
    
    print("ConditionalRoutingComponent Migration Test Complete")


if __name__ == "__main__":
    asyncio.run(test_conditional_routing())
