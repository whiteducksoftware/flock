# Flock Examples Structure: Visual Guide

## Directory Tree with Status

```
examples/
│
├── 01-the-declarative-way/          ✅ COMPLETE - Foundation (30 min)
│   ├── 01_declarative_pizza.py      [153 lines] ⭐    (5 min)  → Single agent basics
│   ├── 02_input_and_output.py       [250 lines] ⭐⭐  (10 min) → Complex nested types
│   ├── 03_mcp_and_tools.py          [321 lines] ⭐⭐⭐ (15 min) → Tools & MCP
│   └── README.md                    [178 lines] Philosophy & guide
│
├── 02-the-blackboard/               🚧 PLANNED - Multi-agent patterns
│   └── README.md                    Placeholder (promises 3 examples)
│       ├── 01_parallel_execution.py     [NOT CREATED]
│       ├── 02_sequential_chaining.py    [NOT CREATED]
│       └── 03_mixed_workflow.py         [NOT CREATED]
│
├── 03-the-dashboard/                🚧 PARTIAL - Real-time visualization
│   ├── 01_declarative_pizza.py      [COPY of 01-the-declarative-way/01]
│   ├── 02-dashboard-edge-cases.py   [96 lines] Conditional consumption + virtual edges
│   ├── 03-scale-test-100-agents.py  [?? lines] Stress testing
│   └── README.md                    Placeholder (claims examples don't exist yet)
│
├── 04-the-api/                      🚧 PLANNED - REST integration
│   └── README.md                    Placeholder (promises 3 examples)
│       ├── 01_fastapi_integration.py    [NOT CREATED]
│       ├── 02_webhook_consumer.py       [NOT CREATED]
│       └── 03_api_client.py             [NOT CREATED]
│
├── 05-claudes-workshop/             ✅ COMPLETE - Masterclass (125 min)
│   ├── lesson_01_code_detective.py  [301 lines] ⭐    (10 min) → Single-agent transform
│   ├── lesson_02_band_formation.py  [404 lines] ⭐⭐  (15 min) → Agent chaining
│   ├── lesson_03_web_detective.py   [449 lines] ⭐⭐⭐ (20 min) → MCP & Playwright
│   ├── lesson_04_debate_club.py     [462 lines] ⭐⭐⭐ (20 min) → Feedback loops
│   ├── lesson_05_tracing_detective.py [558 lines] ⭐⭐⭐ (20 min) → Distributed tracing
│   ├── lesson_06_secret_agents.py   [495 lines] ⭐⭐⭐⭐ (25 min) → Visibility controls
│   ├── lesson_07_news_agency.py     [556 lines] ⭐⭐⭐ (20 min) → Parallel processing
│   └── README.md                    [209 lines] Course structure & tips
│
├── 06-readme/                       ✅ COMPLETE - Quick reference
│   └── 01-BugDiagnosis.py           [84 lines] Simplified lesson_01
│
└── 07-notebooks/                    ✅ PARTIAL - Interactive format
    ├── Untitled-1.ipynb             [1 cell] Bug diagnosis in Jupyter
    └── .flock/                      Trace storage directory
```

---

## Learning Path Flowchart

```
START
  │
  ├─→ 5 MINUTES: Quick Start
  │   └─→ 06-readme/01-BugDiagnosis.py (simplified)
  │       └─→ "Aha! Schemas replace prompts"
  │
  ├─→ 30 MINUTES: Foundation
  │   └─→ 01-the-declarative-way/
  │       ├─→ 01: Pizza (declarative basics)
  │       ├─→ 02: Movies (complex types)
  │       └─→ 03: Web Research (tools & MCP)
  │           └─→ "Ready for production patterns"
  │
  └─→ 2+ HOURS: Mastery
      └─→ 05-claudes-workshop/
          │
          ├─→ BEGINNER (25 min)
          │   ├─→ Lesson 01: Code Detective (single agent)
          │   └─→ Lesson 02: Band Formation (chaining)
          │
          ├─→ INTERMEDIATE (60 min)
          │   ├─→ Lesson 03: Web Detective (MCP tools)
          │   ├─→ Lesson 04: Debate Club (feedback loops)
          │   └─→ Lesson 07: News Agency (parallel processing)
          │
          └─→ ADVANCED (45 min)
              ├─→ Lesson 05: Tracing Detective (observability)
              └─→ Lesson 06: Secret Agents (security)
                  └─→ "Production ready! 🎉"

OPTIONAL BRANCHES
  ├─→ 03-the-dashboard/ (visualization)
  ├─→ 07-notebooks/ (interactive Jupyter)
  └─→ BLOCKED: 02-blackboard, 04-api (not yet created)
```

---

## Feature Coverage Heatmap

```
Legend: ████ High (70-100%)  ███░ Medium (30-70%)  ██░░ Low (10-30%)  █░░░ Minimal (<10%)  ░░░░ None (0%)

CORE API
  @flock_type                    ████████████ 100%  (all examples)
  .consumes()                    ████████████ 100%  (all examples)
  .publishes()                   ████████████ 100%  (all examples)
  .description()                 ██████████░░  90%  (most examples)

AGENT BUILDER
  .with_tools()                  ██░░░░░░░░░░  20%  (01-03, 05-03)
  .with_mcps()                   ██░░░░░░░░░░  20%  (01-03, 05-03)
  .labels()                      █░░░░░░░░░░░  15%  (05-06 only)
  .prevent_self_trigger()        █░░░░░░░░░░░  15%  (05-04 implied)
  .with_utilities()              ░░░░░░░░░░░░   0%  (none)
  .with_engines()                ░░░░░░░░░░░░   0%  (none)
  .best_of()                     ░░░░░░░░░░░░   0%  (none)
  .max_concurrency()             ░░░░░░░░░░░░   0%  (none)
  .calls()                       ░░░░░░░░░░░░   0%  (none)
  .tenant()                      ░░░░░░░░░░░░   0%  (none)

CONSUMPTION PATTERNS
  where= (predicates)            ████░░░░░░░░  40%  (03-02, 05-03, 05-04)
  batch= (BatchSpec)             █░░░░░░░░░░░  10%  (README only)
  join= (JoinSpec)               █░░░░░░░░░░░  10%  (README only)
  text= (TextPredicate)          ░░░░░░░░░░░░   0%  (none)
  from_agents=                   ░░░░░░░░░░░░   0%  (none)
  channels=                      ░░░░░░░░░░░░   0%  (none)
  delivery= modes                ░░░░░░░░░░░░   0%  (none)
  priority=                      ░░░░░░░░░░░░   0%  (none)

VISIBILITY CONTROLS
  PublicVisibility               █░░░░░░░░░░░  15%  (05-06 only)
  PrivateVisibility              █░░░░░░░░░░░  15%  (05-06 only)
  LabelledVisibility             █░░░░░░░░░░░  15%  (05-06 only)
  TenantVisibility               ░░░░░░░░░░░░   0%  (none)
  AfterVisibility                █░░░░░░░░░░░  15%  (05-06 only)

ORCHESTRATION
  flock.publish()                ████████████ 100%  (all examples)
  flock.run_until_idle()         ████████████ 100%  (all examples)
  flock.store.get_by_type()      ██████░░░░░░  50%  (01-02, 05-01, etc.)
  flock.serve(dashboard=)        ██░░░░░░░░░░  20%  (03-02)
  flock.add_mcp()                ██░░░░░░░░░░  20%  (01-03, 05-03)
  traced_run()                   █░░░░░░░░░░░  15%  (05-05)
```

---

## Complexity Progression Grid

```
                   ⭐             ⭐⭐            ⭐⭐⭐           ⭐⭐⭐⭐
                Beginner      Intermediate    Advanced      Expert
                ─────────────────────────────────────────────────────
Agent Count     1 agent       2-3 agents      3-5 agents    8+ agents

Examples        01-01         01-02           01-03         05-06
                05-01         05-02           05-03
                06-01                         05-04
                                              05-05
                                              05-07

Patterns        Transform     Sequential      Feedback      Security
                              chain           loops         Multi-tenant

Tools           None          @flock_tool     MCP           Multiple
                                              integration   MCPs

Time            5-10 min      15 min          20 min        25 min

Output          Console       Get from        Tracing       Full
                logs          store           analysis      observability
```

---

## Pattern → Example Mapping

```
TRANSFORMATION PATTERNS
  Single-Agent Transform
    ├─→ 01-the-declarative-way/01_declarative_pizza.py
    ├─→ 05-claudes-workshop/lesson_01_code_detective.py
    └─→ 06-readme/01-BugDiagnosis.py

  Complex Nested Types
    ├─→ 01-the-declarative-way/02_input_and_output.py
    └─→ Multiple workshop lessons (all use nested types)

WORKFLOW PATTERNS
  Sequential Pipeline (A → B → C)
    └─→ 05-claudes-workshop/lesson_02_band_formation.py
        (Concept → Lineup → Album → Marketing)

  Parallel-Then-Join (A,B → C)
    └─→ README.md quick start example
        (BugAnalysis, SecurityAnalysis → FinalReview)

  Conditional Routing (filter by content)
    ├─→ 03-the-dashboard/02-dashboard-edge-cases.py
    ├─→ 05-claudes-workshop/lesson_03_web_detective.py
    └─→ 05-claudes-workshop/lesson_04_debate_club.py

  Feedback Loops (A ⇄ B with safety)
    └─→ 05-claudes-workshop/lesson_04_debate_club.py
        (Debater ⇄ Critic until score >= 9)

  Fan-Out (1 → N parallel)
    └─→ 05-claudes-workshop/lesson_07_news_agency.py
        (Breaking news → 8 specialized analysts)

INTEGRATION PATTERNS
  Custom Python Tools
    ├─→ 01-the-declarative-way/03_mcp_and_tools.py
    └─→ 05-claudes-workshop/lesson_03_web_detective.py

  MCP External Services
    ├─→ 01-the-declarative-way/03_mcp_and_tools.py (DuckDuckGo, website reader)
    └─→ 05-claudes-workshop/lesson_03_web_detective.py (Playwright)

OBSERVABILITY PATTERNS
  Distributed Tracing
    └─→ 05-claudes-workshop/lesson_05_tracing_detective.py
        (DuckDB queries, trace analysis)

  Dashboard Visualization
    ├─→ 03-the-dashboard/02-dashboard-edge-cases.py
    └─→ Multiple lessons mention dashboard=True

SECURITY PATTERNS
  Visibility Controls
    └─→ 05-claudes-workshop/lesson_06_secret_agents.py
        (5 visibility types: Public, Private, Labelled, Tenant, After)
```

---

## Content Distribution Analysis

```
DOCUMENTATION DENSITY (Comments as % of File)
  High (50%+):    05-claudes-workshop/ (all lessons)
  Medium (30-50%): 01-the-declarative-way/ (all 3)
  Low (10-30%):   03-the-dashboard/02-*
  Minimal (<10%): 06-readme/01-* (intentionally stripped)

EDUCATIONAL ELEMENTS PER FILE
  ✓ Header docstring with objectives       → All 05-claudes-workshop/ + 01-*
  ✓ Section dividers (unicode boxes)       → All 05-claudes-workshop/ + 01-*
  ✓ Inline "KEY INSIGHT" callouts          → All 05-claudes-workshop/
  ✓ Footer "What you learned" summary      → All 05-claudes-workshop/ + 01-*
  ✓ "Try this" challenge suggestions       → 01-the-declarative-way/ README
  ✓ Comparison with alternative approaches → Multiple lessons

EMOJI USAGE (for visual signaling)
  🎯  Learning objectives / key concepts     → 27 occurrences
  🔥  Critical insights / "aha moments"      → 31 occurrences
  💡  Tips / pro techniques                  → 19 occurrences
  ✅  Best practices / validation            → 44 occurrences
  🚧  Work in progress / incomplete          → 4 occurrences
  ⭐  Difficulty stars (1-4)                 → All lessons
  🎬  Scenario descriptions                  → All lessons
  ⏱️   Time estimates                         → All lessons
```

---

## Gap Analysis: What's Missing

```
PLACEHOLDER CATEGORIES (Docs exist, examples don't)
  02-the-blackboard/
    ├─ README promises: 01_parallel_execution.py
    ├─               └─ 02_sequential_chaining.py
    └─               └─ 03_mixed_workflow.py
    └─→ Impact: Users can't practice blackboard patterns independently

  04-the-api/
    ├─ README promises: 01_fastapi_integration.py
    ├─               └─ 02_webhook_consumer.py
    └─               └─ 03_api_client.py
    └─→ Impact: REST API integration undocumented

  03-the-dashboard/
    ├─ Examples exist but README is placeholder
    └─→ Impact: Dashboard features not explained

DOCUMENTED FEATURES WITHOUT EXAMPLES
  ├─ Batch processing (BatchSpec)          → Mentioned in README only
  ├─ Join operations (JoinSpec)            → Mentioned in README only
  ├─ Text predicates                       → No examples at all
  ├─ Multi-tenancy (TenantVisibility)      → No examples at all
  ├─ Performance tuning (best_of, max_concurrency) → No examples
  └─ Custom utilities/engines              → No examples

MISSING REFERENCE MATERIALS
  ├─ API reference docs                    → Needs extraction from source
  ├─ Pattern cookbook                      → Could extract from examples
  ├─ Troubleshooting guide                 → No systematic guide exists
  └─ Quick reference cheat sheet           → No one-pager exists
```

---

## Recommended Doc Structure (Based on Examples)

```
docs/
│
├── getting-started/          [Extract from 01-the-declarative-way/]
│   ├── installation.md
│   ├── your-first-agent.md  ← 01_declarative_pizza.py
│   ├── complex-types.md     ← 02_input_and_output.py
│   └── adding-tools.md      ← 03_mcp_and_tools.py
│
├── tutorials/                [Extract from 05-claudes-workshop/]
│   ├── beginner/
│   │   ├── single-agent.md   ← lesson_01
│   │   └── chaining.md       ← lesson_02
│   ├── intermediate/
│   │   ├── web-tools.md      ← lesson_03
│   │   ├── feedback.md       ← lesson_04
│   │   └── parallel.md       ← lesson_07
│   └── advanced/
│       ├── tracing.md        ← lesson_05
│       └── security.md       ← lesson_06
│
├── guides/                   [NEW: Thematic deep-dives]
│   ├── blackboard-architecture.md
│   ├── conditional-consumption.md
│   ├── mcp-integration.md
│   ├── dashboard.md
│   └── tracing.md
│
└── reference/               [Extract from code + examples]
    ├── api/
    │   ├── agent-builder.md
    │   ├── orchestrator.md
    │   └── visibility.md
    ├── patterns/
    │   └── [6 pattern types].md
    └── cookbook/
        └── common-recipes.md

Status: Only examples exist, docs need creation
Priority: Extract from 01-* and 05-* first (highest ROI)
```

---

## Usage Statistics (Approximate)

```
Total Example Files:           14 Python + 8 READMEs = 22 files
Complete Examples:             11 Python (79%)
Placeholder READMEs:           4 (50% of categories)

Lines of Code (with comments): ~3,900 lines
  ├─ 01-the-declarative-way:   724 lines (19%)
  ├─ 05-claudes-workshop:      3,225 lines (83%)
  ├─ 03-the-dashboard:         ~250 lines (6%)
  └─ Others:                   ~100 lines (3%)

Average Example Length:        279 lines
Average Comment Density:       45%
Most Commented:                05-claudes-workshop lessons (50%+)
Least Commented:               06-readme (minimal by design)

Time Investment to Complete:
  ├─ Quick start:              5-20 minutes
  ├─ Foundation:               30-60 minutes
  ├─ Intermediate:             2 hours
  └─ Advanced:                 3+ hours total
```

---

## Next Actions Priority Matrix

```
                    HIGH IMPACT
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    │  1. Extract docs  │  2. Fix placeholders │
 L  │  from 05-* lessons│  (02-* and 04-*)   │
 O  │                   │                   │
 W  ├───────────────────┼───────────────────┤
    │                   │                   │
 E  │  4. Create        │  3. Document      │
 F  │  cookbook recipes │  agent builder API│
 F  │                   │                   │
 O  └───────────────────┴───────────────────┘
 R                 LOW EFFORT
 T

Legend:
  1. High impact, low effort → Do first
  2. High impact, high effort → Plan carefully
  3. Low impact, low effort → Quick wins
  4. Low impact, high effort → Defer or skip
```

---

**Visual Guide Complete**
See `examples-analysis.md` for full details
See `examples-quick-reference.md` for fast lookups
