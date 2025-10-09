"""
Demonstration of MCPServerConfig TypedDict Benefits
===================================================

This file demonstrates how the TypedDict improves developer experience.
Open this file in your IDE to see autocomplete in action!
"""

from flock.agent import MCPServerConfig
from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock

# Setup
flock = Flock("openai/gpt-4o-mini")
flock.add_mcp(
    name="filesystem",
    connection_params=StdioServerParameters(command="test", args=[]),
    enable_roots_feature=True,
)
flock.add_mcp(
    name="github",
    connection_params=StdioServerParameters(command="test", args=[]),
    enable_roots_feature=True,
)

# ============================================================================
# BENEFIT 1: IDE Autocomplete
# ============================================================================
# When you type the opening brace after "filesystem": {
# your IDE will suggest "roots" and "tool_whitelist" as keys!
#
# Try it: Start typing and watch your IDE suggest the keys

agent = flock.agent("demo").with_mcps({
    "filesystem": {
        # ← Type here and IDE will suggest: roots, tool_whitelist
        "roots": ["/workspace/data"],
        "tool_whitelist": ["read_file", "write_file"]
    }
})

# ============================================================================
# BENEFIT 2: Type Hints in Variables
# ============================================================================
# When you create a config variable, you get full type checking

config: MCPServerConfig = {
    # ← IDE suggests: roots, tool_whitelist
    "roots": ["/workspace/src"],
    "tool_whitelist": ["read_file"]
}

# ============================================================================
# BENEFIT 3: Documentation on Hover
# ============================================================================
# Hover over MCPServerConfig below to see the full documentation
# including what each field does and example usage

my_config: MCPServerConfig = {}  # ← Hover here to see docs

# ============================================================================
# BENEFIT 4: Type Checking Catches Errors
# ============================================================================
# Type checkers will catch these errors:

# ❌ This will be flagged by type checkers (typo: "root" instead of "roots")
# bad_config: MCPServerConfig = {"root": ["/workspace"]}

# ❌ This will be flagged (wrong type: string instead of list)
# bad_config: MCPServerConfig = {"roots": "/workspace"}

# ✅ This is correct
good_config: MCPServerConfig = {"roots": ["/workspace"]}

# ============================================================================
# BENEFIT 5: All Fields Are Optional
# ============================================================================
# TypedDict with total=False means all fields are optional

empty_config: MCPServerConfig = {}  # ✅ Valid

roots_only: MCPServerConfig = {
    "roots": ["/workspace"]
}  # ✅ Valid

whitelist_only: MCPServerConfig = {
    "tool_whitelist": ["read_file"]
}  # ✅ Valid

both: MCPServerConfig = {
    "roots": ["/workspace"],
    "tool_whitelist": ["read_file"]
}  # ✅ Valid

# ============================================================================
# BENEFIT 6: Backward Compatibility
# ============================================================================
# Old format still works (dict value is a list directly)

old_format = flock.agent("old").with_mcps({
    "filesystem": ["/workspace/data"]  # ✅ Still works!
})

# New format (recommended)
new_format = flock.agent("new").with_mcps({
    "filesystem": {
        "roots": ["/workspace/data"],
        "tool_whitelist": ["read_file"]
    }
})

# Mixed format (both old and new in same call)
mixed = flock.agent("mixed").with_mcps({
    "filesystem": ["/workspace/data"],  # Old format
    "github": {  # New format
        "roots": ["/workspace/.git"],
        "tool_whitelist": ["get_repo"]
    }
})

# ============================================================================
# BENEFIT 7: Function Parameter Hints
# ============================================================================

def configure_mcp_server(config: MCPServerConfig) -> None:
    """
    When calling this function, IDE will show:
    - Parameter name: config
    - Type: MCPServerConfig
    - Available keys: roots, tool_whitelist
    """
    if "roots" in config:  # ← IDE knows this key exists
        print(f"Roots: {config['roots']}")
    if "tool_whitelist" in config:  # ← IDE knows this key exists
        print(f"Whitelist: {config['tool_whitelist']}")


# Call the function - IDE shows parameter hints
configure_mcp_server({
    "roots": ["/workspace"],  # ← IDE suggests these keys
    "tool_whitelist": ["read_file"]
})

print("\n✅ All demonstrations completed!")
print("Open this file in your IDE and try editing the configs above")
print("to see autocomplete and type hints in action!")
