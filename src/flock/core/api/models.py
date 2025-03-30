# src/flock/core/api/models.py
"""Pydantic models for the Flock API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FlockAPIRequest(BaseModel):
    """Request model for running an agent via JSON API."""

    agent_name: str = Field(..., description="Name of the agent to run")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input data for the agent"
    )
    async_run: bool = Field(
        default=False, description="Whether to run asynchronously"
    )


class FlockAPIResponse(BaseModel):
    """Response model for API run requests."""

    run_id: str = Field(..., description="Unique ID for this run")
    status: str = Field(..., description="Status of the run")
    result: dict[str, Any] | None = Field(
        None, description="Run result if completed"
    )
    started_at: datetime = Field(..., description="When the run started")
    completed_at: datetime | None = Field(
        None, description="When the run completed"
    )
    error: str | None = Field(None, description="Error message if failed")
