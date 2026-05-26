# Proposal: Integrating `wd.di` Into Flock

## 1  Background
The current `FlockRegistry` solves *discovery* and *serialization*:
* maps names ↔️ Agent / Module / Router / Evaluator classes
* keeps a cache of callables & types for JSON / YAML (de)serialization

What it **does not** try to solve:
* lifetime-controlled instantiation of shared services (e.g. embedding model)
* constructor / property injection
* request-scoped objects
* middleware cross-cutting concerns.

The in-house package located at `.flock/wd-di/src/wd/di` already implements a
robust DI container inspired by ASP.NET:
* `ServiceCollection` ➜ registration DSL
* `Container` ➜ resolver with Singleton / Scoped / Transient lifetimes
* Middleware pipeline with scoped injection
* YAML-backed config binder (optional)

Pairing that with Flock yields cleaner construction and resource reuse while
leaving backward compatibility intact.

---
## 2  Why keep the Registry?
`FlockRegistry` is tightly coupled to serialization.  Replacing it would break
existing save-/load flows, YAML configs, and inter-component look-ups by name.
Therefore **both systems should coexist**:

```
           ┌─────────────┐          ┌──────────────┐
 Agent ⇆──▶│  Registry   │          │   DI Container│
           └─────────────┘◀────────┴──────────────┘
                  ▲  names                    ▲ types
                  └───────────────────────────┘
```

---
## 3  Migration sketch

1. **Bootstrap a container per run**
   In `flock.core.context.initialize_context` (or new helper):

   ```python
   from wd.di import ServiceCollection

   sc = ServiceCollection()
   sc.add_singleton(MetricsModule())  # attach a metrics collector
   sc.add_singleton(lambda: get_logger("run"))
   sc.add_singleton(trace.get_tracer("flock"))

   # Share embedding model across modules if desired
   for module in agent.get_enabled_modules():
       sc.add_singleton(type(module), module)

   container = sc.build()
   run_context.set_variable("di.container", container)
   ```

2. **Helper for resolution**
   Add to `FlockContext`:

   ```python
   def resolve(self, svc_type):
       container = self.get_variable("di.container")
       return container.resolve(svc_type) if container else None
   ```

3. **Gradual module refactor**
   *Example* (EnterpriseMemoryModule constructor):
   ```python
   def __init__(self, name: str, config: Config, container=None):
       super().__init__(name=name, config=config)
       self.metrics = (container or Default()).resolve(MetricsModule)  # fallback
   ```

4. **Middleware pipeline (optional)**
   Build an onion around evaluator execution:
   ```python
   async def evaluator_middleware(next, ctx):
       tracer = ctx.resolve(Tracer)
       with tracer.start_as_current_span("evaluator"):
           return await next()
   ```

5. **Testing**
   Tests create a lightweight `ServiceCollection` and inject fakes, reducing
   patching/monkey-patching need.

---
## 4  Immediate tasks
1. Add `wd.di` to `pyproject.toml` as optional extra.
2. Create `flock.di` thin wrapper exposing `get_current_container()` helper.
3. Update EnterpriseMemoryModule to accept an optional container and resolve
   MetricsModule instead of static call (maintain the static fallback).
4. Document the pattern in `docs/components/di.md`.

---
## 5  Long-term improvements
* Replace ad-hoc singletons (embedding cache, adapters) with DI singletons.
* Use scoped lifetimes for per-run data (OpenAI usage counters, run metadata).
* Enable declarative middleware in YAML/JSON Flock configs.

---
## 6  Verdict
Integrating `wd.di` **adds value** without disrupting existing workflows.  It
should be adopted as an *internal service container* while the Registry
continues to serve serialization/discovery needs. 