"""Component for serving theme files."""

from pathlib import Path
from typing import Any

import toml
from fastapi import HTTPException
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)


class ThemesComponentConfig(ServerComponentConfig):
    """Configuration class for ThemesService."""

    prefix: str = Field(default="/plugin/", description="Optional Prefix.")
    tags: list[str] = Field(
        default=["Theme files"], description="Tags for the OpenAPI documentation."
    )


class ThemesComponent(ServerComponent):
    """ServerComponent that provides theme files."""

    name: str = "themes"
    priority: int = Field(default=2, description="Registration priority.")
    themes_dir: Path | None = Field(default=None, description="Themes directory.")
    config: ThemesComponentConfig = Field(
        default_factory=ThemesComponentConfig, description="Optional config."
    )

    def configure(self, app, orchestrator):
        """Configure the Server Component."""
        logger.debug("Configuring ThemesComponent.")
        if not self.themes_dir:
            self.themes_dir = Path(__file__).parent.parent.parent.parent / "themes"
            logger.debug(
                f"ThemesComponent serving theme files from: {self.themes_dir!s}"
            )

    def register_routes(self, app, orchestrator):
        """Register theme routes."""

        @app.get(self._join_path(self.config.prefix, "themes"), tags=self.config.tags)
        async def list_themes() -> dict[str, list[str]]:
            """List all available theme names.

            Returns:
                Dictionary with 'themes' key containing sorted list of theme names.
            """
            try:
                if not self.themes_dir.exists():
                    logger.warning(
                        f"ThemesComponent: Themes dir: {self.themes_dir!s} does not exist."
                    )
                    return {"themes": []}
                theme_files = list(self.themes_dir.glob("*.toml"))
                theme_names = sorted([f.stem for f in theme_files])
                return {"themes": theme_names}
            except Exception as ex:
                logger.exception(
                    f"Exception occurred while trying to access themes dir: {ex!s}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Failed to list themes: {ex!s}"
                ) from ex

        @app.get(
            self._join_path(self.config.prefix, "themes/{theme_name}"),
            tags=self.config.tags,
        )
        async def get_theme(theme_name: str) -> dict[str, Any]:
            """Get theme data by name.

            Args:
                theme_name: Name of the theme (without .toml extension)
            Returns:
                Dictionary with 'name' and 'data' containing theme colors
            Raises:
                HTTPException: If theme not found or failed to load
            """
            try:
                # Sanitize theme name to prevent path traversal
                theme_name = (
                    theme_name.replace("/", "").replace("\\", "").replace("..", "")
                )
                theme_path = self.themes_dir / f"{theme_name}.toml"
                if not theme_path.exists():
                    raise HTTPException(
                        status_code=404, detail=f"Theme '{theme_name}' not found."
                    )
                theme_data = toml.load(theme_path)
                return {"name": theme_name, "data": theme_data}
            except HTTPException:
                raise
            except Exception as ex:
                logger.exception(
                    f"ThemeComponent: failed to load theme {theme_name}: {ex!s}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load theme '{theme_name}': {ex!s}",
                ) from ex

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
