# Artifact Lineage Analysis

**Date**: 2025-10-13
**Status**: ✅ ANALYSIS COMPLETE - Ready for Review

---

## 📄 Document Index

1. **[correlation-id-analysis.md](./correlation-id-analysis.md)** - Complete analysis of correlation ID behavior in JoinSpec

---

## 🎯 Key Question Answered

**Question**: When an agent produces an artifact from correlated inputs (JoinSpec), which correlation_id does it get?

**Answer**: The correlation_id from the **FIRST** input artifact.

---

## ⚠️ Issue Summary

### Issue: Lost Data Lineage

**Problem**: When radiologist agent correlates XRayImage + LabResults:
- DiagnosticReport gets correlation_id from XRayImage (first)
- LabResults correlation_id is NOT preserved
- Cannot trace outputs back to ALL inputs

**Impact**: Debugging, audit trails, and data provenance queries are incomplete

---

## 💡 Recommendations

| Recommendation | Priority | Issue Solved |
|---------------|----------|--------------|
| **Add parent_artifact_ids field** | HIGH | Track ALL input artifacts |
| **Rename correlation_id → trace_id** | MEDIUM | Reduce terminology confusion |
| **Add lineage query helpers** | MEDIUM | Improve developer experience |
| **Document the distinction** | HIGH | Education and clarity |

---

## 📚 For Full Details

See [correlation-id-analysis.md](./correlation-id-analysis.md) for:
- Complete code flow analysis
- Data flow diagrams
- Proposed implementation
- Test cases
- Migration strategy

---

**Last Updated**: 2025-10-13
