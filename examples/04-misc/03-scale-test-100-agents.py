"""
Scale Test: 100 Agents Dashboard
==================================
This example creates 100 agents to test dashboard UI performance and layout algorithms
with a large number of nodes. Perfect for stress-testing the visualization system.

How to use:
1. Run this script: `uv run examples/03-the-dashboard/03-scale-test-100-agents.py`
2. Open http://localhost:8344 in your browser
3. Right-click canvas → Auto Layout → Try different layout algorithms:
   - Hierarchical (Vertical/Horizontal) - See how Dagre handles 100 nodes
   - Circular - 100 nodes in a perfect circle
   - Grid - 10x10 grid of agents
   - Random - Stress test collision detection

Expected behavior:
- 100 agent nodes in the graph
- Each agent consumes output from the previous agent (chain pattern)
- Click "Show Controls" and publish a Signal to trigger the chain
- Watch the cascade of activations across all 100 agents

Performance expectations:
- Layout algorithms should complete in <500ms
- Graph should remain interactive with pan/zoom
- WebSocket updates should handle 100+ nodes smoothly

Use cases:
- Test layout algorithm performance with large graphs
- Verify UI remains responsive with many nodes
- Validate WebSocket streaming with high node counts
- Test context menu and interactions with crowded canvas
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.registry import flock_type


# Simple signal artifact that gets passed through the chain
@flock_type
class Signal(BaseModel):
    value: int
    hop: int  # Track how many agents this signal has passed through


# Create orchestrator
flock = Flock()

# Create 100 agents in a chain
# Agent 0 consumes Signal(hop=0)
# Agent 1 consumes output from Agent 0 and produces Signal(hop=1)
# Agent 2 consumes output from Agent 1 and produces Signal(hop=2)
# ... and so on
print("Creating 100 agents...")

for i in range(100):
    agent_name = f"agent_{i:03d}"  # agent_000, agent_001, etc.

    # Create a unique type for this agent's output
    # This allows us to chain agents: agent_0 -> agent_1 -> agent_2 -> ...
    output_type_name = f"Signal{i:03d}"

    # Dynamically create the output type
    output_type = type(
        output_type_name,
        (Signal,),
        {
            "__module__": __name__,
            "__annotations__": {"value": int, "hop": int},
        },
    )
    flock_type(output_type)

    # Determine what this agent consumes
    if i == 0:
        # First agent consumes the initial Signal
        input_type = Signal
    else:
        # All other agents consume output from the previous agent
        prev_output_type_name = f"Signal{i - 1:03d}"
        input_type = globals().get(prev_output_type_name)
        if input_type is None:
            # Create the input type if it doesn't exist
            input_type = type(
                prev_output_type_name,
                (Signal,),
                {
                    "__module__": __name__,
                    "__annotations__": {"value": int, "hop": int},
                },
            )
            flock_type(input_type)

    # Register the output type in globals so subsequent agents can find it
    globals()[output_type_name] = output_type

    # Create the agent
    agent = (
        flock.agent(agent_name)
        .description(f"Agent {i} in the chain - passes signal to next agent")
        .consumes(input_type)
        .publishes(output_type)
    )

    if (i + 1) % 10 == 0:
        print(f"  Created {i + 1}/100 agents...")

print("✅ All 100 agents created!")
print("\n📊 Graph structure:")
print("  - 100 agent nodes")
print("  - 99 edges (chain: agent_000 → agent_001 → ... → agent_099)")
print("  - Total nodes: 100")
print("\n🎨 Try different layouts:")
print("  - Hierarchical (Vertical): Long vertical chain")
print("  - Hierarchical (Horizontal): Long horizontal chain")
print("  - Circular: Perfect circle of 100 nodes")
print("  - Grid: 10x10 organized grid")
print("  - Random: Stress test collision detection")
print("\n🚀 Starting dashboard...")


# Run with dashboard
async def main():
    await flock.serve(dashboard=True)


asyncio.run(main())
