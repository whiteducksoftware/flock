# 🎯 Orchestrator Components

Orchestrator components add global coordination across ALL agents—perfect for system-wide monitoring, metrics dashboards, alerting, cross-agent correlation, and centralized governance.

## 🎯 What Are Orchestrator Components?

**Orchestrator Components** extend the entire orchestrator with cross-cutting behavior:

- **Global scope** - One component monitors all agents
- **System-wide hooks** - React to any artifact publication
- **Centralized state** - Track metrics across the entire system
- **Coordination** - Correlate activity across multiple agents

## 💡 Why Use Orchestrator Components?

| Without Components | With Components |
|-------------------|-----------------|
| ❌ Scattered monitoring | ✅ Centralized dashboards |
| ❌ Per-agent metrics | ✅ System-wide analytics |
| ❌ Manual correlation | ✅ Automatic tracking |
| ❌ Duplicate logging | ✅ Unified observability |

**Use orchestrator components when:**
- Monitoring system-wide metrics
- Building operational dashboards
- Implementing alerting across agents
- Tracking cross-agent workflows
- Enforcing global policies
- Collecting centralized analytics

## 📚 Examples

### kitchen_monitor_component.py 🍳
**Pattern:** Real-time monitoring dashboard with system-wide metrics

Track all kitchen activity across multiple chefs:
- **Global metrics** - Track all dishes across all chefs
- **Real-time alerts** - Spice level warnings
- **Performance tracking** - Per-chef statistics
- **Cycle summaries** - Status board after each cycle

```bash
uv run 07-orchestrator-components/kitchen_monitor_component.py
```

**How It Works:**
```python
class KitchenMonitorComponent(OrchestratorComponent):
    dishes_in_progress: int = 0
    completed_dishes: int = 0
    chef_stats: dict[str, dict] = Field(default_factory=dict)
    spice_warnings: int = 0
    start_time: datetime | None = None

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """Called BEFORE any artifact is published - track all dishes."""
        if artifact.type_name == "Dish":
            self.dishes_in_progress += 1
            chef = artifact.payload.get("chef")
            spice = artifact.payload.get("spice_level", 1)

            # Initialize chef tracking
            if chef not in self.chef_stats:
                self.chef_stats[chef] = {
                    "dishes": 0,
                    "total_spice": 0,
                    "reviews": []
                }

            self.chef_stats[chef]["dishes"] += 1
            self.chef_stats[chef]["total_spice"] += spice

            # Real-time alerting!
            if spice >= 4:
                self.spice_warnings += 1
                print(f"🌶️  SPICE ALERT! {chef} (🔥 Level {spice})")

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """Called AFTER any artifact is published - track reviews."""
        if artifact.type_name == "Review":
            rating = artifact.payload.get("rating", 3)

            # Update all chef stats with this review
            for chef, stats in self.chef_stats.items():
                stats["reviews"].append(rating)

            self.dishes_in_progress -= 1
            self.completed_dishes += 1

    async def on_cycle_complete(self, ctx: Context) -> None:
        """Called after each run_until_idle() - show dashboard."""
        print("\n🔥 KITCHEN STATUS BOARD 🔥")
        print(f"📊 In progress: {self.dishes_in_progress}")
        print(f"✅ Completed: {self.completed_dishes}")
        print(f"🌶️  Spice warnings: {self.spice_warnings}")

        # Show per-chef performance
        for chef, stats in self.chef_stats.items():
            avg_rating = sum(stats["reviews"]) / len(stats["reviews"])
            avg_spice = stats["total_spice"] / stats["dishes"]
            print(f"  {chef}: {'⭐' * int(avg_rating)} (spice: {avg_spice:.1f})")

# Attach to orchestrator (NOT individual agents!)
flock = Flock()
flock.with_components(KitchenMonitorComponent())  # ← Monitors ALL agents
```

**Key Features:**
- **System-wide tracking** - Monitors ALL dishes from ALL chefs
- **Real-time alerts** - Immediate warnings when conditions met
- **Aggregate statistics** - Cross-chef analytics
- **Cycle summaries** - Dashboard after each processing cycle

**Use Cases:**
- **Operational dashboards** - Real-time system status
- **Performance monitoring** - Track KPIs across agents
- **Alerting systems** - Notify on threshold breaches
- **Analytics** - Cross-agent correlation and reporting

---

### quest_tracker_component.py 🗡️
**Pattern:** Scoring system with leaderboard across all heroes

Track quest progress and maintain hero leaderboard:
- **Global scoring** - Points awarded across all quests
- **Leaderboard** - Rank heroes by total score
- **Event tracking** - Count total quests processed
- **Bonus logic** - Difficulty-based rewards

```bash
uv run 07-orchestrator-components/quest_tracker_component.py
```

**How It Works:**
```python
class QuestTrackerComponent(OrchestratorComponent):
    hero_scores: dict[str, int] = Field(default_factory=dict)
    total_quests: int = 0

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """Award starting points when quests begin."""
        if artifact.type_name == "Quest":
            hero = artifact.payload.get("hero")
            difficulty = artifact.payload.get("difficulty", "medium")

            self.total_quests += 1

            # Difficulty-based starting bonus
            bonus_map = {"easy": 5, "medium": 10, "hard": 20}
            starting_bonus = bonus_map.get(difficulty.lower(), 10)

            current_score = self.hero_scores.get(hero, 0)
            self.hero_scores[hero] = current_score + starting_bonus

            print(f"🗡️  {hero} accepted a {difficulty} quest! (+{starting_bonus})")

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """Award completion points when quests finish."""
        if artifact.type_name == "QuestProgress":
            hero = artifact.payload.get("hero")
            status = artifact.payload.get("status", "")

            if "complete" in status.lower() or "success" in status.lower():
                # Completion bonus!
                completion_bonus = 50
                current_score = self.hero_scores.get(hero, 0)
                self.hero_scores[hero] = current_score + completion_bonus

                print(f"✨ {hero} completed! (+{completion_bonus})")

    async def on_cycle_complete(self, ctx: Context) -> None:
        """Show leaderboard after each cycle."""
        print("\n🏆 Hero Leaderboard 🏆")
        sorted_heroes = sorted(
            self.hero_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for rank, (hero, score) in enumerate(sorted_heroes, 1):
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
            print(f"{medal} {rank}. {hero:15} - {score:4} points")

        print(f"Total quests: {self.total_quests}")

# Attach to orchestrator
flock = Flock()
flock.with_components(QuestTrackerComponent())
```

**Key Features:**
- **Cross-quest tracking** - One hero can have multiple quests
- **Dynamic scoring** - Different bonuses for different events
- **Leaderboard** - Real-time rankings
- **Lifecycle hooks** - Track both quest start and completion

**Use Cases:**
- **Gamification** - Score tracking and leaderboards
- **SLA monitoring** - Track completion rates across users
- **Resource allocation** - Identify top performers
- **Progress tracking** - Monitor workflow completion

---

## 🔑 Key Concepts

### Orchestrator Component Lifecycle

Components can hook into these orchestrator-level events:

```python
class MyComponent(OrchestratorComponent):
    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        """Called BEFORE any artifact is published (from any agent)"""
        pass

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        """Called AFTER any artifact is published (from any agent)"""
        pass

    async def on_cycle_start(self, ctx: Context) -> None:
        """Called at the beginning of run_until_idle()"""
        pass

    async def on_cycle_complete(self, ctx: Context) -> None:
        """Called at the end of run_until_idle()"""
        pass
```

### Attaching Components to Orchestrator

```python
from flock.components import OrchestratorComponent

flock = Flock()

# Attach to orchestrator (NOT agents!)
flock.with_components(
    MonitoringComponent(),
    MetricsComponent(),
    AlertingComponent()
)
```

### Multiple Components

Orchestrator can have multiple components - they execute in order:

```python
flock.with_components(
    ValidationComponent(),   # Runs first
    MonitoringComponent(),   # Runs second
    AlertingComponent()      # Runs third
)
```

### Global State Tracking

Components can maintain system-wide state:

```python
class SystemMetrics(OrchestratorComponent):
    total_artifacts: int = 0
    artifacts_by_type: dict[str, int] = Field(default_factory=dict)
    start_time: datetime = Field(default_factory=datetime.now)

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        # Track all artifacts system-wide
        self.total_artifacts += 1

        # Track by type
        artifact_type = artifact.type_name
        self.artifacts_by_type[artifact_type] = \
            self.artifacts_by_type.get(artifact_type, 0) + 1
```

## 🎓 Component Patterns

### Real-Time Dashboard Pattern
Show status after each processing cycle:

```python
class DashboardComponent(OrchestratorComponent):
    async def on_cycle_complete(self, ctx: Context) -> None:
        print("\n📊 System Status")
        print(f"Total agents: {len(ctx.orchestrator.agents)}")
        print(f"Active agents: {self.count_active()}")
        print(f"Artifacts: {await ctx.orchestrator.store.count()}")
```

### Alerting Pattern
Notify when thresholds exceeded:

```python
class AlertingComponent(OrchestratorComponent):
    error_count: int = 0
    ERROR_THRESHOLD = 5

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        if artifact.type_name == "Error":
            self.error_count += 1

            if self.error_count >= self.ERROR_THRESHOLD:
                # Send alert!
                print(f"🚨 ALERT: {self.error_count} errors detected!")
                self.error_count = 0  # Reset counter
```

### Correlation Pattern
Track related artifacts across agents:

```python
class WorkflowTracker(OrchestratorComponent):
    workflows: dict[str, list[str]] = Field(default_factory=dict)

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        # Track artifacts by correlation ID
        correlation_id = artifact.correlation_id

        if correlation_id not in self.workflows:
            self.workflows[correlation_id] = []

        self.workflows[correlation_id].append(artifact.type_name)

    async def on_cycle_complete(self, ctx: Context) -> None:
        # Show completed workflows
        for correlation_id, steps in self.workflows.items():
            print(f"Workflow {correlation_id}: {' → '.join(steps)}")
```

### SLA Monitoring Pattern
Track processing times and breaches:

```python
class SLAMonitor(OrchestratorComponent):
    processing_times: dict[str, float] = Field(default_factory=dict)
    sla_breaches: int = 0
    SLA_THRESHOLD_SECONDS = 30

    async def on_pre_publish(self, ctx: Context, artifact) -> None:
        # Record start time
        artifact_id = artifact.id
        self.processing_times[artifact_id] = time.time()

    async def on_post_publish(self, ctx: Context, artifact) -> None:
        # Check processing time
        artifact_id = artifact.id
        if artifact_id in self.processing_times:
            duration = time.time() - self.processing_times[artifact_id]

            if duration > self.SLA_THRESHOLD_SECONDS:
                self.sla_breaches += 1
                print(f"⚠️ SLA breach: {duration:.1f}s for {artifact.type_name}")
```

## 🎯 When to Use Orchestrator vs Agent Components

| Feature | Orchestrator Component | Agent Component |
|---------|----------------------|-----------------|
| **Scope** | All agents | Single agent |
| **Purpose** | System-wide coordination | Agent-specific behavior |
| **State** | Global metrics | Per-agent state |
| **Hooks** | pre/post publish, cycle | Full agent lifecycle |
| **Examples** | Dashboards, alerting | Validation, retry logic |

**Rule of thumb:**
- Use **Orchestrator Component** for "what's happening across the system"
- Use **Agent Component** for "how this specific agent behaves"

## 🚀 Advanced Patterns

### Multi-Component Coordination
```python
# Orchestrator components can work together
flock.with_components(
    CollectionComponent(),   # Collects metrics
    AnalysisComponent(),     # Analyzes patterns
    AlertingComponent()      # Sends alerts based on analysis
)
```

### Dynamic Thresholds
```python
class AdaptiveMonitor(OrchestratorComponent):
    threshold: float = 100.0

    async def on_cycle_complete(self, ctx: Context) -> None:
        # Adjust threshold based on load
        avg_load = self.calculate_avg_load()
        self.threshold = avg_load * 1.2  # 20% above average
```

### Conditional Monitoring
```python
class ConditionalMonitor(OrchestratorComponent):
    async def on_post_publish(self, ctx: Context, artifact) -> None:
        # Only monitor production artifacts
        if ctx.environment == "production":
            self.track_metric(artifact)
```

## 📖 Related Examples

- **03-claudes-workshop/lesson_11_performance_monitor.py** - Workshop lesson on orchestrator components
- **05-engines/** - Custom processing logic
- **06-agent-components/** - Per-agent lifecycle hooks

## 📚 Documentation

- [Orchestrator Components Guide](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/orchestrator-components.md)
- [Component Architecture](https://github.com/whiteducksoftware/flock-flow/blob/main/docs/guides/components.md)
- AGENTS.md - "Components" section

## 💡 Design Tips

1. **Keep it focused** - Each component should have one clear responsibility
2. **Avoid blocking operations** - Don't slow down artifact publishing
3. **Use cycle hooks for heavy work** - Do expensive operations in `on_cycle_complete`
4. **Reset state appropriately** - Clear temporary data after cycles
5. **Make metrics accessible** - Expose data for external monitoring tools

## 🎯 Real-World Use Cases

### Production Monitoring
```python
class ProductionMonitor(OrchestratorComponent):
    # Track uptime, throughput, error rates
    # Generate operational dashboards
    # Send alerts to PagerDuty/Slack
```

### Cost Tracking
```python
class CostTracker(OrchestratorComponent):
    # Track LLM token usage per agent
    # Calculate cost per workflow
    # Alert on budget thresholds
```

### Compliance Auditing
```python
class AuditLogger(OrchestratorComponent):
    # Log all artifacts for compliance
    # Track data lineage
    # Generate audit reports
```

### Performance Analytics
```python
class PerformanceAnalyzer(OrchestratorComponent):
    # Track agent execution times
    # Identify bottlenecks
    # Generate performance reports
```

---

**Ready to monitor your system? Start with kitchen_monitor_component! 🍳**
