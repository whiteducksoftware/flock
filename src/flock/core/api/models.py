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


class FlockBatchRequest(BaseModel):
    """Request model for batch processing via JSON API."""

    agent_name: str = Field(..., description="Name of the agent to run")
    batch_inputs: list[dict[str, Any]] | str = Field(
        ..., description="List of input dictionaries or path to CSV file"
    )
    input_mapping: dict[str, str] | None = Field(
        None, description="Maps DataFrame/CSV column names to agent input keys"
    )
    static_inputs: dict[str, Any] | None = Field(
        None, description="Inputs constant across all batch runs"
    )
    parallel: bool = Field(
        default=True, description="Whether to run jobs in parallel"
    )
    max_workers: int = Field(
        default=5, description="Max concurrent workers for parallel runs"
    )
    use_temporal: bool | None = Field(
        None, description="Override Flock's enable_temporal setting"
    )
    box_results: bool = Field(
        default=True, description="Wrap results in Box objects"
    )
    return_errors: bool = Field(
        default=False, description="Return Exception objects for failed runs"
    )
    silent_mode: bool = Field(
        default=True, description="Suppress output and show progress bar"
    )
    write_to_csv: str | None = Field(
        None, description="Path to save results as CSV file"
    )


class FlockBatchResponse(BaseModel):
    """Response model for batch processing requests."""

    batch_id: str = Field(..., description="Unique ID for this batch run")
    status: str = Field(..., description="Status of the batch run")
    results: list[Any] = Field(
        default_factory=list,
        description="List of results from batch processing",
    )
    started_at: datetime = Field(..., description="When the batch run started")
    completed_at: datetime | None = Field(
        None, description="When the batch run completed"
    )
    error: str | None = Field(None, description="Error message if failed")

    # Additional fields for batch progress tracking
    total_items: int = Field(
        0, description="Total number of items in the batch"
    )
    completed_items: int = Field(
        0, description="Number of completed items in the batch"
    )
    progress_percentage: float = Field(
        0.0, description="Percentage of completion (0-100)"
    )
