# 08-semantic: Semantic Subscriptions Examples

This directory contains examples demonstrating Flock's semantic subscription features, which enable intelligent agent routing and context-aware processing based on **meaning** rather than just keywords.

## 📚 Prerequisites

Install the semantic extras:
```bash
uv add flock-core[semantic]
# or
pip install flock-core[semantic]
```

This installs `sentence-transformers` with the `all-MiniLM-L6-v2` model (~90MB).

## 📖 Examples

### 01_intelligent_ticket_routing.py
**Smart ticket routing based on semantic similarity**

Demonstrates how support tickets automatically route to specialized teams (Security, Billing, Tech Support) based on the *meaning* of their content, not just keywords.

**Key Concepts:**
- Semantic semantic matching (`semantic_match="security vulnerability"`)
- Multi-agent routing patterns
- Automatic team assignment

**Run:**
```bash
uv run examples/08-semantic/01_intelligent_ticket_routing.py
```

**What You'll See:**
- Security issues → Security Team
- Billing issues → Billing Team
- Technical problems → Tech Support
- General questions → General Support

All routing happens automatically based on semantic similarity!

---

### 02_multi_criteria_filtering.py
**Advanced semantic filtering with multiple criteria**

Demonstrates sophisticated filtering combining:
- Multiple semantic predicates (AND logic)
- Field-specific matching
- Custom similarity thresholds
- Structural filters (where clauses)

**Key Concepts:**
- Multiple semantic matching: `text=["topic1", "topic2"]` (both must match)
- Field extraction: `text={"field": "abstract", "query": "..."}`
- Custom thresholds: `text={"threshold": 0.7}` (0.3=loose, 0.7=strict)
- Hybrid filtering: semantic + structural

**Run:**
```bash
uv run examples/08-semantic/02_multi_criteria_filtering.py
```

**What You'll See:**
- Documents filtered by multiple semantic topics
- Field-specific semantic matching (abstract vs content)
- Threshold effects (strict vs loose matching)
- Combination of semantic + structural filters

---

## 🎯 Core Concepts

### Semantic Text Predicates

```python
# Basic semantic matching
.consumes(Ticket, semantic_match="security vulnerability")

# Multiple topics (ALL must match - AND logic)
.consumes(Doc, text=["security", "compliance"])

# Advanced configuration
.consumes(Doc, text={
    "query": "privacy data protection",
    "threshold": 0.7,     # Strictness (0.0-1.0)
    "field": "abstract"   # Specific field
})
```

### SemanticContextProvider

```python
from flock.semantic import SemanticContextProvider

# Find similar historical artifacts
provider = SemanticContextProvider(
    query_semantic_match="database connection timeout",
    threshold=0.4,        # Similarity threshold
    limit=5,              # Max results
    artifact_type=Incident,
    where=lambda a: a.payload["resolved"] is True
)

similar = await provider.get_context(store)
```

### Threshold Guide

- **0.8-1.0**: Very strict (nearly identical)
- **0.6-0.7**: Strict (strongly similar)
- **0.4-0.5**: Moderate (default, related concepts)
- **0.2-0.3**: Loose (broadly related)

## 🎛️ CLI vs Dashboard Mode

Each example supports both modes:

**CLI Mode (default):**
```python
USE_DASHBOARD = False
```
Runs agents and displays results in terminal.

**Dashboard Mode:**
```python
USE_DASHBOARD = True
```
Launches interactive web interface at `http://localhost:8000`.

## 💡 Tips

1. **Start with default threshold (0.4)** - Works well for most cases
2. **Use multiple predicates for precision** - `text=["topic1", "topic2"]`
3. **Combine semantic + structural** - Add `where=` clauses for hybrid filtering
4. **Extract specific fields** - Use `field="abstract"` for targeted matching
5. **Test with CLI first** - Easier debugging before dashboard mode

## 📊 Performance

- **Single embedding**: ~15ms (CPU)
- **Batch 10 texts**: ~45ms (~4.5ms per text)
- **Cache hit**: <1ms
- **Memory**: ~150MB model + ~6MB per 10k cached embeddings

## 🔗 Additional Resources

- **Main Documentation**: `docs/semantic-subscriptions.md`
- **API Reference**: Full API details in main docs
- **Test Suite**: `tests/semantic/` (38 comprehensive tests)

## 🐛 Troubleshooting

**No matches despite relevant content?**
- Lower threshold: `text={"query": "...", "threshold": 0.3}`
- Check if field extraction needed: `field="abstract"`
- Verify semantic extras installed: `uv add flock-core[semantic]`

**Import errors?**
```bash
# Ensure semantic extras installed
uv add flock-core[semantic]
```

---

🚀 **Ready to explore semantic subscriptions? Start with example 01!**
