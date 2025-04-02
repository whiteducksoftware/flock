# src/flock/core/serialization/serializable.py
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

# Use yaml if available, otherwise skip yaml methods
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Use msgpack if available
try:
    import msgpack

    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False

# Use cloudpickle
try:
    import cloudpickle

    PICKLE_AVAILABLE = True
except ImportError:
    PICKLE_AVAILABLE = False


T = TypeVar("T", bound="Serializable")


class Serializable(ABC):
    """Base class for all serializable objects in the system.

    Provides methods for serializing/deserializing objects to various formats.
    Subclasses MUST implement to_dict and from_dict.
    """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert instance to a dictionary representation suitable for serialization.
        This method should handle converting nested Serializable objects and callables.
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create instance from a dictionary representation.
        This method should handle reconstructing nested Serializable objects and callables.
        """
        pass

    # --- JSON Methods ---
    def to_json(self, indent: int | None = 2) -> str:
        """Serialize to JSON string."""
        # Import encoder locally to avoid making it a hard dependency if JSON isn't used
        from .json_encoder import FlockJSONEncoder

        try:
            # Note: to_dict should ideally prepare the structure fully.
            # FlockJSONEncoder is a fallback for types missed by to_dict.
            return json.dumps(
                self.to_dict(), cls=FlockJSONEncoder, indent=indent
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to serialize {self.__class__.__name__} to JSON: {e}"
            ) from e

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create instance from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to deserialize {cls.__name__} from JSON: {e}"
            ) from e

    # --- YAML Methods ---
    def to_yaml(self, sort_keys=False, default_flow_style=False) -> str:
        """Serialize to YAML string."""
        if not YAML_AVAILABLE:
            raise NotImplementedError(
                "YAML support requires PyYAML: pip install pyyaml"
            )
        try:
            # to_dict should prepare a structure suitable for YAML dumping
            return yaml.dump(
                self.to_dict(),
                sort_keys=sort_keys,
                default_flow_style=default_flow_style,
                allow_unicode=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to serialize {self.__class__.__name__} to YAML: {e}"
            ) from e

    @classmethod
    def from_yaml(cls: type[T], yaml_str: str) -> T:
        """Create instance from YAML string."""
        if not YAML_AVAILABLE:
            raise NotImplementedError(
                "YAML support requires PyYAML: pip install pyyaml"
            )
        try:
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                raise TypeError(
                    f"YAML did not yield a dictionary for {cls.__name__}"
                )
            return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML string: {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to deserialize {cls.__name__} from YAML: {e}"
            ) from e

    def to_yaml_file(self, path: Path | str, **yaml_dump_kwargs) -> None:
        """Serialize to YAML file."""
        if not YAML_AVAILABLE:
            raise NotImplementedError(
                "YAML support requires PyYAML: pip install pyyaml"
            )
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            yaml_str = self.to_yaml(**yaml_dump_kwargs)
            path.write_text(yaml_str, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(
                f"Failed to write {self.__class__.__name__} to YAML file {path}: {e}"
            ) from e

    @classmethod
    def from_yaml_file(cls: type[T], path: Path | str) -> T:
        """Create instance from YAML file."""
        if not YAML_AVAILABLE:
            raise NotImplementedError(
                "YAML support requires PyYAML: pip install pyyaml"
            )
        path = Path(path)
        try:
            yaml_str = path.read_text(encoding="utf-8")
            return cls.from_yaml(yaml_str)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read {cls.__name__} from YAML file {path}: {e}"
            ) from e

    # --- MsgPack Methods ---
    def to_msgpack(self) -> bytes:
        """Serialize to msgpack bytes."""
        if not MSGPACK_AVAILABLE:
            raise NotImplementedError(
                "MsgPack support requires msgpack: pip install msgpack"
            )
        try:
            # Use default hook for complex types if needed, or rely on to_dict
            return msgpack.packb(self.to_dict(), use_bin_type=True)
        except Exception as e:
            raise RuntimeError(
                f"Failed to serialize {self.__class__.__name__} to MsgPack: {e}"
            ) from e

    @classmethod
    def from_msgpack(cls: type[T], msgpack_bytes: bytes) -> T:
        """Create instance from msgpack bytes."""
        if not MSGPACK_AVAILABLE:
            raise NotImplementedError(
                "MsgPack support requires msgpack: pip install msgpack"
            )
        try:
            # Use object_hook if custom deserialization is needed beyond from_dict
            data = msgpack.unpackb(msgpack_bytes, raw=False)
            if not isinstance(data, dict):
                raise TypeError(
                    f"MsgPack did not yield a dictionary for {cls.__name__}"
                )
            return cls.from_dict(data)
        except Exception as e:
            raise RuntimeError(
                f"Failed to deserialize {cls.__name__} from MsgPack: {e}"
            ) from e

    def to_msgpack_file(self, path: Path | str) -> None:
        """Serialize to msgpack file."""
        if not MSGPACK_AVAILABLE:
            raise NotImplementedError(
                "MsgPack support requires msgpack: pip install msgpack"
            )
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            msgpack_bytes = self.to_msgpack()
            path.write_bytes(msgpack_bytes)
        except Exception as e:
            raise RuntimeError(
                f"Failed to write {self.__class__.__name__} to MsgPack file {path}: {e}"
            ) from e

    @classmethod
    def from_msgpack_file(cls: type[T], path: Path | str) -> T:
        """Create instance from msgpack file."""
        if not MSGPACK_AVAILABLE:
            raise NotImplementedError(
                "MsgPack support requires msgpack: pip install msgpack"
            )
        path = Path(path)
        try:
            msgpack_bytes = path.read_bytes()
            return cls.from_msgpack(msgpack_bytes)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read {cls.__name__} from MsgPack file {path}: {e}"
            ) from e

    # --- Pickle Methods (Use with caution due to security risks) ---
    def to_pickle(self) -> bytes:
        """Serialize to pickle bytes using cloudpickle."""
        if not PICKLE_AVAILABLE:
            raise NotImplementedError(
                "Pickle support requires cloudpickle: pip install cloudpickle"
            )
        try:
            return cloudpickle.dumps(self)
        except Exception as e:
            raise RuntimeError(
                f"Failed to serialize {self.__class__.__name__} to Pickle: {e}"
            ) from e

    @classmethod
    def from_pickle(cls: type[T], pickle_bytes: bytes) -> T:
        """Create instance from pickle bytes using cloudpickle."""
        if not PICKLE_AVAILABLE:
            raise NotImplementedError(
                "Pickle support requires cloudpickle: pip install cloudpickle"
            )
        try:
            instance = cloudpickle.loads(pickle_bytes)
            if not isinstance(instance, cls):
                raise TypeError(
                    f"Deserialized object is not of type {cls.__name__}"
                )
            return instance
        except Exception as e:
            raise RuntimeError(
                f"Failed to deserialize {cls.__name__} from Pickle: {e}"
            ) from e

    def to_pickle_file(self, path: Path | str) -> None:
        """Serialize to pickle file using cloudpickle."""
        if not PICKLE_AVAILABLE:
            raise NotImplementedError(
                "Pickle support requires cloudpickle: pip install cloudpickle"
            )
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pickle_bytes = self.to_pickle()
            path.write_bytes(pickle_bytes)
        except Exception as e:
            raise RuntimeError(
                f"Failed to write {self.__class__.__name__} to Pickle file {path}: {e}"
            ) from e

    @classmethod
    def from_pickle_file(cls: type[T], path: Path | str) -> T:
        """Create instance from pickle file using cloudpickle."""
        if not PICKLE_AVAILABLE:
            raise NotImplementedError(
                "Pickle support requires cloudpickle: pip install cloudpickle"
            )
        path = Path(path)
        try:
            pickle_bytes = path.read_bytes()
            return cls.from_pickle(pickle_bytes)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read {cls.__name__} from Pickle file {path}: {e}"
            ) from e

    # _filter_none_values remains unchanged
    @staticmethod
    def _filter_none_values(data: Any) -> Any:
        """Filter out None values from dictionaries and lists recursively."""
        if isinstance(data, dict):
            return {
                k: Serializable._filter_none_values(v)
                for k, v in data.items()
                if v is not None
            }
        elif isinstance(data, list):
            # Filter None from list items AND recursively filter within items
            return [
                Serializable._filter_none_values(item)
                for item in data
                if item is not None
            ]
        return data
