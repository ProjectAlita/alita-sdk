# ADO AC Processing Architecture - Quick Reference

## File Overview

| File | Type | Purpose |
|------|------|---------|
| **ADO_Fetcher.yaml** | Pipeline (Orchestrator) | Chains fetch + AC enrichment |
| **ADO_Fetcher_Agent.txt** | Agent Instructions | How to use the orchestrator |
| **ADO_Item_Hierarchy_Fetcher.yaml** | Pipeline (Atomic) | Fetch from ADO only |
| **ADO_AC_Enricher.yaml** | Pipeline (Transformer) | AC enrichment only |
| **AC_Enricher_Agent.txt** | Agent Instructions | How to use the enricher |
| **README_AC_PROCESSING.md** | Documentation | Complete architecture guide |

## Architecture Pattern: Composable Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│                    ADO_Fetcher.yaml                          │
│                     (Orchestrator)                           │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Stage 1: Fetch Hierarchy                           │    │
│  │   CallHierarchyFetcher (agent node)                │    │
│  │     └─→ ADO_Item_Hierarchy_Fetcher                 │    │
│  │          └─→ JSON: epic_9_hierarchy.json           │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Stage 2: AC Enrichment                             │    │
│  │   LoadHierarchyData                                │    │
│  │   ExtractAcceptanceCriteria (LLM)                  │    │
│  │   MatchChildrenToParentACs (LLM)                   │    │
│  │   EnrichHierarchyWithACs (code)                    │    │
│  │     └─→ JSON: epic_9_hierarchy_with_acs.json       │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           ADO_Item_Hierarchy_Fetcher.yaml                    │
│                  (Atomic Component)                          │
│                                                              │
│  - Fetch work items from Azure DevOps                       │
│  - Build hierarchy structure                                │
│  - Calculate basic readiness (no AC)                        │
│  - Generate markdown visualization                          │
│  - Output: JSON + MD files                                  │
│                                                              │
│  Can be used:                                               │
│  • Standalone (direct invocation)                           │
│  • As a skill (called by ADO_Fetcher)                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               ADO_AC_Enricher.yaml                           │
│                (Transformer Component)                       │
│                                                              │
│  - Input: Existing hierarchy JSON                           │
│  - Extract ACs from descriptions                            │
│  - Match children to parent ACs                             │
│  - Enrich structure with AC data                            │
│  - Output: Enriched JSON                                    │
│                                                              │
│  Can be used:                                               │
│  • Re-process old JSON files                                │
│  • Batch process multiple files                             │
│  • Test AC extraction independently                         │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Full Workflow (ADO_Fetcher)
```
User Input: "Fetch epic 9"
    ↓
[ADO_Fetcher]
    ↓
Stage 1: Fetch
    ↓
[ADO_Item_Hierarchy_Fetcher skill]
    ↓
ADO API → Hierarchy → JSON (raw)
    ↓
epic_9_hierarchy_03_23_2026.json
    ↓
Stage 2: Enrich
    ↓
Load JSON → Extract ACs → Match Coverage → Enrich
    ↓
epic_9_hierarchy_03_23_2026_with_acs.json
    ↓
Output: 2 files (raw + enriched)
```

### Standalone AC Enrichment (ADO_AC_Enricher)
```
User Input: "Process epic_9_hierarchy.json"
    ↓
[ADO_AC_Enricher]
    ↓
Load JSON → Extract ACs → Match Coverage → Enrich
    ↓
epic_9_hierarchy_with_acs.json
    ↓
Output: 1 file (enriched)
```

## Quick Decision Tree

```
START: What do you need?

┌─────────────────────────────────────────┐
│ Fetch from ADO + AC enrichment          │ → Use ADO_Fetcher ⭐
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Fetch from ADO only (no AC)             │ → Use ADO_Item_Hierarchy_Fetcher
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Have JSON, need to add ACs              │ → Use ADO_AC_Enricher
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Re-process old JSON with updated ACs    │ → Use ADO_AC_Enricher
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Batch process multiple JSON files       │ → Use ADO_AC_Enricher (loop)
└─────────────────────────────────────────┘
```

## Output Files Comparison

| Pipeline | Output Files | Content |
|----------|-------------|---------|
| **ADO_Fetcher** | 2 files | `epic_X.json` (raw) + `epic_X_with_acs.json` (enriched) |
| **ADO_Item_Hierarchy_Fetcher** | 2 files | `epic_X.json` (raw) + `epic_X.md` (visualization) |
| **ADO_AC_Enricher** | 1 file | `<input>_with_acs.json` (enriched) |

## Benefits of This Architecture

✅ **Composability**: Mix and match components  
✅ **Reusability**: Each component is independently useful  
✅ **Testability**: Test fetch and AC extraction separately  
✅ **Debuggability**: Clear stage boundaries, easy to isolate failures  
✅ **Flexibility**: Multiple use cases supported  
✅ **Maintainability**: Update each component independently  
✅ **Clarity**: Each pipeline has single, clear purpose

## Integration Points

### With Feature Readiness Analyzer
```
Feature_Readiness_Analyzer
    ↓
Can invoke ADO_Fetcher
    ↓
Gets both raw and enriched JSON
    ↓
Presents complete readiness report
```

### With Custom Workflows
```
Custom Pipeline
    ↓
Call ADO_Item_Hierarchy_Fetcher
    ↓
Get raw JSON
    ↓
Apply custom transformations
    ↓
Call ADO_AC_Enricher
    ↓
Get enriched JSON
```

## Key Design Decisions

1. **Orchestrator Pattern**: ADO_Fetcher orchestrates but doesn't duplicate logic
2. **Agent Node**: Reuses ADO_Item_Hierarchy_Fetcher via agent node type
3. **Shared AC Logic**: AC extraction code is identical in orchestrator and enricher
4. **File Naming**: Consistent naming with `_with_acs` suffix for enriched files
5. **Validation**: Each stage validates before proceeding
6. **Error Handling**: Clear error messages at stage boundaries

## Testing Strategy

1. **Test ADO_Item_Hierarchy_Fetcher** → Verify fetch works
2. **Test ADO_AC_Enricher** with mock JSON → Verify AC extraction works
3. **Test ADO_Fetcher** end-to-end → Verify orchestration works

## Migration Path

If you were using the integrated ADO_Item_Hierarchy_Fetcher (with AC extraction built-in):

**Before**: `ADO_Item_Hierarchy_Fetcher` (fetch + AC) → 1 JSON with ACs

**After**: `ADO_Fetcher` (orchestrator) → 2 JSONs (raw + enriched)

**Benefit**: Cleaner separation, raw hierarchy available for other uses

---

For complete documentation, see [README_AC_PROCESSING.md](README_AC_PROCESSING.md)
