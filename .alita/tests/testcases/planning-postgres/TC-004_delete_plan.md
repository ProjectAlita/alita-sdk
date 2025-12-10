# Delete Plan (PostgreSQL)

## Objective

Verify that the `delete_plan` tool correctly removes a plan from PostgreSQL storage and that subsequent retrieval returns no plan.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Create)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Delete)** | `delete_plan` | Planning tool to delete a plan |
| **Tool (Retrieve)** | `get_plan_status` | Planning tool to get plan status |
| **Conversation ID** | `TC-004` | Conversation ID for scoping the plan |
| **Title** | `Plan To Delete` | Plan title |
| **Steps** | `["Step 1", "Step 2"]` | Plan steps |

## Config

path: .alita/tool_configs/planning-postgres-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (via pgvector_configuration connection_string)
- PostgreSQL database is running and accessible

## Test Steps & Expectations

### Step 1: Create a Plan

Execute the `update_plan` tool with:
- conversation_id: "TC-004"
- title: "Plan To Delete"
- steps: ["Step 1", "Step 2"]

**Expectation:** Plan is created successfully in PostgreSQL.

### Step 2: Verify Plan Exists

Execute the `get_plan_status` tool with:
- conversation_id: "TC-004"

**Expectation:** Plan exists with title "Plan To Delete" and 2 steps.

### Step 3: Delete the Plan

Execute the `delete_plan` tool with:
- conversation_id: "TC-004"

**Expectation:** The tool returns success indicating the plan was deleted from PostgreSQL.

### Step 4: Verify Plan is Deleted

Execute the `get_plan_status` tool with:
- conversation_id: "TC-004"

**Expectation:** The tool indicates no plan exists (empty response or "no plan found" message).

## Final Result

- ✅ **Pass:** If the plan is deleted successfully and cannot be retrieved afterwards
- ❌ **Fail:** If deletion fails or plan still exists after deletion
