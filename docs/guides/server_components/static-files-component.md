---
title: StaticFiles Component
description: Documentation for the StaticFiles Component
tags:
 - static files
 - endpoints
search:
  boost: 0.1
---
# StaticFilesServerComponent

The `StaticFilesServerComponent` serves static files (HTML, CSS, JavaScript, images) for the Flock dashboard or custom UIs.

## Overview

This component mounts a directory of static files to the FastAPI application, enabling SPA (Single Page Application) routing with fallback to index.html.

**⚠️ CRITICAL:** This component MUST have the highest priority (be registered LAST) to avoid catching routes meant for other components.

## Configuration

### StaticFilesComponentConfig

**Fields:**
- `prefix` (str, default: `""`) - Optional prefix (usually empty for root mounting)
- `tags` (list[str], default: `["Static Files"]`) - OpenAPI tags
- `mount_point` (Path | str, default: `"/"`) - Where to mount static files
- `static_files_path` (Path | str, **required**) - Path to static files directory

## Usage

```python
from flock import Flock
from flock.components.server import (
    StaticFilesServerComponent,
    StaticFilesComponentConfig
)
from pathlib import Path

# Serve dashboard UI
static = StaticFilesServerComponent(
    config=StaticFilesComponentConfig(
        static_files_path=Path(__file__).parent / "dist"
    ),
    priority=99  # ⚠️ MUST BE LAST!
)

await flock.serve(components=[static])
```

## Best Practices

### 1. Always Use Highest Priority

```python
# ✅ CORRECT: Static files last
components = [
    HealthAndMetricsComponent(priority=0),
    AgentsServerComponent(priority=20),
    StaticFilesServerComponent(priority=99),  # ✅ Last!
]

# ❌ WRONG: Static files first
components = [
    StaticFilesServerComponent(priority=10),  # ❌ Catches all routes!
    AgentsServerComponent(priority=20),       # Never reached
]
```

### 2. Use with Dashboard

```python
# Flock automatically configures static files when dashboard=True
await flock.serve(dashboard=True)

# Equivalent to:
# StaticFilesServerComponent(
#     config=StaticFilesComponentConfig(
#         static_files_path=<flock_frontend_dist>
#     ),
#     priority=10_000_000
# )
```

### 3. Serve Custom UI

```python
# Serve your own React/Vue/Angular app
static = StaticFilesServerComponent(
    config=StaticFilesComponentConfig(
        static_files_path="./my-ui/build",
        mount_point="/app"  # Mount at /app/*
    ),
    priority=99
)
```

## SPA Routing

The component automatically serves `index.html` for client-side routing:

```
GET /             → serves index.html
GET /agents       → serves index.html (SPA handles routing)
GET /artifacts    → serves index.html (SPA handles routing)
GET /styles.css   → serves styles.css
GET /app.js       → serves app.js
```

## Component Properties

- **Name:** `static_files`
- **Priority:** `10_000_000` (default - MUST BE LAST!)
- **Mount Point:** `/` (default)

## Example

See: **[examples/09-server-components/09_static_files_component.py](../../../examples/09-server-components/09_static_files_component.py)**

## Troubleshooting

### API routes return HTML instead of JSON

**Problem:** Static files catch-all is intercepting API routes

**Solution:** Ensure static files have HIGHEST priority

```python
# Check priority order
components = [
    AgentsServerComponent(priority=20),      # API routes
    StaticFilesServerComponent(priority=99), # ✅ After API
]
```

### 404 for static assets

**Problem:** Files not found in static directory

**Solution:** Verify `static_files_path` exists and contains files

```python
from pathlib import Path

static_path = Path("./dist")
if not static_path.exists():
    raise ValueError(f"Static files directory not found: {static_path}")

static = StaticFilesServerComponent(
    config=StaticFilesComponentConfig(static_files_path=static_path)
)
```
