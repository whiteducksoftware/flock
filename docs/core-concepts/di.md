# Dependency Injection in Flock

> *New in 0.6* — Flock ships with a first-class integration for the [`wd.di`](https://pypi.org/project/wd.di/) service-container.
>
> The feature is **completely optional**: existing projects continue to run if you ignore it.  But once you taste constructor injection, you will never want to go back to hand-rolled singletons.

---

## 1  Why DI?

1. **Reuse expensive resources**  
   Most agents and modules need an embedding model, a vector store, a logger, …
   The container guarantees a *single* instance per run (or per request) without global variables.
2. **Constructor injection**  
   Dependencies are spelled out in the `__init__()` signature – no more `from … import SOME_GLOBAL`.
3. **Testability**  
   Replace real services with fakes in one line:
   ```python
   sc.add_singleton(S3Client, FakeS3Client())
   ```
4. **Middleware**  
   Cross-cutting concerns such as tracing, error handling or retries are just pipeline components.

---

## 2  Bootstrapping a container

Create and fill a `ServiceCollection` *once* at the beginning of a run — usually in your CLI entry-point or notebook.

```python
from wd.di import ServiceCollection
from flock.modules.performance.metrics_module import MetricsModule
from flock.core.logging.logging import get_logger

sc = ServiceCollection()

# 1. Register concrete instances
sc.add_singleton(MetricsModule())
sc.add_singleton(get_logger("run"))

# 2. Register types – the container will build them on demand
from sentence_transformers import SentenceTransformer
sc.add_singleton(SentenceTransformer)  # 👈 singleton lifetime

# 3. Build the provider (immutable after this call)
container = sc.build()
```

Attach the container to the **runtime context** so that every component can reach it:

```python
from flock.core.context.context import FlockContext
ctx = FlockContext()
ctx.set_variable("di.container", container)
```

If you do not have the context at bootstrap time (e.g. inside `agent.run()`), store the container in a global and copy it into the context later.  The key name `di.container` is conventional.

---

## 3  Resolving services

### 3.1  Inside modules / agents

Call the convenience helper that was added to `FlockContext`:

```python
logger = context.resolve(Logger)
```

It returns `None` if no container is attached or the type is not registered, making the call safe in older projects.

### 3.2  Anywhere else

Import the tiny wrapper shipped in `flock.di`:

```python
from flock.di import get_current_container

container = get_current_container(context)
embedding_model = container.get_service(SentenceTransformer)
```

---

## 4  Using middleware

The `wd.di` package comes with a lightweight **`MiddlewarePipeline`**.  When you register one as a singleton, Flock will automatically wrap evaluator execution:

```python
from wd.di.middleware_di import create_application_builder
from wd.di.middleware import LoggingMiddleware, ExceptionHandlerMiddleware

builder = create_application_builder(sc)  # sc is your ServiceCollection
builder.configure_middleware(
    lambda m: (
        m.use_middleware(ExceptionHandlerMiddleware)
         .use_middleware(LoggingMiddleware)  # <- your own too!
    )
)

container = builder.build()  # replaces sc.build()
```

Each middleware receives `(context, next)` where *context* is the **current FlockContext**.  You can therefore obtain scoped services, record traces, short-circuit execution, etc.

---

## 5  Gradual refactoring pattern

1. **Accept an optional container** in your module constructor:
   ```python
   def __init__(self, name: str, config: MyConfig, *, container=None):
       super().__init__(name=name, config=config)
       self._metrics = (container or Default()).get_service(MetricsModule)
   ```
2. **Resolve shared services** instead of calling module globals.
3. **Fallback** to the current "global" singletons to stay backward compatible.
4. Migrate call-sites one by one.

---

## 6  Testing with DI

Creating an isolated container inside your pytest fixtures is easy:

```python
import pytest
from wd.di import ServiceCollection
from flock.modules.performance.metrics_module import MetricsModule

@pytest.fixture()
def di_container():
    sc = ServiceCollection()
    sc.add_singleton(MetricsModule, FakeMetricsModule())
    return sc.build()
```

Pass the fixture to your SUT and you never have to monkey-patch again.

---

## 7  FAQ

**Does it work without `wd.di` installed?**  Yes.  Flock guards every optional import so your code still runs.

**Can I have per-request lifetimes?**  Absolutely. Just call `container.create_scope()` before the request, store the scoped provider under the `di.container` key for the duration and dispose it afterwards.

**Will the registry go away?**  No.  The registry continues to handle *serialization* and *lookup by name*.  DI is about *instantiation* and *lifetimes*.

---

Happy wiring! 🚀 