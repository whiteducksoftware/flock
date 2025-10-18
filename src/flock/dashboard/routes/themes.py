"""Theme management API routes for dashboard."""

from pathlib import Path
from typing import Any

import toml
from fastapi import FastAPI, HTTPException

from flock.logging.logging import get_logger


logger = get_logger("dashboard.routes.themes")


def register_theme_routes(app: FastAPI) -> None:
    """Register theme API endpoints for dashboard customization.

    Args:
        app: FastAPI application instance
    """
    themes_dir = Path(__file__).parent.parent.parent / "themes"

    @app.get("/api/themes")
    async def list_themes() -> dict[str, Any]:
        """Get list of available theme names.

        Returns:
            {"themes": ["dracula", "nord", ...]}
        """
        try:
            if not themes_dir.exists():
                return {"themes": []}

            theme_files = list(themes_dir.glob("*.toml"))
            theme_names = sorted([f.stem for f in theme_files])

            return {"themes": theme_names}
        except Exception as e:
            logger.exception(f"Failed to list themes: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list themes: {e!s}")

    @app.get("/api/themes/{theme_name}")
    async def get_theme(theme_name: str) -> dict[str, Any]:
        """Get theme data by name.

        Args:
            theme_name: Name of theme (without .toml extension)

        Returns:
            {
                "name": "dracula",
                "data": {
                    "colors": {...}
                }
            }
        """
        try:
            # Sanitize theme name to prevent path traversal
            theme_name = theme_name.replace("/", "").replace("\\", "").replace("..", "")

            theme_path = themes_dir / f"{theme_name}.toml"

            if not theme_path.exists():
                raise HTTPException(
                    status_code=404, detail=f"Theme '{theme_name}' not found"
                )

            # Load TOML theme
            theme_data = toml.load(theme_path)

            return {"name": theme_name, "data": theme_data}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to load theme '{theme_name}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to load theme: {e!s}")
