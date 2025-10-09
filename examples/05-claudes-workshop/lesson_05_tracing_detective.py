"""
🔍 LESSON 05: Debugging the Detective - Unified Tracing Deep Dive
==================================================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How to use traced_run() for unified workflow tracing
2. How to query DuckDB traces to understand execution
3. How to debug complex multi-agent workflows
4. How to use tracing for performance analysis
5. How AI agents can help debug using trace data

🎬 THE SCENARIO:
---------------
You've built a complex recipe generation system, but something's wrong:
- Recipes sometimes take too long
- Occasional errors occur
- You're not sure which agent is the bottleneck

Using Flock's built-in OpenTelemetry + DuckDB tracing, you'll:
1. Instrument the workflow with traced_run()
2. Execute the system and capture traces
3. Query the trace database like a detective
4. Find and fix performance issues

⏱️  TIME: 25 minutes
💡 COMPLEXITY: ⭐⭐⭐⭐ Advanced

Let's debug! 🔍👇
"""

import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define Recipe Pipeline Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class RecipeRequest(BaseModel):
    """Initial request for a recipe"""

    cuisine: str
    dietary_restrictions: list[str] = Field(default_factory=list)
    max_prep_time_minutes: int = Field(default=60)


@flock_type
class RecipeDraft(BaseModel):
    """Draft recipe from chef"""

    title: str
    ingredients: list[str] = Field(min_length=5)
    instructions: list[str] = Field(min_length=5)
    prep_time: int
    cuisine_type: str


@flock_type
class NutritionAnalysis(BaseModel):
    """Nutritional breakdown"""

    calories: int = Field(ge=0)
    protein_grams: int = Field(ge=0)
    carbs_grams: int = Field(ge=0)
    fat_grams: int = Field(ge=0)
    health_score: int = Field(ge=1, le=10)


@flock_type
class FinalRecipe(BaseModel):
    """Complete recipe with nutrition"""

    title: str
    ingredients: list[str]
    instructions: list[str]
    prep_time: int
    nutrition: dict[str, int]
    health_score: int


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👨‍🍳 STEP 3: Define Recipe Pipeline Agents
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

chef = (
    flock.agent("chef")
    .description("Creates delicious recipe drafts")
    .consumes(RecipeRequest)
    .publishes(RecipeDraft)
)

nutritionist = (
    flock.agent("nutritionist")
    .description("Analyzes nutritional content of recipes")
    .consumes(RecipeDraft)
    .publishes(NutritionAnalysis)
)

publisher = (
    flock.agent("publisher")
    .description("Combines recipe and nutrition into final format")
    .consumes(RecipeDraft, NutritionAnalysis)
    .publishes(FinalRecipe)
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔍 STEP 4: Run with Unified Tracing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    This example demonstrates TWO ways to trace workflows:

    1. WITHOUT traced_run() - Separate traces (old way)
    2. WITH traced_run() - Unified trace (recommended)

    Then we'll query the DuckDB trace database to analyze performance!
    """

    print("🔍 Tracing Detective Workshop\n")
    print("=" * 70)
    print("📋 SETUP")
    print("=" * 70)
    print("This lesson requires tracing to be enabled.")
    print("Make sure you ran with:")
    print("  export FLOCK_AUTO_TRACE=true")
    print("  export FLOCK_TRACE_FILE=true")
    print("=" * 70)
    print()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🎯 EXAMPLE 1: Without traced_run() (Separate Traces)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📍 EXAMPLE 1: Without traced_run() (Old Way)")
    print("─" * 70)
    print("This will create SEPARATE root traces for publish() and run_until_idle()")
    print()

    request1 = RecipeRequest(
        cuisine="Italian",
        dietary_restrictions=["vegetarian"],
        max_prep_time_minutes=45,
    )

    # ❌ OLD WAY: Each operation gets its own root trace
    await flock.publish(request1)  # ← Trace 1
    await flock.run_until_idle()  # ← Trace 2

    print("✅ Recipe 1 generated with separate traces\n")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🎯 EXAMPLE 2: With traced_run() (Unified Trace) ⭐ RECOMMENDED
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📍 EXAMPLE 2: With traced_run() (New Way) ⭐")
    print("─" * 70)
    print("This will create ONE unified trace for the entire workflow")
    print()

    request2 = RecipeRequest(
        cuisine="Japanese",
        dietary_restrictions=["gluten-free"],
        max_prep_time_minutes=30,
    )

    # ✅ NEW WAY: Everything under a single parent trace
    async with flock.traced_run("recipe_generation_workflow"):
        await flock.publish(request2)  # ← Part of unified trace
        await flock.run_until_idle()  # ← Part of unified trace

    print("✅ Recipe 2 generated with unified trace\n")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔍 STEP 5: Query the Trace Database
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n" + "=" * 70)
    print("🔍 TRACE ANALYSIS")
    print("=" * 70)

    # Import DuckDB for querying
    try:
        import duckdb
    except ImportError:
        print("❌ DuckDB not installed. Install with: pip install duckdb")
        return

    # Connect to the trace database (read-only)
    try:
        conn = duckdb.connect(".flock/traces.duckdb", read_only=True)
    except Exception as e:
        print(f"❌ Could not connect to trace database: {e}")
        print("   Make sure FLOCK_TRACE_FILE=true was set before running")
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 QUERY 1: Compare Separate vs Unified Traces
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📊 QUERY 1: Root Traces Overview")
    print("─" * 70)

    result = conn.execute("""
        SELECT
            trace_id,
            name,
            duration_ms,
            (SELECT COUNT(*) FROM spans s2 WHERE s2.trace_id = s1.trace_id) as total_spans
        FROM spans s1
        WHERE parent_id IS NULL  -- Root spans only
        ORDER BY start_time DESC
        LIMIT 10
    """).fetchall()

    print(f"{'Trace ID':<40} {'Operation':<30} {'Duration':<12} {'Spans'}")
    print("─" * 70)
    for row in result:
        trace_id_short = row[0][:8] + "..."
        print(f"{trace_id_short:<40} {row[1]:<30} {row[2]:>8.0f}ms {row[3]:>6}")

    print(
        "\n💡 Notice: Unified traces show 'recipe_generation_workflow' "
        "with ALL spans nested underneath!"
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 QUERY 2: Agent Performance Breakdown
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📊 QUERY 2: Agent Performance")
    print("─" * 70)

    result = conn.execute("""
        SELECT
            service as agent_name,
            COUNT(*) as executions,
            AVG(duration_ms) as avg_duration_ms,
            MAX(duration_ms) as max_duration_ms,
            MIN(duration_ms) as min_duration_ms
        FROM spans
        WHERE name LIKE '%.execute'
        GROUP BY service
        ORDER BY avg_duration_ms DESC
    """).fetchall()

    print(f"{'Agent':<15} {'Executions':<12} {'Avg (ms)':<12} {'Max (ms)':<12} {'Min (ms)'}")
    print("─" * 70)
    for row in result:
        print(f"{row[0]:<15} {row[1]:<12} {row[2]:>8.0f}ms {row[3]:>8.0f}ms {row[4]:>8.0f}ms")

    print("\n💡 This shows which agent is the slowest bottleneck!")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 QUERY 3: Execution Timeline for Latest Workflow
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📊 QUERY 3: Latest Workflow Timeline")
    print("─" * 70)

    result = conn.execute("""
        WITH latest_trace AS (
            SELECT trace_id
            FROM spans
            WHERE name = 'recipe_generation_workflow'
            ORDER BY start_time DESC
            LIMIT 1
        )
        SELECT
            name,
            service,
            duration_ms,
            status_code
        FROM spans
        WHERE trace_id = (SELECT trace_id FROM latest_trace)
        ORDER BY start_time ASC
    """).fetchall()

    print(f"{'Operation':<40} {'Agent':<15} {'Duration':<12} {'Status'}")
    print("─" * 70)
    for row in result:
        print(f"{row[0]:<40} {row[1] or 'N/A':<15} {row[2]:>8.0f}ms {row[3]}")

    print("\n💡 This shows the complete execution timeline!")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 QUERY 4: Error Detection
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📊 QUERY 4: Error Detection")
    print("─" * 70)

    result = conn.execute("""
        SELECT
            name,
            service,
            status_description,
            start_time
        FROM spans
        WHERE status_code = 'ERROR'
        ORDER BY start_time DESC
        LIMIT 5
    """).fetchall()

    if result:
        print(f"{'Operation':<40} {'Agent':<15} {'Error'}")
        print("─" * 70)
        for row in result:
            error_msg = row[2][:50] + "..." if len(row[2]) > 50 else row[2]
            print(f"{row[0]:<40} {row[1] or 'N/A':<15} {error_msg}")
    else:
        print("✅ No errors found - all executions successful!")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📊 QUERY 5: Performance Percentiles (P50, P95, P99)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n📊 QUERY 5: Performance Percentiles")
    print("─" * 70)

    result = conn.execute("""
        SELECT
            service,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) as p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99
        FROM spans
        WHERE name LIKE '%.execute' AND service IS NOT NULL
        GROUP BY service
    """).fetchall()

    print(f"{'Agent':<15} {'P50 (ms)':<12} {'P95 (ms)':<12} {'P99 (ms)'}")
    print("─" * 70)
    for row in result:
        print(f"{row[0]:<15} {row[1]:>8.0f}ms {row[2]:>8.0f}ms {row[3]:>8.0f}ms")

    print("\n💡 P95 and P99 show worst-case latencies - important for SLAs!")

    conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🧹 BONUS: Clear Traces (Optional)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print("\n" + "=" * 70)
    print("🧹 TRACE MANAGEMENT")
    print("=" * 70)
    print("\nYou can clear traces for a fresh debugging session:")
    print("  result = Flock.clear_traces()")
    print("  print(f\"Cleared {result['deleted_count']} spans\")")
    print("\n(Not running it now so you can explore the traces!)")
    print("=" * 70)

    print("\n✨ Tracing analysis complete!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You're now a tracing expert!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ UNIFIED TRACING WITH traced_run()
   - Groups entire workflows under single trace
   - Much easier to understand execution flow
   - Single trace_id for all operations
   - Better for debugging complex workflows

2️⃣ DUCKDB TRACE QUERYING
   - All traces stored in .flock/traces.duckdb
   - Use SQL to analyze performance
   - Find bottlenecks, errors, outliers
   - Production-ready analytics

3️⃣ PERFORMANCE ANALYSIS
   - Identify slow agents with AVG(duration_ms)
   - Find outliers with P95/P99 percentiles
   - Track error rates with status_code
   - Analyze execution timelines

4️⃣ AI-ASSISTED DEBUGGING
   - AI agents can query DuckDB directly
   - Automatic root cause analysis
   - Performance regression detection
   - Anomaly detection

🆚 COMPARISON: Separate vs Unified Traces
-----------------------------------------

❌ WITHOUT traced_run():
```
Trace A: Flock.publish
  └─ (isolated)

Trace B: Flock.run_until_idle
  ├─ Agent chef.execute
  ├─ Agent nutritionist.execute
  └─ Agent publisher.execute

Problem: Hard to connect operations!
```

✅ WITH traced_run():
```
Trace: recipe_generation_workflow
  ├─ Flock.publish
  └─ Flock.run_until_idle
      ├─ Agent chef.execute
      ├─ Agent nutritionist.execute
      └─ Agent publisher.execute

Solution: Complete hierarchy in ONE trace!
```

💡 USEFUL QUERIES FOR DEBUGGING:
--------------------------------

1. **Find Slowest Operations**:
```sql
SELECT name, AVG(duration_ms) as avg_ms
FROM spans
WHERE duration_ms > 1000
GROUP BY name
ORDER BY avg_ms DESC
```

2. **Trace Specific Workflow**:
```sql
SELECT * FROM spans
WHERE trace_id = '<your-trace-id>'
ORDER BY start_time ASC
```

3. **Error Analysis**:
```sql
SELECT
    name,
    status_description,
    json_extract(attributes, '$.input') as input_data
FROM spans
WHERE status_code = 'ERROR'
```

4. **Agent Dependency Graph**:
```sql
SELECT DISTINCT
    json_extract(s1.attributes, '$.output.type') as artifact_type,
    s1.service as producer,
    s2.service as consumer
FROM spans s1
JOIN spans s2 ON
    json_extract(s1.attributes, '$.output.type') =
    json_extract(s2.attributes, '$.input.artifacts[0].type')
WHERE s1.service != s2.service
```

🧪 ADVANCED TRACING TECHNIQUES:
-------------------------------

1. **Custom Attributes**:
```python
async with flock.traced_run("my_workflow") as span:
    span.set_attribute("workflow.version", "2.0")
    span.set_attribute("user_id", "user_123")
    await flock.publish(data)
```

2. **Nested Workflows**:
```python
async with flock.traced_run("outer_workflow"):
    await flock.publish(data1)
    async with flock.traced_run("inner_subtask"):
        await flock.publish(data2)
    await flock.run_until_idle()
```

3. **Export for External Systems**:
```python
import duckdb
conn = duckdb.connect('.flock/traces.duckdb')
conn.execute('''
    COPY (SELECT * FROM spans WHERE start_time > NOW() - INTERVAL '1 hour')
    TO 'recent_traces.parquet' (FORMAT PARQUET)
''')
# Upload to Grafana, DataDog, etc.
```

⚠️  PRODUCTION TIPS:
-------------------

1. **Enable Filtering**:
```bash
export FLOCK_TRACE_SERVICES='["flock", "agent", "dspyengine"]'
# Avoid tracing noisy operations
```

2. **Periodic Cleanup**:
```python
# Clean old traces weekly
result = Flock.clear_traces()
```

3. **Monitor Trace Size**:
```sql
SELECT COUNT(*) as total_spans,
       SUM(LENGTH(attributes)) as total_bytes
FROM spans
```

4. **Set Up Alerts**:
```sql
-- Find agents with >5s P95 latency
SELECT service
FROM (
    SELECT service,
           PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95
    FROM spans
    WHERE name LIKE '%.execute'
    GROUP BY service
)
WHERE p95 > 5000
```

📈 NEXT LESSON:
--------------
Lesson 06: The Secret Agent Network
- Visibility controls for security
- Multi-tenancy with TenantVisibility
- Private/Public/Labelled artifacts
- Zero-trust architecture

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_06_secret_agents.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
