"""Module for serializable objects in the system."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

import cloudpickle
import msgpack

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
