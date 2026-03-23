# ADO Acceptance Criteria Processing

This directory contains two separate pipelines for Azure DevOps work item hierarchy analysis with Acceptance Criteria (AC) extraction.

## Pipelines

### 1. ADO_Item_Hierarchy_Fetcher.yaml
**Purpose**: Fetch ADO work item hierarchy with integrated AC extraction

**Input**: Work item ID (epic, feature, etc.)

**Process**:
1. Fetch work item from ADO
2. Recursively fetch all descendants
3. Build hierarchy structure
4. Extract acceptance criteria from descriptions
5. Match child items to parent ACs
6. Calculate readiness metrics (work items + ACs)
7. Generate markdown visualization
8. Save JSON + Markdown files

**Output Files**:
- `epic_{id}_hierarchy_{timestamp}.json` - Full hierarchy with AC data
- `epic_{id}_hierarchy_{timestamp}.md` - Visual tree with AC coverage

**Use When**: You need to fetch fresh data from ADO and get complete readiness analysis

**Agent**: Feature_Readiness_Analyzer.txt

---

### 2. ADO_AC_Enricher.yaml
**Purpose**: Process existing hierarchy JSON and add AC extraction (standalone)

**Input**: Path to existing hierarchy JSON artifact

**Process**:
1. Load hierarchy JSON from artifact storage
2. Extract acceptance criteria from descriptions
3. Match child items to parent ACs
4. Enrich hierarchy structure with AC data
5. Save enriched JSON

**Output File**:
- `<original_name>_with_acs.json` - Enriched hierarchy with AC data

**Use When**: 
- You already have hierarchy JSON and want to add AC extraction
- Re-processing old hierarchy files after description updates
- Batch processing multiple hierarchies
- Testing AC extraction separately
- Custom AC analysis workflows

**Agent**: AC_Enricher_Agent.txt

---

## Architecture Decision

**Why Two Pipelines?**

1. **Separation of Concerns**
   - Fetching is separate from AC analysis
   - Easier to maintain and debug
   - Can update AC extraction logic without touching fetch logic

2. **Flexibility**
   - Run full flow or just AC enrichment
   - Re-process old hierarchies without re-fetching from ADO
   - Batch process multiple files independently

3. **Simplicity**
   - Each pipeline has single, clear purpose
   - Fewer conditionals and branches
   - Easier to understand and modify

4. **Reusability**
   - AC enricher works with any hierarchy JSON (not just ADO)
   - Can be used as preprocessing step for other tools
   - Enables custom workflows

---

## Data Structure

Both pipelines produce the same enriched structure:

```json
{
  "epic": {
    "id": 9,
    "title": "User Authentication",
    "description": "...",
    "state": "In Progress",
    "own_acs": [
      {
        "ac_id": "9-ac-1",
        "text": "User can login with email",
        "status": "done",
        "source": "checkbox",
        "covered_by_children": [123, 124]
      }
    ]
  },
  "items": {
    "123": {
      "id": 123,
      "title": "Implement login validation",
      "parent_id": 9,
      "own_acs": [],
      "covered_parent_acs": [
        {
          "parent_ac_id": "9-ac-1",
          "confidence": "explicit",
          "reason": "Implements email login validation"
        }
      ]
    }
  },
  "metadata": {...},
  "readiness": {...}  // Only in ADO_Item_Hierarchy_Fetcher output
}
```

---

## Usage Examples

### Full Flow (Fetch + AC Extraction)
```
Agent: Feature_Readiness_Analyzer
Input: "Fetch epic 9"
Output: 
  - epic_9_hierarchy_03_23_2026_14_30_45.json (with ACs)
  - epic_9_hierarchy_03_23_2026_14_30_45.md
  - Readiness report (work items + ACs)
```

### AC Enrichment Only
```
Agent: AC_Enricher_Agent
Input: "Enrich epic_9_hierarchy_03_23_2026_14_30_45.json with ACs"
Output:
  - epic_9_hierarchy_03_23_2026_14_30_45_with_acs.json
```

### Re-process Old Hierarchy
```
# Scenario: Descriptions were updated in ADO, need to re-extract ACs
1. Fetch fresh hierarchy (without ACs disabled in future version)
2. Use AC_Enricher to add updated ACs
```

---

## AC Extraction Details

### Recognized Patterns
1. **Labeled sections**: "Acceptance Criteria", "AC", "ACs", "Definition of Done", "DoD"
2. **Markdown checkboxes**: `- [ ]` (not done), `- [x]` (done)
3. **Numbered lists**: `1.`, `2.`, etc. under AC header
4. **Bulleted lists**: `-` or `*` under AC header
5. **Gherkin scenarios**: `Given...When...Then` format

### Matching Rules
- **Direct parent only**: Children matched only to immediate parent's ACs
- **Explicit match**: Child description/ACs directly reference parent AC
- **Semantic match**: Child title implies work toward parent AC (when no explicit ACs in child)
- **No forced matching**: Only confident matches recorded

### Confidence Levels
- `explicit`: Child clearly implements parent AC
- `semantic`: Child title suggests relation to parent AC
- `none`: No match found

---

## Configuration

Both pipelines use the `epic_artifacts` toolkit for file storage.

Configure in your toolkit config:
```json
{
  "type": "artifact",
  "name": "epic_artifacts",
  "settings": {
    "bucket": "your-bucket-name"
  }
}
```

---

## Testing

1. **Test ADO_Item_Hierarchy_Fetcher**:
   ```bash
   # With AC extraction enabled
   curl -X POST "<deployment_url>/api/v2/elitea_core/predict/prompt_lib/<project_id>/<pipeline_id>" \
     -H "Authorization: Bearer <token>" \
     -d '{"user_input": "Fetch epic 9"}'
   ```

2. **Test ADO_AC_Enricher**:
   ```bash
   # Process existing file
   curl -X POST "<deployment_url>/api/v2/elitea_core/predict/prompt_lib/<project_id>/<pipeline_id>" \
     -H "Authorization: Bearer <token>" \
     -d '{"user_input": "Process artifact at epic_9_hierarchy_03_23_2026.json"}'
   ```

---

## Future Enhancements

Potential improvements:
- Add AC extraction toggle to ADO_Item_Hierarchy_Fetcher (skip AC nodes if disabled)
- Support multiple AC matching strategies (strict vs. lenient)
- Add AC diff comparison between versions
- Generate AC coverage heat map
- Export AC checklist for standup/sprint planning
