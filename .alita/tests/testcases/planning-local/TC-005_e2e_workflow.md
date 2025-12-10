# End-to-End Plan Workflow

## Objective

Verify the complete lifecycle of an execution plan: create, track progress, complete all steps, and clean up.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Update)** | `update_plan` | Planning tool to create/update plans |
| **Tool (Complete)** | `complete_step` | Planning tool to mark steps complete |
| **Tool (Status)** | `get_plan_status` | Planning tool to get plan status |
| **Tool (Delete)** | `delete_plan` | Planning tool to delete plans |
| **Thread ID** | `TC-005-local` | Thread ID for scoping the plan |
| **Plan Title** | `E2E Test Workflow` | Title for the test plan |

## Config

path: .alita/tool_configs/planning-local-config.json

## Pre-requisites

- The planning toolkit is properly configured with all tools enabled
- Storage backend: PostgreSQL (if pgvector_configuration provided) or filesystem (default)

## Test Steps & Expectations

### Step 1: Create a Multi-Step Plan

Execute the `update_plan` tool with:
- thread_id: "TC-005-local"
- title: "E2E Test Workflow"
- steps: ["Initialize environment", "Run tests", "Collect results", "Generate report"]

**Expectation:** Plan is created with 4 steps, all marked as not completed.

### Step 2: Verify Initial State

Execute the `get_plan_status` tool with:
- thread_id: "TC-005-local"

**Expectation:** 
- Plan status is "in_progress"
- 0/4 steps completed
- All steps show completed: false

### Step 3: Complete First Two Steps

Execute `complete_step` with thread_id: "TC-005-local", step_number: 1, then with thread_id: "TC-005-local", step_number: 2.

**Expectation:** Both operations succeed. Progress should be 2/4 (50%).

### Step 4: Check Mid-Progress Status

Execute the `get_plan_status` tool with:
- thread_id: "TC-005-local"

**Expectation:**
- Steps 1 and 2 are completed
- Steps 3 and 4 are not completed
- Progress: 50%

### Step 5: Complete Remaining Steps

Execute `complete_step` with thread_id: "TC-005-local", step_number: 3, then with thread_id: "TC-005-local", step_number: 4.

**Expectation:** Both operations succeed. All steps now completed.

### Step 6: Verify Completion

Execute the `get_plan_status` tool with:
- thread_id: "TC-005-local"

**Expectation:**
- Status is "completed" or all 4 steps are marked completed
- Progress: 100% (4/4)

### Step 7: Clean Up - Delete the Plan

Execute the `delete_plan` tool with:
- thread_id: "TC-005-local"

**Expectation:** Plan is deleted successfully.

### Step 8: Verify Cleanup

Execute the `get_plan_status` tool with:
- thread_id: "TC-005-local"

**Expectation:** No plan found for current thread.

## Final Result

- ✅ **Pass:** If entire lifecycle works: create → track progress → complete → delete
- ❌ **Fail:** If any step in the workflow fails or returns unexpected results
