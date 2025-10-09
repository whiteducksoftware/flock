# Research Examples: Compelling Demonstrations of Blackboard Advantages

**Purpose:** Quick-reference examples for academic presentations, papers, and demonstrations.
**Audience:** Researchers, paper reviewers, conference attendees

---

## Example 1: The "Aha!" Moment - Adding an Agent Without Rewiring

**Context:** Show temporal decoupling in action
**Use case:** Paper introduction, conference demo, elevator pitch

### Graph-Based Approach (The Problem)

```python
# Original system with 3 agents:
workflow = StateGraph()
workflow.add_node("radiologist", radiology_func)
workflow.add_node("lab_tech", lab_func)
workflow.add_node("diagnostician", diagnosis_func)

# Explicit edges (hardcoded topology):
workflow.add_edge("radiologist", "diagnostician")
workflow.add_edge("lab_tech", "diagnostician")

compiled = workflow.compile()

# 🔥 NOW: Add performance analyzer
# Problem: Need to rewire entire topology
workflow.add_node("performance", performance_func)
workflow.add_edge("radiologist", "performance")  # Add new edge
workflow.add_edge("lab_tech", "performance")     # Add new edge
workflow.add_edge("performance", "diagnostician") # Modify existing flow

# Must recompile and redeploy entire system
compiled = workflow.compile()
```

**Pain points:**
- 🔴 Identified which agents to connect (requires understanding full topology)
- 🔴 Modified existing edges (brittle, error-prone)
- 🔴 Recompiled entire graph (slow, risky)
- 🔴 Redeployed system (downtime)

---

### Blackboard Approach (The Solution)

```python
# Original system with 3 agents:
radiologist = flock.agent("radiologist").consumes(Scan).publishes(XRayAnalysis)
lab_tech = flock.agent("lab_tech").consumes(Scan).publishes(LabResults)
diagnostician = flock.agent("diagnostician").consumes(XRayAnalysis, LabResults).publishes(Diagnosis)

# ✨ NOW: Add performance analyzer (ONE LINE)
performance = flock.agent("performance").consumes(Scan).publishes(PerfAnalysis)

# That's it. No rewiring. No recompilation. No downtime.
# Performance analyzer immediately starts consuming Scan artifacts in parallel with radiologist and lab_tech.
# Diagnostician can optionally start consuming PerfAnalysis (just add it to consumes list).
```

**Benefits:**
- ✅ Zero knowledge of existing topology required
- ✅ Zero changes to existing agents
- ✅ Zero recompilation
- ✅ Zero downtime

**Demo script:**
1. Show original 3-agent system running
2. Add `performance` agent with one line of code
3. Publish a `Scan` artifact
4. Show all 4 agents in dashboard (3 parallel, 1 sequential)
5. Point out: "No rewiring. The topology emerged from type subscriptions."

---

## Example 2: The Scaling Problem - 50 Agents

**Context:** Demonstrate O(n) vs O(n²) complexity
**Use case:** Scalability section of paper, technical deep-dive

### Graph-Based: O(n²) Edge Explosion

```python
# 50 signal analyzers (volatility, sentiment, volume, momentum, etc.)
workflow = StateGraph()

# Add all 50 analyzers:
for signal in signal_analyzers:  # 50 agents
    workflow.add_node(signal.name, signal.func)

# 🔥 NOW: Wire them to aggregator
# Problem: Must add 50 explicit edges
for signal in signal_analyzers:
    workflow.add_edge(signal.name, "aggregator")  # 50 edges!

# 🔥 NOW: Add correlation analyzer
# Problem: It needs to connect to 20 of the signals
for signal in selected_signals:  # 20 signals
    workflow.add_edge(signal.name, "correlator")  # 20 more edges!

# Total edges: 70 (and growing quadratically)
# Mental model: "Which agents connect to which other agents?"
# Maintenance: Nightmare (add signal_51 → update 70 edges?)
```

**Complexity analysis:**
- 50 agents = 1,225 potential edges (n×(n-1)/2)
- Adding agent_51 = reading entire graph to find dependencies
- Debugging: "Why is signal_23 not connected to correlator?"
- Memory: O(n²) edge storage

---

### Blackboard: O(n) Subscriptions

```python
# 50 signal analyzers:
for signal_type in signal_types:  # 50 types
    flock.agent(f"{signal_type}_analyzer").consumes(MarketData).publishes(Signal)

# Aggregator (automatically waits for all 50 signals):
aggregator = flock.agent("aggregator").consumes(Signal).publishes(AggregatedSignal)

# ✨ Add correlation analyzer (ONE LINE):
correlator = flock.agent("correlator").consumes(Signal, where=lambda s: s.category in MOMENTUM_SIGNALS).publishes(Correlation)

# That's it. 50 agents + 2 consumers = 52 lines of code.
# Mental model: "What data types do I care about?"
# Maintenance: Trivial (add signal_51 → one line: consumes(MarketData).publishes(Signal))
```

**Complexity analysis:**
- 50 agents = 50-150 subscriptions (each agent: 1-3 types)
- Adding agent_51 = declare what types it consumes (no graph knowledge needed)
- Debugging: "Which agents subscribe to Signal?" (grep for `consumes(Signal)`)
- Memory: O(n) subscription storage

**Demo script:**
1. Show graph with 50 nodes and 1,225 edges (spaghetti diagram)
2. Show blackboard with 50 agents, each listing 1-3 types (clean list)
3. Live-code adding agent_51:
   - Graph: Must identify dependencies, add edges, recompile
   - Blackboard: One line: `agent_51.consumes(MarketData).publishes(NewSignal)`
4. Show dashboard: agent_51 immediately active

---

## Example 3: The Security Problem - Multi-Tenant SaaS

**Context:** Demonstrate visibility-driven scheduling
**Use case:** Security section, HIPAA/SOC2 compliance discussion

### Graph-Based: No Built-In Security

```python
# Graph-based frameworks: DIY security
def process_customer_data(state):
    customer_id = state["customer_id"]
    data = state["data"]

    # 🔥 Problem: Must implement authorization manually
    if not check_authorization(current_agent, customer_id):
        raise UnauthorizedError("Agent cannot access this customer's data")

    # 🔥 Problem: Authorization check happens AFTER agent is scheduled
    # Agent was already invoked, wasting LLM calls if unauthorized

    # Process data...
    return {"result": result}

# 🔥 Problem: No framework-level enforcement
# Developer must remember to add checks in EVERY agent
# One forgotten check = security vulnerability
```

**Pain points:**
- 🔴 No framework-level security model
- 🔴 Manual checks in every agent (error-prone)
- 🔴 Authorization happens after scheduling (wasted LLM calls)
- 🔴 No tenant isolation guarantees
- 🔴 Difficult to audit (scattered authorization logic)

---

### Blackboard: Visibility-Driven Scheduling

```python
# Producer-controlled access (enforced at schedule time):

# Customer A's agent produces data:
agent_a = flock.agent("agent_a").identity(AgentIdentity(
    name="agent_a",
    tenant_id="customer_a"
)).consumes(Input).publishes(
    CustomerData,
    visibility=TenantVisibility(tenant_id="customer_a")  # 🔒 Tenant isolation
)

# Customer B's agent tries to consume:
agent_b = flock.agent("agent_b").identity(AgentIdentity(
    name="agent_b",
    tenant_id="customer_b"
)).consumes(CustomerData)

# 🎯 What happens:
# 1. agent_a publishes CustomerData with tenant_id="customer_a"
# 2. Orchestrator checks: agent_b.tenant_id == artifact.tenant_id?
# 3. "customer_b" != "customer_a" → agent_b is NEVER scheduled
# 4. No LLM call wasted, no authorization logic in agent code

# Enforcement at orchestrator level (orchestrator.py:699):
if not self._check_visibility(artifact, identity):
    continue  # Don't schedule agent
```

**Benefits:**
- ✅ Framework-level enforcement (no manual checks needed)
- ✅ Authorization before scheduling (no wasted LLM calls)
- ✅ Tenant isolation by construction (no cross-tenant leakage possible)
- ✅ Easy to audit (visibility declarations are self-documenting)
- ✅ Five built-in patterns (Public, Private, Labelled, Tenant, After)

**Demo script:**
1. Show two agents with different tenant IDs
2. Publish artifact with `TenantVisibility(tenant_id="customer_a")`
3. Show in dashboard: Only customer_a's agent is scheduled
4. Point out: "Customer B's agent never even sees the data. Enforced by orchestrator."
5. Query DuckDB: "Show audit trail of who accessed this data"

---

## Example 4: The Parallelism Problem - 100 Customer Reviews

**Context:** Demonstrate automatic parallelism via type-based fanout
**Use case:** Performance section, scalability benchmarks

### Graph-Based: Sequential Execution

```python
# Graph-based: Each invocation is independent
results = []
for review in customer_reviews:  # 100 reviews
    result = workflow.invoke({"review": review})  # Blocks until complete
    results.append(result)

# Total time: 100 reviews × 5 seconds = 500 seconds

# 🔥 Workaround: Manual parallelization with asyncio.gather
results = await asyncio.gather(*[
    workflow.ainvoke({"review": review})
    for review in customer_reviews
])

# This works, but:
# 🔴 Tightly coupled to graph execution model
# 🔴 Developer must remember to use gather()
# 🔴 No framework-level concurrency control
```

---

### Blackboard: Automatic Parallel Execution

```python
# Batch publish (fast - just queuing):
for review in customer_reviews:  # 100 reviews
    await flock.publish(review)  # ~1ms each (just scheduling)

# Execute all in parallel:
await flock.run_until_idle()  # All sentiment_analyzer agents run concurrently

# Total time: ~6 seconds (for 100 reviews!)

# Framework automatically:
# 1. Detects 100 Review artifacts on blackboard
# 2. Schedules 100 sentiment_analyzer tasks concurrently
# 3. Executes via asyncio task pool
# 4. Returns when all complete
```

**Performance comparison:**

| Approach | Execution Model | 100 Reviews | 1000 Reviews | Speedup |
|----------|----------------|-------------|--------------|---------|
| Graph (sequential) | Blocking invocation | 500s | 5000s | 1x |
| Graph (manual gather) | Manual parallelization | 6s | 60s | 83x |
| Blackboard (automatic) | Type-based fanout | 6s | 60s | 83x |

**Why blackboard wins:**
- ✅ Parallelism is automatic (no `gather()` needed)
- ✅ Scales to arbitrary fanout (publish 1000 reviews, all run in parallel)
- ✅ Explicit control over concurrency (`flock.agent().max_concurrency(10)`)
- ✅ Composable with other patterns (multi-type workflows run in parallel)

**Demo script:**
1. Show graph-based: Loop with `workflow.invoke()` (slow)
2. Show blackboard: Batch `publish()`, single `run_until_idle()` (fast)
3. Live timer: 100 reviews in 6 seconds
4. Show dashboard: 100 concurrent agent executions
5. Point out: "No explicit parallelization code. It emerged from subscriptions."

---

## Example 5: The Feedback Loop Problem - Iterative Refinement

**Context:** Demonstrate compositional feedback loops with safety
**Use case:** Agent interaction patterns, self-improving systems

### Graph-Based: Explicit Loop Logic

```python
def iterative_refinement(state):
    iteration = state.get("iteration", 0)

    # 🔥 Manual termination logic
    if iteration >= 10:
        return state  # Circuit breaker

    # Generate argument
    essay = refine_essay(state["essay"], state.get("feedback"))

    # Critique argument
    feedback = critique_essay(essay)

    # 🔥 Manual loop condition
    if feedback.score >= 9:
        return {"essay": essay, "done": True}

    # 🔥 Manual state accumulation
    return {
        "essay": essay,
        "feedback": feedback,
        "iteration": iteration + 1,
        # Must explicitly loop back to self
    }

# Developer must:
# 🔴 Track iteration count manually
# 🔴 Implement termination logic
# 🔴 Prevent infinite loops
# 🔴 Handle state accumulation
```

---

### Blackboard: Declarative Feedback Loop

```python
# Circuit breaker at orchestrator level:
flock = Flock(max_agent_iterations=20)

# Feedback loop emerges from subscriptions:
debater = flock.agent("debater").consumes(Topic).consumes(
    Critique,
    where=lambda c: c.score < 9  # 🎯 Declarative termination condition
).publishes(Argument)

critic = flock.agent("critic").consumes(Argument).publishes(Critique).prevent_self_trigger(True)

# 🎯 What happens:
# 1. Publish Topic → debater creates Argument v1
# 2. Argument v1 → critic creates Critique (score=6)
# 3. Critique (score=6 < 9) → debater creates Argument v2
# 4. Argument v2 → critic creates Critique (score=8)
# 5. Critique (score=8 < 9) → debater creates Argument v3
# 6. Argument v3 → critic creates Critique (score=9)
# 7. Critique (score=9 >= 9) → predicate fails, loop stops
# 8. Circuit breaker prevents runaway costs (max_agent_iterations=20)
```

**Safety mechanisms:**

1. **Prevent self-triggering:**
```python
# orchestrator.py:692-693
if agent.prevent_self_trigger and artifact.produced_by == agent.name:
    continue  # Agent won't consume its own outputs
```

2. **Circuit breaker:**
```python
# orchestrator.py:695-698
if iteration_count >= self.max_agent_iterations:
    continue  # Stop scheduling to prevent runaway LLM costs
```

3. **Declarative termination:**
```python
where=lambda c: c.score < 9  # Loop stops when condition becomes false
```

**Benefits:**
- ✅ No manual iteration tracking
- ✅ Declarative termination (self-documenting)
- ✅ Built-in safety (circuit breaker + prevent_self_trigger)
- ✅ Compositional (feedback loops emerge from subscriptions)

**Demo script:**
1. Show debate loop: Topic → Argument → Critique → Argument → ...
2. Live trace: Show iterations in dashboard (v1, v2, v3...)
3. Point out termination: "Score=9 → predicate fails → loop stops"
4. Query DuckDB: "Show iteration count per agent" (verify circuit breaker)

---

## Example 6: The Routing Problem - Content-Based Routing

**Context:** Demonstrate lambda predicates for distributed routing
**Use case:** Conditional consumption, decision trees without graphs

### Graph-Based: Central Router (God Object)

```python
# Central router needs domain knowledge of ALL types
def route_diagnosis(state):
    diagnosis = state["diagnosis"]

    # 🔥 Problem: Router has domain knowledge of diagnosis logic
    if diagnosis.severity in ["Critical", "High"]:
        return "urgent_care"
    elif diagnosis.confidence < 0.7:
        return "second_opinion"
    elif diagnosis.category == "infectious":
        return "infectious_disease_specialist"
    elif diagnosis.patient_age > 65:
        return "geriatric_specialist"
    else:
        return "standard_care"

# 🔥 Problem: Adding new routing logic requires modifying router
# 🔥 Problem: Router becomes God object with knowledge of all domains
# 🔥 Problem: Routing logic is centralized (not compositional)
```

**Pain points:**
- 🔴 Router has domain knowledge (violates separation of concerns)
- 🔴 Adding new route requires modifying central router
- 🔴 Routing logic is not self-documenting
- 🔴 Difficult to test (need full graph to test routing)

---

### Blackboard: Distributed Routing via Predicates

```python
# Each agent declares its own routing criteria:

urgent_care = flock.agent("urgent").consumes(
    Diagnosis,
    where=lambda d: d.severity in ["Critical", "High"]  # 🎯 Self-contained routing logic
)

second_opinion = flock.agent("second_opinion").consumes(
    Diagnosis,
    where=lambda d: d.confidence < 0.7
)

infectious_specialist = flock.agent("infectious_specialist").consumes(
    Diagnosis,
    where=lambda d: d.category == "infectious"
)

geriatric_specialist = flock.agent("geriatric_specialist").consumes(
    Diagnosis,
    where=lambda d: d.patient_age > 65
)

standard_care = flock.agent("standard").consumes(
    Diagnosis,
    where=lambda d: d.severity in ["Low", "Medium"] and d.confidence >= 0.7
)

# 🎯 What happens:
# 1. Publish Diagnosis(severity="Critical", confidence=0.9)
# 2. Orchestrator evaluates ALL predicates in parallel
# 3. urgent_care matches (severity="Critical")
# 4. Only urgent_care is scheduled
# 5. No central router needed!
```

**Benefits:**
- ✅ Routing logic is distributed (each agent owns its criteria)
- ✅ Adding new route is one line (no central router modification)
- ✅ Self-documenting (predicate shows what agent cares about)
- ✅ Testable in isolation (mock Diagnosis, verify predicate)
- ✅ Compositional (multiple agents can match same artifact)

**Demo script:**
1. Publish various Diagnosis artifacts with different properties
2. Show dashboard: Different agents activate based on predicates
3. Live-code adding new route:
   ```python
   pediatric_specialist.consumes(Diagnosis, where=lambda d: d.patient_age < 18)
   ```
4. Publish child diagnosis: Show pediatric_specialist automatically activates
5. Point out: "No central router modified. Logic is distributed."

---

## Example 7: The Type Safety Problem - Runtime Validation

**Context:** Demonstrate Pydantic validation vs prompt engineering
**Use case:** Reliability section, comparison to traditional LLM workflows

### Traditional: 500-Line Prompt (Hope-Based Typing)

```python
prompt = """You are an expert software engineer and bug analyst.

INSTRUCTIONS:
1. Read the bug report carefully
2. Determine severity (must be: Critical, High, Medium, Low)
3. Classify category (e.g., "performance", "security", "UI")
4. Formulate root cause hypothesis (minimum 50 characters)
5. Assign confidence score (0.0 to 1.0)

OUTPUT FORMAT:
You MUST return valid JSON:
{
  "severity": "string (Critical|High|Medium|Low)",
  "category": "string",
  "root_cause_hypothesis": "string (min 50 chars)",
  "confidence_score": "number (0.0-1.0)"
}

VALIDATION RULES:
- severity: Exactly one of: Critical, High, Medium, Low (case-sensitive)
- category: Single word or short phrase
- root_cause_hypothesis: At least 50 characters
- confidence_score: Decimal between 0.0 and 1.0

EXAMPLES:
Input: "App crashes when user clicks submit"
Output: {"severity": "Critical", ...}

IMPORTANT:
- NO explanatory text before/after JSON
- NO markdown code blocks
- NO comments
- Valid and parseable JSON
- Never return null

Now analyze: {bug_report}"""

result = llm.invoke(prompt)
data = json.loads(result.content)  # 🔥 Crashes if LLM misbehaves

# 🔥 Problems:
# 🔴 500-line prompt that LLM ignores
# 🔴 No runtime validation (garbage data reaches business logic)
# 🔴 Breaks on model updates (GPT-4 → GPT-5 changes behavior)
# 🔴 Difficult to test (how to mock LLM output?)
```

---

### Flock: Schema IS the Instruction

```python
@flock_type
class BugDiagnosis(BaseModel):
    severity: str = Field(pattern="^(Critical|High|Medium|Low)$")
    category: str = Field(description="Bug category")
    root_cause_hypothesis: str = Field(min_length=50)
    confidence_score: float = Field(ge=0.0, le=1.0)

agent.consumes(BugReport).publishes(BugDiagnosis)

# 🎯 What happens:
# 1. LLM generates output based on BugDiagnosis schema
# 2. Pydantic validates output at agent boundary
# 3. If invalid: ValidationError (full trace to source)
# 4. If valid: Type-safe BugDiagnosis object published to blackboard
# 5. Downstream agents NEVER see invalid data

# 🎯 Example validation failures:
# - severity="very bad" → REJECTED (pattern mismatch)
# - confidence_score="high" → REJECTED (not a float)
# - root_cause_hypothesis="unknown" → REJECTED (min_length=50)
# - Missing field → REJECTED (required field)
```

**Comparison:**

| Approach | Validation | Error Location | Debugging | Model Upgrade Safety |
|----------|-----------|----------------|-----------|---------------------|
| 500-line prompt | Hope | Runtime crash | "LLM misbehaved" | Breaks |
| Pydantic schema | Runtime | Agent boundary | Full trace | Survives |

**Benefits:**
- ✅ Survives model upgrades (GPT-6 will still understand schemas)
- ✅ Runtime validation prevents garbage data
- ✅ Self-documenting (schema shows exactly what agent produces)
- ✅ Testable (mock BugReport, assert BugDiagnosis schema)
- ✅ No 500-line prompt maintenance

**Demo script:**
1. Show 500-line prompt (scroll for effect)
2. Show 5-line Pydantic schema (clean, readable)
3. Intentionally inject invalid data: `severity="very bad"`
4. Show validation error with full trace
5. Point out: "Invalid data never reached blackboard. Caught at boundary."

---

## Appendix: Code Locations for Verification

**For reviewers:** All patterns are implemented and testable in Flock 0.5.0:

1. **Temporal decoupling:** `orchestrator.py:685-708` (`_schedule_artifact()`)
2. **Opportunistic parallelism:** `orchestrator.py:710-713` (`_schedule_task()`)
3. **Visibility-driven scheduling:** `orchestrator.py:699-700` (`_check_visibility()`)
4. **Conditional consumption:** `subscription.py:80-97` (`matches()` with predicates)
5. **Automatic dependency resolution:** `subscription.py:41-103` (multi-type subscriptions)
6. **Event-driven batching:** `orchestrator.py:348-357` (`run_until_idle()`)
7. **Compositional feedback loops:** `orchestrator.py:692-698` (circuit breaker + prevent_self_trigger)
8. **Type-safe communication:** `artifacts.py` + `registry.py` (Pydantic validation)
9. **Automatic lineage:** `artifacts.py` (`produced_by`, `correlation_id` fields)
10. **O(n) scaling:** `orchestrator.py:685-708` (linear agent scan)

**Example code locations:**
- Band formation (emergent chaining): `examples/05-claudes-workshop/lesson_02_band_formation.py`
- Feedback loops: `examples/05-claudes-workshop/lesson_04_debate_club.py`
- Visibility controls: `examples/05-claudes-workshop/lesson_06_secret_agents.py`
- Parallel execution: `examples/01-the-declarative-way/01_declarative_pizza.py`

**Test coverage:** 700+ tests, >75% coverage (>90% on critical paths)
