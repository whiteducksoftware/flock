"""Module for serializable objects in the system."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import cloudpickle
import msgpack
import toml

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

    def to_toml(self) -> str:
        """Serialize to TOML string.

        Note that TOML doesn't support None/null values, so these will be filtered out.

        Returns:
            A TOML formatted string representation of the object.

        Raises:
            Exception: If serialization fails for any reason.
        """
        try:
            # Get the dictionary representation
            data_dict = self.to_dict()

            # Filter out None values since TOML doesn't support them
            filtered_dict = self._filter_none_values(data_dict)

            # Serialize to TOML
            return toml.dumps(filtered_dict)
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

    @classmethod
    def from_toml(cls: type[T], toml_str: str) -> T:
        """Create instance from TOML string.

        Note that TOML doesn't support None/null values, so any None values in the original
        data structure will not be present in the deserialized object.

        Args:
            toml_str: A TOML formatted string to deserialize.

        Returns:
            An instance of the class created from the TOML data.

        Raises:
            Exception: If deserialization fails for any reason.
        """
        try:
            data = toml.loads(toml_str)
            return cls.from_dict(data)
        except Exception:
            raise

    def to_toml_file(self, path: Path) -> None:
        """Save instance to a TOML file.

        Args:
            path: Path where the TOML file should be saved.

        Raises:
            Exception: If file operations or serialization fails.
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write TOML content to file
            path.write_text(self.to_toml())
        except Exception:
            raise

    @classmethod
    def from_toml_file(cls: type[T], path: Path) -> T:
        """Create instance from TOML file.

        Args:
            path: Path to the TOML file to load.

        Returns:
            An instance of the class created from the TOML file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            Exception: If deserialization fails for any other reason.
        """
        try:
            if not path.exists():
                raise FileNotFoundError(f"TOML file not found: {path}")

            return cls.from_toml(path.read_text())
        except Exception:
            raise
