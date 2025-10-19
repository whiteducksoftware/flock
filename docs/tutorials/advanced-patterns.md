# Advanced Patterns: Parallel Processing at Scale

**Difficulty:** ⭐⭐⭐ Advanced | **Time:** 45 minutes

Master parallel processing at scale with Flock's blackboard architecture. Build an 8-agent news agency where all analysts process breaking news simultaneously.

**Prerequisites:** Complete all previous tutorials

## What You'll Build

A real-time news agency with **8 specialized analysts**:

- World News Analyst
- Tech News Analyst
- Business Analyst
- Sports Analyst
- Entertainment Analyst
- Science Analyst
- Politics Analyst
- Health Analyst

When breaking news arrives, **ALL analysts process it in PARALLEL**, each producing their specialized perspective. No coordination needed!

## The O(n) vs O(n²) Problem

### ❌ Graph-Based Approach (O(n²) complexity)

```python
graph = Graph()

# Manual split node
graph.add_node("split_news", lambda x: [x]*8)

# Add all analysts
for category in categories:
    graph.add_node(category, analyst_functions[category])
    graph.add_edge("split_news", category)  # 8 edges!

# Manual join node
graph.add_node("join_analyses", aggregate_function)
for category in categories:
    graph.add_edge(category, "join_analyses")  # Another 8 edges!

# Total: 16+ edges to manage
```

**Problems:**

- 16+ edges to manage (split + join)
- Explicit split/join logic required
- Adding analyst = rewiring graph
- Tight coupling between nodes
- O(n²) complexity as agents grow

### ✅ Flock Approach (O(n) complexity)

```python
# Define analysts (auto-parallel!)
for category in categories:
    flock.agent(f"{category}_analyst") \
        .consumes(BreakingNews) \
        .publishes(NewsAnalysis)

# Define aggregator
editor.consumes(NewsAnalysis).publishes(NewsDigest)

# Run
await flock.publish(breaking_news)
await flock.run_until_idle()
```

**Benefits:**

- Zero edges to manage
- No split/join nodes needed
- Adding analyst = one line
- Loose coupling via types
- O(n) complexity

## Step 1: Define News Artifacts

```python
from typing import Literal
from pydantic import BaseModel, Field
from flock import Flock
from flock.registry import flock_type

@flock_type
class BreakingNews(BaseModel):
    """
    SEED INPUT: Raw breaking news that triggers all analysts

    🔥 KEY INSIGHT:
    This SINGLE artifact will be consumed by 8 agents IN PARALLEL!
    No explicit coordination needed - blackboard handles it.
    """
    headline: str
    raw_story: str = Field(min_length=100)
    source: str
    timestamp: str

@flock_type
class NewsAnalysis(BaseModel):
    """OUTPUT: Specialized analysis from each analyst"""
    category: Literal[
        "world", "technology", "business", "sports",
        "entertainment", "science", "politics", "health",
    ]
    analyst_name: str
    key_takeaways: list[str] = Field(min_length=3, max_length=5)
    impact_assessment: str
    related_context: str
    audience_recommendation: str

@flock_type
class NewsDigest(BaseModel):
    """AGGREGATION: Final digest combining all analyses"""
    headline: str
    comprehensive_summary: str
    perspectives_included: list[str]
    cross_category_insights: list[str]
    total_analysts: int
```

## Step 2: Define 8 Parallel Analyst Agents

**💡 The Magic:**

All 8 agents consume the SAME type (BreakingNews) but produce DIFFERENT analyses.

When BreakingNews is published, ALL 8 agents fire IN PARALLEL automatically!

No need to:

- Create split/join nodes
- Manage thread pools
- Write coordination logic
- Define execution order

The blackboard handles it all! 🎉

```python
flock = Flock("openai/gpt-4.1")

categories = [
    ("world", "Analyzes global events, international relations, geopolitics"),
    ("technology", "Covers tech trends, startups, AI, and innovation"),
    ("business", "Focuses on markets, economics, corporate news"),
    ("sports", "Covers athletics, competitions, player news"),
    ("entertainment", "Analyzes movies, music, celebrity culture"),
    ("science", "Covers research, discoveries, scientific breakthroughs"),
    ("politics", "Analyzes political developments, elections, policy"),
    ("health", "Focuses on medical news, public health, wellness"),
]

# Create 8 analysts automatically
for category, description in categories:
    flock.agent(f"{category}_analyst") \
        .description(description) \
        .consumes(BreakingNews) \
        .publishes(NewsAnalysis)
```

**🔥 What Just Happened?**

We created 8 agents that ALL subscribe to BreakingNews!

Execution flow:

1. `publish(BreakingNews)` → appears on blackboard
2. Flock sees 8 agents subscribed
3. All 8 execute concurrently (async)
4. Each produces their NewsAnalysis
5. No coordination code needed!

## Step 3: Add Aggregator Agent

```python
# Agent 9: The Editor (Aggregates all analyses)
# Waits for ALL analyses to complete before publishing digest
editor = (
    flock.agent("editor")
    .description("Synthesizes all analyst perspectives into comprehensive digest")
    .consumes(NewsAnalysis)  # Will collect all 8 analyses
    .publishes(NewsDigest)
)
```

## Step 4: Run the News Agency

```python
import time

async def main():
    print("📰 News Agency - Parallel Processing Demo\n")

    # 📰 Breaking news arrives!
    news = BreakingNews(
        headline="Major AI Breakthrough Announced at Tech Summit",
        raw_story="""
        Scientists at the Global Technology Summit announced a major breakthrough
        in artificial intelligence safety and alignment. The new technique, called
        'Constitutional AI', enables AI systems to better understand and follow
        human values and ethical guidelines...
        """,
        source="Global Tech News Wire",
        timestamp="2025-10-07T12:00:00Z",
    )

    # Track execution time
    start_time = time.time()

    # 📤 Publish the news (this triggers ALL 8 analysts simultaneously!)
    await flock.publish(news)

    # ⏳ Wait for all processing to complete
    await flock.run_until_idle()

    end_time = time.time()
    total_duration = end_time - start_time

    # 📊 Retrieve all analyses
    analyses = await flock.store.get_artifacts_by_type("NewsAnalysis")

    print(f"\n⚡ PERFORMANCE METRICS")
    print(f"   Total Analysts: {len(analyses)}")
    print(f"   Execution Time: {total_duration:.2f}s")
    print(f"   Speedup: ~{len(analyses)}x (thanks to parallel execution!)")
```

## Performance Comparison

### Sequential Processing (Graph frameworks)

```
Time = analyst1 + analyst2 + ... + analyst8
     = 5s + 5s + 5s + 5s + 5s + 5s + 5s + 5s
     = 40 seconds! 😱
```

### Parallel Processing (Flock)

```
Time = MAX(analyst1, analyst2, ..., analyst8)
     = MAX(5s, 5s, 5s, 5s, 5s, 5s, 5s, 5s)
     = 5 seconds! ⚡

Speedup: 8x faster!
```

## Key Takeaways

### 1. Automatic Parallelization

- Multiple agents subscribe to same type
- All fire concurrently when artifact published
- No manual coordination needed
- Blackboard handles all scheduling

### 2. Opportunistic Execution

- Agents decide what to process based on types
- No explicit workflow graph
- Adding agents = adding subscriptions
- Linear complexity: O(n) agents, not O(n²) edges

### 3. Scalability

- 8 agents? 80 agents? Same pattern!
- No split/join nodes
- No thread pool management
- Just define subscriptions

### 4. Natural Concurrency

- Async by default
- Agents run in parallel when independent
- Sequential when dependent (via types)
- Best of both worlds!

## Execution Patterns

### 1. All Parallel (This Lesson)

```python
# All consume same type → all run in parallel
analyst1.consumes(News)
analyst2.consumes(News)
analyst3.consumes(News)
# All fire simultaneously!
```

### 2. Sequential Chain

```python
# Different types → runs in sequence
agent1.consumes(A).publishes(B)
agent2.consumes(B).publishes(C)
agent3.consumes(C).publishes(D)
# Runs: agent1 → agent2 → agent3
```

### 3. Mixed (Parallel + Sequential)

```python
# Parallel analysts
analyst1.consumes(News).publishes(Analysis)
analyst2.consumes(News).publishes(Analysis)
# Sequential synthesizer
synthesizer.consumes(Analysis).publishes(Summary)
# Runs: analyst1+analyst2 in parallel → synthesizer
```

### 4. Conditional Parallel

```python
# Only some agents fire based on predicates
quick.consumes(News, where=lambda n: n.priority == "breaking")
deep.consumes(News, where=lambda n: n.priority == "investigative")
# Different agents for different news types!
```

## Try It Yourself

**Challenge 1: Add More Specialists**

```python
categories = [
    "world", "tech", "business", "sports",
    "entertainment", "science", "politics", "health",
    "climate", "crypto", "ai", "space"  # Add 4 more!
]
# Still O(n) complexity!
```

**Challenge 2: Create Multi-Stage Pipeline**

```python
# Stage 1: 8 analysts (parallel)
for cat in categories:
    flock.agent(f"{cat}_analyst") \
        .consumes(News).publishes(Analysis)

# Stage 2: 3 fact-checkers (parallel)
for i in range(3):
    flock.agent(f"fact_checker_{i}") \
        .consumes(Analysis).publishes(VerifiedAnalysis)

# Stage 3: 1 editor (sequential)
editor.consumes(VerifiedAnalysis).publishes(Digest)
# 8 + 3 + 1 = 12 agents, zero coordination code!
```

**Challenge 3: Trace Parallel Execution**

```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
# Query to see parallel execution:
python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)
spans = conn.execute('''
    SELECT name, start_time, duration_ms
    FROM spans
    WHERE name LIKE '%_analyst.execute'
    ORDER BY start_time
''').fetchall()
for span in spans:
    print(f'{span[0]}: start={span[1]}, duration={span[2]:.2f}ms')
"
# You'll see all 8 started at nearly same time!
```

## Gotchas & Tips

### ⚠️ Resource Limits

- Running 100 agents in parallel = 100 LLM calls
- Watch your rate limits!
- Use `.max_concurrency(10)` to throttle:

```python
agent.consumes(News).max_concurrency(10)
```

### ⚠️ Aggregation Timing

- Editor will fire for EACH analysis
- Use batch consumption if you want to wait for all:

```python
from flock.subscription import BatchSpec
from datetime import timedelta

editor.consumes(
    NewsAnalysis,
    batch=BatchSpec(size=8, timeout=timedelta(seconds=30))
)
```

### ⚠️ Error Handling

- If one analyst fails, others continue
- Use `.on_error()` hooks to handle failures gracefully

### ⚠️ Cost Optimization

- Parallel = more concurrent API calls
- Monitor costs carefully
- Consider selective parallelization

## Congratulations! 🎓

You've completed the entire Flock tutorial series!

**You now know:**

✅ Declarative type contracts
✅ Agent chaining through blackboard
✅ MCP tools integration
✅ Parallel processing at scale

## Next Steps

1. **Build your own multi-agent system**
2. **Explore [User Guides](../guides/index.md)** for advanced patterns
3. **Check [Use Cases](../guides/use-cases.md)** for production examples
4. **Read [API Reference](../reference/api.md)** for complete documentation

**Welcome to the future of AI orchestration!** 🚀

## Reference Links

- [Patterns Guide](../guides/patterns.md) - All architectural patterns
- [Use Cases](../guides/use-cases.md) - Production examples
- [API Reference](../reference/api.md) - Complete API documentation
- [Tracing Guide](../guides/tracing/index.md) - Debugging with traces
