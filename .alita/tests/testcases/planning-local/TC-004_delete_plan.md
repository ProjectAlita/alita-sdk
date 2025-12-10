# Delete Plan

## Objective

Verify that the `delete_plan` tool correctly removes an existing plan from the database.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Create)** | `update_plan` | Planning tool to create a plan |
| **Tool (Delete)** | `delete_plan` | Planning tool to delete a plan |
| **Tool (Status)** | `get_plan_status` | Planning tool to check if plan exists |
| **Thread ID** | `TC-004-local` | Thread ID for scoping the plan |

## Config

path: .alita/tool_configs/planning-local-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (if pgvector_configuration provided) or filesystem (default)

## Test Steps & Expectations

### Step 1: Create a Plan for Deletion

Execute the `update_plan` tool with:
- thread_id: "TC-004-local"
- title: "Plan to Delete"
- steps: ["Step 1", "Step 2"]

**Expectation:** Plan is created successfully.

### Step 2: Verify Plan Exists

Execute the `get_plan_status` tool with:
- thread_id: "TC-004-local"

**Expectation:** Plan is returned with title "Plan to Delete".

### Step 3: Delete the Plan

Execute the `delete_plan` tool with:
- thread_id: "TC-004-local"

**Expectation:** The tool returns success message indicating the plan was deleted.

### Step 4: Verify Plan is Gone

Execute the `get_plan_status` tool with:
- thread_id: "TC-004-local"

**Expectation:** The tool returns a message indicating no plan exists for the current thread, such as "No plan found" or an empty response.

## Final Result

- ✅ **Pass:** If plan is created, then successfully deleted and no longer retrievable
- ❌ **Fail:** If deletion fails or plan still exists after deletion
