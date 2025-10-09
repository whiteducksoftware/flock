import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class Signal(BaseModel):
    value: int
    hop: int

flock = Flock("openai/gpt-4.1")

print("Creating 100 agents...")

for i in range(100):
    agent_name = f"agent_{i:03d}"
    output_type_name = f"Signal{i:03d}"
    output_type = type(
        output_type_name,
        (Signal,),
        {
            "__module__": __name__,
            "__annotations__": {"value": int, "hop": int},
        },
    )
    flock_type(output_type)
    
    if i == 0:
        input_type = Signal
    else:
        prev_output_type_name = f"Signal{i - 1:03d}"
        input_type = globals().get(prev_output_type_name)
        if input_type is None:
            input_type = type(
                prev_output_type_name,
                (Signal,),
                {
                    "__module__": __name__,
                    "__annotations__": {"value": int, "hop": int},
                },
            )
            flock_type(input_type)
    
    globals()[output_type_name] = output_type
    
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
print("  - Grid: 10×10 organized grid")
print("  - Random: Stress test collision detection")
print("\n🚀 Starting dashboard...")

async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
