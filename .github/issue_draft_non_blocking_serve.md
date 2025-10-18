# 🚀 [FEATURE] Non-Blocking `serve()` for Dashboard Examples

### Is your feature request related to a problem?

Dashboard examples currently face a limitation: once `flock.serve(dashboard=True)` is called, execution blocks indefinitely. This makes it impossible to publish messages or perform any setup logic after starting the dashboard server, unlike CLI examples which use `run_until_idle()` for controlled execution.

**Current workaround:**
Users must publish all messages *before* calling `serve()`, which is awkward for demos and prevents realistic workflows where the server runs continuously while processing incoming messages.

**Example of the problem:**
```python
# This doesn't work - can't execute after serve()
async def main():
    await flock.serve(dashboard=True)  # blocks forever

    # This code never runs! ❌
    pizza = MyDreamPizza(pizza_idea="pizza with pineapple")
    await flock.publish(pizza)
    await flock.run_until_idle()
```

### Describe the solution you want to see

Add a `blocking` parameter to `serve()` that allows starting the dashboard server as a background task:

```python
async def serve(
    self,
    *,
    dashboard: bool = False,
    dashboard_v2: bool = False,
    host: str = "127.0.0.1",
    port: int = 8344,
    blocking: bool = True,  # NEW: default True for backwards compatibility
) -> Task[None] | None:
```

**Usage example:**
```python
async def main():
    # Start dashboard in background
    await flock.serve(dashboard=True, blocking=False)

    # Now we can publish messages!
    pizza = MyDreamPizza(pizza_idea="pizza with pineapple")
    await flock.publish(pizza)
    await flock.run_until_idle()

    # Dashboard stays alive for inspection
    print("Check dashboard at http://localhost:8344")
    await asyncio.Event().wait()  # Keep running
```

**Key requirements:**
- Backwards compatible (`blocking=True` by default)
- Return `Task[None]` handle when `blocking=False`
- Proper cleanup of dashboard launcher and server on shutdown or task cancellation
- Works seamlessly with `run_until_idle()`

### Describe alternatives you have considered

**Option 1: Startup hook pattern**
```python
async def setup():
    await flock.publish(...)

await flock.serve(dashboard=True, on_startup=setup)
```
❌ Less flexible, doesn't allow continuous message publishing

**Option 2: Separate `serve_background()` method**
```python
await flock.serve_background(dashboard=True)
```
❌ API duplication, less discoverable

**Option 3: Always non-blocking**
```python
await flock.serve(dashboard=True)  # always returns immediately
```
❌ Breaking change for existing users

### Additional context

**Complexity: Medium** (6-9 hours estimated)
- Core async pattern is straightforward (codebase already uses `asyncio.create_task` extensively)
- Cleanup coordination requires careful handling (dashboard launcher + server task lifecycle)
- Backwards compatibility is preserved with default parameter

---

## 🛠️ Implementation Plan

### 1. Core Changes

**File: `src/flock/orchestrator.py`**

- Add `blocking: bool = True` parameter to `serve()` method (line 753)
- Add `_server_task: Task[None] | None = None` field to `__init__` (around line 165)
- Update return type: `-> Task[None] | None`
- When `blocking=False`:
  - Wrap server execution in `asyncio.create_task()`
  - Add cleanup callback for dashboard launcher on task completion
  - Track task in `_server_task` field
  - Return task handle

**Estimated effort:** 2-3 hours

### 2. Cleanup Logic

**File: `src/flock/orchestrator.py`**

- Add server cleanup to `shutdown()` method (line 718)
  - Cancel `_server_task` if running
  - Stop `_dashboard_launcher` if present
  - Handle `asyncio.CancelledError` gracefully
- Ensure proper resource cleanup on both normal completion and cancellation

**Estimated effort:** 1-2 hours

### 3. Testing

**File: `tests/integration/test_orchestrator_dashboard.py` (or new test file)**

Test scenarios:
- ✅ Non-blocking serve starts successfully and returns task
- ✅ Can publish messages after non-blocking serve
- ✅ Server processes messages during `run_until_idle()`
- ✅ Dashboard launcher cleanup on task completion
- ✅ Cleanup on explicit `shutdown()` call
- ✅ Backwards compatibility: `blocking=True` works as before
- ✅ Task cancellation cleans up resources properly

**Estimated effort:** 2-3 hours

### 4. Documentation

**Files to update:**
- `src/flock/orchestrator.py` - Update `serve()` docstring with:
  - New `blocking` parameter description
  - Example showing non-blocking usage
  - Return type documentation

**Estimated effort:** 30 minutes

### 5. Example

**File: `examples/02-dashboard/02_non_blocking_serve.py` (new)**

Create example demonstrating:
- Starting dashboard in non-blocking mode
- Publishing messages after server starts
- Using `run_until_idle()` to process messages
- Keeping server alive for inspection

**Estimated effort:** 1 hour

---

## ✅ Definition of Done

- [ ] `blocking` parameter implemented with default `True`
- [ ] Non-blocking mode returns `Task[None]` handle
- [ ] Server cleanup logic handles both normal and cancelled completion
- [ ] All tests passing (new + existing)
- [ ] Docstring updated with parameter and examples
- [ ] New example created: `examples/02-dashboard/02_non_blocking_serve.py`
- [ ] Backwards compatibility verified (existing examples still work)
- [ ] Manual validation: example runs and dashboard stays accessible

---

## 🧪 Validation Strategy

**Automated:**
- Unit/integration tests for non-blocking behavior
- Cleanup verification tests
- Backwards compatibility regression tests

**Manual:**
1. Run new example: `python examples/02-dashboard/02_non_blocking_serve.py`
2. Verify dashboard accessible at http://localhost:8344
3. Verify messages appear in dashboard
4. Verify server stays alive after `run_until_idle()`
5. Test graceful shutdown (Ctrl+C)

---

## 📅 Timeline Estimate

**Total effort:** 6-9 hours

Breakdown:
- Implementation: 3-5 hours
- Testing: 2-3 hours
- Documentation + Example: 1.5 hours

---

## 🔗 Technical References

- `orchestrator.py:753` - Current `serve()` implementation
- `orchestrator.py:580, 588, 1417` - Existing `asyncio.create_task` usage patterns
- `orchestrator.py:718` - Existing `shutdown()` method
- `service.py:279` - `BlackboardHTTPService.run_async()` (blocks on `uvicorn.Server.serve()`)
