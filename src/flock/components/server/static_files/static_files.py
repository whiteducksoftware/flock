"""ServerComponent for static files."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.core.orchestrator import Flock


class StaticFilesComponentConfig(ServerComponentConfig):
    """Configuration class for StaticFilesServerComponent."""
    prefix: str = Field(
        default="",
        description="Optional prefix."
    )
    tags: list[str] = Field(
        default=["Static Files"],
        description="OpenAPI tags."
    )

class StaticFilesServerComponent(ServerComponent):
    """ServerComponent for serving static files."""
    name: str = "static_files"
    config: StaticFilesComponentConfig = Field(
        default_factory=StaticFilesComponentConfig,
        description="Configuration for the component."
    )
    priority: int = Field(
        default=10_000_000,
        description="Registration priority. STATIC FILES MUST BE REGISTERED LAST AS THEY ACT AS A CATCH-ALL"
    )

    def configure(self, app: FastAPI, orchestrator: Flock):
        # No op
        pass

    def register_routes(self, app: FastAPI, orchestrator: Flock):
        """Register Routes (mount static files)."""
        current_files = __file__
        asset_folder = "assets"
        full_path = f"{current_files}/{asset_folder}/"
        static_files_path: Path = Path(full_path)

        if not static_files_path.exists():
            raise ValueError(
                f"StaticFilesComponent: Static Files dir does not exist: {full_path}"
            )
        app.mount(
            "/",
            StaticFiles(
                directory=static_files_path
            ),
        )

    async def on_startup_async(self, orchestrator: Flock):
        # No - op
        pass

    async def on_shutdown_async(self, orchestrator: Flock):
        # No - op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
