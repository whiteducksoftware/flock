# Refactor Plan: FlockRegistry

## Current Issues Analysis

### 1. **Single Responsibility Principle Violations**
- FlockRegistry does too many things: registration, discovery, path management, auto-scanning, serialization support
- ~688 lines in one class with 9 different concerns
- Mixing low-level path string generation with high-level component discovery

### 2. **Thread Safety & Global State Issues**
- Global singleton pattern without proper synchronization
- Race conditions possible during component registration
- Global `_COMPONENT_CONFIG_MAP` dictionary not thread-safe
- No locking mechanisms for concurrent access

### 3. **Complex Method Responsibilities**
- `get_callable()` does: exact lookup + simple name search + dynamic import + builtins check
- `register_module_components()` mixes discovery logic with registration logic
- Auto-registration method is overly complex with hardcoded paths

### 4. **Code Organization Issues**
- Overloaded decorators with complex branching logic
- Mixed sync/static methods for configuration mapping
- Hard-coded package paths for auto-discovery
- Inconsistent error handling patterns

## Proposed Refactoring Strategy

### Phase 1: Separate Core Concerns (High Priority)

#### 1.1 Create Focused Registry Classes
```
FlockComponentRegistry     - Component type registration & lookup
FlockCallableRegistry     - Function/method registration & import  
FlockAgentRegistry        - Agent instance management
FlockServerRegistry       - MCP server management
FlockTypeRegistry         - Type/model registration
```

#### 1.2 Extract Path Management
```
PathResolver              - Generate & resolve import paths
DynamicImporter          - Handle dynamic module imports
```

#### 1.3 Extract Discovery System
```
ComponentDiscovery       - Auto-scan packages for components
ModuleScanner           - Low-level module introspection
```

### Phase 2: Thread Safety & Configuration (Medium Priority)

#### 2.1 Thread-Safe Registry Hub
```python
class FlockRegistryHub:
    """Thread-safe coordinator for all registry types."""
    def __init__(self):
        self._lock = threading.RLock()
        self._component_registry = FlockComponentRegistry()
        self._callable_registry = FlockCallableRegistry()
        # ... other registries
    
    @contextmanager
    def _with_lock(self):
        with self._lock:
            yield
```

#### 2.2 Configuration Separation
```python
class RegistryConfig:
    """Configuration for registry behavior."""
    auto_discovery_enabled: bool = True
    auto_discovery_packages: list[str] = ["flock.tools", ...]
    cache_dynamic_imports: bool = True
    thread_safe: bool = True
```

### Phase 3: Simplified Decorators (Low Priority)

#### 3.1 Focused Decorator Classes
```python
class ComponentRegistrar:
    def __init__(self, registry_hub: FlockRegistryHub):
        self.hub = registry_hub
    
    def component(self, cls=None, *, name=None, config_class=None):
        # Simplified single-purpose decorator
    
    def tool(self, func=None, *, name=None):
        # Simplified tool registration
```

## Detailed Implementation Plan

### New File Structure
```
src/flock/core/registry/
├── __init__.py                 # Public API & backward compatibility
├── registry_hub.py            # Main coordinator (thread-safe)
├── component_registry.py      # Component type management
├── callable_registry.py       # Function/tool management  
├── agent_registry.py          # Agent instance management
├── server_registry.py         # MCP server management
├── type_registry.py          # Pydantic/dataclass types
├── path_resolver.py           # Import path utilities
├── dynamic_importer.py        # Module import logic
├── discovery/
│   ├── __init__.py
│   ├── component_discovery.py # High-level auto-discovery
│   ├── module_scanner.py      # Low-level scanning
│   └── discovery_config.py    # Discovery configuration
└── decorators/
    ├── __init__.py
    ├── component_decorators.py # @flock_component
    ├── tool_decorators.py     # @flock_tool
    └── type_decorators.py     # @flock_type
```

### Key Architectural Changes

#### 1. Thread-Safe Registry Hub
```python
class FlockRegistryHub:
    """Main registry coordinator with thread safety."""
    
    def __init__(self, config: RegistryConfig | None = None):
        self._config = config or RegistryConfig()
        self._lock = threading.RLock()
        
        # Initialize sub-registries
        self.components = FlockComponentRegistry(self._lock)
        self.callables = FlockCallableRegistry(self._lock)
        self.agents = FlockAgentRegistry(self._lock)
        self.servers = FlockServerRegistry(self._lock)
        self.types = FlockTypeRegistry(self._lock)
        
        # Initialize utilities
        self.path_resolver = PathResolver()
        self.importer = DynamicImporter(self.callables)
        self.discovery = ComponentDiscovery(self, self._config)
    
    def auto_discover(self, packages: list[str] | None = None):
        """Run auto-discovery on specified packages."""
        return self.discovery.discover_packages(packages or self._config.auto_discovery_packages)
```

#### 2. Focused Component Registry
```python
class FlockComponentRegistry:
    """Manages component class registration and lookup."""
    
    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._components: dict[str, type] = {}
        self._config_mappings: dict[type, type] = {}
    
    def register_component(self, component_class: type, name: str | None = None) -> str:
        """Register a component class."""
        with self._lock:
            # Implementation...
    
    def register_config_mapping(self, config_cls: type, component_cls: type):
        """Register config -> component mapping."""
        with self._lock:
            # Implementation...
    
    def get_component(self, name: str) -> type:
        """Get component class by name."""
        with self._lock:
            # Implementation...
```

#### 3. Smart Callable Registry
```python
class FlockCallableRegistry:
    """Manages callable registration with smart lookup."""
    
    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._callables: dict[str, Callable] = {}
        self._path_resolver = PathResolver()
        self._importer = DynamicImporter()
    
    def register_callable(self, func: Callable, name: str | None = None) -> str:
        """Register a callable function."""
        # Implementation...
    
    def get_callable(self, name_or_path: str) -> Callable:
        """Smart callable lookup with fallback to dynamic import."""
        # 1. Try exact match
        # 2. Try simple name resolution  
        # 3. Try dynamic import
        # 4. Try builtins
        # Implementation...
```

#### 4. Simplified Discovery System
```python
class ComponentDiscovery:
    """Handles automatic component discovery."""
    
    def __init__(self, registry_hub: FlockRegistryHub, config: RegistryConfig):
        self.hub = registry_hub
        self.config = config
        self.scanner = ModuleScanner()
    
    def discover_packages(self, packages: list[str]) -> DiscoveryResult:
        """Discover and register components from packages."""
        # Implementation...
    
    def discover_module(self, module_path: str) -> DiscoveryResult:
        """Discover components in a single module."""
        # Implementation...
```

### Backward Compatibility Strategy

#### Maintain Current API
```python
# In src/flock/core/registry/__init__.py
from .registry_hub import FlockRegistryHub
from .decorators import flock_component, flock_tool, flock_type

# Global instance for backward compatibility
_default_hub = FlockRegistryHub()

# Legacy API functions
def get_registry() -> FlockRegistryHub:
    """Get the default registry hub."""
    return _default_hub

class FlockRegistry:
    """Legacy compatibility wrapper."""
    def __init__(self):
        import warnings
        warnings.warn("FlockRegistry is deprecated, use get_registry() instead", DeprecationWarning)
        self._hub = _default_hub
    
    def register_component(self, *args, **kwargs):
        return self._hub.components.register_component(*args, **kwargs)
    
    # ... other legacy method delegations
```

## Benefits of This Refactoring

### 1. **Improved Maintainability**
- Each class has a single, clear responsibility
- Easier to test individual components
- Clearer error boundaries and handling

### 2. **Better Thread Safety**
- Explicit locking strategy
- No race conditions in registration
- Safe for concurrent use

### 3. **Enhanced Extensibility**
- Easy to add new registry types
- Pluggable discovery mechanisms
- Configurable behavior

### 4. **Cleaner Architecture**
- Clear separation between registration and discovery
- Focused interfaces for different concerns
- Better testability with dependency injection

### 5. **Performance Improvements**
- Lazy loading of expensive operations
- Caching of frequently accessed items
- Reduced memory footprint per registry type

## Migration Strategy

### Phase 1: Create New Structure (1-2 days)
1. Create new directory structure
2. Implement core registry classes
3. Add thread safety mechanisms
4. Create backward compatibility layer

### Phase 2: Migrate Functionality (2-3 days)
1. Move component registration logic
2. Move callable/tool registration
3. Migrate auto-discovery system
4. Update decorators

### Phase 3: Testing & Integration (1-2 days)
1. Ensure all existing tests pass
2. Add new tests for thread safety
3. Performance testing
4. Update documentation

### Phase 4: Cleanup (1 day)
1. Remove old FlockRegistry class
2. Update import statements
3. Add deprecation warnings for old API
4. Final testing

## Risk Assessment

### Low Risk
- Backward compatibility maintained
- Gradual migration possible
- Well-defined interfaces

### Medium Risk  
- Thread safety changes behavior slightly
- Performance characteristics may change
- Need thorough testing of auto-discovery

### Mitigation Strategies
- Keep old FlockRegistry as compatibility wrapper
- Extensive integration testing
- Performance benchmarking before/after
- Feature flags for new vs old behavior during transition
