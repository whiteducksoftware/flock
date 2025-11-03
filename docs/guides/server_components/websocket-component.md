---
title: WebSocketServerComponent
description: WebSocketServerComponent. Provide real-time bidirectional communication
tags:
 - websockets
 - realtime
 - endpoints
 - events
search:
  boost: 1.6
---
# WebSocketServerComponent

The `WebSocketServerComponent` enables real-time bidirectional communication between your Flock server and clients (typically the dashboard). It manages WebSocket connections, broadcasts events, and provides live updates for agent executions and artifact changes.

## Overview

This component is essential for the Flock dashboard's real-time visualization capabilities. It handles connection lifecycle, broadcasts agent events, streams LLM outputs, and updates the UI with artifact changes as they occur.

## Features

- **Real-time Event Broadcasting** - Push agent execution events to connected clients
- **Connection Management** - Handle multiple concurrent WebSocket connections
- **Heartbeat Support** - Keep connections alive with optional ping/pong
- **Graceful Disconnection** - Clean up resources when clients disconnect
- **WebSocket Pool** - Manage active connections efficiently
- **Async Streaming** - Non-blocking message delivery

## Configuration

### WebSocketComponentConfig

Configuration for the WebSocket component.

**Fields:**

- `prefix` (str, default: `"/plugin/"`) - Prefix for the WebSocket endpoint
- `tags` (list[str], default: `["WebSocket"]`) - OpenAPI documentation tags
- `heartbeat_interval` (int, default: `120`) - Interval in seconds for heartbeat messages
- `enable_heartbeat` (bool, default: `False`) - Whether to enable WebSocket heartbeat

## Usage Examples

### Example 1: Basic WebSocket Configuration

```python
from flock import Flock
from flock.components.server import (
    WebSocketServerComponent,
    WebSocketComponentConfig
)

flock = Flock()

# Use default configuration
websocket = WebSocketServerComponent()

await flock.serve(
    components=[websocket],
    dashboard=True  # Dashboard uses WebSocket
)
```

**Endpoint:**
- `WS /plugin/ws` - WebSocket connection for real-time updates

### Example 2: Custom Configuration

```python
websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(
        prefix="/api/ws",  # Custom prefix
        heartbeat_interval=60,  # Ping every 60 seconds
        enable_heartbeat=True  # Enable keepalive
    )
)
```

**Endpoint:**
- `WS /api/ws/ws` - Custom WebSocket endpoint

### Example 3: Production Configuration with Heartbeat

```python
websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(
        prefix="/realtime",
        heartbeat_interval=30,  # More frequent for production
        enable_heartbeat=True,
        tags=["Real-time", "Dashboard"]
    )
)

await flock.serve(components=[websocket], dashboard=True)
```

## Event Types

The WebSocket component broadcasts various event types to connected clients:

### Agent Execution Events

```json
{
  "type": "agent_execution_started",
  "agent_id": "pizza_master",
  "run_id": "uuid-here",
  "timestamp": "2025-10-31T12:00:00Z"
}
```

```json
{
  "type": "agent_execution_completed",
  "agent_id": "pizza_master",
  "run_id": "uuid-here",
  "duration_ms": 1234.5,
  "status": "success"
}
```

### Streaming Output Events

```json
{
  "type": "streaming_output",
  "agent_id": "pizza_master",
  "run_id": "uuid-here",
  "content": "Analyzing pizza toppings...",
  "is_complete": false
}
```

### Artifact Events

```json
{
  "type": "artifact_published",
  "artifact_id": "uuid-here",
  "artifact_type": "Pizza",
  "produced_by": "pizza_master",
  "correlation_id": "workflow-123"
}
```

### Graph Update Events

```json
{
  "type": "graph_updated",
  "nodes": [...],
  "edges": [...]
}
```

## Integration with Dashboard

The WebSocket component is automatically integrated with the Flock dashboard:

```python
from flock import Flock

flock = Flock()

# Dashboard automatically connects to WebSocket
await flock.serve(
    dashboard=True,  # Enables dashboard + WebSocket
    port=8000
)

# Dashboard connects to: ws://localhost:8000/plugin/ws
```

## Client-Side Usage

### JavaScript/TypeScript Client

```typescript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/plugin/ws');

ws.onopen = () => {
  console.log('Connected to Flock WebSocket');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'agent_execution_started':
      console.log(`Agent ${message.agent_id} started`);
      break;

    case 'streaming_output':
      console.log(`Output: ${message.content}`);
      break;

    case 'artifact_published':
      console.log(`New artifact: ${message.artifact_type}`);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};
```

### Python Client

```python
import asyncio
import websockets
import json

async def connect_to_flock():
    uri = "ws://localhost:8000/plugin/ws"

    async with websockets.connect(uri) as websocket:
        print("Connected to Flock WebSocket")

        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "agent_execution_started":
                print(f"Agent {data['agent_id']} started")

            elif data["type"] == "streaming_output":
                print(f"Output: {data['content']}")

            elif data["type"] == "artifact_published":
                print(f"New artifact: {data['artifact_type']}")

asyncio.run(connect_to_flock())
```

## Best Practices

### 1. Enable Heartbeat for Long-Running Connections

```python
# ✅ CORRECT: Keep connections alive
websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(
        enable_heartbeat=True,
        heartbeat_interval=30  # Ping every 30 seconds
    )
)
```

### 2. Handle Disconnections Gracefully

The component automatically cleans up disconnected clients:

```python
# Component handles this automatically
# - Removes client from connection pool
# - Releases resources
# - Logs disconnection
```

### 3. Use with Dashboard Component

```python
# ✅ CORRECT: Dashboard + WebSocket + Static files
from flock.components.server import (
    WebSocketServerComponent,
    StaticFilesServerComponent
)

components = [
    WebSocketServerComponent(),           # Real-time updates
    StaticFilesServerComponent(priority=99),  # Dashboard UI
]

await flock.serve(components=components, dashboard=True)
```

### 4. Secure WebSocket Connections

```python
# For production, use WSS (WebSocket Secure)
# Configure your reverse proxy (nginx, etc.) for SSL/TLS

# nginx example:
# location /plugin/ws {
#     proxy_pass http://localhost:8000;
#     proxy_http_version 1.1;
#     proxy_set_header Upgrade $http_upgrade;
#     proxy_set_header Connection "upgrade";
# }
```

### 5. Monitor Connection Count

```python
# Access WebSocket manager for monitoring
from flock.api.websocket import WebSocketManager

websocket_manager = WebSocketManager()

# Get active connection count
active_connections = len(websocket_manager._connections)
print(f"Active WebSocket connections: {active_connections}")
```

## Connection Lifecycle

```
1. Client connects → WS /plugin/ws
2. Connection accepted → Added to WebSocketManager pool
3. Events broadcast → All connected clients receive updates
4. Optional heartbeat → Keep connection alive (if enabled)
5. Client disconnects → Removed from pool, resources cleaned
```

## Error Handling

The component handles common WebSocket errors:

### Connection Errors

```python
# Component logs and handles:
# - Connection refused
# - Network timeout
# - Invalid handshake
# - Protocol errors
```

### Broadcast Errors

```python
# Component handles individual client failures:
# - Removes failed connections
# - Continues broadcasting to healthy connections
# - Logs errors for monitoring
```

## Performance Considerations

### Connection Limits

```python
# Consider connection limits for production
# Default: No hard limit (uses WebSocketManager pool)

# Monitor active connections:
# - Too many connections = memory pressure
# - Broadcast latency increases with connection count
# - Consider load balancing for >1000 connections
```

### Message Size

```python
# Large messages can impact performance
# Component handles streaming for large outputs
# - Breaks into chunks automatically
# - Sends incrementally during LLM streaming
```

## Component Properties

- **Name:** `websocket`
- **Priority:** `7` (default)
- **Default Prefix:** `/plugin/`
- **Dependencies:** WebSocketManager (singleton)
- **Middleware:** None
- **Lifecycle Hooks:** Connection management

## Related Components

- **[ControlRoutesComponent](control-routes-component.md)** - Trigger events via HTTP
- **[StaticFilesServerComponent](static-files-component.md)** - Serve dashboard UI
- **[AgentsServerComponent](agents-component.md)** - Agent metadata for UI
- **[ArtifactsComponent](artifacts-component.md)** - Artifact data for UI

## Example Code

See the complete example: **[examples/09-server-components/05_websocket_component.py](../../../examples/09-server-components/05_websocket_component.py)**

## Troubleshooting

### WebSocket connection refused

**Problem:** Client cannot connect to WebSocket

**Solution:** Verify endpoint path and server configuration

```python
# Check endpoint matches client connection string
websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(prefix="/plugin/")
)
# Endpoint: ws://localhost:8000/plugin/ws

# Client must connect to same path
# ws = new WebSocket('ws://localhost:8000/plugin/ws');
```

### Connection drops frequently

**Problem:** WebSocket connections disconnect unexpectedly

**Solution:** Enable heartbeat to keep connections alive

```python
# ✅ Enable heartbeat for unstable networks
websocket = WebSocketServerComponent(
    config=WebSocketComponentConfig(
        enable_heartbeat=True,
        heartbeat_interval=30  # Adjust based on network
    )
)
```

### No events received

**Problem:** Client connected but receives no messages

**Solution:** Verify event broadcasting is working

```python
# Check that events are being triggered
# - Publish artifacts
# - Execute agents
# - Check server logs for broadcast attempts

# Test with simple artifact publish:
await flock.publish(MyArtifact(...))
# Should trigger artifact_published event
```

### CORS errors with WebSocket

**Problem:** Browser blocks WebSocket connection due to CORS

**Solution:** Configure CORS component to allow WebSocket upgrade

```python
from flock.components.server import CORSComponent, CORSComponentConfig

cors = CORSComponent(
    config=CORSComponentConfig(
        allow_origins=["http://localhost:3000"],  # Your frontend
        allow_credentials=True,
        allow_headers=["*"],  # Required for WebSocket upgrade
    )
)

components = [
    cors,  # Before WebSocket
    WebSocketServerComponent(),
]
```

### Production deployment issues

**Problem:** WebSocket not working behind reverse proxy

**Solution:** Configure proxy for WebSocket support

```nginx
# nginx configuration
location /plugin/ws {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
}
```
