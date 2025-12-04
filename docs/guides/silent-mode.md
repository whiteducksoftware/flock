---
title: Silent Mode (no_output)
description: Suppress terminal output when running Flock as a service or in production
tags:
  - configuration
  - service
  - production
  - output
  - silent
search:
  boost: 1.2
---

# Silent Mode (no_output)

**Run Flock quietly when embedded in other applications or deployed as a service.**

When using Flock as part of a larger application, you may want to suppress the decorative terminal output (banners, Rich tables, streaming displays) while keeping logs available for debugging.

---

## Quick Start

```python
from flock import Flock

# Suppress all decorative terminal output
flock = Flock("openai/gpt-4.1", no_output=True)
```

That's it! The banner, Rich tables, and streaming displays are now suppressed. Only programmatic output (your own `print()` statements) and configured logging will appear.

---

## What Gets Suppressed

| Output Type | Default | With `no_output=True` |
|-------------|---------|----------------------|
| Startup banner | ✅ Shown | ❌ Hidden |
| Rich streaming display | ✅ Shown | ❌ Hidden |
| Agent output tables | ✅ Shown | ❌ Hidden |
| Your `print()` statements | ✅ Shown | ✅ Shown |
| Logging output | ✅ Shown | ✅ Shown |

---

## Use Cases

### Running as a Service

When Flock is embedded in a web service, the decorative output clutters logs:

```python
from fastapi import FastAPI
from flock import Flock, flock_type
from pydantic import BaseModel

app = FastAPI()

# Silent mode for service deployment
flock = Flock("openai/gpt-4.1", no_output=True)

@flock_type
class Query(BaseModel):
    text: str

@flock_type  
class Response(BaseModel):
    answer: str

agent = flock.agent("responder").consumes(Query).publishes(Response)

@app.post("/ask")
async def ask(query: Query):
    await flock.publish(query)
    await flock.run_until_idle()
    responses = await flock.get_artifacts(Response)
    return {"answer": responses[0].answer}
```

### Batch Processing

When running many jobs, the output would be overwhelming:

```python
from flock import Flock

flock = Flock("openai/gpt-4.1", no_output=True)

# Process 1000 items without terminal spam
for item in items:
    await flock.publish(item)
    
await flock.run_until_idle()

# Your summary output only
print(f"Processed {len(items)} items")
```

### Testing

Keep test output clean:

```python
import pytest
from flock import Flock

@pytest.fixture
def silent_flock():
    return Flock("openai/gpt-4.1", no_output=True)

def test_agent_workflow(silent_flock):
    # Tests run without decorative output
    ...
```

### CI/CD Pipelines

Avoid cluttering CI logs:

```python
import os
from flock import Flock

# Auto-enable silent mode in CI
no_output = os.getenv("CI", "false").lower() == "true"
flock = Flock("openai/gpt-4.1", no_output=no_output)
```

---

## Propagation to Components

The `no_output` flag automatically propagates to all engines and components:

```python
from flock import Flock, DSPyEngine

flock = Flock("openai/gpt-4.1", no_output=True)

# Custom engines automatically inherit no_output
custom_engine = DSPyEngine(model="openai/gpt-4.1")

agent = (
    flock.agent("processor")
    .consumes(Input)
    .publishes(Output)
    .with_engines(custom_engine)  # no_output=True is propagated
)
```

This works for:

- ✅ Default DSPyEngine
- ✅ Custom engines added via `.with_engines()`
- ✅ Default OutputUtilityComponent
- ✅ Custom utilities added via `.with_utilities()`

---

## Combining with Logging

Silent mode suppresses decorative output but not logging. Configure logging for production visibility:

```python
import logging
from flock import Flock
from flock.logging.logging import configure_logging

# Enable structured logging
configure_logging(level=logging.INFO)

# Suppress decorative output
flock = Flock("openai/gpt-4.1", no_output=True)

# Logs still appear
# INFO:flock.core.orchestrator:Agent 'processor' executed successfully
```

### Recommended Production Configuration

```python
import logging
import os
from flock import Flock
from flock.logging.logging import configure_logging

# Production settings
configure_logging(
    level=logging.INFO if os.getenv("DEBUG") else logging.WARNING
)

flock = Flock(
    os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"),
    no_output=True  # Always silent in production
)
```

---

## Dashboard Compatibility

Silent mode works with the dashboard. The dashboard receives data via WebSocket, not terminal output:

```python
flock = Flock("openai/gpt-4.1", no_output=True)

# Dashboard still works!
await flock.serve(dashboard=True)  # Terminal is quiet, dashboard shows everything
```

---

## Environment Variable Alternative

You can also control output via environment variable in your code:

```python
import os
from flock import Flock

flock = Flock(
    "openai/gpt-4.1",
    no_output=os.getenv("FLOCK_NO_OUTPUT", "false").lower() == "true"
)
```

Then set in your deployment:

```bash
export FLOCK_NO_OUTPUT=true
python my_service.py
```

---

## See Also

- [Configuration Reference](../reference/configuration.md) - All environment variables
- [Distributed Tracing](tracing/index.md) - Production observability
- [Testing Strategies](testing.md) - Test configuration best practices
