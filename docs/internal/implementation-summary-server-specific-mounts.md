# Implementation Summary: Server-Specific Mount Points

## Overview

Successfully implemented server-specific mount points for MCP servers in the Flock framework. This allows agents to specify different directory access rights for different MCP servers, improving security and clarity.

## Key Changes

### 1. API Design

**New Recommended API:**
```python
agent = (
    orchestrator.agent("researcher")
    .with_mcps({
        "filesystem": ["/workspace/data", "/workspace/results"],
        "github": ["/workspace/.git"],
        "search": []  # No restrictions
    })
)
```

**Backward Compatible:**
```python
# Old style still works but shows deprecation warning
agent.with_mcps(["filesystem"]).mount("/workspace/src")
```

### 2. Modified Files

#### `src/flock/agent.py`
- Added `mcp_server_mounts: dict[str, list[str]] = {}` field to Agent class
- Rewrote `with_mcps()` to accept multiple formats:
  - `Iterable[str]` - List of server names (no mounts)
  - `dict[str, list[str]]` - Server-specific mounts
  - `list[str | dict[str, list[str]]]` - Mixed format
- Updated `_get_mcp_tools()` to pass `server_mounts` dict to manager
- Deprecated `mount()` method with warning (backward compatible)

#### `src/flock/mcp/manager.py`
- Updated `get_tools_for_agent()` to accept `server_mounts: dict[str, list[str]] | None`
- Modified to extract server-specific mount points and pass to `get_client()`
- Each server now receives only its own mount points (not all mounts)
- Added info logging when setting mount points

#### `src/flock/mcp/client.py`
- Added debug logging in `_perform_initial_handshake()` showing root URIs being sent

#### `docs/mcp-roots.md`
- Comprehensive documentation with new API examples
- Migration guide from old to new API
- Security best practices

#### `examples/showcase/07_mcp_roots.py`
- Updated to demonstrate new server-specific mount API

### 3. Test Coverage

#### `tests/test_agent_server_specific_mounts.py` (New File)
Comprehensive test suite with 12 test cases:

1. **Format Tests:**
   - `test_with_mcps_dict_format` - Dict format for server-specific mounts
   - `test_with_mcps_list_format` - List format for no mounts  
   - `test_with_mcps_mixed_format` - Mixed format (backward compatible)

2. **Validation Tests:**
   - `test_with_mcps_invalid_server` - Unregistered server validation
   - `test_with_mcps_invalid_format` - Invalid format type checking
   - `test_mount_validation` - Path validation

3. **Deprecation Tests:**
   - `test_mount_deprecation_warning` - Deprecation warning for .mount()
   - `test_mount_backward_compatibility` - Backward compatibility of .mount()
   - `test_multiple_mount_calls_accumulate` - Multiple mount calls

4. **Integration Tests:**
   - `test_empty_mounts_in_dict` - Empty mounts handling
   - `test_get_mcp_tools_passes_server_mounts` - Agent passes mounts to manager
   - `test_manager_passes_server_specific_mounts_to_client` - Manager filters per server

#### `tests/test_mcp_manager.py` (Updated)
Fixed 3 existing tests to include `mount_points` parameter:
- `test_get_tools_for_agent_success`
- `test_get_tools_for_agent_multiple_servers`  
- `test_get_tools_for_agent_partial_failure`

### 4. Test Results

```bash
# Server-specific mounts tests
✓ 12/12 tests passing

# Related MCP tests
✓ 47/47 tests passing (44 existing + 3 fixed)

# Total
✓ 59/59 tests passing
```

## Migration Guide

### Before (Global Mounts)
```python
agent = (
    orchestrator.agent("researcher")
    .with_mcps(["filesystem", "github", "search"])
    .mount(["/workspace/src", "/workspace/data"])  # Applied to ALL servers
)
```

### After (Server-Specific Mounts)
```python
agent = (
    orchestrator.agent("researcher")
    .with_mcps({
        "filesystem": ["/workspace/src", "/workspace/data"],
        "github": ["/workspace/.git"],
        "search": []  # No restrictions
    })
)
```

## Security Improvements

1. **Principle of Least Privilege**: Each server only receives mount points it needs
2. **Clear Intent**: Developers explicitly specify which paths go to which servers
3. **No Accidental Leakage**: Filesystem paths not accidentally shared with all servers

## Architecture Decisions Validated

- ✅ **AD001 (Two-Level)**: Servers at orchestrator, referenced by agents
- ✅ **AD003 (Tool Namespacing)**: `{server}__{tool}` format preserved
- ✅ **AD004 (Per-run Isolation)**: Mount points passed per (agent_id, run_id)
- ✅ **AD005 (Lazy Connection)**: Root notification during connection handshake
- ✅ **AD007 (Graceful Degradation)**: Maintained with new mount parameter

## Next Steps

1. ✅ Fix lint errors in test file
2. ✅ Run test suite to validate implementation
3. ✅ Update existing tests broken by API changes
4. 🔲 Update any other examples using old `.mount()` API
5. 🔲 Consider updating documentation/blog posts if needed

## Implementation Date

October 7, 2025

## Contributors

- AI Assistant (implementation)
- Tilman Sattler (requirements & review)
