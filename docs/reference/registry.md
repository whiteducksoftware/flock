# `RegistryHub` — Thread‑Safe Registries

Central access to component, callable, agent, server, and type registries.

## Decorators

- `@flock_component` — Register component classes (optional `config_class=`)
- `@flock_tool` / `@flock_callable` — Register callables as tools
- `@flock_type` — Register Pydantic/dataclass types used in contracts

## Key Lookups

- `get_agent(name)` / `register_agent(agent)`
- `get_server(name)` / `register_server(server)`
- `get_callable(name_or_path)` / `register_callable(func, name=None)`
- `get_type(name)` / `register_type(type_obj, name=None)`
- `get_component(name)` / `register_component(cls, name=None)`

See `src/flock/core/registry/` for the full API.
