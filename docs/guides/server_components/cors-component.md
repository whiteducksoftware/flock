---
title: CORSComponent
description: The CORSComponent
tags:
 - server-components
 - cors
 - endpoints
 - middleware
search:
  boost: 2.0
---

# Enhanced CORS Component Documentation

## Overview

The enhanced CORS (Cross-Origin Resource Sharing) component provides comprehensive control over CORS policies in your Flock application. It supports both global CORS settings and route-specific overrides, giving developers fine-grained control over cross-origin access.

## Features

✨ **Global CORS Settings** - Set default CORS policies for all routes
🎯 **Route-Specific Overrides** - Define different CORS policies for different path patterns
🔒 **Origin Regex Patterns** - Use regex to match allowed origins dynamically
⏱️ **Preflight Caching** - Control how long browsers cache preflight requests
🔑 **Credential Control** - Manage cookie and authorization header access
📤 **Exposed Headers** - Control which response headers are visible to browsers

## Configuration

### CORSComponentConfig

Main configuration class for CORS settings.

**Fields:**

- `allow_origins` (list[str], default: `["*"]`) - List of allowed origins
- `allow_origin_regex` (str | None) - Regex pattern for allowed origins
- `allow_credentials` (bool, default: `True`) - Allow credentials in requests
- `allow_methods` (list[str], default: `["*"]`) - Allowed HTTP methods
- `allow_headers` (list[str], default: `["*"]`) - Allowed request headers
- `expose_headers` (list[str], default: `[]`) - Headers exposed to browser
- `max_age` (int, default: `600`) - Preflight cache duration in seconds
- `route_configs` (list[RouteSpecificCORSConfig], default: `[]`) - Route-specific overrides

### RouteSpecificCORSConfig

Configuration for applying different CORS settings to specific routes.

**Fields:**

- `path_pattern` (str, **required**) - Regex pattern to match request paths
- `allow_origins` (list[str], default: `["*"]`) - Origins for this route
- `allow_methods` (list[str], default: `["GET"]`) - Methods for this route
- `allow_headers` (list[str], default: `["*"]`) - Headers for this route
- `expose_headers` (list[str], default: `[]`) - Exposed headers for this route
- `allow_credentials` (bool, default: `False`) - Allow credentials for this route
- `max_age` (int, default: `600`) - Preflight cache for this route

## Usage Examples

### Example 1: Basic CORS Configuration

```python
from flock import Flock
from flock.components.server import CORSComponent, CORSComponentConfig
from flock.orchestrator.server_manager import ServerManager

flock = Flock()

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["https://example.com"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=True,
    )
)

await ServerManager.serve(flock, plugins=[cors])
```

### Example 2: Origin Regex Pattern

Allow all subdomains of example.com:

```python
cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origin_regex=r"https://.*\.example\.com",
        allow_credentials=True,
        allow_methods=["*"],
        expose_headers=["X-Request-ID"],
    )
)
```

### Example 3: Route-Specific CORS

Different CORS policies for public and private APIs:

```python
from flock.components.server import RouteSpecificCORSConfig

cors = CORSComponent(
    config=CORSComponentConfig(
        # Default: restrictive
        allow_origins=["https://app.example.com"],
        allow_credentials=True,

        # Route overrides
        route_configs=[
            # Public API - allow all
            RouteSpecificCORSConfig(
                path_pattern=r"^/api/public/.*",
                allow_origins=["*"],
                allow_credentials=False,
            ),

            # Admin API - very strict
            RouteSpecificCORSConfig(
                path_pattern=r"^/api/admin/.*",
                allow_origins=["https://admin.example.com"],
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_credentials=True,
            ),
        ],
    )
)
```

### Example 4: Multi-Tenant CORS

Different policies per tenant:

```python
cors = CORSComponent(
    config=CORSComponentConfig(
        route_configs=[
            RouteSpecificCORSConfig(
                path_pattern=r"^/tenant/tenant-a/.*",
                allow_origins=["https://tenant-a.example.com"],
                allow_credentials=True,
            ),
            RouteSpecificCORSConfig(
                path_pattern=r"^/tenant/tenant-b/.*",
                allow_origins=["https://tenant-b.example.com"],
                allow_credentials=True,
            ),
        ],
    )
)
```

### Example 5: Development vs Production

```python
import os

is_prod = os.getenv("ENVIRONMENT") == "production"

if is_prod:
    cors = CORSComponent(
        config=CORSComponentConfig(
            allow_origins=["https://app.example.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            max_age=3600,
        )
    )
else:
    cors = CORSComponent(
        config=CORSComponentConfig(
            allow_origins=["*"],
            allow_methods=["*"],
            allow_credentials=False,
        )
    )
```

## How It Works

### Global CORS Mode

When no `route_configs` are specified, the component uses Starlette's standard `CORSMiddleware` with the global configuration.

### Route-Specific CORS Mode

When `route_configs` are provided, the component creates a custom middleware that:

1. Checks the request path against each route pattern (in order)
2. Uses the first matching route's CORS configuration
3. Falls back to global configuration if no route matches
4. Applies the selected CORS settings using Starlette's `CORSMiddleware`

## Best Practices

### 1. Security First

❌ **Don't** use wildcard origins with credentials:
```python
# INSECURE - allows any origin to send credentials
CORSComponentConfig(
    allow_origins=["*"],
    allow_credentials=True,  # ⚠️ Security risk!
)
```

✅ **Do** specify exact origins when using credentials:
```python
# SECURE - credentials only from trusted origin
CORSComponentConfig(
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
)
```

### 2. Use Regex for Subdomains

✅ **Good** for dynamic subdomains:
```python
CORSComponentConfig(
    allow_origin_regex=r"https://.*\.example\.com",
    allow_credentials=True,
)
```

### 3. Minimize Preflight Requests

Set appropriate `max_age` to reduce preflight overhead:

```python
CORSComponentConfig(
    max_age=3600,  # Cache for 1 hour
)
```

### 4. Expose Only Necessary Headers

❌ **Don't** expose all headers:
```python
expose_headers=["*"]  # Not supported by CORS spec
```

✅ **Do** specify exact headers to expose:
```python
expose_headers=["X-Request-ID", "X-RateLimit-Remaining"]
```

### 5. Route Pattern Order Matters

Routes are matched in order. Put specific patterns before general ones:

```python
route_configs=[
    # Specific pattern first
    RouteSpecificCORSConfig(
        path_pattern=r"^/api/admin/users$",
        allow_origins=["https://admin.example.com"],
    ),
    # General pattern second
    RouteSpecificCORSConfig(
        path_pattern=r"^/api/admin/.*",
        allow_origins=["https://admin.example.com"],
    ),
]
```

## Common Use Cases

### API Gateway Pattern

```python
cors = CORSComponent(
    config=CORSComponentConfig(
        route_configs=[
            # Health checks - open
            RouteSpecificCORSConfig(
                path_pattern=r"^/health$",
                allow_origins=["*"],
                allow_methods=["GET"],
            ),
            # API endpoints - restricted
            RouteSpecificCORSConfig(
                path_pattern=r"^/api/.*",
                allow_origins=["https://app.example.com"],
                allow_credentials=True,
            ),
        ],
    )
)
```

### Webhook Endpoints

```python
cors = CORSComponent(
    config=CORSComponentConfig(
        route_configs=[
            RouteSpecificCORSConfig(
                path_pattern=r"^/webhooks/.*",
                allow_origins=[
                    "https://github.com",
                    "https://stripe.com",
                ],
                allow_methods=["POST"],
                allow_credentials=False,
            ),
        ],
    )
)
```

### GraphQL Endpoints

```python
cors = CORSComponent(
    config=CORSComponentConfig(
        route_configs=[
            RouteSpecificCORSConfig(
                path_pattern=r"^/graphql$",
                allow_origins=["https://app.example.com"],
                allow_methods=["POST", "GET"],
                allow_headers=["Content-Type", "Authorization", "X-Apollo-Tracing"],
                expose_headers=["X-Apollo-Tracing"],
                allow_credentials=True,
            ),
        ],
    )
)
```

## Migration Guide

### From Old CORS Component

**Before:**
```python
cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
)
```

**After (same behavior):**
```python
cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # New features available:
        expose_headers=["X-Custom-Header"],
        max_age=3600,
    )
)
```

### From Manual CORS Middleware

**Before:**
```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**After:**
```python
from flock.components.server import CORSComponent, CORSComponentConfig

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
)

await ServerManager.serve(flock, plugins=[cors])
```

## Troubleshooting

### CORS Error: "Origin not allowed"

**Issue:** Browser blocks request due to CORS policy

**Solution:** Check that the origin is included in `allow_origins` or matches `allow_origin_regex`

### CORS Error: "Credentials not allowed"

**Issue:** Using credentials with wildcard origin

**Solution:** Replace `allow_origins=["*"]` with specific origins when `allow_credentials=True`

### Preflight Request Failing

**Issue:** OPTIONS request returns 403 or wrong headers

**Solution:** Ensure `OPTIONS` is in `allow_methods` and appropriate headers are in `allow_headers`

### Route-Specific Config Not Applied

**Issue:** Route pattern not matching

**Solution:** Test your regex pattern:
```python
import re
pattern = re.compile(r"^/api/public/.*")
print(pattern.match("/api/public/users"))  # Should match
```

## API Reference

See the code documentation for complete API details:

- `CORSComponent` - Main component class
- `CORSComponentConfig` - Global CORS configuration
- `RouteSpecificCORSConfig` - Route-specific CORS configuration

## Performance Considerations

1. **Route Matching Overhead**: Each request checks route patterns sequentially. Keep the number of route configs reasonable (< 20).

2. **Preflight Caching**: Set appropriate `max_age` to reduce preflight requests:
   - Development: 600 (10 minutes)
   - Production: 3600-86400 (1-24 hours)

3. **Middleware Order**: CORS middleware runs with priority 8. Lower priority middleware runs first.

## Security Considerations

⚠️ **Never use `allow_origins=["*"]` with `allow_credentials=True`** - This is a security vulnerability!

✅ **Always validate origins** when accepting credentials

✅ **Use HTTPS** origins in production

✅ **Limit exposed headers** to only what's necessary

✅ **Review route patterns** to ensure they match intended endpoints

## Related Documentation

- [Server Components Guide](../guides/server-components.md)
- [Starlette CORS Documentation](https://www.starlette.io/middleware/#corsmiddleware)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
