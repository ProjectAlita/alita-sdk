# Complete Step and Verify Progress

## Objective

Verify that the `complete_step` tool correctly marks a step as completed and updates the plan progress.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Complete)** | `complete_step` | Planning tool to mark a step as complete |
| **Tool (Status)** | `get_plan_status` | Planning tool to check plan status |
| **Thread ID** | `TC-002-local` | Thread ID for scoping the plan |
| **Step Number** | `1` | The step number to mark as complete |

## Config

path: .alita/tool_configs/planning-local-config.json

## Pre-requisites

- The planning toolkit is properly configured
- A plan must already exist (run TC-001 first or create one in this test)
- The plan should have at least 1 step that is not completed

## Test Steps & Expectations

### Step 1: Create a Plan (Setup)

Execute the `update_plan` tool with:
- thread_id: "TC-002-local"
- title: "Progress Test Plan"
- steps: ["Step 1: First task", "Step 2: Second task", "Step 3: Third task"]

**Expectation:** Plan is created successfully.

### Step 2: Complete the First Step

Execute the `complete_step` tool with:
- thread_id: "TC-002-local"
- step_number: 1

**Expectation:** The tool returns success, indicating Step 1 has been marked as completed.

### Step 3: Verify Step Completion

Execute the `get_plan_status` tool with:
- thread_id: "TC-002-local"

**Expectation:** The plan shows:
- Step 1 marked as completed (completed: true)
- Steps 2 and 3 still marked as not completed
- Overall progress: 1/3 steps completed (33%)

### Step 4: Complete the Second Step

Execute the `complete_step` tool with:
- thread_id: "TC-002-local"
- step_number: 2

**Expectation:** The tool returns success.

### Step 5: Verify Incremental Progress

Execute the `get_plan_status` tool with:
- thread_id: "TC-002-local"

**Expectation:** The plan shows:
- Steps 1 and 2 marked as completed
- Step 3 still not completed
- Overall progress: 2/3 steps completed (67%)

### Step 6: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- thread_id: "TC-002-local"

**Expectation:** The plan is deleted successfully, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If steps can be completed individually, progress is tracked correctly, and cleanup succeeds
- ❌ **Fail:** If step completion fails, progress tracking is incorrect, or cleanup fails
