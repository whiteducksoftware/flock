"""JSON encoder utilities for Flock objects."""

import json
from datetime import datetime
from typing import Any


class FlockJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling Pydantic models and other non-serializable objects."""

    def default(self, obj: Any) -> Any:
        from pydantic import BaseModel

        # Handle Pydantic models
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        # Handle datetime objects
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Handle sets, convert to list
        if isinstance(obj, set):
            return list(obj)

        # Handle objects with a to_dict method
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            return obj.to_dict()

        # Handle objects with a __dict__ attribute
        if hasattr(obj, "__dict__"):
            return {
                k: v for k, v in obj.__dict__.items() if not k.startswith("_")
            }

        # Let the parent class handle it or raise TypeError
        try:
            return super().default(obj)
        except TypeError:
            # If all else fails, convert to string
            return str(obj)
