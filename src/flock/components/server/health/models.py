from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: Literal["ok"] = Field(default="ok", description="Health status")
