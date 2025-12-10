# Create and Retrieve Execution Plan (PostgreSQL)

## Objective

Verify that the `update_plan` tool correctly creates a new execution plan in PostgreSQL storage and that the `get_plan_status` tool can retrieve it.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Create)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Retrieve)** | `get_plan_status` | Planning tool to get plan status |
| **Conversation ID** | `TC-001` | Conversation ID for scoping the plan |
| **Title** | `Test Plan 001` | Plan title |
| **Steps** | `["Step 1: Setup", "Step 2: Execute", "Step 3: Verify"]` | Plan steps |

## Config

path: .alita/tool_configs/planning-postgres-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (via pgvector_configuration connection_string)
- PostgreSQL database is running and accessible
- Required tables will be auto-created if not exist

## Test Steps & Expectations

### Step 1: Create a New Plan

Execute the `update_plan` tool with the following parameters:
- conversation_id: "TC-001"
- title: "Test Plan 001"
- steps: ["Step 1: Setup", "Step 2: Execute", "Step 3: Verify"]

**Expectation:** The tool runs without errors and returns a success message indicating the plan was created in PostgreSQL.

### Step 2: Retrieve the Plan Status

Execute the `get_plan_status` tool with:
- conversation_id: "TC-001"

**Expectation:** The tool returns the plan with:
- Title: "Test Plan 001"
- 3 steps total
- All steps marked as incomplete (not completed)
- Status: "in_progress"

### Step 3: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- conversation_id: "TC-001"

**Expectation:** The plan is deleted successfully from PostgreSQL, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If the plan is created successfully in PostgreSQL, can be retrieved with correct data, and is cleaned up
- ❌ **Fail:** If plan creation fails, retrieval fails, data doesn't match, or cleanup fails
