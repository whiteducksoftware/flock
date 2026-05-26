import inspect
import json
from typing import Any

def is_pydantic_model(obj: Any) -> bool:
    """
    Check if an object is a Pydantic model instance.
    More robust detection for both v1 and v2 Pydantic models.
    """
    # Check for Pydantic v2 model
    if hasattr(obj, "__class__") and hasattr(obj.__class__, "model_dump"):
        return True
    
    # Check for Pydantic v1 model
    if hasattr(obj, "__class__") and hasattr(obj.__class__, "schema") and hasattr(obj, "dict"):
        return True
    
    # Check if it has a __pydantic_core__ attribute (v2 models)
    if hasattr(obj, "__pydantic_core__"):
        return True
        
    # Final check: class name check and module check
    if hasattr(obj, "__class__"):
        cls = obj.__class__
        cls_name = cls.__name__
        module_name = getattr(cls, "__module__", "")
        if "pydantic" in module_name.lower() or "basemodel" in cls_name.lower():
            return True
    
    return False

def is_json_serializable(obj: Any) -> bool:
    """Check if an object can be serialized to JSON."""
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False

def pydantic_to_dict(obj: Any) -> Any:
    """
    Recursively convert Pydantic models to dictionaries.
    Works with nested models, lists, and dictionaries containing models.
    Falls back to string representation if object can't be serialized.
    """
    if obj is None:
        return None
        
    if is_pydantic_model(obj):
        # Handle Pydantic v2 models
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Handle Pydantic v1 models
        elif hasattr(obj, "dict"):
            return obj.dict()
        # Last resort - try __dict__ if it exists
        elif hasattr(obj, "__dict__"):
            return {k: pydantic_to_dict(v) for k, v in obj.__dict__.items() 
                   if not k.startswith("_")}
    
    elif isinstance(obj, dict):
        # Handle dictionaries that might contain Pydantic models
        return {k: pydantic_to_dict(v) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        # Handle lists that might contain Pydantic models
        return [pydantic_to_dict(item) for item in obj]
    
    elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
        # Handle namedtuples
        return dict(zip(obj._fields, (pydantic_to_dict(item) for item in obj)))
    
    elif isinstance(obj, (list, tuple)):
        # Handle regular lists and tuples
        return [pydantic_to_dict(item) for item in obj]
    
    # Final check - if object is not JSON serializable, convert to string
    if not is_json_serializable(obj):
        try:
            return str(obj)
        except Exception:
            return f"<Unserializable object of type {type(obj).__name__}>"
    
    # Return other types unchanged - these should be JSON serializable by default
    return obj 