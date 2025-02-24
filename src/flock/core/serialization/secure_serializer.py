import cloudpickle


class SecureSerializer:
    """Security-focused serialization system with capability controls for Flock objects."""

    # Define capability levels for different modules
    MODULE_CAPABILITIES = {
        # Core Python - unrestricted
        "builtins": "unrestricted",
        "datetime": "unrestricted",
        "re": "unrestricted",
        "math": "unrestricted",
        "json": "unrestricted",
        # Framework modules - unrestricted
        "flock": "unrestricted",
        # System modules - restricted but allowed
        "os": "restricted",
        "io": "restricted",
        "sys": "restricted",
        "subprocess": "high_risk",
        # Network modules - high risk
        "socket": "high_risk",
        "requests": "high_risk",
    }

    # Functions that should never be serialized
    BLOCKED_FUNCTIONS = {
        "os.system",
        "os.popen",
        "os.spawn",
        "os.exec",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "eval",
        "exec",
        "__import__",
    }

    @staticmethod
    def _get_module_capability(module_name):
        """Get the capability level for a module."""
        for prefix, level in SecureSerializer.MODULE_CAPABILITIES.items():
            if module_name == prefix or module_name.startswith(f"{prefix}."):
                return level
        return "unknown"  # Default to unknown for unlisted modules

    @staticmethod
    def _is_safe_callable(obj):
        """Check if a callable is safe to serialize."""
        if not callable(obj) or isinstance(obj, type):
            return True, "Not a callable function"

        module = obj.__module__
        func_name = (
            f"{module}.{obj.__name__}"
            if hasattr(obj, "__name__")
            else "unknown"
        )

        # Check against blocked functions
        if func_name in SecureSerializer.BLOCKED_FUNCTIONS:
            return False, f"Function {func_name} is explicitly blocked"

        # Check module capability level
        capability = SecureSerializer._get_module_capability(module)
        if capability == "unknown":
            return False, f"Module {module} has unknown security capability"

        return True, capability

    @staticmethod
    def serialize(obj, allow_restricted=True, allow_high_risk=False):
        """Serialize an object with capability checks."""
        if callable(obj) and not isinstance(obj, type):
            is_safe, capability = SecureSerializer._is_safe_callable(obj)

            if not is_safe:
                raise ValueError(
                    f"Cannot serialize unsafe callable: {capability}"
                )

            if capability == "high_risk" and not allow_high_risk:
                raise ValueError(
                    f"High risk callable {obj.__module__}.{obj.__name__} requires explicit permission"
                )

            if capability == "restricted" and not allow_restricted:
                raise ValueError(
                    f"Restricted callable {obj.__module__}.{obj.__name__} requires explicit permission"
                )

            # Store metadata about the callable for verification during deserialization
            metadata = {
                "module": obj.__module__,
                "name": getattr(obj, "__name__", "unknown"),
                "capability": capability,
            }

            return {
                "__serialized_callable__": True,
                "data": cloudpickle.dumps(obj).hex(),
                "metadata": metadata,
            }

        if isinstance(obj, list):
            return [
                SecureSerializer.serialize(
                    item, allow_restricted, allow_high_risk
                )
                for item in obj
            ]

        if isinstance(obj, dict):
            return {
                k: SecureSerializer.serialize(
                    v, allow_restricted, allow_high_risk
                )
                for k, v in obj.items()
            }

        return obj

    @staticmethod
    def deserialize(obj, allow_restricted=True, allow_high_risk=False):
        """Deserialize an object with capability enforcement."""
        if isinstance(obj, dict) and obj.get("__serialized_callable__") is True:
            # Validate the capability level during deserialization
            metadata = obj.get("metadata", {})
            capability = metadata.get("capability", "unknown")

            if capability == "high_risk" and not allow_high_risk:
                raise ValueError(
                    f"Cannot deserialize high risk callable {metadata.get('module')}.{metadata.get('name')}"
                )

            if capability == "restricted" and not allow_restricted:
                raise ValueError(
                    f"Cannot deserialize restricted callable {metadata.get('module')}.{metadata.get('name')}"
                )

            try:
                callable_obj = cloudpickle.loads(bytes.fromhex(obj["data"]))

                # Additional verification that the deserialized object matches its metadata
                if callable_obj.__module__ != metadata.get("module") or (
                    hasattr(callable_obj, "__name__")
                    and callable_obj.__name__ != metadata.get("name")
                ):
                    raise ValueError(
                        "Callable metadata mismatch - possible tampering detected"
                    )

                return callable_obj
            except Exception as e:
                raise ValueError(f"Failed to deserialize callable: {e!s}")

        if isinstance(obj, list):
            return [
                SecureSerializer.deserialize(
                    item, allow_restricted, allow_high_risk
                )
                for item in obj
            ]

        if isinstance(obj, dict) and "__serialized_callable__" not in obj:
            return {
                k: SecureSerializer.deserialize(
                    v, allow_restricted, allow_high_risk
                )
                for k, v in obj.items()
            }

        return obj
