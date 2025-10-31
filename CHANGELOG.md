# Changelog

## 0.5.30

- Cron support (UTC, 5-field: `*`, lists, ranges, steps; Sunday 0/7) for scheduled agents.
- Timer metadata injection (Option B): timer-triggered agents receive empty inputs, and `ctx.trigger_type`, `ctx.timer_iteration`, `ctx.fire_time` are available via injected context state.
- Implicit one-time datetime: schedules with `at=datetime(...)` and no `max_repeats` fire once and stop.
- Validation hardening: `after >= 0`, `max_repeats > 0`, and scheduled agents must declare `.publishes()`.

