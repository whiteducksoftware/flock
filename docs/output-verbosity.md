# Output Verbosity Control

This document describes how to control output verbosity in Flock agents.

## Environment Variables

Flock supports several environment variables to control default output behavior:

### `FLOCK_NO_OUTPUT`
Controls whether agent output is suppressed by default.

- `FLOCK_NO_OUTPUT=true` or `FLOCK_NO_OUTPUT=1`: Forces quiet mode (no console output)
- `FLOCK_NO_OUTPUT=false` or `FLOCK_NO_OUTPUT=0`: Forces verbose mode (console output enabled)
- Not set: Automatic detection based on context

### `FLOCK_PROGRAMMATIC` 
Forces quiet mode when set to `true` or `1`. Useful for programmatic usage where console output is not desired.

### `CI`
Standard CI environment variable. When set to `true` or `1`, Flock automatically defaults to quiet mode.

## Automatic Context Detection

When no explicit environment variables are set, Flock automatically detects the context:

- **Interactive terminals** (TTY): Verbose mode (shows output)
- **Non-interactive contexts** (pipes, scripts): Quiet mode (suppresses output)
- **CI environments**: Quiet mode (suppresses output)

## Explicit Control

You can always override defaults by explicitly setting parameters:

```python
# Always quiet
agent = FlockFactory.create_default_agent(
    name="my_agent",
    no_output=True,  # Explicit override
    # ... other parameters
)

# Always verbose
agent = FlockFactory.create_default_agent(
    name="my_agent", 
    no_output=False,  # Explicit override
    # ... other parameters
)
```

## Batch Operations

Batch operations have their own silent mode that shows a progress bar instead of individual outputs:

```python
results = flock.run_batch(
    start_agent="my_agent",
    batch_inputs=inputs,
    silent_mode=True,  # Progress bar instead of individual outputs
)
```

## Backward Compatibility

- Interactive use remains verbose by default (preserves existing UX)
- Explicit parameters always override environment variables
- OutputModuleConfig defaults unchanged (no_output=False, print_context=False)