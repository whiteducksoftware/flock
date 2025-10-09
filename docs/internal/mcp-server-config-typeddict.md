# MCPServerConfig TypedDict Implementation Summary

## Overview

Implemented `MCPServerConfig` as a `TypedDict` to provide better type hints and IDE support for the `with_mcps()` method, making it easier for developers to understand what values and types are expected.

## Changes Made

### 1. Added TypedDict Definition (`src/flock/agent.py`)

```python
class MCPServerConfig(TypedDict, total=False):
    """Configuration for MCP server assignment to an agent.

    All fields are optional. If omitted, no restrictions apply.

    Attributes:
        roots: Filesystem paths this server can access.
               Empty list or omitted = no mount restrictions.
        tool_whitelist: Tool names the agent can use from this server.
                       Empty list or omitted = all tools available.

    Examples:
        >>> # No restrictions
        >>> config: MCPServerConfig = {}

        >>> # Mount restrictions only
        >>> config: MCPServerConfig = {"roots": ["/workspace/data"]}

        >>> # Tool whitelist only
        >>> config: MCPServerConfig = {"tool_whitelist": ["read_file", "write_file"]}

        >>> # Both restrictions
        >>> config: MCPServerConfig = {
        ...     "roots": ["/workspace/data"],
        ...     "tool_whitelist": ["read_file"]
        ... }
    """
    roots: list[str]
    tool_whitelist: list[str]
```

### 2. Updated `with_mcps()` Method Signature

**Before:**
```python
def with_mcps(
    self,
    servers: Iterable[str] | dict[str, dict[str, list[str]]] | list[str | dict[str, dict[str, list[str]]]],
) -> AgentBuilder:
```

**After:**
```python
def with_mcps(
    self,
    servers: (
        Iterable[str]
        | dict[str, MCPServerConfig | list[str]]  # Support both new and old format
        | list[str | dict[str, MCPServerConfig | list[str]]]
    ),
) -> AgentBuilder:
```

### 3. Backward Compatibility

The implementation supports **both** old and new formats:

**Old Format (still works):**
```python
agent.with_mcps({
    "filesystem": ["/workspace/data"],  # Direct list
})
```

**New Format (recommended):**
```python
agent.with_mcps({
    "filesystem": {
        "roots": ["/workspace/data"],
        "tool_whitelist": ["read_file", "write_file"]
    }
})
```

### 4. Implementation Details

The `with_mcps()` method now detects the format automatically:

```python
if isinstance(server_config, list):
    # Old format: direct list of paths (backward compatibility)
    if len(server_config) > 0:
        server_mounts[server_name] = list(server_config)
elif isinstance(server_config, dict):
    # New format: MCPServerConfig with optional roots and tool_whitelist
    mounts = server_config.get("roots", None)
    # ... handle roots and tool_whitelist
```

## Benefits

### ✅ 1. IDE Autocomplete

IDEs will now provide autocomplete suggestions for the dictionary keys:

```python
agent.with_mcps({
    "filesystem": {
        "roots": ...     # ← IDE suggests this key
        "tool_whitelist": ...  # ← IDE suggests this key
    }
})
```

### ✅ 2. Type Checking

Type checkers (mypy, pyright) will catch typos:

```python
# ❌ Type checker catches error
agent.with_mcps({
    "filesystem": {"root": ["/workspace"]}  # Typo: "root" instead of "roots"
})

# ✅ Correct
agent.with_mcps({
    "filesystem": {"roots": ["/workspace"]}
})
```

### ✅ 3. Self-Documenting Code

The TypedDict includes comprehensive docstrings explaining each field:

```python
# Developers can hover over MCPServerConfig in their IDE to see:
# - What fields are available
# - What each field does
# - Example usage
```

### ✅ 4. Backward Compatible

All existing code continues to work without changes:

```python
# Old code still works
agent.with_mcps({
    "filesystem": ["/workspace/data"]
})
```

### ✅ 5. Optional Fields

All fields are optional (using `total=False`), matching the implementation:

```python
# All valid
config1: MCPServerConfig = {}
config2: MCPServerConfig = {"roots": ["/path"]}
config3: MCPServerConfig = {"tool_whitelist": ["tool1"]}
config4: MCPServerConfig = {"roots": ["/path"], "tool_whitelist": ["tool1"]}
```

## Testing

Created comprehensive tests in `tests/test_mcp_server_config_typeddict.py`:

- ✅ New format with tool_whitelist
- ✅ New format with roots only
- ✅ New format with empty config (no restrictions)
- ✅ Old format still works (backward compatibility)
- ✅ Mixed old and new format
- ✅ TypedDict type hints work correctly
- ✅ Optional fields validation

All existing tests pass (19/19 in MCP-related tests).

## Example Usage

### Basic (No Restrictions)
```python
agent.with_mcps(["filesystem", "github"])
```

### New Format with Tool Whitelist
```python
agent.with_mcps({
    "filesystem": {
        "roots": ["/workspace/data"],
        "tool_whitelist": ["read_file", "write_file", "list_directory"]
    },
    "github": {}  # No restrictions
})
```

### Backward Compatible (Old Format)
```python
agent.with_mcps({
    "filesystem": ["/workspace/data"],
    "github": ["/workspace/.git"]
})
```

### Mixed Format
```python
agent.with_mcps({
    "filesystem": ["/workspace/data"],  # Old format
    "github": {"roots": ["/workspace/.git"], "tool_whitelist": ["get_repo"]}  # New format
})
```

## Documentation Updates

Updated `docs/mcp-roots.md` to include:
- MCPServerConfig TypedDict documentation
- Updated method signature
- Examples showing both old and new formats

## Summary

The TypedDict implementation provides:
1. **Better Developer Experience** - IDE autocomplete and type hints
2. **Type Safety** - Catch errors at development time
3. **Self-Documentation** - Clear explanation of expected fields
4. **Backward Compatibility** - No breaking changes
5. **Extensibility** - Easy to add new optional fields in the future

All changes maintain 100% backward compatibility while significantly improving the developer experience.
