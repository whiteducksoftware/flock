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
        # Sanitize theme name: only allow alphanumeric, hyphen, underscore
        # This prevents path traversal attacks
        import re

        if not re.match(r"^[a-zA-Z0-9_-]+$", theme_name):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid theme name '{theme_name}'. "
                "Only alphanumeric characters, hyphens, and underscores allowed.",
            )

        # Get list of valid theme files (safe enumeration, not user-controlled path)
        themes_dir_resolved = THEMES_DIR.resolve()
        valid_themes = {f.stem: f for f in themes_dir_resolved.glob("*.toml")}

        # Lookup theme from validated names only (no path construction from user input)
        if theme_name not in valid_themes:
            raise HTTPException(
                status_code=404, detail=f"Theme '{theme_name}' not found"
            )

        theme_path = valid_themes[theme_name]

        # Defense in depth: verify resolved path is still within THEMES_DIR
        # (should always pass since we looked up from glob, but extra safety)
        if not theme_path.is_relative_to(themes_dir_resolved):
            raise HTTPException(
                status_code=400, detail=f"Invalid theme name '{theme_name}'"
            )

        # Load TOML theme (path exists since it came from glob)
        theme_data = toml.load(theme_path)

        return {"name": theme_name, "data": theme_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load theme '{theme_name}': {e!s}"
        )
