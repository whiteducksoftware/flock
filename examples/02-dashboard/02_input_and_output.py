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

asyncio.run(flock.serve(dashboard=True), debug=True)
