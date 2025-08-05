#!/usr/bin/env python3
"""Quick serialization test for unified FlockAgent."""

import json
from flock.core.flock_agent import FlockAgent

def test_basic_serialization():
    """Quick test of basic agent serialization."""
    print("🧪 Quick Serialization Test")
    print("-" * 30)
    
    try:
        # Create a simple agent
        agent = FlockAgent(
            name="test_agent",
            model="openai/gpt-4o-mini",
            description="Test agent",
            input="query: str",
            output="result: str"
        )
        
        print(f"✅ Agent created: {agent.name}")
        print(f"   - Components: {len(agent.components)}")
        print(f"   - Evaluator: {agent.evaluator}")
        print(f"   - Router: {agent.router}")
        
        # Test serialization
        agent_dict = agent.to_dict()
        print(f"✅ Serialization successful")
        print(f"   - Keys: {list(agent_dict.keys())}")
        
        # Test JSON
        json_str = json.dumps(agent_dict, indent=2, default=str)
        print(f"✅ JSON conversion successful: {len(json_str)} chars")
        
        # Test deserialization  
        restored_agent = FlockAgent.from_dict(agent_dict)
        print(f"✅ Deserialization successful: {restored_agent.name}")
        
        print("🎉 Basic serialization working!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_basic_serialization()
