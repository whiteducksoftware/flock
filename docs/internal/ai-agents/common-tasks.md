# Common Tasks & Performance Guide for AI Agents

This document covers common development tasks and performance optimization for AI agents working with Flock Flow.

## 🛠️ Common Tasks

### Add a New Agent

```python
# 1. Define artifact types
@flock_type
class MyInput(BaseModel):
    data: str

@flock_type
class MyOutput(BaseModel):
    result: str

# 2. Create agent
agent = (
    orchestrator.agent("my-agent")
    .description("Process my custom data")
    .consumes(MyInput)
    .publishes(MyOutput)
    .with_engines(DSPyEngine())
)

# 3. Write tests
# tests/test_my_agent.py
```

### Add a New Component

```python
# 1. Create component class
from flock.components import AgentComponent

class MyComponent(AgentComponent):
    name: str = "my_component"

    async def on_pre_evaluate(self, agent, ctx, inputs):
        # Your logic here
        return inputs

# 2. Register with agent
agent.with_utilities(MyComponent())

# 3. Write tests
# tests/test_my_component.py
```

### Add a New Dashboard Module

```typescript
// 1. Create module component
const MyModule: React.FC<ModuleProps> = ({ id, position }) => {
  // Module implementation
};

// 2. Register module
import { ModuleRegistry } from '../modules/ModuleRegistry';

ModuleRegistry.register({
  name: 'MyModule',
  component: MyModule,
  icon: '📊',
  defaultSize: { width: 400, height: 300 }
});

// 3. Write tests
// frontend/src/test/modules.test.tsx
```

## 🚀 Performance Optimization

### Backend Optimization

```python
# ✅ Use asyncio.gather for parallel operations
results = await asyncio.gather(
    agent_a.execute(ctx, artifacts),
    agent_b.execute(ctx, artifacts),
)

# ✅ Use semaphores for concurrency control
async with self._semaphore:  # Limit concurrent executions
    result = await expensive_operation()
```

### Frontend Optimization

```typescript
// ✅ Use React.memo for expensive components
const ExpensiveNode = React.memo(({ data }: NodeProps) => {
  // Component implementation
});

// ✅ Use useMemo for expensive calculations
const layout = useMemo(() => {
  return calculateLayout(nodes, edges);
}, [nodes, edges]);
```

### Visibility Enforcement

```python
# Always check visibility before scheduling
if not artifact.visibility.allows(agent.identity):
    logger.warning(f"Access denied: {agent.name} → {artifact.id}")
    continue  # Don't schedule
```

## 📊 Metrics & Monitoring

### Current Metrics

**Backend Metrics:**
- `artifacts_published` - Total artifacts published
- `agent_runs` - Total agent executions
- `websocket_connections` - Active dashboard connections
- `event_latency` - Event processing latency

**Frontend Metrics:**
- Graph rendering time (<200ms target)
- WebSocket message throughput (>100 events/sec)
- Autocomplete response time (<50ms target)

### Adding Custom Metrics

```python
# In your component
class MetricsComponent(AgentComponent):
    async def on_post_evaluate(self, agent, ctx, inputs, result):
        result.metrics["my_metric"] = value
        return result

# Metrics automatically aggregated in orchestrator
```

## 🔐 Security Best Practices

### API Keys

```bash
# ✅ Use environment variables
export OPENAI_API_KEY="sk-..."
export AZURE_API_KEY="..."

# ❌ Never commit API keys to git!
# Add to .gitignore:
.env
*.key
```

### Input Validation

```python
# ✅ Validate all external inputs
@flock_type
class UserInput(BaseModel):
    query: str = Field(max_length=1000)  # Prevent abuse

# ✅ Sanitize before processing
def sanitize(text: str) -> str:
    # Remove HTML, SQL injection attempts, etc.
    return text
```

## 🎯 Quick Reference

### File Locations

- **Tests**: `/tests` - All test files
- **Source Code**: `/src/flock` - Production code
- **Documentation**: `/docs` - Documentation
- **Examples**: `/examples` - Example scripts
- **Frontend**: `/frontend/src` - React components

### Common Commands

```bash
# Development
poe install          # Install all dependencies
poe build           # Build project
poe lint            # Lint code
poe format          # Format code

# Testing
poe test            # Run tests
poe test-cov        # Run with coverage
poe test-critical   # Run critical path tests

# Frontend
cd frontend
npm run dev         # Start dev server
npm test            # Run frontend tests
npm run build       # Build for production
```

---

*For more details, see:*
- *[Architecture Guide](./architecture.md)*
- *[Development Workflow](./development.md)*
- *[Frontend Guide](./frontend.md)*
- *[Dependencies Guide](./dependencies.md)*
