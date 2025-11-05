"""ServerComponent for static files."""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig


class StaticFilesComponentConfig(ServerComponentConfig):
    """Configuration class for StaticFilesServerComponent."""

    prefix: str = Field(default="", description="Optional prefix.")
    tags: list[str] = Field(default=["Static Files"], description="OpenAPI tags.")
    mount_point: Path | str | None = Field(
        default="/",
        description="The path where the static files should be mounted under. (Defaults to '/')",
    )
    static_files_path: Path | str | None = Field(
        description="Path where the static files that should be served are located."
    )


class StaticFilesServerComponent(ServerComponent):
    """ServerComponent for serving static files."""

    name: str = Field(default="static_files", description="Name for the Component.")
    config: StaticFilesComponentConfig = Field(
        default_factory=StaticFilesComponentConfig,
        description="Configuration for the component.",
    )
    priority: int = Field(
        default=10_000_000,
        description="Registration priority. STATIC FILES MUST BE REGISTERED LAST AS THEY ACT AS A CATCH-ALL",
    )

    def configure(self, app, orchestrator):
        # No op
        pass

    def register_routes(self, app, orchestrator):
        """Register Routes (mount static files)."""
        static_files_path: Path = Path(self.config.static_files_path)

        if not static_files_path.exists():
            raise ValueError(
                f"StaticFilesComponent: Static Files dir does not exist: {self.config.static_files_path}"
            )
        app.mount(
            "/",
            StaticFiles(
                directory=static_files_path,
                html=True,
                follow_symlink=True,
            ),
        )

    async def on_startup_async(self, orchestrator):
        # No - op
        pass

    async def on_shutdown_async(self, orchestrator):
        # No - op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
