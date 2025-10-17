"""
Theme API Endpoints

Serves 300+ terminal color themes from TOML files.
Themes are loaded from src/flock/themes/
"""

from pathlib import Path
from typing import Any

import toml
from fastapi import APIRouter, HTTPException


router = APIRouter()

# Path to themes directory
THEMES_DIR = Path(__file__).parent.parent / "themes"


@router.get("/themes")
async def list_themes() -> dict[str, list[str]]:
    """
    List all available theme names.

    Returns:
        Dictionary with 'themes' key containing sorted list of theme names
    """
    try:
        if not THEMES_DIR.exists():
            return {"themes": []}

        theme_files = list(THEMES_DIR.glob("*.toml"))
        theme_names = sorted([f.stem for f in theme_files])

        return {"themes": theme_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list themes: {e!s}")


@router.get("/themes/{theme_name}")
async def get_theme(theme_name: str) -> dict[str, Any]:
    """
    Get theme data by name.

    Args:
        theme_name: Name of the theme (without .toml extension)

    Returns:
        Dictionary with 'name' and 'data' containing theme colors

    Raises:
        HTTPException: If theme not found or failed to load
    """
    try:
        # Sanitize theme name to prevent path traversal
        theme_name = theme_name.replace("/", "").replace("\\", "").replace("..", "")

        theme_path = THEMES_DIR / f"{theme_name}.toml"

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
        raise HTTPException(
            status_code=500, detail=f"Failed to load theme '{theme_name}': {e!s}"
        )
