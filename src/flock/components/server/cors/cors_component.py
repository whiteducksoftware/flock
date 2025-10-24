"""ServerComponent for configuring CORS."""

from typing import Any

from fastapi import FastAPI
from pydantic import Field
from starlette.middleware.cors import CORSMiddleware

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.orchestrator import Flock


class CORSComponentConfig(ServerComponentConfig):
    """Config for CORS-ServerComponent."""
    allow_origins: list[Any] = Field(
        default=["*"],
        description="list of allowed origins."
    )
    allow_credentials: bool = Field(
        default=True
    )
    allow_methods: list[Any] = Field(
        default=["*"],
        description="List of allowed methods."
    )
    allow_headers: list[Any] = Field(
        default=["*"],
        description="List of allowed headers."
    )

class CORSComponent(ServerComponent):
    """Component that allows configuring CORS behavior."""
    name = "cors"
    priority: int = Field(
        default=8,
        description="Registration priority."
    )
    config: CORSComponentConfig = Field(
        default_factory=CORSComponentConfig,
        description="CORS Configuration."
    )

    def configure(self, app: FastAPI, orchestrator: Flock):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.allow_origins,
            allow_credentials=self.config.allow_credentials,
            allow_methods=self.config.allow_methods,
            allow_headers=self.config.allow_headers,
        )

    def register_routes(self, app, orchestrator):
        # No routes to register here.
        pass

    async def on_shutdown_async(self, orchestrator):
        # No op
        pass

    async def on_startup_async(self, orchestrator):
        # No op
        pass

    def get_dependencies(self) -> list[type[ServerComponent]]:
        return [] # no dependencies
