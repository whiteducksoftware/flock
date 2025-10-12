import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class UserRequest(BaseModel):
    message: str
    priority: str = "normal"

@flock_type
class Response(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str]

flock = Flock("openai/gpt-4.1")

assistant = (
    flock.agent("assistant")
    .description("Helpful assistant that answers questions with sources")
    .consumes(UserRequest)
    .publishes(Response)
)

async def main():
    request = UserRequest(
        message="What are the key benefits of async programming?",
        priority="high"
    )

    print(f"❓ Question: {request.message}")
    print(f"📌 Priority: {request.priority}\n")

    await flock.publish(request)
    await flock.run_until_idle()

    responses = await flock.store.get_by_type(Response)
    if responses:
        response = responses[0]
        print(f"💡 Answer: {response.answer}\n")
        print(f"📊 Confidence: {response.confidence:.2f}")
        print(f"📚 Sources: {len(response.sources)}")
        for i, source in enumerate(response.sources, 1):
            print(f"   {i}. {source}")

if __name__ == "__main__":
    asyncio.run(main())
