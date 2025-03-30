"""Unit tests for YAML serialization in Serializable base class."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from flock.core.serialization.serializable import Serializable


class MockSerializable(Serializable):
    """Mock implementation of Serializable for testing purposes."""

    def __init__(
        self,
        string_val: str = "test",
        int_val: int = 42,
        float_val: float = 3.14,
        bool_val: bool = True,
        list_val: Optional[List[Any]] = None,
        dict_val: Optional[Dict[str, Any]] = None,
        nested_val: Optional[Dict[str, Any]] = None,
    ):
        self.string_val = string_val
        self.int_val = int_val
        self.float_val = float_val
        self.bool_val = bool_val
        self.list_val = list_val or ["a", "b", "c"]
        self.dict_val = dict_val or {"key1": "value1", "key2": "value2"}
        self.nested_val = nested_val or {
            "nested1": {"key": "value"},
            "nested2": [1, 2, 3],
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "string_val": self.string_val,
            "int_val": self.int_val,
            "float_val": self.float_val,
            "bool_val": self.bool_val,
            "list_val": self.list_val,
            "dict_val": self.dict_val,
            "nested_val": self.nested_val,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MockSerializable":
        """Create instance from dictionary representation."""
        return cls(
            string_val=data.get("string_val", "test"),
            int_val=data.get("int_val", 42),
            float_val=data.get("float_val", 3.14),
            bool_val=data.get("bool_val", True),
            list_val=data.get("list_val", ["a", "b", "c"]),
            dict_val=data.get("dict_val", {"key1": "value1", "key2": "value2"}),
            nested_val=data.get(
                "nested_val",
                {
                    "nested1": {"key": "value"},
                    "nested2": [1, 2, 3],
                },
            ),
        )


class TestSerializableYAML:
    """Tests for YAML serialization in Serializable."""

    def test_to_yaml_method_exists(self):
        """Test that to_yaml method exists and works."""
        obj = MockSerializable()
        yaml_str = obj.to_yaml()
        assert isinstance(yaml_str, str)
        assert "string_val: test" in yaml_str

    def test_from_yaml_method_exists(self):
        """Test that from_yaml method exists and works."""
        yaml_str = "string_val: test\nint_val: 42"
        obj = MockSerializable.from_yaml(yaml_str)
        assert isinstance(obj, MockSerializable)
        assert obj.string_val == "test"
        assert obj.int_val == 42

    def test_to_yaml_file_method_exists(self):
        """Test that to_yaml_file method exists and works."""
        obj = MockSerializable()
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            obj.to_yaml_file(tmp_path)
            assert tmp_path.exists()
            content = tmp_path.read_text()
            assert "string_val: test" in content
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_from_yaml_file_method_exists(self):
        """Test that from_yaml_file method exists and works."""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            yaml_content = """
string_val: from_file_test
int_val: 99
"""
            tmp.write(yaml_content.encode())
            tmp_path = Path(tmp.name)
        
        try:
            obj = MockSerializable.from_yaml_file(tmp_path)
            assert isinstance(obj, MockSerializable)
            assert obj.string_val == "from_file_test"
            assert obj.int_val == 99
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_to_yaml_basic_types(self):
        """Test serializing objects with primitive types."""
        obj = MockSerializable(
            string_val="test",
            int_val=42,
            float_val=3.14,
            bool_val=True,
        )
        
        # Expected YAML after implementation
        expected_yaml = """string_val: test
int_val: 42
float_val: 3.14
bool_val: true
list_val:
  - a
  - b
  - c
dict_val:
  key1: value1
  key2: value2
nested_val:
  nested1:
    key: value
  nested2:
    - 1
    - 2
    - 3
"""
        
        yaml_str = obj.to_yaml()
        # Compare the parsed YAML dictionaries to handle whitespace differences
        assert yaml.safe_load(yaml_str) == yaml.safe_load(expected_yaml)

    def test_from_yaml_basic_types(self):
        """Test deserializing objects with primitive types."""
        yaml_str = """string_val: test_from_yaml
int_val: 100
float_val: 6.28
bool_val: false
list_val:
  - x
  - y
  - z
dict_val:
  custom_key: custom_value
nested_val:
  custom_nested:
    nested_key: nested_value
"""
        
        obj = MockSerializable.from_yaml(yaml_str)
        assert obj.string_val == "test_from_yaml"
        assert obj.int_val == 100
        assert obj.float_val == 6.28
        assert obj.bool_val is False
        assert obj.list_val == ["x", "y", "z"]
        assert obj.dict_val == {"custom_key": "custom_value"}
        assert obj.nested_val == {
            "custom_nested": {"nested_key": "nested_value"}
        }

    def test_yaml_file_operations(self):
        """Test file operations with YAML serialization."""
        obj = MockSerializable(string_val="file_test")
        
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            obj.to_yaml_file(tmp_path)
            loaded_obj = MockSerializable.from_yaml_file(tmp_path)
            assert loaded_obj.string_val == "file_test"
            assert loaded_obj.int_val == 42
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_special_characters(self):
        """Test serializing objects with special characters."""
        obj = MockSerializable(
            string_val="Special chars: ñ, é, ü, ß, 你好",
            dict_val={"key:with:colons": "value with spaces"}
        )
        
        yaml_str = obj.to_yaml()
        loaded_obj = MockSerializable.from_yaml(yaml_str)
        assert loaded_obj.string_val == "Special chars: ñ, é, ü, ß, 你好"
        assert loaded_obj.dict_val == {"key:with:colons": "value with spaces"}

    def test_yaml_error_handling(self):
        """Test error handling for malformed YAML."""
        malformed_yaml = """
        string_val: "unclosed quote
        int_val: 42
        """
        
        with pytest.raises(yaml.YAMLError):
            MockSerializable.from_yaml(malformed_yaml) 