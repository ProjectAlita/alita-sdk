# End-to-End Planning Workflow (PostgreSQL)

## Objective

Verify the complete planning workflow from creation through completion and deletion works correctly with PostgreSQL storage, testing all planning tools in a realistic scenario.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tools** | `update_plan`, `complete_step`, `get_plan_status`, `delete_plan` | All planning tools |
| **Conversation ID** | `TC-005` | Conversation ID for scoping the plan |
| **Title** | `Feature Implementation Plan` | Realistic plan title |
| **Steps** | See below | Multi-step development workflow |

### Plan Steps

```json
[
  "Step 1: Analyze requirements and create design doc",
  "Step 2: Set up development environment",
  "Step 3: Implement core functionality",
  "Step 4: Write unit tests",
  "Step 5: Code review and refactoring",
  "Step 6: Integration testing",
  "Step 7: Documentation and deployment"
]
```

## Config

path: .alita/tool_configs/planning-postgres-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (via pgvector_configuration connection_string)
- PostgreSQL database is running and accessible
- No existing plan for the current conversation (clean state)

## Test Steps & Expectations

### Step 1: Create the Development Plan

Execute the `update_plan` tool with:
- conversation_id: "TC-005"
- title: "Feature Implementation Plan"
- steps: [7 steps as listed above]

**Expectation:** Plan is created with 7 steps, all incomplete, status "in_progress".

### Step 2: Check Initial Status

Execute the `get_plan_status` tool with:
- conversation_id: "TC-005"

**Expectation:** 
- Title: "Feature Implementation Plan"
- 7 steps, 0 completed
- Progress: 0%
- Status: "in_progress"

### Step 3: Complete First Three Steps

Execute `complete_step` three times with:
- conversation_id: "TC-005", step_number: 1 (Analyze requirements)
- conversation_id: "TC-005", step_number: 2 (Setup environment)
- conversation_id: "TC-005", step_number: 3 (Implement core)

**Expectation:** Each step is marked as completed successfully.

### Step 4: Check Mid-Progress Status

Execute the `get_plan_status` tool with:
- conversation_id: "TC-005"

**Expectation:**
- Steps 1, 2, 3: completed = true
- Steps 4, 5, 6, 7: completed = false
- Progress: ~43% (3/7)
- Status: "in_progress"

### Step 5: Update Plan Mid-Execution

Execute the `update_plan` tool to add a new step:
- conversation_id: "TC-005"
- title: "Feature Implementation Plan (Revised)"
- steps: [original 7 steps + "Step 8: Performance optimization"]

**Expectation:** Plan is updated with 8 steps. Note: Completion status may be reset depending on implementation.

### Step 6: Complete Remaining Steps

Execute `complete_step` for all remaining incomplete steps (use conversation_id: "TC-005" for each call).

**Expectation:** All steps are marked as completed.

### Step 7: Verify Completion

Execute the `get_plan_status` tool with:
- conversation_id: "TC-005"

**Expectation:**
- All steps: completed = true
- Progress: 100%
- Status: "completed"

### Step 8: Clean Up - Delete Plan

Execute the `delete_plan` tool with:
- conversation_id: "TC-005"

**Expectation:** Plan is deleted successfully from PostgreSQL.

### Step 9: Verify Deletion

Execute the `get_plan_status` tool with:
- conversation_id: "TC-005"

**Expectation:** No plan found.

## Final Result

- ✅ **Pass:** If the entire workflow completes successfully with all operations working as expected
- ❌ **Fail:** If any operation fails or produces unexpected results

## Notes

This test verifies:
- Plan persistence across multiple operations in PostgreSQL
- Correct completion tracking in database
- Status transitions (in_progress → completed)
- Update behavior for existing plans
- Clean deletion and verification
