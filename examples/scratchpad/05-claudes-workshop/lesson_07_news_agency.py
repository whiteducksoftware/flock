"""
📰 LESSON 07: The News Agency - Parallel Processing at Scale
=============================================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How blackboard enables automatic parallel execution
2. How multiple agents process the same artifact concurrently
3. How to scale to dozens of agents without complexity
4. Why parallel processing is O(n) in Flock vs O(n²) in graphs

🎬 THE SCENARIO:
---------------
You're building a real-time news agency with 8 specialized analysts:
- World News Analyst
- Tech News Analyst
- Business Analyst
- Sports Analyst
- Entertainment Analyst
- Science Analyst
- Politics Analyst
- Health Analyst

When breaking news arrives, ALL analysts process it in PARALLEL,
each producing their specialized perspective. No coordination needed!

⏱️  TIME: 20 minutes
💡 COMPLEXITY: ⭐⭐⭐ Intermediate-Advanced

Let's publish! 📰👇
"""

import asyncio
import time
from typing import Literal

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define News Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


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
    """
    OUTPUT: Specialized analysis from each analyst

    Each analyst produces one of these with their unique perspective.
    """

    category: Literal[
        "world",
        "technology",
        "business",
        "sports",
        "entertainment",
        "science",
        "politics",
        "health",
    ]
    analyst_name: str
    key_takeaways: list[str] = Field(min_length=3, max_length=5)
    impact_assessment: str
    related_context: str
    audience_recommendation: str = Field(description="Who should care about this and why")


@flock_type
class NewsDigest(BaseModel):
    """
    AGGREGATION: Final digest combining all analyses

    This agent waits for ALL analyses, then synthesizes them.
    """

    headline: str
    comprehensive_summary: str
    perspectives_included: list[str]
    cross_category_insights: list[str]
    total_analysts: int


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📰 STEP 3: Define 8 Parallel Analyst Agents
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 THE MAGIC:
# All 8 agents consume the SAME type (BreakingNews) but produce DIFFERENT analyses.
# When BreakingNews is published, ALL 8 agents fire IN PARALLEL automatically!
#
# No need to:
# - Create split/join nodes
# - Manage thread pools
# - Write coordination logic
# - Define execution order
#
# The blackboard handles it all! 🎉

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
    flock.agent(f"{category}_analyst").description(description).consumes(BreakingNews).publishes(
        NewsAnalysis
    )

# 🔥 WHAT JUST HAPPENED?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# We created 8 agents that ALL subscribe to BreakingNews!
#
# Execution flow:
# 1. publish(BreakingNews) → appears on blackboard
# 2. Flock sees 8 agents subscribed
# 3. All 8 execute concurrently (async)
# 4. Each produces their NewsAnalysis
# 5. No coordination code needed!
#
# 🆚 VS GRAPH-BASED FRAMEWORKS:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Traditional graph-based approach:
#
# graph.add_node("split", lambda x: [x]*8)  # Manual split
# for category in categories:
#     graph.add_node(category, analyst_func)
#     graph.add_edge("split", category)
#     graph.add_edge(category, "join")
# graph.add_node("join", aggregate_func)  # Manual join
#
# Flock's subscription-based approach:
#   Just define subscriptions. Done! 🎉

# 📊 Agent 9: The Editor (Aggregates all analyses)
# Waits for ALL analyses to complete before publishing digest

editor = (
    flock.agent("editor")
    .description("Synthesizes all analyst perspectives into comprehensive digest")
    .consumes(NewsAnalysis)  # Will collect all 8 analyses
    .publishes(NewsDigest)
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the News Agency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Publish breaking news and watch 8 agents process it in parallel!

    Timeline:
    1. Breaking news published
    2. All 8 analysts start simultaneously
    3. Each produces their specialized analysis
    4. Editor waits for all, then synthesizes
    """

    print("📰 News Agency - Parallel Processing Demo\n")

    # 📰 Breaking news arrives!
    news = BreakingNews(
        headline="Major AI Breakthrough Announced at Tech Summit",
        raw_story="""
        Scientists at the Global Technology Summit announced a major breakthrough
        in artificial intelligence safety and alignment. The new technique, called
        'Constitutional AI', enables AI systems to better understand and follow
        human values and ethical guidelines. Industry leaders predict this could
        accelerate AI adoption across healthcare, education, and scientific research
        while addressing longstanding safety concerns. Stock markets responded
        positively, with tech sector shares rising 3%. Critics warn that regulatory
        frameworks must keep pace with rapid advancement.
        """,
        source="Global Tech News Wire",
        timestamp="2025-10-07T12:00:00Z",
    )

    print("=" * 70)
    print("🚨 BREAKING NEWS ALERT")
    print("=" * 70)
    print(f"Headline: {news.headline}")
    print(f"Source: {news.source}")
    print(f"Time: {news.timestamp}")
    print("=" * 70)
    print()

    print("📡 Dispatching to all analysts...")
    print("   (Watch them process in PARALLEL!)\n")

    # Track execution time
    start_time = time.time()

    # 📤 Publish the news (this triggers ALL 8 analysts simultaneously!)
    await flock.publish(news)

    # ⏳ Wait for all processing to complete
    await flock.run_until_idle()

    end_time = time.time()
    total_duration = end_time - start_time

    # 📊 Retrieve and display all analyses
    print("\n" + "=" * 70)
    print("📊 ANALYST PERSPECTIVES")
    print("=" * 70)

    analyses = await flock.store.get_artifacts_by_type("NewsAnalysis")

    for analysis in analyses:
        obj = analysis.obj
        print(f"\n📍 {obj.category.upper()} PERSPECTIVE")
        print(f"   Analyst: {obj.analyst_name}")
        print("   Key Takeaways:")
        for takeaway in obj.key_takeaways:
            print(f"      • {takeaway}")
        print(f"   Impact: {obj.impact_assessment[:100]}...")
        print(f"   Audience: {obj.audience_recommendation[:80]}...")

    # 📰 Show the final digest
    digests = await flock.store.get_artifacts_by_type("NewsDigest")
    if digests:
        digest = digests[-1].obj
        print("\n" + "=" * 70)
        print("📰 FINAL NEWS DIGEST")
        print("=" * 70)
        print(f"\nHeadline: {digest.headline}")
        print("\nComprehensive Summary:")
        print(f"   {digest.comprehensive_summary}")
        print(f"\nPerspectives Included ({digest.total_analysts}):")
        for perspective in digest.perspectives_included:
            print(f"   ✓ {perspective}")
        print("\nCross-Category Insights:")
        for insight in digest.cross_category_insights:
            print(f"   → {insight}")
        print("=" * 70)

    # 📈 Performance stats
    print("\n⚡ PERFORMANCE METRICS")
    print(f"   Total Analysts: {len(analyses)}")
    print(f"   Execution Time: {total_duration:.2f}s")
    print(f"   Parallelization: {len(analyses)} analyses completed in {total_duration:.2f}s")
    if len(analyses) > 0:
        print(f"   Avg Time per Analysis: {total_duration / len(analyses):.2f}s (if sequential)")
        print(f"   Speedup: ~{len(analyses)}x (thanks to parallel execution!)")

    print("\n✨ News processing complete!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You've mastered parallel processing with Flock!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ AUTOMATIC PARALLELIZATION
   - Multiple agents subscribe to same type
   - All fire concurrently when artifact published
   - No manual coordination needed
   - Blackboard handles all scheduling

2️⃣ OPPORTUNISTIC EXECUTION
   - Agents decide what to process based on types
   - No explicit workflow graph
   - Adding agents = adding subscriptions
   - Linear complexity: O(n) agents, not O(n²) edges

3️⃣ SCALABILITY
   - 8 agents? 80 agents? Same pattern!
   - No split/join nodes
   - No thread pool management
   - Just define subscriptions

4️⃣ NATURAL CONCURRENCY
   - Async by default
   - Agents run in parallel when independent
   - Sequential when dependent (via types)
   - Best of both worlds!

🆚 VS GRAPH-BASED FRAMEWORKS:
-----------------------------

❌ Traditional Graph-Based Example (Parallel Processing):
```python
from some_graph_framework import Graph

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

# Set entry point
graph.set_entry_point("split_news")

# Compile
app = graph.compile()

# Run
result = app.invoke(breaking_news)
```

Problems:
- 16+ edges to manage (split + join)
- Explicit split/join logic required
- Adding analyst = rewiring graph
- Tight coupling between nodes
- O(n²) complexity as agents grow

✅ Flock Example (Parallel Processing):
```python
# Define analysts (auto-parallel!)
for category in categories:
    flock.agent(f"{category}_analyst") \\
        .consumes(BreakingNews) \\
        .publishes(NewsAnalysis)

# Define aggregator
editor.consumes(NewsAnalysis).publishes(NewsDigest)

# Run
await flock.publish(breaking_news)
await flock.run_until_idle()
```

Benefits:
- Zero edges to manage
- No split/join nodes needed
- Adding analyst = one line
- Loose coupling via types
- O(n) complexity

💡 EXECUTION PATTERNS:
---------------------

1. **All Parallel (This Lesson)**:
```python
# All consume same type → all run in parallel
analyst1.consumes(News)
analyst2.consumes(News)
analyst3.consumes(News)
# All fire simultaneously!
```

2. **Sequential Chain**:
```python
# Different types → runs in sequence
agent1.consumes(A).publishes(B)
agent2.consumes(B).publishes(C)
agent3.consumes(C).publishes(D)
# Runs: agent1 → agent2 → agent3
```

3. **Mixed (Parallel + Sequential)**:
```python
# Parallel analysts
analyst1.consumes(News).publishes(Analysis)
analyst2.consumes(News).publishes(Analysis)
# Sequential synthesizer
synthesizer.consumes(Analysis).publishes(Summary)
# Runs: analyst1+analyst2 in parallel → synthesizer
```

4. **Conditional Parallel**:
```python
# Only some agents fire based on predicates
quick.consumes(News, where=lambda n: n.priority == "breaking")
deep.consumes(News, where=lambda n: n.priority == "investigative")
# Different agents for different news types!
```

🧪 EXPERIMENT IDEAS:
-------------------

1. **Add More Specialists**:
```python
categories = [
    "world", "tech", "business", "sports",
    "entertainment", "science", "politics", "health",
    "climate", "crypto", "ai", "space"  # Add 4 more!
]
# Still O(n) complexity!
```

2. **Create Multi-Stage Pipeline**:
```python
# Stage 1: 8 analysts (parallel)
for cat in categories:
    flock.agent(f"{cat}_analyst") \\
        .consumes(News).publishes(Analysis)

# Stage 2: 3 fact-checkers (parallel)
for i in range(3):
    flock.agent(f"fact_checker_{i}") \\
        .consumes(Analysis).publishes(VerifiedAnalysis)

# Stage 3: 1 editor (sequential)
editor.consumes(VerifiedAnalysis).publishes(Digest)
# 8 + 3 + 1 = 12 agents, zero coordination code!
```

3. **Dynamic Priority Routing**:
```python
# High priority goes to 10 analysts
for i in range(10):
    flock.agent(f"analyst_{i}") \\
        .consumes(News, where=lambda n: n.priority == "high") \\
        .publishes(Analysis)

# Low priority goes to 2 analysts
for i in range(2):
    flock.agent(f"basic_analyst_{i}") \\
        .consumes(News, where=lambda n: n.priority == "low") \\
        .publishes(Analysis)
```

4. **Trace Parallel Execution**:
```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
# Query to see parallel execution:
SELECT
    name,
    start_time,
    end_time,
    duration_ms
FROM spans
WHERE name LIKE '%_analyst.execute'
ORDER BY start_time
# You'll see all 8 started at nearly same time!
```

⚡ PERFORMANCE IMPLICATIONS:
---------------------------

Sequential Processing (Graph frameworks):
```
Time = analyst1_time + analyst2_time + ... + analyst8_time
     = 5s + 5s + 5s + 5s + 5s + 5s + 5s + 5s
     = 40 seconds! 😱
```

Parallel Processing (Flock):
```
Time = MAX(analyst1_time, analyst2_time, ..., analyst8_time)
     = MAX(5s, 5s, 5s, 5s, 5s, 5s, 5s, 5s)
     = 5 seconds! ⚡
Speedup: 8x faster!
```

⚠️  GOTCHAS & TIPS:
------------------

1. **Resource Limits**:
   - Running 100 agents in parallel = 100 LLM calls
   - Watch your rate limits!
   - Use .max_concurrency(10) to throttle:
   ```python
   agent.consumes(News).max_concurrency(10)
   ```

2. **Aggregation Timing**:
   - Editor will fire for EACH analysis
   - Use batch consumption if you want to wait for all:
   ```python
   from flock.subscription import BatchSpec
   editor.consumes(
       NewsAnalysis,
       batch=BatchSpec(size=8, timeout=timedelta(seconds=30))
   )
   ```

3. **Error Handling**:
   - If one analyst fails, others continue
   - Use .on_error() hooks to handle failures gracefully

4. **Cost Optimization**:
   - Parallel = more concurrent API calls
   - Monitor costs carefully
   - Consider selective parallelization

🏆 FINAL THOUGHTS:
-----------------

You've completed the entire Flock workshop! You now know:

✅ Declarative type contracts (Lesson 01)
✅ Agent chaining through blackboard (Lesson 02)
✅ MCP tools integration (Lesson 03)
✅ Feedback loops & iteration (Lesson 04)
✅ Unified tracing & debugging (Lesson 05)
✅ Visibility controls & security (Lesson 06)
✅ Parallel processing at scale (Lesson 07)

🎓 YOU'RE NOW A BLACKBOARD ORCHESTRATION EXPERT! 🎓

Next steps:
1. Build your own multi-agent system
2. Explore the main Flock examples in examples/showcase/
3. Read AGENTS.md for contribution guidelines
4. Join the community and share what you build!

🚀 Welcome to the future of AI orchestration! 🚀
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
