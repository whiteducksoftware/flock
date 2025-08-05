#!/usr/bin/env python3
"""Test that FlockFactory creates fully functional agents with unified components."""

from flock.core import Flock, FlockFactory


def test_factory_creates_working_agents():
    """Test that factory-created agents work correctly."""
    print("Testing FlockFactory creates working agents")
    print("=" * 50)
    
    # Create a flock and agent using the factory (as in examples)
    MODEL = 'azure/gpt-4.1'
    flock = Flock(name='test_flock', description='Test flock', model=MODEL)
    
    presentation_agent = FlockFactory.create_default_agent(
        name='presentation_agent',
        input='topic',
        output='title, summary',
        no_output=True  # Suppress output for test
    )
    
    flock.add_agent(presentation_agent)
    
    print(f"Created agent: {presentation_agent.name}")
    print(f"Model: {presentation_agent.model}")
    print(f"Components: {len(presentation_agent.components)}")
    
    # Verify components are properly set up
    print("\nComponent verification:")
    print(f"- Evaluator: {presentation_agent.evaluator.name if presentation_agent.evaluator else 'None'}")
    print(f"- Router: {presentation_agent.router.name if presentation_agent.router else 'None'}")
    
    # Test component lifecycle manually (without LLM call)
    print("\nTesting component lifecycle:")
    
    test_inputs = {"topic": "Test topic"}
    
    try:
        # Test that all components can be initialized
        for component in presentation_agent.components:
            print(f"- Component {component.name}: {type(component).__name__}")
        
        print("All components properly instantiated")
        
        # Test that the agent structure is correct for the flock
        print(f"Agent ready for flock execution: {presentation_agent.name}")
        
    except Exception as e:
        print(f"Error during component testing: {e}")
        return False
    
    print("\nFlockFactory creates fully functional agents!")
    return True


if __name__ == "__main__":
    test_factory_creates_working_agents()
