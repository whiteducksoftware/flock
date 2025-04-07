# src/flock/core/loader.py
"""Provides functionality to load Flock instances from files."""

from pathlib import Path
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid runtime circular import if Flock imports this module indirectly
if TYPE_CHECKING:
    from flock.core.flock import Flock

# Import locally within the function to ensure Serializable methods are available
# from .serialization.serializable import Serializable # Serializable defines the file methods

# Cloudpickle check needs to be top-level
try:
    import cloudpickle

    PICKLE_AVAILABLE = True
except ImportError:
    PICKLE_AVAILABLE = False


def load_flock_from_file(file_path: str) -> "Flock":
    """Load a Flock instance from various file formats (detects type)."""
    # Import Flock locally within the function to avoid circular dependency at module level
    from flock.core.flock import Flock

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Flock file not found: {file_path}")

    try:
        if p.suffix.lower() in [".yaml", ".yml"]:
            return Flock.from_yaml_file(p)
        elif p.suffix.lower() == ".json":
            # Assuming from_json is available via Serializable or directly on Flock
            return Flock.from_json(p.read_text())
        elif p.suffix.lower() == ".msgpack":
            # Assuming from_msgpack_file is available via Serializable or directly on Flock
            return Flock.from_msgpack_file(p)
        elif p.suffix.lower() == ".pkl":
            if PICKLE_AVAILABLE:
                # Assuming from_pickle_file is available via Serializable or directly on Flock
                return Flock.from_pickle_file(p)
            else:
                raise RuntimeError(
                    "Cannot load Pickle file: cloudpickle not installed."
                )
        else:
            raise ValueError(f"Unsupported file extension: {p.suffix}")
    except Exception as e:
        # Add specific error logging if helpful
        from flock.core.logging.logging import get_logger

        logger = get_logger("loader")
        logger.error(
            f"Error loading Flock from {file_path}: {e}", exc_info=True
        )
        raise  # Re-raise the original exception
