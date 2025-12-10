# Update Existing Plan

## Objective

Verify that the `update_plan` tool correctly updates an existing plan with new title and steps.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Update)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Status)** | `get_plan_status` | Planning tool to get plan status |
| **Thread ID** | `TC-003-local` | Thread ID for scoping the plan |
| **Original Title** | `Original Plan` | Initial plan title |
| **Updated Title** | `Updated Plan` | Modified plan title |

## Config

path: .alita/tool_configs/planning-local-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (if pgvector_configuration provided) or filesystem (default)

## Test Steps & Expectations

### Step 1: Create Initial Plan

Execute the `update_plan` tool with:
- thread_id: "TC-003-local"
- title: "Original Plan"
- steps: ["Original Step 1", "Original Step 2"]

**Expectation:** Plan is created successfully with title "Original Plan" and 2 steps.

### Step 2: Verify Initial Plan

Execute the `get_plan_status` tool with:
- thread_id: "TC-003-local"

**Expectation:** Plan exists with:
- Title: "Original Plan"
- 2 steps as defined

### Step 3: Update the Plan

Execute the `update_plan` tool with:
- thread_id: "TC-003-local"
- title: "Updated Plan"
- steps: ["New Step 1", "New Step 2", "New Step 3", "New Step 4"]

**Expectation:** Plan is updated successfully.

### Step 4: Verify Updated Plan

Execute the `get_plan_status` tool with:
- thread_id: "TC-003-local"

**Expectation:** Plan now shows:
- Title: "Updated Plan" (changed)
- 4 steps (changed from 2)
- All steps marked as not completed (reset)

### Step 5: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- thread_id: "TC-003-local"

**Expectation:** The plan is deleted successfully, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If plan can be modified with new title and steps, and cleanup succeeds
- ❌ **Fail:** If update fails, previous data is not properly replaced, or cleanup fails
