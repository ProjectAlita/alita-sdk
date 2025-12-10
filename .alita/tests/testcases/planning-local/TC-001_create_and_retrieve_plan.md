# Create and Retrieve Execution Plan

## Objective

Verify that the `update_plan` tool correctly creates a new execution plan and that the `get_plan_status` tool can retrieve it.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Create)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Retrieve)** | `get_plan_status` | Planning tool to get plan status |
| **Thread ID** | `TC-001-local` | Thread ID for scoping the plan |
| **Title** | `Test Plan 001` | Plan title |
| **Steps** | `["Step 1: Setup", "Step 2: Execute", "Step 3: Verify"]` | Plan steps |

## Config

path: .alita/tool_configs/planning-local-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (if pgvector_configuration provided) or filesystem (default for CLI)

## Test Steps & Expectations

### Step 1: Create a New Plan

Execute the `update_plan` tool with the following parameters:
- thread_id: "TC-001-local"
- title: "Test Plan 001"
- steps: ["Step 1: Setup", "Step 2: Execute", "Step 3: Verify"]

**Expectation:** The tool runs without errors and returns a success message indicating the plan was created.

### Step 2: Retrieve the Plan Status

Execute the `get_plan_status` tool with:
- thread_id: "TC-001-local"

**Expectation:** The tool returns the plan with:
- Title: "Test Plan 001"
- 3 steps total
- All steps marked as incomplete (not completed)
- Status: "in_progress"

### Step 3: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- thread_id: "TC-001-local"

**Expectation:** The plan is deleted successfully, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If the plan is created successfully, can be retrieved with correct data, and is cleaned up
- ❌ **Fail:** If plan creation fails, retrieval fails, data doesn't match, or cleanup fails
