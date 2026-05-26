import os
import random  # Added for random theme selection
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flock.core.flock import Flock

from flock.core.logging.formatters.themes import OutputTheme

FLOCK_FILES_DIR = Path(os.getenv("FLOCK_FILES_DIR", "./.flock_ui_projects"))
FLOCK_FILES_DIR.mkdir(parents=True, exist_ok=True)

# --- Shared Links Database Configuration ---
# Default path is relative to the .flock/ directory in the workspace root if FLOCK_ROOT is not set
# or if .flock is not a sibling of FLOCK_BASE_DIR.
# More robustly, place it inside a user-specific or project-specific data directory.
_default_shared_links_db_parent = Path(os.getenv("FLOCK_ROOT", ".")) / ".flock"
SHARED_LINKS_DB_PATH = Path(
    os.getenv(
        "SHARED_LINKS_DB_PATH",
        str(_default_shared_links_db_parent / "shared_links.db")
    )
)
# Ensure the directory for the DB exists, though the store will also do this.
SHARED_LINKS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- Theme Configuration ---
# Calculate themes directory relative to this config file's location, assuming structure:
# src/flock/webapp/app/config.py
# src/flock/themes/
CONFIG_FILE_PATH = Path(__file__).resolve() # src/flock/webapp/app/config.py
FLOCK_WEBAPP_DIR = CONFIG_FILE_PATH.parent.parent # src/flock/webapp/
FLOCK_BASE_DIR = FLOCK_WEBAPP_DIR.parent # src/flock/
THEMES_DIR = FLOCK_BASE_DIR / "themes"

# Global state for MVP - NOT SUITABLE FOR PRODUCTION/MULTI-USER
CURRENT_FLOCK_INSTANCE: "Flock | None" = None
CURRENT_FLOCK_FILENAME: str | None = None

DEFAULT_THEME_NAME = OutputTheme.ciapre.value # Default if random fails or invalid theme specified

def list_available_themes() -> list[str]:
    """Scans the THEMES_DIR for .toml files and returns their names (without .toml)."""
    if not THEMES_DIR.exists() or not THEMES_DIR.is_dir():
        return []
    return sorted([p.stem for p in THEMES_DIR.glob("*.toml") if p.is_file()])

# Initialize CURRENT_THEME_NAME
_initial_theme_from_env = os.environ.get("FLOCK_WEB_THEME")
_resolved_initial_theme = DEFAULT_THEME_NAME

if _initial_theme_from_env:
    if _initial_theme_from_env.lower() == "random":
        available_themes = list_available_themes()
        if available_themes:
            _resolved_initial_theme = random.choice(available_themes)
            print(f"Config: Initial theme from FLOCK_WEB_THEME='random' resolved to: {_resolved_initial_theme}")
        else:
            print(f"Warning: FLOCK_WEB_THEME='random' specified, but no themes found in {THEMES_DIR}. Using default: {DEFAULT_THEME_NAME}")
            _resolved_initial_theme = DEFAULT_THEME_NAME
    elif _initial_theme_from_env in [t.value for t in OutputTheme] or _initial_theme_from_env in list_available_themes():
        _resolved_initial_theme = _initial_theme_from_env
        print(f"Config: Initial theme set from FLOCK_WEB_THEME env var: {_resolved_initial_theme}")
    else:
        print(f"Warning: Invalid theme name '{_initial_theme_from_env}' in FLOCK_WEB_THEME. Using default: {DEFAULT_THEME_NAME}")
        _resolved_initial_theme = DEFAULT_THEME_NAME

CURRENT_THEME_NAME: str = _resolved_initial_theme

def set_current_theme_name(theme_name: str | None):
    """Sets the globally accessible current theme name.
    If 'random' is passed, a random theme is chosen.
    """
    global CURRENT_THEME_NAME
    resolved_theme = DEFAULT_THEME_NAME # Default to start

    if theme_name:
        if theme_name.lower() == "random":
            available = list_available_themes()
            if available:
                resolved_theme = random.choice(available)
                print(f"Config: Theme 'random' resolved to: {resolved_theme}")
            else:
                print(f"Warning: Theme 'random' specified, but no themes found in {THEMES_DIR}. Using default: {DEFAULT_THEME_NAME}")
                # resolved_theme remains DEFAULT_THEME_NAME
        elif theme_name in list_available_themes():
            resolved_theme = theme_name
        else:
            print(f"Warning: Invalid theme name provided ('{theme_name}'). Using default: {DEFAULT_THEME_NAME}")
            # resolved_theme remains DEFAULT_THEME_NAME
    else: # theme_name is None
        # resolved_theme remains DEFAULT_THEME_NAME (set at the beginning of function)
        pass

    CURRENT_THEME_NAME = resolved_theme
    # Ensure the theme name is set in the environment if we want other processes to see it,
    # though this might be better handled by the calling process (e.g. CLI)
    # os.environ["FLOCK_WEB_THEME"] = CURRENT_THEME_NAME
    print(f"Config: Current theme explicitly set to: {CURRENT_THEME_NAME}")

def get_current_theme_name() -> str:
    """Gets the globally accessible current theme name."""
    return CURRENT_THEME_NAME
