# src/flock/core/registry/config_mapping.py
"""Config-to-component mapping functionality."""

import threading
from typing import TypeVar

from pydantic import BaseModel
from flock.core.logging.logging import get_logger

logger = get_logger("registry.config_mapping")

ConfigType = TypeVar("ConfigType", bound=BaseModel)
ClassType = TypeVar("ClassType", bound=type)

# Global config mapping with thread safety
_component_config_map: dict[type[BaseModel], type] = {}
_config_map_lock = threading.RLock()


class ConfigMapping:
    """Manages config-to-component mappings with thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock

    def register_config_component_pair(
        self, config_cls: type[ConfigType], component_cls: type[ClassType]
    ) -> None:
        """Explicitly register the mapping between a config and component class."""
        # Component config validation can be added here if needed
        # Add more checks if needed (e.g., component_cls inherits from Module/Router/Evaluator)

        with _config_map_lock:
            if (
                config_cls in _component_config_map
                and _component_config_map[config_cls] != component_cls
            ):
                logger.warning(
                    f"Config class {config_cls.__name__} already mapped to {_component_config_map[config_cls].__name__}. "
                    f"Overwriting with {component_cls.__name__}."
                )

            _component_config_map[config_cls] = component_cls
            logger.debug(
                f"Registered config mapping: {config_cls.__name__} -> {component_cls.__name__}"
            )

    def get_component_class_for_config(
        self, config_cls: type[ConfigType]
    ) -> type[ClassType] | None:
        """Look up the Component Class associated with a Config Class."""
        with _config_map_lock:
            return _component_config_map.get(config_cls)

    def get_all_config_mappings(self) -> dict[type[BaseModel], type]:
        """Get all config-to-component mappings."""
        with _config_map_lock:
            return _component_config_map.copy()

    def clear_config_mappings(self) -> None:
        """Clear all config-to-component mappings."""
        with _config_map_lock:
            _component_config_map.clear()
            logger.debug("Cleared all config-to-component mappings")
