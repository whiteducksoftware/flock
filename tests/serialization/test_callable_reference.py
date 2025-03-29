"""Tests for the callable reference system used in TOML serialization."""

import inspect
import pickle
from typing import Any, Callable, Dict

import pytest
import toml

# Import placeholder for the CallableRegistry class that will be created
# This import will fail until the implementation is created
from flock.core.serialization.callable_registry import CallableRegistry


# Test functions for reference handling
def sample_function(x: int, y: int) -> int:
    """Sample function that adds two numbers."""
    return x + y


class SampleClass:
    """Sample class with methods for testing callable references."""

    def instance_method(self, x: int) -> int:
        """Sample instance method."""
        return x * 2

    @classmethod
    def class_method(cls, x: int) -> int:
        """Sample class method."""
        return x * 3

    @staticmethod
    def static_method(x: int) -> int:
        """Sample static method."""
        return x * 4


# Lambda and closures for testing more complex cases
sample_lambda = lambda x: x * 5
sample_closure_factory = lambda multiplier: lambda x: x * multiplier
sample_closure = sample_closure_factory(6)


@pytest.fixture
def registry():
    """Fixture for a callable registry."""
    # This will fail until CallableRegistry is implemented
    registry = CallableRegistry()
    registry.register("sample_function", sample_function)
    registry.register("instance_method", SampleClass().instance_method)
    registry.register("class_method", SampleClass.class_method)
    registry.register("static_method", SampleClass.static_method)
    return registry


class TestCallableReferenceSystem:
    """Tests for the callable reference system."""

    def test_registry_registration(self):
        """Test registering a callable in the registry."""
        # This test will fail until CallableRegistry is implemented
        registry = CallableRegistry()
        registry.register("test_func", sample_function)
        
        # Verify the callable was registered
        assert registry.has("test_func")
        assert registry.get("test_func") == sample_function

    def test_registry_retrieval(self):
        """Test retrieving a callable from the registry."""
        # This test will fail until CallableRegistry is implemented
        registry = CallableRegistry()
        registry.register("test_func", sample_function)
        
        # Retrieve and verify the callable
        func = registry.get("test_func")
        assert func is not None
        assert func(5, 3) == 8

    def test_callable_to_reference(self, registry):
        """Test converting a registered callable to a reference string."""
        # This test will fail until to_reference is implemented
        ref = registry.to_reference(sample_function)
        
        # Verify the reference format
        assert ref.startswith("@registry:")
        assert "sample_function" in ref

    def test_reference_to_callable(self, registry):
        """Test resolving a reference string back to a callable."""
        # This test will fail until from_reference is implemented
        ref = "@registry:sample_function"
        func = registry.from_reference(ref)
        
        # Verify the callable was correctly resolved and works
        assert func is not None
        assert func(5, 3) == 8

    def test_import_reference(self):
        """Test referencing a callable by import path."""
        # This test will fail until from_reference is implemented
        registry = CallableRegistry()
        
        # Create an import reference to a standard library function
        import math
        ref = "@import:math:sqrt"
        
        # Resolve the reference
        func = registry.from_reference(ref)
        
        # Verify the callable was correctly resolved and works
        assert func is not None
        assert func(4) == 2.0

    def test_pickle_fallback(self, registry):
        """Test fallback to pickle for non-referenceable callables."""
        # This test will fail until to_reference and from_reference are implemented
        
        # Try to create a reference for a lambda (which should use pickle fallback)
        ref = registry.to_reference(sample_lambda)
        
        # Verify the reference format indicates pickle
        assert ref.startswith("@pickle:")
        
        # Resolve the reference
        func = registry.from_reference(ref)
        
        # Verify the callable was correctly resolved and works
        assert func is not None
        assert func(5) == 25

    def test_callable_round_trip(self, registry):
        """Test round-trip conversion (callable to reference and back)."""
        # This test will fail until to_reference and from_reference are implemented
        
        # Convert sample function to reference
        ref = registry.to_reference(sample_function)
        
        # Convert reference back to callable
        func = registry.from_reference(ref)
        
        # Verify the callable was correctly preserved
        assert func is not None
        assert func(5, 3) == 8

    def test_instance_method_reference(self, registry):
        """Test handling of instance methods."""
        # This test will fail until to_reference and from_reference are implemented
        
        # Create an instance and its method
        instance = SampleClass()
        method = instance.instance_method
        
        # Convert to reference (this may use pickle fallback)
        ref = registry.to_reference(method)
        
        # Resolve back to callable
        func = registry.from_reference(ref)
        
        # Verify the method works correctly
        assert func is not None
        assert func(5) == 10

    def test_class_method_reference(self, registry):
        """Test handling of class methods."""
        # This test will fail until to_reference and from_reference are implemented
        
        # Convert to reference
        ref = registry.to_reference(SampleClass.class_method)
        
        # Resolve back to callable
        func = registry.from_reference(ref)
        
        # Verify the method works correctly
        assert func is not None
        assert func(5) == 15

    def test_closure_reference(self, registry):
        """Test handling of closures with captured variables."""
        # This test will fail until to_reference and from_reference are implemented
        
        # Convert to reference (this should use pickle fallback)
        ref = registry.to_reference(sample_closure)
        
        # Resolve back to callable
        func = registry.from_reference(ref)
        
        # Verify the closure works correctly with its captured variable
        assert func is not None
        assert func(5) == 30

    def test_malformed_reference(self, registry):
        """Test handling of malformed reference strings."""
        # This test will fail until proper error handling is implemented
        
        # Create some malformed references
        malformed_refs = [
            "not_a_reference",
            "@invalid:something",
            "@registry:",  # Missing function name
            "@import:math",  # Missing function part
            "@pickle:not_base64",
        ]
        
        # All should raise exceptions when resolved
        for ref in malformed_refs:
            with pytest.raises(Exception):
                registry.from_reference(ref)

    def test_non_existent_registry_reference(self, registry):
        """Test handling of non-existent registry references."""
        # This test will fail until proper error handling is implemented
        
        # Reference a function that doesn't exist in the registry
        ref = "@registry:non_existent_function"
        
        # Should raise an exception
        with pytest.raises(Exception):
            registry.from_reference(ref)

    def test_non_existent_import_reference(self, registry):
        """Test handling of invalid import paths."""
        # This test will fail until proper error handling is implemented
        
        # References to non-existent modules or functions
        bad_refs = [
            "@import:non_existent_module:func",
            "@import:math:non_existent_function",
        ]
        
        # All should raise exceptions
        for ref in bad_refs:
            with pytest.raises(Exception):
                registry.from_reference(ref)

    def test_integration_with_toml(self, registry):
        """Test integration with TOML serialization."""
        # This test will fail until both CallableRegistry and TOML integration are implemented
        
        # Create a dictionary with callable references
        data = {
            "function": registry.to_reference(sample_function),
            "method": registry.to_reference(SampleClass.static_method),
            "normal_data": "This is a string",
        }
        
        # Convert to TOML
        toml_str = toml.dumps(data)
        
        # Verify TOML string contains the references
        assert "@registry:sample_function" in toml_str
        assert "static_method" in toml_str
        
        # Parse back from TOML
        parsed = toml.loads(toml_str)
        
        # Convert references back to callables
        resolved_data = {
            "function": registry.from_reference(parsed["function"]),
            "method": registry.from_reference(parsed["method"]),
            "normal_data": parsed["normal_data"],
        }
        
        # Verify the functions work
        assert resolved_data["function"](5, 3) == 8
        assert resolved_data["method"](5) == 20
        assert resolved_data["normal_data"] == "This is a string" 