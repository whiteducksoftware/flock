# Multi-Artifact Publishing Examples

**Real-world scenarios showing `.publishes()` fan-out in action**

---

## Example 1: Research Task Generation (Classic Fan-Out)

**Scenario**: Generate 4 research tasks for parallel execution

### Agent Definitions

```python
from pydantic import BaseModel, Field
from flock import Flock, flock_type
from datetime import datetime

@flock_type
class SpecifyRequest(BaseModel):
    feature_description: str
    requester: str

@flock_type
class SpecMetadata(BaseModel):
    spec_id: str
    feature_description: str
    created_at: datetime

@flock_type
class ResearchTask(BaseModel):
    task_id: str
    spec_id: str
    research_type: str  # "market" | "technical" | "security" | "ux"
    focus_area: str

@flock_type
class ResearchFindings(BaseModel):
    task_id: str
    spec_id: str
    findings: str
    sources: list[str]

# Initialize flock
flock = Flock()

# Agent 1: Create spec metadata
spec_initializer = (
    flock.agent("spec_initializer")
    .description(
        "Creates specification metadata with unique ID and timestamp. "
        "Extracts key details from the feature description."
    )
    .consumes(SpecifyRequest)
    .publishes(SpecMetadata)
)

# Agent 2: Generate 4 research tasks (FAN-OUT!)
task_generator = (
    flock.agent("task_generator")
    .description(
        "Generates 4 research tasks for parallel execution:\n"
        "1. Market research (competitors, market fit)\n"
        "2. Technical research (feasibility, architecture)\n"
        "3. Security research (vulnerabilities, compliance)\n"
        "4. UX research (user needs, usability)\n\n"
        "Return 4 ResearchTask objects using EvalResult.from_objects()."
    )
    .consumes(SpecMetadata)
    .publishes(ResearchTask, fan_out=4)  # ← Magic happens here!
)

# Agents 3-6: Research specialists (run in parallel!)
market_researcher = (
    flock.agent("market_researcher")
    .description("Analyzes market landscape, competitors, and market fit.")
    .consumes(ResearchTask, where=lambda t: t.research_type == "market")
    .with_mcps({"search_web": ["search"], "read_website": ["read"]})
    .publishes(ResearchFindings)
)

technical_researcher = (
    flock.agent("technical_researcher")
    .description("Assesses technical feasibility and proposes architecture.")
    .consumes(ResearchTask, where=lambda t: t.research_type == "technical")
    .with_mcps({"filesystem": ["read"], "search_web": ["search"]})
    .publishes(ResearchFindings)
)

security_researcher = (
    flock.agent("security_researcher")
    .description("Identifies security risks and compliance requirements.")
    .consumes(ResearchTask, where=lambda t: t.research_type == "security")
    .with_mcps({"search_web": ["search"]})
    .publishes(ResearchFindings)
)

ux_researcher = (
    flock.agent("ux_researcher")
    .description("Studies user needs, pain points, and usability considerations.")
    .consumes(ResearchTask, where=lambda t: t.research_type == "ux")
    .with_mcps({"search_web": ["search"]})
    .publishes(ResearchFindings)
)
```

### What Happens (Emergent Flow)

```
User publishes: SpecifyRequest(feature_description="Add OAuth 2.0 login")
                    ↓
spec_initializer reacts → publishes SpecMetadata(spec_id="S001", ...)
                    ↓
task_generator reacts → publishes 4 ResearchTask artifacts:
                    ├─ ResearchTask(research_type="market", ...)
                    ├─ ResearchTask(research_type="technical", ...)
                    ├─ ResearchTask(research_type="security", ...)
                    └─ ResearchTask(research_type="ux", ...)
                    ↓
                4 specialists react IN PARALLEL:
                    ├─ market_researcher → ResearchFindings (market)
                    ├─ technical_researcher → ResearchFindings (technical)
                    ├─ security_researcher → ResearchFindings (security)
                    └─ ux_researcher → ResearchFindings (ux)
```

**Key Insight**: ONE publish by user → 4 parallel executions! Pure emergence! 🎉

---

## Example 2: Test Case Generation (Variable Count)

**Scenario**: Generate multiple test cases from specification

### Agent Definitions

```python
@flock_type
class TestSpecification(BaseModel):
    spec_id: str
    functionality: str
    requirements: list[str]

@flock_type
class TestCase(BaseModel):
    test_id: str
    spec_id: str
    test_type: str  # "happy_path" | "edge_case" | "error_case"
    description: str
    expected_behavior: str

@flock_type
class TestResult(BaseModel):
    test_id: str
    passed: bool
    execution_time_ms: int
    error_message: str | None = None

# Generate 10 test cases
test_generator = (
    flock.agent("test_generator")
    .description(
        "Generates 10 comprehensive test cases:\n"
        "- 4 happy path tests\n"
        "- 4 edge case tests\n"
        "- 2 error handling tests\n\n"
        "Each test should have clear expected behavior and validation criteria."
    )
    .consumes(TestSpecification)
    .publishes(TestCase, fan_out=10)
)

# Execute tests in parallel (with concurrency limit)
test_executor = (
    flock.agent("test_executor")
    .description("Executes test case and reports results.")
    .consumes(TestCase)
    .publishes(TestResult)
    .max_concurrency(5)  # 5 tests run in parallel
)
```

### What Happens

```
User publishes: TestSpecification(functionality="User registration", ...)
                    ↓
test_generator reacts → publishes 10 TestCase artifacts
                    ↓
test_executor processes 10 tests:
    Wave 1: Tests 1-5 execute in parallel
    Wave 2: Tests 6-10 execute in parallel
                    ↓
10 TestResult artifacts published
```

**Performance Win**: 10 tests / 5 concurrent = 2 waves (vs 10 sequential!)

---

## Example 3: Data Chunking for Parallel Processing

**Scenario**: Split large dataset into chunks for distributed processing

### Agent Definitions

```python
@flock_type
class Dataset(BaseModel):
    dataset_id: str
    total_records: int
    source_file: str

@flock_type
class DataChunk(BaseModel):
    chunk_id: str
    dataset_id: str
    chunk_number: int
    total_chunks: int
    record_range: tuple[int, int]  # (start, end)

@flock_type
class ProcessedChunk(BaseModel):
    chunk_id: str
    dataset_id: str
    chunk_number: int
    records_processed: int
    processing_time_ms: int

@flock_type
class FinalResult(BaseModel):
    dataset_id: str
    total_records: int
    total_time_ms: int
    chunks_processed: int

# Split into 8 chunks
chunk_creator = (
    flock.agent("chunk_creator")
    .description(
        "Splits dataset into 8 equal chunks for parallel processing. "
        "Calculate record ranges based on total_records / 8. "
        "Example: 1600 records → 8 chunks of 200 records each."
    )
    .consumes(Dataset)
    .publishes(DataChunk, fan_out=8)
)

# Process chunks in parallel
chunk_processor = (
    flock.agent("chunk_processor")
    .description("Processes a single data chunk: validate, transform, and aggregate.")
    .consumes(DataChunk)
    .with_mcps({"filesystem": ["read", "write"]})
    .publishes(ProcessedChunk)
    .max_concurrency(8)  # All 8 chunks can run simultaneously!
)

# Aggregate results (FAN-IN!)
result_aggregator = (
    flock.agent("result_aggregator")
    .description(
        "Waits for ALL 8 chunks to complete, then aggregates results. "
        "Sum records_processed and processing_time_ms across all chunks."
    )
    .consumes(
        ProcessedChunk,
        join=JoinSpec(
            by=lambda c: c.dataset_id,
            timeout=timedelta(minutes=30)
        )
    )
    .publishes(FinalResult)
)
```

### What Happens

```
User publishes: Dataset(total_records=1600, ...)
                    ↓
chunk_creator → publishes 8 DataChunk artifacts
                    ├─ DataChunk(chunk_number=1, record_range=(0, 200))
                    ├─ DataChunk(chunk_number=2, record_range=(200, 400))
                    ├─ ... 6 more chunks
                    └─ DataChunk(chunk_number=8, record_range=(1400, 1600))
                    ↓
chunk_processor (8 parallel executions!) → 8 ProcessedChunk artifacts
                    ↓
result_aggregator (JoinSpec waits for all 8) → FinalResult
```

**Speedup**: If each chunk takes 5 minutes:
- Sequential: 8 × 5 = 40 minutes
- Parallel: max(5, 5, 5, 5, 5, 5, 5, 5) = 5 minutes
- **8x faster!** ⚡

---

## Example 4: Workflow Initialization (Mixed Types)

**Scenario**: One agent sets up entire workflow state

### Agent Definitions

```python
@flock_type
class WorkflowRequest(BaseModel):
    workflow_id: str
    workflow_type: str
    requester: str

@flock_type
class WorkflowMetadata(BaseModel):
    workflow_id: str
    status: str
    created_at: datetime
    estimated_duration_min: int

@flock_type
class AuditLog(BaseModel):
    log_id: str
    workflow_id: str
    event_type: str
    timestamp: datetime

@flock_type
class Notification(BaseModel):
    notification_id: str
    recipient: str
    message: str
    channel: str  # "email" | "slack" | "dashboard"

# Initialize with 3 different artifact types!
workflow_initializer = (
    flock.agent("workflow_initializer")
    .description(
        "Initializes workflow by creating:\n"
        "1. WorkflowMetadata (status='pending', duration estimate)\n"
        "2. AuditLog (event_type='workflow_started')\n"
        "3. Notification (to requester via email)\n\n"
        "Return all 3 using EvalResult.from_objects()."
    )
    .consumes(WorkflowRequest)
    .publishes(WorkflowMetadata, AuditLog, Notification)  # 3 different types!
)

# Different agents react to each
progress_tracker = (
    flock.agent("progress_tracker")
    .description("Tracks workflow progress and updates status.")
    .consumes(WorkflowMetadata)
    .publishes(...)
)

audit_logger = (
    flock.agent("audit_logger")
    .description("Writes audit logs to persistent storage.")
    .consumes(AuditLog)
    .with_mcps({"filesystem": ["write"]})
    .publishes(...)
)

notifier = (
    flock.agent("notifier")
    .description("Sends notifications via configured channel.")
    .consumes(Notification)
    .publishes(...)
)
```

### What Happens

```
User publishes: WorkflowRequest(workflow_id="WF-123", ...)
                    ↓
workflow_initializer → publishes 3 artifacts:
                    ├─ WorkflowMetadata(status="pending", ...)
                    ├─ AuditLog(event_type="workflow_started", ...)
                    └─ Notification(message="Workflow started", ...)
                    ↓
                3 different agents react:
                    ├─ progress_tracker
                    ├─ audit_logger
                    └─ notifier
```

**Key Insight**: One agent can bootstrap entire workflow with different artifact types!

---

## Example 5: Incremental Batch Processing

**Scenario**: Process items in batches with controlled parallelism

### Agent Definitions

```python
@flock_type
class BatchRequest(BaseModel):
    batch_id: str
    total_items: int

@flock_type
class BatchJob(BaseModel):
    job_id: str
    batch_id: str
    batch_number: int

@flock_type
class BatchComplete(BaseModel):
    job_id: str
    batch_id: str
    items_processed: int

# Create 5 batch jobs
batch_creator = (
    flock.agent("batch_creator")
    .description("Creates 5 batch jobs for incremental processing.")
    .consumes(BatchRequest)
    .publishes(BatchJob, fan_out=5)
)

# Process with rate limiting
batch_processor = (
    flock.agent("batch_processor")
    .description("Processes one batch (rate-limited to 2 concurrent).")
    .consumes(BatchJob)
    .publishes(BatchComplete)
    .max_concurrency(2)  # Only 2 batches run at once (rate limiting!)
)
```

### What Happens

```
User publishes: BatchRequest(total_items=500)
                    ↓
batch_creator → 5 BatchJob artifacts
                    ↓
batch_processor (max 2 concurrent):
    Wave 1: Jobs 1-2 process (parallel)
    Wave 2: Jobs 3-4 process (parallel)
    Wave 3: Job 5 processes (alone)
                    ↓
5 BatchComplete artifacts
```

**Use Case**: Rate-limited API calls, database batch inserts, etc.

---

## Example 6: Multi-Stage Pipeline (Realistic Complexity)

**Scenario**: Complete analysis pipeline with fan-out at multiple stages

### Agent Definitions

```python
@flock_type
class AnalysisRequest(BaseModel):
    project_name: str
    codebase_path: str

@flock_type
class AnalysisTask(BaseModel):
    task_id: str
    analysis_type: str  # "structure" | "dependencies" | "quality" | "security"
    target_path: str

@flock_type
class AnalysisResult(BaseModel):
    task_id: str
    analysis_type: str
    findings: list[str]
    score: int  # 0-100

@flock_type
class DetailedIssue(BaseModel):
    issue_id: str
    analysis_task_id: str
    severity: str  # "critical" | "high" | "medium" | "low"
    description: str
    fix_suggestion: str

@flock_type
class FinalReport(BaseModel):
    project_name: str
    total_score: int
    critical_issues: int
    recommendations: list[str]

# Stage 1: Create 4 analysis tasks
task_creator = (
    flock.agent("task_creator")
    .consumes(AnalysisRequest)
    .publishes(AnalysisTask, fan_out=4)
)

# Stage 2: 4 analyzers run in parallel
structure_analyzer = (
    flock.agent("structure_analyzer")
    .consumes(AnalysisTask, where=lambda t: t.analysis_type == "structure")
    .publishes(AnalysisResult)
)

dependency_analyzer = (
    flock.agent("dependency_analyzer")
    .consumes(AnalysisTask, where=lambda t: t.analysis_type == "dependencies")
    .publishes(AnalysisResult)
)

quality_analyzer = (
    flock.agent("quality_analyzer")
    .consumes(AnalysisTask, where=lambda t: t.analysis_type == "quality")
    .publishes(AnalysisResult)
)

security_analyzer = (
    flock.agent("security_analyzer")
    .consumes(AnalysisTask, where=lambda t: t.analysis_type == "security")
    .publishes(AnalysisResult)
)

# Stage 3: Each result spawns multiple detailed issues (FAN-OUT AGAIN!)
issue_extractor = (
    flock.agent("issue_extractor")
    .description(
        "Extracts 3-5 detailed issues from analysis results. "
        "Generate one DetailedIssue for each significant finding."
    )
    .consumes(AnalysisResult)
    .publishes(DetailedIssue, fan_out=5)  # Variable: 3-5 issues per result
)

# Stage 4: Aggregate everything (FAN-IN!)
report_generator = (
    flock.agent("report_generator")
    .description("Waits for ALL issues, then generates final report.")
    .consumes(
        DetailedIssue,
        join=JoinSpec(
            by=lambda i: i.issue_id.split("-")[0],  # Group by project
            timeout=timedelta(minutes=15)
        )
    )
    .publishes(FinalReport)
)
```

### What Happens

```
User publishes: AnalysisRequest(project_name="flock")
                    ↓
task_creator → 4 AnalysisTask artifacts
                    ↓
4 analyzers (parallel) → 4 AnalysisResult artifacts
                    ↓
issue_extractor (4 times) → 4 × 5 = 20 DetailedIssue artifacts
                    ↓
report_generator (waits for all 20) → FinalReport
```

**Complexity**:
- 1 request → 4 tasks (fan-out)
- 4 tasks → 4 results (parallel)
- 4 results → 20 issues (fan-out again)
- 20 issues → 1 report (fan-in)

**Total agents triggered**: 1 + 1 + 4 + 4 + 1 = 11 agents from ONE publish!

---

## Example 7: Dynamic Fan-Out (LLM Decides Count)

**Future Enhancement**: Let LLM decide how many artifacts to create

### Proposed Syntax

```python
dynamic_task_creator = (
    flock.agent("dynamic_task_creator")
    .description(
        "Analyzes the request and determines optimal number of tasks. "
        "Small features: 2-3 tasks. Large features: 5-10 tasks. "
        "Generate as many ResearchTask objects as needed."
    )
    .consumes(FeatureRequest)
    .publishes(ResearchTask, fan_out="*")  # ← LLM decides!
)
```

**Implementation Note**: Would require:
1. `count: int | Literal["*"]` in AgentOutput
2. Skip count validation when `count == "*"`
3. Accept whatever LLM generates (1-100 artifacts)

**Use Cases**:
- Variable-sized batches
- Adaptive chunking
- Context-dependent task creation

---

## Summary: When to Use Each Pattern

| Pattern | Syntax | Use Case |
|---------|--------|----------|
| **Fixed fan-out** | `.publishes(A, fan_out=4)` | Known count (4 research tasks) |
| **Multiple same type** | `.publishes(A, A, A)` | Small fixed count (explicit) |
| **Mixed types** | `.publishes(A, B, C)` | Different artifacts at once |
| **Variable count** | `.publishes(A, fan_out=10)` | Larger counts (10 test cases) |
| **Dynamic (future)** | `.publishes(A, fan_out="*")` | LLM decides count |

---

## Key Takeaways

1. **Fan-out enables parallel execution** → massive speedups
2. **Symmetry with `.consumes()`** → intuitive API
3. **Explicit count** → clear intent, no surprises
4. **Mixed types** → complex initialization in one agent
5. **JoinSpec for fan-in** → wait for all parallel results
6. **max_concurrency** → control parallelism level

**This pattern unlocks TRUE emergent orchestration!** 🚀
