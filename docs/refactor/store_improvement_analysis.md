# store.py - In-Depth Improvement Analysis

## 🚨 Current State Assessment

**File:** `src/flock/store.py`
**Current Size:** 1,090 LOC
**Overall Maintainability:** C (8.31) ⚠️
**Average Complexity:** A (2.80)

### Critical Issues

**4 C-Rated Methods:**
1. `InMemoryBlackboardStore.summarize_artifacts` - **C (17)**
2. `SQLiteBlackboardStore.query_artifacts` - **C (12)**
3. `SQLiteBlackboardStore.summarize_artifacts` - **C (12)**
4. `_deserialize_visibility` - **C (11)**

**Problem:** Despite Phase 7 extraction, the file still has **C maintainability** due to these complex methods.

---

## 📊 Detailed Method Analysis

### 1. `_deserialize_visibility` - C (11) Complexity

**Location:** Lines 59-78 (20 LOC)
**Complexity:** C (11) - 8 return statements
**Issue:** Too many early returns and nested conditionals

**Current Structure:**
```python
def _deserialize_visibility(data: Any) -> Visibility:
    if isinstance(data, Visibility):  # return 1
        return data
    if not data:  # return 2
        return PublicVisibility()
    kind = data.get("kind") if isinstance(data, dict) else None
    if kind == "Public":  # return 3
        return PublicVisibility()
    if kind == "Private":  # return 4
        return PrivateVisibility(agents=set(data.get("agents", [])))
    if kind == "Labelled":  # return 5
        return LabelledVisibility(required_labels=set(data.get("required_labels", [])))
    if kind == "Tenant":  # return 6
        return TenantVisibility(tenant_id=data.get("tenant_id"))
    if kind == "After":  # return 7
        ttl = _parse_iso_duration(data.get("ttl"))
        then_data = data.get("then") if isinstance(data, dict) else None
        then_visibility = _deserialize_visibility(then_data) if then_data else None
        return AfterVisibility(ttl=ttl, then=then_visibility)
    return PublicVisibility()  # return 8
```

**Complexity Drivers:**
- 8 return statements (limit is 6)
- Multiple if-elif chains
- Nested conditional logic
- Used in both InMemory and SQLite stores

**Extraction Opportunity:**
- Move to `utils/visibility_utils.py`
- Use dictionary dispatch instead of if-elif chain
- Reduce to 3-4 returns maximum

**Estimated Reduction:** C (11) → **B (5-6)**

---

### 2. `InMemoryBlackboardStore.summarize_artifacts` - C (17) Complexity

**Location:** Lines 334-394 (61 LOC)
**Complexity:** C (17) - Highest complexity in file!
**Issue:** Too many responsibilities in one method

**Current Structure:**
```python
async def summarize_artifacts(self, filters: FilterConfig | None = None) -> dict[str, Any]:
    # 1. Query artifacts (complexity +2)
    filters = filters or FilterConfig()
    artifacts, total = await self.query_artifacts(...)

    # 2. Initialize 5 aggregation dicts (complexity +5)
    by_type: dict[str, int] = {}
    by_producer: dict[str, int] = {}
    by_visibility: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    earliest/latest datetime tracking

    # 3. Loop through artifacts (complexity +1)
    for artifact in artifacts:
        # Type checking (complexity +1)
        if not isinstance(artifact, Artifact):
            raise TypeError(...)

        # 4 separate aggregations (complexity +4)
        by_type[artifact.type] = by_type.get(artifact.type, 0) + 1
        by_producer[...] = ...
        by_visibility[...] = ...

        # Tag counting loop (complexity +1)
        for tag in artifact.tags:
            tag_counts[tag] = ...

        # Date range tracking (complexity +2)
        if earliest is None or artifact.created_at < earliest:
            earliest = ...
        if latest is None or artifact.created_at > latest:
            latest = ...

    # 5. Time span calculation (complexity +4)
    if earliest and latest:
        span = latest - earliest
        if span.days >= 2:  # +1
            span_label = f"{span.days} days"
        elif span.total_seconds() >= 3600:  # +1
            hours = ...
            span_label = f"{hours:.1f} hours"
        elif span.total_seconds() > 0:  # +1
            minutes = ...
            span_label = f"{minutes} minutes"
        else:
            span_label = "moments"
    else:
        span_label = "empty"

    # 6. Build result dict
    return {...}
```

**Complexity Breakdown:**
- Querying artifacts: +2
- Multiple aggregation dicts: +5
- Artifact iteration: +1
- Type checking: +1
- Aggregation updates: +4
- Tag loop: +1
- Date tracking: +2
- Time span calculation: +4
- **Total: 20 (but radon counts 17)**

**Extraction Opportunities:**

**Option A: Extract Aggregation Logic**
```
Create: storage/artifact_aggregator.py (~80 LOC)
- ArtifactAggregator class
  - aggregate_by_type()
  - aggregate_by_producer()
  - aggregate_by_visibility()
  - aggregate_tags()
  - calculate_time_span()
```

**Option B: Extract Time Span Calculation**
```
Create: utils/time_utils.py (~30 LOC)
- format_time_span(earliest, latest) -> str
```

**Option C: Both A + B (Recommended)**
- Aggregator handles all counting logic
- Time utils handles date formatting
- Main method becomes orchestration only

**Estimated Reduction:** C (17) → **B (5-7)**

---

### 3. `SQLiteBlackboardStore.query_artifacts` - C (12) Complexity

**Location:** Lines 693-784 (92 LOC)
**Complexity:** C (12)
**Issue:** Doing too much - querying + consumption embedding

**Current Structure:**
```python
async def query_artifacts(...) -> tuple[list[Artifact | ArtifactEnvelope], int]:
    # 1. Setup and count query (complexity +2)
    filters = filters or FilterConfig()
    conn = await self._get_connection()
    where_clause, params = self._build_filters(filters)
    count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"
    cursor = await conn.execute(count_query, tuple(params))
    total_row = await cursor.fetchone()
    await cursor.close()
    total = total_row["total"] if total_row else 0

    # 2. Main query with pagination logic (complexity +4)
    query = f"SELECT ... FROM artifacts {where_clause} ORDER BY ..."
    query_params: tuple[Any, ...]
    if limit <= 0:  # +1
        if offset > 0:  # +1
            query += " LIMIT -1 OFFSET ?"
            query_params = (*params, max(offset, 0))
        else:
            query_params = tuple(params)
    else:
        query += " LIMIT ? OFFSET ?"
        query_params = (*params, limit, max(offset, 0))

    cursor = await conn.execute(query, query_params)
    rows = await cursor.fetchall()
    await cursor.close()
    artifacts = [self._row_to_artifact(row) for row in rows]

    # 3. Early return if no embed_meta (complexity +1)
    if not embed_meta or not artifacts:
        return artifacts, total

    # 4. Consumption embedding logic (complexity +5)
    artifact_ids = [str(artifact.id) for artifact in artifacts]
    placeholders = ", ".join("?" for _ in artifact_ids)
    consumption_query = f"SELECT ... WHERE artifact_id IN ({placeholders}) ..."
    cursor = await conn.execute(consumption_query, artifact_ids)
    consumption_rows = await cursor.fetchall()
    await cursor.close()

    consumptions_map: dict[UUID, list[ConsumptionRecord]] = defaultdict(list)
    for row in consumption_rows:  # +1
        artifact_uuid = UUID(row["artifact_id"])
        consumptions_map[artifact_uuid].append(
            ConsumptionRecord(...)
        )

    envelopes: list[ArtifactEnvelope] = [
        ArtifactEnvelope(
            artifact=artifact,
            consumptions=consumptions_map.get(artifact.id, []),
        )
        for artifact in artifacts
    ]
    return envelopes, total
```

**Complexity Breakdown:**
- Count query: +2
- Pagination logic: +4
- Early return: +1
- Consumption embedding: +5
- **Total: 12**

**Extraction Opportunity:**
```
Create: storage/sqlite/consumption_loader.py (~60 LOC)
- SQLiteConsumptionLoader class
  - load_consumptions_for_artifacts(conn, artifact_ids)
    Returns: dict[UUID, list[ConsumptionRecord]]
```

**Benefits:**
- Main method focuses on artifact querying only
- Consumption logic tested independently
- Reusable for other query methods

**Estimated Reduction:** C (12) → **B (6-8)**

---

### 4. `SQLiteBlackboardStore.summarize_artifacts` - C (12) Complexity

**Location:** Lines 786-871 (86 LOC)
**Complexity:** C (12)
**Issue:** 6 separate SQL queries in one method

**Current Structure:**
```python
async def summarize_artifacts(...) -> dict[str, Any]:
    filters = filters or FilterConfig()
    conn = await self._get_connection()
    where_clause, params = self._build_filters(filters)
    params_tuple = tuple(params)

    # Query 1: Count
    count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"
    cursor = await conn.execute(count_query, params_tuple)
    total_row = await cursor.fetchone()
    await cursor.close()
    total = total_row["total"] if total_row else 0

    # Query 2: By Type
    by_type_query = f"SELECT canonical_type, COUNT(*) AS count FROM artifacts {where_clause} GROUP BY canonical_type"
    cursor = await conn.execute(by_type_query, params_tuple)
    by_type_rows = await cursor.fetchall()
    await cursor.close()
    by_type = {row["canonical_type"]: row["count"] for row in by_type_rows}

    # Query 3: By Producer
    by_producer_query = f"SELECT produced_by, COUNT(*) AS count FROM artifacts {where_clause} GROUP BY produced_by"
    cursor = await conn.execute(by_producer_query, params_tuple)
    by_producer_rows = await cursor.fetchall()
    await cursor.close()
    by_producer = {row["produced_by"]: row["count"] for row in by_producer_rows}

    # Query 4: By Visibility
    by_visibility_query = f"SELECT json_extract(visibility, '$.kind') AS visibility_kind, COUNT(*) AS count FROM artifacts {where_clause} GROUP BY json_extract(visibility, '$.kind')"
    cursor = await conn.execute(by_visibility_query, params_tuple)
    by_visibility_rows = await cursor.fetchall()
    await cursor.close()
    by_visibility = {(row["visibility_kind"] or "Unknown"): row["count"] for row in by_visibility_rows}

    # Query 5: Tags
    tag_query = f"SELECT json_each.value AS tag, COUNT(*) AS count FROM artifacts JOIN json_each(artifacts.tags) {where_clause} GROUP BY json_each.value"
    cursor = await conn.execute(tag_query, params_tuple)
    tag_rows = await cursor.fetchall()
    await cursor.close()
    tag_counts = {row["tag"]: row["count"] for row in tag_rows}

    # Query 6: Date Range
    range_query = f"SELECT MIN(created_at) AS earliest, MAX(created_at) AS latest FROM artifacts {where_clause}"
    cursor = await conn.execute(range_query, params_tuple)
    range_row = await cursor.fetchone()
    await cursor.close()
    earliest = range_row["earliest"] if range_row and range_row["earliest"] else None
    latest = range_row["latest"] if range_row and range_row["latest"] else None

    return {
        "total": total,
        "by_type": by_type,
        "by_producer": by_producer,
        "by_visibility": by_visibility,
        "tag_counts": tag_counts,
        "earliest_created_at": earliest,
        "latest_created_at": latest,
    }
```

**Complexity Drivers:**
- 6 separate database queries
- Repetitive cursor open/fetch/close pattern
- Each query adds to complexity

**Extraction Opportunity:**
```
Create: storage/sqlite/summary_queries.py (~120 LOC)
- SQLiteSummaryQueries class
  - get_total_count(conn, where_clause, params)
  - get_type_distribution(conn, where_clause, params)
  - get_producer_distribution(conn, where_clause, params)
  - get_visibility_distribution(conn, where_clause, params)
  - get_tag_counts(conn, where_clause, params)
  - get_date_range(conn, where_clause, params)
```

**Benefits:**
- Each query method is simple (A-rated)
- Main method becomes orchestration
- Queries testable independently
- Potential for query optimization (e.g., CTE combining queries)

**Estimated Reduction:** C (12) → **B (5-7)**

---

## 🎯 Proposed Extraction Plan

### Phase 7B: Complexity Reduction (Recommended)

**Target:** Achieve **A/B ratings** for ALL methods and **B+ maintainability** for file

### Extraction 1: Visibility Utils
**File:** `utils/visibility_utils.py` (~80 LOC)
- `parse_iso_duration(value)` - A (2)
- `deserialize_visibility(data)` - B (5)
- `_deserialize_after_visibility(data)` - A (3)

**Impact:**
- Removes C-rated function from store.py
- Reusable across codebase
- Testable in isolation

**Effort:** 1-2 hours

---

### Extraction 2: Artifact Aggregator
**File:** `storage/artifact_aggregator.py` (~100 LOC)
- `ArtifactAggregator` class
  - `aggregate_by_type(artifacts)` - A (2)
  - `aggregate_by_producer(artifacts)` - A (2)
  - `aggregate_by_visibility(artifacts)` - A (2)
  - `aggregate_tags(artifacts)` - A (3)
  - `track_date_range(artifacts)` - A (3)
  - `build_summary(...)` - A (4)

**Impact:**
- `InMemoryBlackboardStore.summarize_artifacts`: C (17) → **B (5)**
- Clean, testable aggregation logic
- Reusable for future stores

**Effort:** 2-3 hours

---

### Extraction 3: Consumption Loader
**File:** `storage/sqlite/consumption_loader.py` (~70 LOC)
- `SQLiteConsumptionLoader` class
  - `load_for_artifacts(conn, artifact_ids)` - A (4)
  - `build_consumption_map(rows)` - A (3)

**Impact:**
- `SQLiteBlackboardStore.query_artifacts`: C (12) → **B (6)**
- Cleaner query method
- Consumption logic isolated

**Effort:** 1-2 hours

---

### Extraction 4: Summary Query Builder
**File:** `storage/sqlite/summary_queries.py` (~150 LOC)
- `SQLiteSummaryQueries` class
  - `count_total(conn, where, params)` - A (2)
  - `group_by_type(conn, where, params)` - A (2)
  - `group_by_producer(conn, where, params)` - A (2)
  - `group_by_visibility(conn, where, params)` - A (2)
  - `count_tags(conn, where, params)` - A (2)
  - `get_date_range(conn, where, params)` - A (2)

**Impact:**
- `SQLiteBlackboardStore.summarize_artifacts`: C (12) → **B (6)**
- Each query testable
- Potential for optimization (single CTE query)

**Effort:** 2-3 hours

---

### Optional Extraction 5: Time Utilities
**File:** `utils/time_utils.py` (~40 LOC)
- `format_time_span(earliest, latest)` - A (4)
- Helper for human-readable time spans

**Impact:**
- Further reduces aggregator complexity
- Reusable across dashboard

**Effort:** 30 mins

---

## 📊 Expected Results

### Before Phase 7B
```
store.py: 1,090 LOC
Overall Maintainability: C (8.31)
C-rated methods: 4
  - _deserialize_visibility: C (11)
  - InMemoryBlackboardStore.summarize_artifacts: C (17)
  - SQLiteBlackboardStore.query_artifacts: C (12)
  - SQLiteBlackboardStore.summarize_artifacts: C (12)
```

### After Phase 7B (Estimated)
```
store.py: ~650 LOC (440 LOC reduction - 40%)
Overall Maintainability: B (15-20)
C-rated methods: 0
Highest complexity: B (6-8)

New Modules (All A/B-rated):
- utils/visibility_utils.py: 80 LOC, A maintainability
- storage/artifact_aggregator.py: 100 LOC, A maintainability
- storage/sqlite/consumption_loader.py: 70 LOC, A maintainability
- storage/sqlite/summary_queries.py: 150 LOC, A maintainability
- utils/time_utils.py: 40 LOC, A maintainability

Total extracted: 440 LOC into 5 focused modules
```

---

## 🎯 Metrics Targets

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| File LOC | 1,090 | ~650 | -40% |
| Maintainability | C (8.31) | B (15-20) | +120% |
| C-rated methods | 4 | 0 | -100% |
| Average complexity | A (2.80) | A (2.0) | Better |
| Highest complexity | C (17) | B (6-8) | -65% |

---

## 🧪 Testing Strategy

**New Unit Tests Required:**
1. `tests/utils/test_visibility_utils.py` - 15 tests
   - All visibility types
   - Edge cases (null, invalid)
   - ISO duration parsing

2. `tests/storage/test_artifact_aggregator.py` - 20 tests
   - Each aggregation method
   - Empty artifact lists
   - Time span formatting

3. `tests/storage/sqlite/test_consumption_loader.py` - 10 tests
   - Load consumptions
   - Empty results
   - Multiple consumers

4. `tests/storage/sqlite/test_summary_queries.py` - 12 tests
   - Each query method
   - With/without filters
   - Empty results

**Total new tests:** ~57 tests

---

## ⏱️ Effort Estimate

| Task | Effort |
|------|--------|
| Extraction 1: Visibility Utils | 1-2h |
| Extraction 2: Artifact Aggregator | 2-3h |
| Extraction 3: Consumption Loader | 1-2h |
| Extraction 4: Summary Queries | 2-3h |
| Optional: Time Utils | 0.5h |
| Unit tests (57 tests) | 4-5h |
| Integration testing | 1h |
| Documentation | 1h |
| **Total** | **12-17 hours** |

---

## 💡 Recommended Approach

### Option A: Full Phase 7B (Recommended)
**Do all 4 extractions + time utils**
- Achieves A/B ratings across board
- Best maintainability improvement
- 40% LOC reduction
- Comprehensive test coverage
- Effort: 12-17 hours

### Option B: Critical Only
**Do extractions 1, 2, 3 only**
- Fixes the worst C-rated methods
- Skip summary query extraction
- Still leaves one C-rated method
- Effort: 7-10 hours

### Option C: Quick Wins
**Do extractions 1 & 2 only**
- Fix visibility and in-memory summarize
- Leaves 2 C-rated methods in SQLite
- Partial improvement
- Effort: 4-6 hours

---

## 🚀 Next Steps

**For Review:**
1. Do you want **full cleanup** (Option A) or **partial** (B/C)?
2. Should we combine some extractions for speed?
3. Any specific concerns about the approach?
4. Want to see code samples before extraction?

**Ready to execute once approved!** 💪

---

## 📋 File Structure After Phase 7B

```
src/flock/
├── store.py (650 LOC) - Core interfaces & simple operations
├── utils/
│   ├── visibility_utils.py (80 LOC) - Visibility deserialization
│   └── time_utils.py (40 LOC) - Time span formatting
└── storage/
    ├── artifact_aggregator.py (100 LOC) - Aggregation logic
    └── sqlite/
        ├── query_builder.py (111 LOC) - Already extracted
        ├── schema_manager.py (167 LOC) - Already extracted
        ├── consumption_loader.py (70 LOC) - NEW
        └── summary_queries.py (150 LOC) - NEW

tests/
├── utils/
│   ├── test_visibility_utils.py (15 tests)
│   └── test_time_utils.py (5 tests)
└── storage/
    ├── test_artifact_aggregator.py (20 tests)
    └── sqlite/
        ├── test_consumption_loader.py (10 tests)
        └── test_summary_queries.py (12 tests)
```

**Total:**
- 5 new focused modules
- 62 new unit tests
- Zero C-rated methods
- B maintainability overall
