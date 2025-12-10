# Update Existing Plan (PostgreSQL)

## Objective

Verify that the `update_plan` tool correctly modifies an existing plan's title and/or steps when the plan already exists in PostgreSQL storage.

## Test Data Configuration

### Settings

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Tool (Update)** | `update_plan` | Planning tool to create or update a plan |
| **Tool (Retrieve)** | `get_plan_status` | Planning tool to get plan status |
| **Conversation ID** | `TC-003` | Conversation ID for scoping the plan |
| **Initial Title** | `Original Plan` | Initial plan title |
| **Initial Steps** | `["Original Step 1", "Original Step 2"]` | Initial plan steps |
| **Updated Title** | `Updated Plan` | New plan title |
| **Updated Steps** | `["New Step A", "New Step B", "New Step C"]` | New plan steps |

## Config

path: .alita/tool_configs/planning-postgres-config.json

## Pre-requisites

- The planning toolkit is properly configured
- Storage backend: PostgreSQL (via pgvector_configuration connection_string)
- PostgreSQL database is running and accessible

## Test Steps & Expectations

### Step 1: Create Initial Plan

Execute the `update_plan` tool with:
- conversation_id: "TC-003"
- title: "Original Plan"
- steps: ["Original Step 1", "Original Step 2"]

**Expectation:** Plan is created with 2 steps in PostgreSQL.

### Step 2: Verify Initial Plan

Execute the `get_plan_status` tool with:
- conversation_id: "TC-003"

**Expectation:** Plan has title "Original Plan" with 2 steps.

### Step 3: Update the Plan

Execute the `update_plan` tool with:
- conversation_id: "TC-003"
- title: "Updated Plan"
- steps: ["New Step A", "New Step B", "New Step C"]

**Expectation:** The tool returns success indicating the plan was updated in PostgreSQL.

### Step 4: Verify Updated Plan

Execute the `get_plan_status` tool with:
- conversation_id: "TC-003"

**Expectation:** Plan now has:
- Title: "Updated Plan"
- 3 steps (New Step A, B, C)
- All steps marked as incomplete

### Step 5: Cleanup - Delete the Plan

Execute the `delete_plan` tool with:
- conversation_id: "TC-003"

**Expectation:** The plan is deleted successfully from PostgreSQL, leaving a clean state for subsequent tests.

## Final Result

- ✅ **Pass:** If the plan can be updated, changes are persisted correctly to PostgreSQL, and cleanup succeeds
- ❌ **Fail:** If update fails, previous data persists after update, or cleanup fails
