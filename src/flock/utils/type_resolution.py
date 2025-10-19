"""Type registry resolution utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flock.registry import TypeRegistry

from flock.registry import RegistryError


class TypeResolutionHelper:
    """Helper for safe type resolution.

    This utility eliminates 8+ duplicate type resolution patterns
    scattered across agent.py, store.py, orchestrator.py, and context_provider.py.
    """

    @staticmethod
    def safe_resolve(registry: "TypeRegistry", type_name: str) -> str:
        """
        Safely resolve type name to canonical form.

        Args:
            registry: Type registry instance
            type_name: Type name to resolve

        Returns:
            Canonical type name (or original if not found)

        Example:
            >>> canonical = TypeResolutionHelper.safe_resolve(registry, "MyType")
            >>> # Returns "my_module.MyType" if found, else "MyType"
        """
        try:
            return registry.resolve_name(type_name)
        except RegistryError:
            # Type not found or ambiguous - return original name
            return type_name
