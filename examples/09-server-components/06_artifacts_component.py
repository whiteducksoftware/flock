"""
Artifacts Component Examples

This example demonstrates the ArtifactsComponent capabilities:
1. REST API for querying artifacts
2. Publishing artifacts via HTTP POST
3. Pagination and filtering
4. Integration with blackboard storage
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.server import ArtifactComponentConfig, ArtifactsComponent


class Task(BaseModel):
    """Example task artifact."""

    title: str
    priority: str
    completed: bool = False


class TaskResult(BaseModel):
    """Example task result artifact."""

    task_title: str
    result: str
    success: bool


async def main():
    """Demonstrate Artifacts component usage."""
    print("📦 Artifacts Component Examples\n")
    print("=" * 60)

    # Example 1: Basic Artifacts component
    print("\n1️⃣  Basic Artifacts Component")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    artifacts_component = ArtifactsComponent(
        config=ArtifactComponentConfig(
            prefix="/api/v1",
            tags=["Artifacts"],
            enable_pagination=True,
            default_page_size=50,
        )
    )

    print("✅ Artifacts component created")
    print("   Endpoints:")
    print(f"   - GET  {artifacts_component.config.prefix}/artifacts")
    print(f"   - POST {artifacts_component.config.prefix}/artifacts")
    print(f"   Pagination: {artifacts_component.config.enable_pagination}")
    print(f"   Default page size: {artifacts_component.config.default_page_size}")

    # Example 2: Create agent that processes tasks
    print("\n2️⃣  Task Processing Agent")
    print("-" * 60)

    task_processor = (
        flock.agent("task_processor")
        .description("Process tasks and generate results")
        .consumes(Task)
        .publishes(TaskResult)
        .instruction("Analyze the task and provide a detailed result")
    )

    print("✅ Agent created:")
    print(f"   Name: {task_processor.name}")
    print("   Consumes: Task")
    print("   Publishes: TaskResult")

    # Example 3: Full server setup
    print("\n3️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with Artifacts component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Available endpoints:")
    print("   - GET  http://127.0.0.1:8344/api/v1/artifacts")
    print("   - POST http://127.0.0.1:8344/api/v1/artifacts")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[artifacts_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 4: Publish some test tasks
    print("\n4️⃣  Publishing Test Tasks")
    print("-" * 60)

    test_tasks = [
        Task(title="Review code changes", priority="high", completed=False),
        Task(title="Update documentation", priority="medium", completed=False),
        Task(title="Fix bug #123", priority="high", completed=False),
        Task(title="Write unit tests", priority="low", completed=False),
    ]

    for i, task in enumerate(test_tasks, 1):
        print(f"\n📤 Publishing task {i}/{len(test_tasks)}")
        print(f"   Title: {task.title}")
        print(f"   Priority: {task.priority}")

        await flock.publish(task)
        await flock.run_until_idle()

        # Small delay between tasks
        await asyncio.sleep(1)

    print("\n✅ All tasks published and processed!")

    # Example 5: Query artifacts via API
    print("\n5️⃣  Query Artifacts via REST API")
    print("-" * 60)

    print("\n   You can now query artifacts using curl:")
    print("\n   # Get all artifacts:")
    print("   curl http://127.0.0.1:8344/api/v1/artifacts")
    print("\n   # Get artifacts with pagination:")
    print("   curl 'http://127.0.0.1:8344/api/v1/artifacts?page=1&page_size=10'")
    print("\n   # Filter by type:")
    print("   curl 'http://127.0.0.1:8344/api/v1/artifacts?type=Task'")
    print("\n   # Publish new artifact:")
    print("   curl -X POST http://127.0.0.1:8344/api/v1/artifacts \\")
    print('     -H "Content-Type: application/json" \\')
    print(
        '     -d \'{"type": "__main__.Task", "payload": {"title": "New task", "priority": "high", "completed": false}}\''
    )

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try the curl commands above!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
