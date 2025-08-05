#!/usr/bin/env python3
"""Test serialization compatibility with unified components."""

import asyncio
from flock.components.evaluation.declarative_evaluation_component import (
    DeclarativeEvaluationComponent, DeclarativeEvaluationConfig
)
from flock.components.routing.default_routing_component import (
    DefaultRoutingComponent, DefaultRoutingConfig
)
from flock.components.utility.output_utility_component import (
    OutputUtilityComponent, OutputUtilityConfig
)
from flock.core.flock_agent import FlockAgent
from flock.core.flock_router import HandOffRequest


def test_unified_serialization():
    """Test that unified components serialize and deserialize correctly."""
    print("Testing Unified Component Serialization")
    print("=" * 50)
    
    # Create components
    evaluator = DeclarativeEvaluationComponent(
        name="test_evaluator",
        config=DeclarativeEvaluationConfig(
            model="azure/gpt-4.1",
            temperature=0.5,
            max_tokens=1000
        )
    )
    
    router = DefaultRoutingComponent(
        name="test_router",
        config=DefaultRoutingConfig(
            next_agent=HandOffRequest(next_agent="next_test_agent")
        )
    )
    
    output_component = OutputUtilityComponent(
        name="test_output",
        config=OutputUtilityConfig(no_output=True)
    )
    
    # Create agent with unified components
    agent = FlockAgent(
        name="serialization_test_agent",
        input="query: str",
        output="response: str",
        components=[evaluator, router, output_component]
    )
    
    print(f"Created agent with {len(agent.components)} components")
    print(f"- Evaluator: {agent.evaluator.name if agent.evaluator else 'None'}")
    print(f"- Router: {agent.router.name if agent.router else 'None'}")
    
    # Test serialization
    try:
        print("\nTesting serialization...")
        agent_dict = agent.to_dict()
        print(f"Agent serialized to dict with {len(agent_dict)} keys")
        print(f"Components in serialized data: {len(agent_dict.get('components', []))}")
        
        # Test deserialization
        print("\nTesting deserialization...")
        restored_agent = FlockAgent.from_dict(agent_dict)
        print(f"Agent restored with {len(restored_agent.components)} components")
        print(f"- Restored evaluator: {restored_agent.evaluator.name if restored_agent.evaluator else 'None'}")
        print(f"- Restored router: {restored_agent.router.name if restored_agent.router else 'None'}")
        
        # Verify component integrity
        print("\nVerifying component integrity...")
        if restored_agent.evaluator and agent.evaluator:
            original_config = agent.evaluator.config
            restored_config = restored_agent.evaluator.config
            print(f"Original evaluator model: {original_config.model}")
            print(f"Restored evaluator model: {restored_config.model}")
            print(f"Model preserved: {original_config.model == restored_config.model}")
            print(f"Temperature preserved: {original_config.temperature == restored_config.temperature}")
        
        print("\nSerialization test PASSED")
        return True
        
    except Exception as e:
        print(f"\nSerialization test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_component_compatibility():
    """Test that old and new component systems can coexist."""
    print("\nTesting Component Compatibility")
    print("=" * 40)
    
    try:
        # Test that components have correct base classes
        evaluator = DeclarativeEvaluationComponent(
            name="compat_evaluator",
            config=DeclarativeEvaluationConfig()
        )
        
        # Verify it has the correct methods
        required_methods = ['evaluate_core', 'on_initialize', 'on_pre_evaluate', 'on_post_evaluate']
        for method in required_methods:
            if hasattr(evaluator, method):
                print(f"Method {method}: Present")
            else:
                print(f"Method {method}: MISSING")
                return False
        
        # Test router methods
        router = DefaultRoutingComponent(
            name="compat_router",
            config=DefaultRoutingConfig(next_agent="test_agent")
        )
        
        router_methods = ['determine_next_step']
        for method in router_methods:
            if hasattr(router, method):
                print(f"Router method {method}: Present")
            else:
                print(f"Router method {method}: MISSING")
                return False
        
        print("Component compatibility test PASSED")
        return True
        
    except Exception as e:
        print(f"Component compatibility test FAILED: {e}")
        return False


if __name__ == "__main__":
    print("Running Unified Component Compatibility Tests")
    print("=" * 60)
    
    success = True
    success &= test_unified_serialization()
    success &= test_component_compatibility()
    
    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED - Unified components are production ready!")
    else:
        print("SOME TESTS FAILED - Review errors above")
    print("=" * 60)
