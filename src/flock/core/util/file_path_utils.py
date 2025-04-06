"""Utility functions for handling file paths in Flock.

This module provides utilities for working with file paths,
especially for components that may be loaded from file system paths
rather than module imports.
"""

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Any


def get_file_path(obj: Any) -> str | None:
    """Get the file path for a Python object.

    Args:
        obj: The object to get the file path for

    Returns:
        The file path if it can be determined, None otherwise
    """
    try:
        if inspect.ismodule(obj):
            return obj.__file__
        elif inspect.isclass(obj) or inspect.isfunction(obj):
            return inspect.getfile(obj)
        return None
    except (TypeError, ValueError):
        return None


def normalize_path(path: str) -> str:
    """Normalize a path for consistent representation.

    Args:
        path: The path to normalize

    Returns:
        The normalized path
    """
    return os.path.normpath(path)


def is_same_path(path1: str, path2: str) -> bool:
    """Check if two paths point to the same file.

    Args:
        path1: The first path
        path2: The second path

    Returns:
        True if the paths point to the same file, False otherwise
    """
    return os.path.normpath(os.path.abspath(path1)) == os.path.normpath(
        os.path.abspath(path2)
    )


def get_relative_path(path: str, base_path: str | None = None) -> str:
    """Get a path relative to a base path.

    Args:
        path: The path to make relative
        base_path: The base path (defaults to current working directory)

    Returns:
        The relative path
    """
    if base_path is None:
        base_path = os.getcwd()

    return os.path.relpath(path, base_path)


def load_class_from_file(file_path: str, class_name: str) -> type | None:
    """Load a class from a file.

    Args:
        file_path: The path to the file
        class_name: The name of the class to load

    Returns:
        The loaded class, or None if it could not be loaded
    """
    try:
        # Generate a unique module name to avoid conflicts
        module_name = f"flock_dynamic_import_{hash(file_path)}"

        # Create a spec for the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            return None

        # Create and load the module
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get the class from the module
        if not hasattr(module, class_name):
            return None

        return getattr(module, class_name)
    except Exception:
        return None


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        The project root path
    """
    # Try to find the directory containing pyproject.toml or setup.py
    current_dir = Path(os.getcwd())

    # Walk up the directory tree looking for project markers
    for path in [current_dir, *current_dir.parents]:
        if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
            return path

    # Default to current directory if no project markers found
    return current_dir


def component_path_to_file_path(component_path: str) -> str | None:
    """Convert a component path (module.ClassName) to a file path.

    Args:
        component_path: The component path in the form module.ClassName

    Returns:
        The file path if it can be determined, None otherwise
    """
    try:
        # Split into module path and class name
        if "." not in component_path:
            return None

        module_path, class_name = component_path.rsplit(".", 1)

        # Import the module
        module = importlib.import_module(module_path)

        # Get the file path
        if hasattr(module, "__file__"):
            return module.__file__

        return None
    except (ImportError, AttributeError):
        return None


def file_path_to_component_path(file_path: str, class_name: str) -> str | None:
    """Convert a file path and class name to a component path (module.ClassName).

    This is approximate and may not work in all cases, especially for non-standard
    module structures.

    Args:
        file_path: The file path to the module
        class_name: The name of the class

    Returns:
        The component path if it can be determined, None otherwise
    """
    try:
        # Convert the file path to an absolute path
        abs_path = os.path.abspath(file_path)

        # Get the project root
        root = get_project_root()

        # Get the relative path from the project root
        rel_path = os.path.relpath(abs_path, root)

        # Convert to a module path
        module_path = os.path.splitext(rel_path)[0].replace(os.sep, ".")

        # Remove 'src.' prefix if present (common in Python projects)
        if module_path.startswith("src."):
            module_path = module_path[4:]

        # Combine with the class name
        return f"{module_path}.{class_name}"
    except Exception:
        return None


def register_file_paths_in_registry(
    component_paths: dict[str, str], registry: Any | None = None
) -> bool:
    """Register file paths in the registry.

    Args:
        component_paths: Dictionary mapping component paths to file paths
        registry: The registry to register in (defaults to the global registry)

    Returns:
        True if all paths were registered, False otherwise
    """
    try:
        # Get the global registry if none provided
        if registry is None:
            from flock.core.flock_registry import get_registry

            registry = get_registry()

        # Initialize component_file_paths if needed
        if not hasattr(registry, "_component_file_paths"):
            registry._component_file_paths = {}

        # Register each path
        for component_name, file_path in component_paths.items():
            if component_name in registry._components:
                registry._component_file_paths[component_name] = file_path

        return True
    except Exception:
        return False
