"""Module for serializable objects in the system."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import cloudpickle
import msgpack
import yaml

T = TypeVar("T", bound="Serializable")


class Serializable(ABC):
    """Base class for all serializable objects in the system.

    Provides methods for serializing/deserializing objects to various formats.
    """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary representation."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create instance from dictionary representation."""
        pass

    def to_json(self) -> str:
        """Serialize to JSON string."""
        try:
            return json.dumps(self.to_dict())
        except Exception:
            raise

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create instance from JSON string."""
        try:
            return cls.from_dict(json.loads(json_str))
        except Exception:
            raise

    def to_yaml(self) -> str:
        """Serialize to YAML string.

        Returns:
            str: YAML string representation of the object.

        Raises:
            Exception: If serialization fails.
        """
        try:
            return yaml.dump(
                self.to_dict(), sort_keys=False, default_flow_style=False
            )
        except Exception:
            raise

    @classmethod
    def from_yaml(cls: type[T], yaml_str: str) -> T:
        """Create instance from YAML string.

        Args:
            yaml_str: YAML string to deserialize.

        Returns:
            T: Instance of class created from YAML.

        Raises:
            yaml.YAMLError: If YAML parsing fails.
            Exception: If deserialization fails.
        """
        try:
            return cls.from_dict(yaml.safe_load(yaml_str))
        except Exception:
            raise

    def to_yaml_file(self, path: Path) -> None:
        """Serialize to YAML file.

        Args:
            path: Path where to save the YAML file.

        Raises:
            Exception: If serialization or file operation fails.
        """
        try:
            # Create parent directories if they don't exist
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

            yaml_str = self.to_yaml()
            path.write_text(yaml_str)
        except Exception:
            raise

    @classmethod
    def from_yaml_file(cls: type[T], path: Path) -> T:
        """Create instance from YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            T: Instance of class created from YAML file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
            Exception: If deserialization fails.
        """
        try:
            return cls.from_yaml(path.read_text())
        except Exception:
            raise

    def to_msgpack(self, path: Path | None = None) -> bytes:
        """Serialize to msgpack bytes."""
        try:
            msgpack_bytes = msgpack.packb(self.to_dict())
            if path:
                path.write_bytes(msgpack_bytes)
            return msgpack_bytes
        except Exception:
            raise

    @classmethod
    def from_msgpack(cls: type[T], msgpack_bytes: bytes) -> T:
        """Create instance from msgpack bytes."""
        try:
            return cls.from_dict(msgpack.unpackb(msgpack_bytes))
        except Exception:
            raise

    @classmethod
    def from_msgpack_file(cls: type[T], path: Path) -> T:
        """Create instance from msgpack file."""
        try:
            return cls.from_msgpack(path.read_bytes())
        except Exception:
            raise

    def to_pickle(self) -> bytes:
        """Serialize to pickle bytes."""
        try:
            return cloudpickle.dumps(self)
        except Exception:
            raise

    @classmethod
    def from_pickle(cls, pickle_bytes: bytes) -> T:
        """Create instance from pickle bytes."""
        try:
            return cloudpickle.loads(pickle_bytes)
        except Exception:
            raise

    @classmethod
    def from_pickle_file(cls: type[T], path: Path) -> T:
        """Create instance from pickle file."""
        try:
            return cls.from_pickle(path.read_bytes())
        except Exception:
            raise

    @staticmethod
    def _filter_none_values(data: Any) -> Any:
        """Filter out None values from dictionaries.

        Args:
            data: The data to filter.

        Returns:
            The filtered data with None values removed.
        """
        if data is None:
            return None
        elif isinstance(data, dict):
            return {
                k: Serializable._filter_none_values(v)
                for k, v in data.items()
                if v is not None
            }
        elif isinstance(data, list):
            return [
                Serializable._filter_none_values(item)
                for item in data
                if item is not None
            ]
        return data
