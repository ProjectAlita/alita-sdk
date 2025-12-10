# Complete Step in Plan (PostgreSQL)

## Objective

Verify that the `complete_step` tool correctly marks a step as completed in a PostgreSQL-stored plan and updates the plan status accordingly.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Create)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Complete)** | `complete_step` | Planning tool to mark a step as completed |
| **Tool (Retrieve)** | `get_plan_status` | Planning tool to get plan status |
| **Conversation ID** | `TC-002` | Conversation ID for scoping the plan |
| **Title** | `Test Plan 002` | Plan title |
| **Steps** | `["Step A: Initialize", "Step B: Process", "Step C: Finalize"]` | Plan steps |
| **Step to Complete** | `0` | Index of step to mark as completed |

## Config

path: .alita/tool_configs/planning-postgres-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (via pgvector_configuration connection_string)
- PostgreSQL database is running and accessible

## Test Steps & Expectations

### Step 1: Create a Plan

Execute the `update_plan` tool with the following parameters:
- conversation_id: "TC-002"
- title: "Test Plan 002"
- steps: ["Step A: Initialize", "Step B: Process", "Step C: Finalize"]

**Expectation:** The plan is created successfully with 3 incomplete steps in PostgreSQL.

### Step 2: Complete the First Step

Execute the `complete_step` tool with:
- conversation_id: "TC-002"
- step_number: 1

**Expectation:** The tool returns success indicating step 0 (Step A: Initialize) is now completed.

### Step 3: Verify Plan Status

Execute the `get_plan_status` tool with:
- conversation_id: "TC-002"

**Expectation:** The plan shows:
- Step 1 (Step A: Initialize): completed = true
- Steps 2 and 3: completed = false
- Status: "in_progress" (since not all steps are complete)

### Step 4: Complete All Remaining Steps

Execute the `complete_step` tool twice:
- First call: conversation_id: "TC-002", step_number: 2
- Second call: conversation_id: "TC-002", step_number: 3

**Expectation:** Both steps are marked as completed.

### Step 5: Verify Final Plan Status

Execute the `get_plan_status` tool with:
- conversation_id: "TC-002"

**Expectation:** The plan shows:
- All 3 steps: completed = true
- Status: "completed"

### Step 6: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- conversation_id: "TC-002"

**Expectation:** The plan is deleted successfully from PostgreSQL, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If steps can be completed individually, plan status updates correctly, and cleanup succeeds
- ❌ **Fail:** If step completion fails, status doesn't reflect completed steps, or cleanup fails
