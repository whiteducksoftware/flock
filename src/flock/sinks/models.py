"""The receipts a sink publishes for every delivery."""

from __future__ import annotations

from pydantic import BaseModel, Field

from flock.registry import flock_type


@flock_type
class Delivered(BaseModel):
    """The target accepted the artifacts (HTTP 2xx)."""

    sink: str = Field(description="Name of the sink")
    method: str = Field(description="HTTP method, e.g. POST")
    target: str = Field(description="The target as declared, e.g. myapp:/billing")
    status: int = Field(description="HTTP status of the target's answer")
    attempts: int = Field(description="Requests sent, retries included")
    latency_ms: float = Field(description="From the first request to the answer")
    artifact_ids: list[str] = Field(description="The delivered artifacts")
    response_error: str | None = Field(
        default=None,
        description="Why the answer did not parse into the sink's response type",
    )


@flock_type
class DeliveryFailed(BaseModel):
    """The target refused the artifacts, or every attempt failed."""

    sink: str = Field(description="Name of the sink")
    method: str = Field(description="HTTP method, e.g. POST")
    target: str = Field(description="The target as declared, e.g. myapp:/billing")
    status: int | None = Field(
        description="HTTP status of the last answer; None without an answer"
    )
    attempts: int = Field(description="Requests sent, retries included")
    error: str = Field(description="What went wrong")
    artifact_ids: list[str] = Field(description="The artifacts not delivered")


__all__ = ["Delivered", "DeliveryFailed"]
