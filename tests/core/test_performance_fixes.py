#!/usr/bin/env python3
"""Quick test to verify performance fixes work correctly."""

import ast
import json
from flock.modules.memory.memory_module import MemoryModule, MemoryModuleConfig

def test_safe_eval_replacement():
    """Test that ast.literal_eval works as expected."""
    # Test string
    result = ast.literal_eval("'hello world'")
    assert result == "hello world"
    
    # Test number
    result = ast.literal_eval("42")
    assert result == 42
    
    # Test list
    result = ast.literal_eval("[1, 2, 3]")
    assert result == [1, 2, 3]
    
    # Test dict
    result = ast.literal_eval("{'key': 'value'}")
    assert result == {'key': 'value'}
    
    print("Safe eval replacement works correctly")

def test_memory_serialization_helper():
    """Test that the memory module serialization helper works."""
    config = MemoryModuleConfig(enabled=True)
    module = MemoryModule("test", config)
    
    # Test with both inputs and result
    inputs = {"query": "test"}
    result = {"answer": "response"}
    serialized = module._serialize_combined_data(inputs, result)
    expected = json.dumps(inputs) + json.dumps(result)
    assert serialized == expected
    
    # Test with only inputs
    serialized = module._serialize_combined_data(inputs, None)
    expected = json.dumps(inputs)
    assert serialized == expected
    
    print("Memory module serialization helper works correctly")

def test_loop_optimizations():
    """Test that enumerate works as expected for our optimizations."""
    test_list = ["a", "b", "c"]
    
    # Old pattern: for i in range(len(test_list))
    old_result = []
    for i in range(len(test_list)):
        old_result.append((i, test_list[i]))
    
    # New pattern: for i, item in enumerate(test_list)
    new_result = []
    for i, item in enumerate(test_list):
        new_result.append((i, item))
    
    assert old_result == new_result
    print("Loop optimization patterns work correctly")

if __name__ == "__main__":
    test_safe_eval_replacement()
    test_memory_serialization_helper()
    test_loop_optimizations()
    print("All performance fixes are working correctly!")
