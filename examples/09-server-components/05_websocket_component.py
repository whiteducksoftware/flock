"""
WebSocket Component Examples

This example demonstrates the WebSocketServerComponent capabilities:
1. Basic WebSocket connection
2. Real-time event streaming
3. Connection management
4. Custom configuration
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.server import (
    WebSocketComponentConfig,
    WebSocketServerComponent,
)


class TaskUpdate(BaseModel):
    """Example artifact for task updates."""

    task_id: str
    status: str
    progress: float
    message: str


async def main():
    """Demonstrate WebSocket component usage."""
    print("🔌 WebSocket Component Examples\n")
    print("=" * 60)

    # Example 1: Basic WebSocket setup
    print("\n1️⃣  Basic WebSocket Setup")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    websocket_component = WebSocketServerComponent(
        config=WebSocketComponentConfig(
            prefix="/ws",
            max_connections=100,
        )
    )

    print("✅ WebSocket component created")
    print(f"   Endpoint: ws://127.0.0.1:8344{websocket_component.config.prefix}")
    print(f"   Max connections: {websocket_component.config.max_connections}")

    # Example 2: Create agent that publishes updates
    print("\n2️⃣  Agent with Real-time Updates")
    print("-" * 60)

    task_processor = (
        flock.agent("task_processor")
        .description("Process tasks and publish updates")
        .consumes(TaskUpdate)
        .publishes(TaskUpdate)
        .instruction("Update the task progress and add processing details")
    )

    print("✅ Agent created:")
    print(f"   Name: {task_processor.name}")
    print("   Consumes: TaskUpdate")
    print("   Publishes: TaskUpdate")

    # Example 3: Full server setup with WebSocket
    print("\n3️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with WebSocket component...")
    print("   WebSocket endpoint: ws://127.0.0.1:8344/ws")
    print("\n   The WebSocket will broadcast:")
    print("   - Agent activation events")
    print("   - Agent completion events")
    print("   - Artifact publications")
    print("   - Streaming LLM output")
    print("\n   Connect using JavaScript:")
    print("   const ws = new WebSocket('ws://127.0.0.1:8344/ws');")
    print("   ws.onmessage = (event) => console.log(JSON.parse(event.data));")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[websocket_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 4: Publish some test updates to trigger WebSocket events
    print("\n4️⃣  Publishing Test Updates")
    print("-" * 60)

    test_updates = [
        TaskUpdate(
            task_id="task-001",
            status="started",
            progress=0.0,
            message="Task processing started",
        ),
        TaskUpdate(
            task_id="task-001",
            status="processing",
            progress=0.5,
            message="Halfway through processing",
        ),
        TaskUpdate(
            task_id="task-001",
            status="completed",
            progress=1.0,
            message="Task completed successfully",
        ),
    ]

    for i, update in enumerate(test_updates, 1):
        print(f"\n📤 Publishing update {i}/{len(test_updates)}")
        print(f"   Task ID: {update.task_id}")
        print(f"   Status: {update.status}")
        print(f"   Progress: {update.progress * 100}%")
        print(f"   Message: {update.message}")

        await flock.publish(update)
        await flock.run_until_idle()

        # Small delay between updates
        await asyncio.sleep(2)

    print("\n✅ All updates published!")
    print("   WebSocket clients should have received all events")

    # Keep server running
    print("\n⏳ Keeping server running for 30 seconds...")
    try:
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
