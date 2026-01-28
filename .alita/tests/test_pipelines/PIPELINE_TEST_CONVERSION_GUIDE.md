# Pipeline Test Conversion Guide for AI Agents

## Purpose
This guide provides comprehensive instructions for converting Markdown test cases to YAML pipeline tests for the Alita SDK testing framework. Follow these rules and patterns to ensure consistency and correctness.

---

## Table of Contents
1. [Overview & Objectives](#overview--objectives)
2. [File Structure & Naming](#file-structure--naming)
3. [Pipeline Architecture](#pipeline-architecture)
4. [State Management](#state-management)
5. [Node Types & Patterns](#node-types--patterns)
6. [Input/Output Mapping](#inputoutput-mapping)
7. [LLM Validation Pattern](#llm-validation-pattern)
8. [Test Atomicity Principles](#test-atomicity-principles)
9. [Conversion Workflow](#conversion-workflow)
10. [Examples & Templates](#examples--templates)
11. [Common Pitfalls](#common-pitfalls)

---

## Overview & Objectives

### Primary Goal
Convert Markdown test cases into executable YAML pipeline tests that:
- Test **ONE tool operation** per pipeline (atomic tests)
- Validate tool execution and output correctness
- Provide structured test results in JSON format
- Follow consistent patterns and naming conventions

### Test Philosophy
- **Atomic**: Each test validates a single tool operation
- **Self-contained**: All test data and expectations in one file
- **Deterministic**: Same inputs produce same validation results
- **Maintainable**: Clear structure, consistent patterns, easy to debug

---

## File Structure & Naming

### Naming Conventions

#### File Names
**Format**: `test_case_XX_[operation_name].yaml`

**Rules**:
- Sequential numbering: `01`, `02`, `03`, etc.
- Use underscores `_` as separators
- All lowercase
- Operation name should match the tool being tested
- Extension: `.yaml` (not `.yml`)

**Examples**:
```
✅ test_case_01_get_page_tree.yaml
✅ test_case_11_site_search.yaml
✅ test_case_07_create_delete_page.yaml
❌ test_case_1_get_page.yaml          # Missing leading zero
❌ TestCase01GetPage.yaml             # Wrong case
❌ test-case-01-get-page.yaml         # Wrong separator
```

#### Pipeline Metadata

**Name Field**:
- Format: `"[PREFIX]XX - [Human Readable Description]"`
- PREFIX: Toolkit identifier (CF=Confluence, JR=Jira, GH=GitHub)
- XX: Sequential number matching filename
- Title case for description

**Examples**:
```yaml
✅ name: "CF01 - Get Page Tree with Descendants"
✅ name: "JR01 - Search Issues by JQL"
✅ name: "GH01 - List Branches"
❌ name: "Test Case 01"                # Missing prefix
❌ name: "cf01 - get page tree"        # Wrong case
```

**Description Field**:
- Brief explanation of what is being tested
- Start with "Verify [tool_name] tool..."
- Include key validation points

**Examples**:
```yaml
✅ description: "Verify get_page_tree tool retrieves complete hierarchical structure including all descendant pages"
✅ description: "Verify search_issues tool returns issues matching a JQL query"
❌ description: "Test the tool"        # Too vague
```

### File Locations

**Source Markdown Tests**:
```
.alita/tests/testcases/[toolkit_name]/TC-XXX_[test_name].md
```

**Converted Pipeline YAML**:
```
.alita/tests/test_pipelines/[toolkit_name]_toolkit/tests/test_case_XX_[test_name].yaml
```

**Tool Configuration**:
```
.alita/tool_configs/[toolkit_name]-config.json
```

---

## Pipeline Architecture

### ⚠️ MANDATORY RULE: All Pipelines Must End with LLM Node

**CRITICAL REQUIREMENT:** Every pipeline MUST end with an LLM validation node as the final node before `transition: END`.

**Why This Rule Exists:**
1. Ensures consistent test result format (`test_results` dict)
2. Validates ALL operations including cleanup
3. Provides comprehensive pass/fail determination
4. Allows state-based validation after all operations complete

**The Pattern:**
```yaml
nodes:
  # 1. Execute main operation(s)
  - id: invoke_tool
    type: toolkit
    output: [create_result]
    transition: cleanup_node  # NOT to END
    
  # 2. Cleanup resources (if needed)
  - id: cleanup_node
    type: toolkit
    output: [delete_result]
    transition: process_results  # MUST go to LLM node
    
  # 3. Final LLM validation - MANDATORY LAST NODE
  - id: process_results
    type: llm
    input: [create_result, delete_result]  # All results from state
    output: [test_results]
    transition: END  # ONLY the LLM node goes to END
```

**❌ INCORRECT - Cleanup node ends pipeline:**
```yaml
- id: process_results
  type: llm
  transition: cleanup_delete  # ❌ LLM not last

- id: cleanup_delete
  type: toolkit
  transition: END  # ❌ Toolkit node cannot end pipeline
```

**✅ CORRECT - LLM node ends pipeline:**
```yaml
- id: invoke_tool
  type: toolkit
  transition: cleanup_delete

- id: cleanup_delete
  type: toolkit
  transition: process_results  # ✅ Goes to LLM

- id: process_results
  type: llm
  transition: END  # ✅ Only LLM node ends pipeline
```

**Key Points:**
- LLM node MUST be the last node in every pipeline
- Cleanup nodes MUST complete BEFORE LLM validation
- LLM validation node receives ALL operation results via state variables
- Only the `process_results` (LLM) node has `transition: END`

---

### Standard Two-Node Pattern

**Every pipeline follows this structure**:
```yaml
nodes:
  - id: invoke_[tool_name]          # Node 1: Execute the tool
    type: toolkit
    tool: [tool_name]
    # ... tool configuration ...
    transition: process_results
    
  - id: process_results              # Node 2: Validate with LLM
    type: llm
    # ... validation logic ...
    transition: END
```

### Why Two Nodes?

1. **Separation of Concerns**:
   - Node 1: Execute the tool (action)
   - Node 2: Validate the result (assertion)

2. **Reusability**: Tool execution is isolated from validation logic

3. **Debugging**: Easy to identify if failure is in tool execution or validation

4. **Consistency**: Same pattern across all tests

### Entry Point
```yaml
entry_point: invoke_[tool_name]  # Always start with the tool execution node
```

### Multi-Node Patterns (Advanced)

**For tests requiring setup, execution, and cleanup:**

#### Pattern 1: Three-Node with Cleanup
```yaml
nodes:
  - id: invoke_[tool_name]          # Node 1: Execute main tool
    transition: process_results
    
  - id: process_results              # Node 2: Validate results
    transition: cleanup_delete_page
    
  - id: cleanup_delete_page          # Node 3: Cleanup resources
    transition: END
```

**Use case:** Create operations that need cleanup (CF14)

#### Pattern 2: Setup-Execute-Validate-Cleanup
```yaml
nodes:
  - id: setup_create_page            # Node 1: Setup test data
    transition: invoke_[tool_name]
    
  - id: invoke_[tool_name]           # Node 2: Execute main tool
    transition: process_results
    
  - id: process_results              # Node 3: Validate
    transition: cleanup_delete_page
    
  - id: cleanup_delete_page          # Node 4: Cleanup
    transition: END
```

**Use case:** Update/Delete operations requiring test data (CF17, CF18)

#### Pattern 3: Multi-Setup with Sequential Cleanup
```yaml
nodes:
  - id: setup_create_page_1          # Node 1: Setup first resource
    transition: setup_create_page_2
    
  - id: setup_create_page_2          # Node 2: Setup second resource
    transition: invoke_[tool_name]
    
  - id: invoke_[tool_name]           # Node 3: Execute main operation
    transition: process_results
    
  - id: process_results              # Node 4: Validate
    transition: cleanup_delete_page_1
    
  - id: cleanup_delete_page_1        # Node 5: Cleanup first resource
    transition: cleanup_delete_page_2
    
  - id: cleanup_delete_page_2        # Node 6: Cleanup second resource
    transition: END
```

**Use case:** Bulk operations requiring multiple test pages (CF15, CF16, CF19, CF20, CF21)

#### Pattern 4: Setup-Get-ID-Execute-Validate-Cleanup
```yaml
nodes:
  - id: setup_create_page_1
    transition: setup_create_page_2
    
  - id: setup_create_page_2
    transition: get_page_id_1         # ID resolution node
    
  - id: get_page_id_1                 # Extract page ID for operations
    transition: invoke_[tool_name]
    
  - id: invoke_[tool_name]
    transition: process_results
    
  - id: process_results
    transition: cleanup_delete_page_1
    
  - id: cleanup_delete_page_1
    transition: cleanup_delete_page_2
    
  - id: cleanup_delete_page_2
    transition: END
```

**Use case:** Operations requiring page IDs from created pages (CF19, CF20, CF21)

### Multi-Node Naming Conventions

**Setup Nodes:**
- Format: `setup_[action]_[resource]`
- Examples: `setup_create_page`, `setup_create_page_1`, `setup_create_page_2`

**Cleanup Nodes:**
- Format: `cleanup_[action]_[resource]`
- Examples: `cleanup_delete_page`, `cleanup_delete_page_1`, `cleanup_delete_page_2`

**ID Resolution Nodes:**
- Format: `get_[resource]_id_[number]`
- Examples: `get_page_id_1`, `get_page_id_2`

**Verification Nodes:**
- Format: `verify_[condition]`
- Examples: `verify_deletion`, `verify_update`

---

## State Management

### State Block Structure

**Purpose**: Define all variables used throughout the pipeline

**Required Variables**:
```yaml
state:
  # 1. Input parameters (tool-specific)
  [param_name]:
    type: str|dict|list
    value: [initial_value]
  
  # 2. Tool output storage (ALWAYS REQUIRED)
  tool_result:
    type: str
  
  # 3. Validation results (ALWAYS REQUIRED)
  test_results:
    type: dict
```

### Variable Types

| Type | Usage | Example |
|------|-------|---------|
| `str` | Text values, IDs, queries, URLs | `page_id`, `query`, `label` |
| `dict` | Structured data, JSON objects | `test_results`, `config` |
| `list` | Arrays, collections | `messages`, `items` |

**Special Case: JSON Strings**

For tools that accept JSON arrays or objects as strings, use type `str` with JSON-formatted value:

```yaml
state:
  pages_info:
    type: str
    value: '[{"TC_15_Page_A": "<h1>Page A Content</h1>"}, {"TC_15_Page_B": "<p>Page B Content</p>"}]'
  
  new_contents:
    type: str
    value: '["<p>Updated content for page 1</p>", "<p>Updated content for page 2</p>"]'
  
  new_labels:
    type: str
    value: '["test-label", "automation"]'
```

**Rules:**
1. Use type `str` (not `list` or `dict`) when the tool expects JSON as a string
2. Wrap the entire JSON in single quotes
3. Use double quotes for JSON property names and values
4. Escape special characters if needed

**Examples from converted tests:**
- CF15: Bulk create with pages_info JSON array
- CF19: Update with distinct bodies JSON array
- CF20: Update with shared body JSON array (single-element)
- CF21: Update labels with JSON array of label names

### State Variable Patterns

**Single Parameter Tools**:
```yaml
state:
  page_id:
    type: str
    value: "104038676"
  tool_result:
    type: str
  test_results:
    type: dict
```

**Multi-Parameter Tools**:
```yaml
state:
  method:
    type: str
    value: "GET"
  relative_url:
    type: str
    value: "/rest/api/space/AT"
  tool_result:
    type: str
  test_results:
    type: dict
```

**Tools with Complex Queries**:
```yaml
state:
  query:
    type: str
    value: "Template"
  tool_result:
    type: str
  test_results:
    type: dict
```

**Multi-Node Tests with Multiple Resources:**
```yaml
state:
  # Resource 1 parameters
  page_title_1:
    type: str
    value: "TC_Test_Page1"
  
  # Resource 2 parameters
  page_title_2:
    type: str
    value: "TC_Test_Page2"
  
  # Shared parameters
  space:
    type: str
    value: "AT"
  initial_body:
    type: str
    value: "<p>Initial content</p>"
  
  # ID storage for propagation
  page_ids:
    type: str
  
  # Standard output variables
  tool_result:
    type: str
  test_results:
    type: dict
```

**Key Rules for Multi-Node Tests:**
1. Number similar variables: `page_title_1`, `page_title_2`, etc.
2. Use shared variables for common values: `space`, `initial_body`
3. Include ID storage variables for state propagation: `page_ids`
4. Always include `tool_result` and `test_results`

### State Variable Naming

**Rules**:
- Use snake_case
- Match tool parameter names exactly
- Be descriptive but concise
- Avoid abbreviations unless standard (e.g., `url`, `id`)

**Examples**:
```
✅ page_id, query, label, relative_url
❌ pgId, q, lbl, relUrl
```

---

## Node Types & Patterns

### Toolkit Node (Node 1)

**Purpose**: Execute the tool being tested

**Standard Template**:
```yaml
- id: invoke_[tool_name]
  type: toolkit
  tool: [tool_name]                    # Exact tool name from toolkit
  toolkit_name: ${TOOLKIT_NAME}        # Environment variable reference
  input:
    - [param1]
    - [param2]
  input_mapping:
    [param1]:
      type: variable
      value: [param1]
    [param2]:
      type: variable
      value: [param2]
  output:
    - tool_result                      # ALWAYS output to tool_result
  structured_output: true              # ALWAYS true for toolkit nodes
  transition: process_results          # ALWAYS transition to validation
```

**Key Rules**:
1. Node ID format: `invoke_[tool_name]`
2. Tool name must match exactly (case-sensitive)
3. Always use `structured_output: true`
4. Always output to `tool_result`
5. Always transition to `process_results`

**Toolkit Name Reference**:
```yaml
# Preferred: Use environment variables
toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
toolkit_name: ${JIRA_TOOLKIT_NAME}
toolkit_name: ${GITHUB_TOOLKIT_NAME}

# Alternative: Hardcoded for local testing
toolkit_name: confluence-testing
toolkit_name: jira-testing
```

### LLM Node (Node 2)

**Purpose**: Validate tool output using LLM

**Standard Template**:
```yaml
- id: process_results
  type: llm
  model: gpt-4o                        # Standard model
  input:
    - tool_result
    - [other_variables_for_context]
  input_mapping:
    system:
      type: fixed
      value: "You are a quality assurance validator."
    task:
      type: fstring
      value: |
        [Validation prompt - see LLM Validation Pattern section]
    chat_history:
      type: fixed
      value: []
  output:
    - test_results                     # ALWAYS output to test_results
  structured_output_dict:
    test_results: "dict"               # ALWAYS dict type
  transition: END                      # ALWAYS end here
```

**Key Rules**:
1. Node ID: Always `process_results`
2. Model: Always `gpt-4o`
3. System prompt: Always "You are a quality assurance validator."
4. Always include `tool_result` in input
5. Always output to `test_results` as dict
6. Always transition to `END`

---

## Input/Output Mapping

### Input Mapping Types

#### 1. Variable Reference
**Use when**: Referencing a state variable

```yaml
input_mapping:
  page_id:
    type: variable
    value: page_id        # References state.page_id
```

**Parameter Name Mapping:**

When the tool parameter name differs from the state variable name, use the tool's parameter name in input_mapping:

```yaml
state:
  page_title:              # State variable name
    type: str
    value: "Test Page"

input_mapping:
  title:                   # Tool parameter name (different!)
    type: variable
    value: page_title      # References state variable
```

**Common Mappings:**
- State: `page_title` → Tool parameter: `title`
- State: `page_body` → Tool parameter: `body`
- State: `page_id` → Tool parameter: `page_id` (same name)
- State: `new_labels` → Tool parameter: `new_labels` (same name)

**Rule:** Always use the exact tool parameter name in `input_mapping`, but reference the state variable name in the `value` field.

#### 2. Fixed Value
**Use when**: Hardcoding a value that doesn't change

```yaml
input_mapping:
  system:
    type: fixed
    value: "You are a quality assurance validator."
  
  chat_history:
    type: fixed
    value: []
  
  status:
    type: fixed
    value: "current"
```

#### 3. F-String Template
**Use when**: Composing text with variable substitution

```yaml
input_mapping:
  task:
    type: fstring
    value: |
      Analyze the output from the tool.
      
      Tool Result: {tool_result}
      Query: {query}
      Page ID: {page_id}
```

**F-String Rules**:
- Use `{variable_name}` for substitution
- Variables must exist in `input` list
- Multi-line strings use `|` for literal block scalar
- Preserve indentation for readability

### Output Mapping

#### Toolkit Node Output
```yaml
output:
  - tool_result              # ALWAYS this exact variable name
structured_output: true      # ALWAYS true
```

#### LLM Node Output
```yaml
output:
  - test_results             # ALWAYS this exact variable name
structured_output_dict:
  test_results: "dict"       # ALWAYS dict type
```

#### ID Resolution Node Output
```yaml
output:
  - page_ids                 # Store extracted IDs for later use
structured_output: true
```

**Rules**:
- Toolkit nodes: Use `structured_output: true`
- LLM nodes: Use `structured_output_dict` with type specification
- Variable names must match state definitions
- ID resolution nodes output to specific ID storage variables (e.g., `page_ids`)

### Empty Input Arrays

**For cleanup nodes with only fixed values:**

When all input_mapping values are `type: fixed`, you can use an empty input array:

```yaml
- id: cleanup_delete_page_a
  type: toolkit
  tool: delete_page
  input: []                  # Empty - no state variables needed
  input_mapping:
    page_title:
      type: fixed
      value: "TC_15_Page_A"  # Using fixed value only
  output:
    - tool_result
  structured_output: true
  transition: END
```

**When to use empty input array:**
- All parameters use `type: fixed`
- No state variables are referenced
- Hardcoded cleanup targets

**When to use populated input array:**
- Any parameter uses `type: variable`
- State variables are referenced
- Dynamic values needed

---

## LLM Validation Pattern

### Standard Validation Prompt Template

```yaml
task:
  type: fstring
  value: |
    Analyze the output from the '[tool_name]' tool.
    
    Tool Result: {tool_result}
    [Additional Context Variables]: {var_name}
    
    Perform the following checks:
    
    1. Confirm the tool executed successfully (the result is not empty or null).
    2. [Specific validation check 1 - describe expected behavior]
    3. [Specific validation check 2 - describe expected data structure]
    4. [Specific validation check 3 - describe expected values]
    N. [Additional checks as needed]
    
    Return a JSON object named test_results with the following structure:
    
    {{
      "test_passed": boolean (true if all checks pass),
      "tool_executed": boolean (true if tool ran without errors),
      "[specific_field_1]": type (description of what this validates),
      "[specific_field_2]": type (description of what this validates),
      "failed_checks": [string] // list of failed assertion descriptions
    }}
    
    Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
    Do not use markdown ```json when returning the json.
    Do not include any explanations, summaries, or additional text.
```

### Validation Checks Structure

**Pattern**: Numbered list, increasing specificity

**Always Include**:
1. ✅ Tool execution success check (result not empty/null)
2. ✅ Output format validation
3. ✅ Data structure validation
4. ✅ Content validation
5. ✅ Count/quantity validation (if applicable)

**Examples**:

**For Search/List Operations**:
```
1. Confirm the tool executed successfully.
2. Verify the output contains search results.
3. Check if results have valid structure (page_id, page_title, page_url).
4. Count the number of results returned.
5. Validate each result has required fields.
```

**For CRUD Operations**:
```
1. Confirm the tool executed successfully.
2. Verify the output contains confirmation message.
3. Check if operation details are present (id, title, status).
4. Validate the returned data matches expected format.
```

**For Read Operations**:
```
1. Confirm the tool executed successfully.
2. Verify the output contains content data.
3. Check if content has expected format (markdown/text/json).
4. Validate content length is reasonable (not empty).
5. Check for presence of expected fields/keywords.
```

**For Create Operations**:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output contains success message "The page '[title]' was created".
3. Check if output includes details object with keys: title, id, space key, author, link.
4. Extract the page ID from the details for cleanup (if needed).
5. Validate all required fields are present in the response.
```

**For Bulk Create Operations**:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output is a stringified list with per-page success messages.
3. Check if each message includes page details (title, id, space key, author, link).
4. Count the number of pages created (should match expected count).
5. Validate all pages have success confirmations.
```

**For Update Operations**:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output contains "was updated successfully" message.
3. Check if output includes a web UI link.
4. Validate the update was applied (via title/ID resolution).
5. Ensure no "Page with title ... not found" error message.
```

**For Bulk Update Operations**:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output is a stringified list with per-page status messages.
3. Check if each status contains "was updated successfully".
4. Count the number of pages updated (should match expected count).
5. Validate all pages have success confirmations.
```

**For Delete Operations**:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output contains success message with page ID.
3. Check if message states "Page with ID ... has been successfully deleted."
4. Validate the tool resolved page_title to page_id correctly (if applicable).
5. Ensure deletion was successful.
```

### Test Results JSON Structure

**Required Fields** (ALWAYS include):
```json
{
  "test_passed": boolean,        // Overall pass/fail
  "tool_executed": boolean,      // Tool ran without errors
  "failed_checks": [string]      // List of failed checks
}
```

**Tool-Specific Fields** (add as needed):

**For Search/List Tools**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "results_found": boolean,
  "result_count": integer,
  "has_valid_structure": boolean,
  "sample_page_title": string,
  "failed_checks": [string]
}
```

**For Read/Get Tools**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "has_content": boolean,
  "content_length": integer,
  "has_valid_format": boolean,
  "content_preview": string,
  "failed_checks": [string]
}
```

**For CRUD Tools**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "operation_successful": boolean,
  "has_details": boolean,
  "returned_id": string,
  "failed_checks": [string]
}
```

**For Create Operations with Cleanup**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "has_success_message": boolean,
  "has_details": boolean,
  "page_id": string,              // For potential ID extraction
  "page_created": boolean,
  "failed_checks": [string]
}
```

**For Bulk Operations**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "is_list_format": boolean,      // Verify list/array response
  "pages_created_count": integer,  // or pages_updated_count
  "all_have_details": boolean,
  "expected_count": integer,      // Expected number of operations
  "failed_checks": [string]
}
```

**For Update/Delete Operations**:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "has_success_message": boolean,
  "has_page_id": boolean,         // For operations resolving IDs
  "page_updated": boolean,        // or page_deleted
  "has_web_link": boolean,        // For update confirmations
  "failed_checks": [string]
}
```

**Key Patterns:**
1. Always include `test_passed` (boolean) and `failed_checks` (array)
2. Add `expected_count` for bulk operations to validate completeness
3. Include ID extraction fields when cleanup depends on created resources
4. Add operation-specific booleans: `page_created`, `page_updated`, `page_deleted`

### Critical Validation Instructions

**ALWAYS include at the end of validation prompt**:
```
Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
Do not use markdown ```json when returning the json.
Do not include any explanations, summaries, or additional text.
```

**Why**: Ensures LLM returns only parseable JSON, no markdown formatting or extra text

---

## Test Atomicity Principles

### What is Test Atomicity?

**Definition**: Each test validates exactly ONE tool operation with ONE clear purpose.

### ✅ GOOD - Atomic Tests

**Single Tool, Single Operation**:
```yaml
# ✅ Tests ONE thing: retrieving page tree
name: "CF01 - Get Page Tree with Descendants"
tool: get_page_tree

# ✅ Tests ONE thing: searching pages by query
name: "CF04 - Search Pages"
tool: search_pages

# ✅ Tests ONE thing: reading a page by ID
name: "CF03 - Read Page by ID"
tool: read_page_by_id
```

**Clear Validation**:
- One primary assertion
- Supporting validations for data structure
- No multi-step workflows

### ⚠️ ACCEPTABLE - Coupled Operations

**When operations are inherently linked**:
```yaml
# ⚠️ ACCEPTABLE: Create requires cleanup
name: "CF07 - Create and Delete Page"
# Node 1: Create page
# Node 2: Validate creation
# Node 3: Delete page (cleanup)
```

**Rules for Coupled Tests**:
- Operations must be logically dependent
- Primary operation is tested, secondary is cleanup/setup
- Maximum 3 nodes (setup/action/cleanup)

**New Pattern: Multi-Step Operations (4-7 nodes)**

**Acceptable for complex workflows**:
```yaml
# ⚠️ ACCEPTABLE: Multi-step with setup and cleanup
name: "CF19 - Bulk Update Pages with Distinct Bodies"
# Nodes: setup_1 → setup_2 → get_id → invoke_update → validate → cleanup_1 → cleanup_2
```

**Rules for Multi-Step Tests:**
- Primary operation must be clear (e.g., "update_pages")
- Setup nodes are for creating test data
- Cleanup nodes are for removing test data
- ID resolution nodes are for state propagation
- Maximum recommended: 7 nodes (2 setup + 1 ID + 1 action + 1 validate + 2 cleanup)
- Each node has single, clear responsibility

**Cleanup Best Practices:**

1. **Always cleanup in reverse order of creation:**
```yaml
setup_create_page_1 → setup_create_page_2 → ... → cleanup_delete_page_1 → cleanup_delete_page_2
```

2. **Use descriptive cleanup node names:**
```yaml
cleanup_delete_page          # Single cleanup
cleanup_delete_page_1        # First cleanup (in sequence)
cleanup_delete_child_a       # Specific resource cleanup
```

3. **Cleanup nodes don't need validation:**
```yaml
- id: cleanup_delete_page
  type: toolkit
  tool: delete_page
  # No process_results needed - just clean up
  output:
    - tool_result
  structured_output: true
  transition: END  # or next cleanup
```

4. **Use fixed values for known cleanup targets:**
```yaml
- id: cleanup_delete_page_a
  input: []
  input_mapping:
    page_title:
      type: fixed
      value: "TC_15_Page_A"  # Hardcoded cleanup target
```

### ❌ AVOID - Non-Atomic Tests

**Multiple Unrelated Operations**:
```yaml
# ❌ BAD: Tests multiple unrelated operations
name: "CF-BAD - Create, Update, Search, and Delete Page"
# Too many operations, unclear primary purpose

# ❌ BAD: Primitive test with no real validation
name: "CF-BAD - Open Page"
# Expected: "Page is opened" - too simple, no value
```

**Why Avoid**:
- Hard to debug failures
- Unclear test purpose
- Brittle (one failure breaks entire test)
- Poor maintainability

### Atomicity Checklist

Before creating a test, verify:
- [ ] Tests exactly ONE tool
- [ ] Has ONE clear validation goal
- [ ] Failure reason would be immediately obvious
- [ ] Can run independently of other tests
- [ ] Name clearly states what is being tested
- [ ] Validation checks are focused on the tool operation

---

## Conversion Workflow

### Step 1: Analyze Source MD File

**Extract Key Information**:
1. Tool name (from Objective section)
2. Input parameters (from Test Data Configuration)
3. Expected output (from Test Steps & Expectations)
4. Validation criteria (from Expectation statements)

**Example MD Analysis**:
```markdown
# Site Search                          → Tool: site_search
## Objective
Verify that the `site_search` tool... → Tool name: site_search

### Settings
| **Query** | `test` |               → Input: query="test"

### Step 2: Verify the Output
The output is a string containing...  → Expected: string with page data
separated by `---` for each result.   → Validation: check for --- delimiter
```

### Step 2: Define State Variables

**From MD → YAML State**:
```markdown
| **Page ID** | `104038676` |
| **Query** | `test` |
```

Converts to:
```yaml
state:
  page_id:
    type: str
    value: "104038676"
  query:
    type: str
    value: "test"
  tool_result:
    type: str
  test_results:
    type: dict
```

### Step 3: Create Toolkit Node

**Template**:
```yaml
- id: invoke_[tool_name_from_md]
  type: toolkit
  tool: [exact_tool_name]
  toolkit_name: ${TOOLKIT_NAME}
  input:
    - [list_all_parameters]
  input_mapping:
    [param]:
      type: variable
      value: [param]
  output:
    - tool_result
  structured_output: true
  transition: process_results
```

### Step 4: Create Validation Checks

**From MD Expectations → Validation Checks**:

MD:
```markdown
**Expectation:** The tool runs without errors and returns page information.
**Expectation:** The output contains page details including page_id, page_title.
**Expectation:** Content field must be not blank.
```

Converts to:
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output contains page information.
3. Check if pages have valid structure (page_id, page_title fields).
4. Validate content field is not blank.
```

### Step 5: Define Test Results Structure

**From Validation Checks → JSON Fields**:

Checks:
```
1. Tool executed successfully
2. Output contains page information
3. Valid structure (page_id, page_title)
4. Content not blank
```

Converts to:
```json
{
  "test_passed": boolean,
  "tool_executed": boolean,
  "has_page_info": boolean,
  "has_valid_structure": boolean,
  "content_not_blank": boolean,
  "failed_checks": [string]
}
```

### Step 6: Assemble Complete YAML

**Combine all elements**:
1. Metadata (name, description)
2. Toolkits reference
3. State block
4. Entry point
5. Toolkit node
6. LLM validation node

### Step 7: Validate and Test

**Pre-submission Checklist**:
- [ ] File name follows convention
- [ ] All state variables defined
- [ ] Toolkit node has structured_output: true
- [ ] LLM node has structured_output_dict
- [ ] Validation prompt has critical instructions
- [ ] Test results JSON structure is complete
- [ ] Transitions are correct (toolkit→process_results→END)
- [ ] No syntax errors (proper YAML indentation)

---

## Examples & Templates

### Template 1: Single Parameter Read Operation

```yaml
name: "CF03 - Read Page by ID"
description: "Verify read_page_by_id tool retrieves page content using page ID"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  page_id:
    type: str
    value: "104038676"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_read_page_by_id

nodes:
  - id: invoke_read_page_by_id
    type: toolkit
    tool: read_page_by_id
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - page_id
    input_mapping:
      page_id:
        type: variable
        value: page_id
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - page_id
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'read_page_by_id' tool.
          
          Tool Result: {tool_result}
          Page ID: {page_id}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output contains page content in text/markdown format.
          3. Check if content length is reasonable (not empty).
          4. Validate the content has expected structure.
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if all checks pass),
            "tool_executed": boolean (true if tool ran without errors),
            "has_content": boolean (true if result contains content),
            "content_length": integer (length of content in characters),
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: END
```

### Template 2: Search/List Operation

```yaml
name: "CF04 - Search Pages"
description: "Verify search_pages tool searches for pages by query text in title or content"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  query:
    type: str
    value: "Template"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_search_pages

nodes:
  - id: invoke_search_pages
    type: toolkit
    tool: search_pages
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - query
    input_mapping:
      query:
        type: variable
        value: query
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - query
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'search_pages' tool.
          
          Tool Result: {tool_result}
          Query: {query}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output contains search results with page information.
          3. Check if pages were found matching the search query.
          4. Count the number of pages in the search results.
          5. Validate that each result has page details (page_id, page_title, page_url).
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if tool executed and returned valid search results),
            "tool_executed": boolean (true if tool ran without errors),
            "results_found": boolean (true if at least one page was returned),
            "result_count": integer (number of pages in search results),
            "has_valid_structure": boolean (true if results have required fields),
            "sample_page_title": string (title of first page found, or null if none),
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: END
```

### Template 3: Multi-Parameter API Operation

```yaml
name: "CF13 - Execute Generic Confluence API"
description: "Verify execute_generic_confluence tool executes generic Confluence REST API calls"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  method:
    type: str
    value: "GET"
  relative_url:
    type: str
    value: "/rest/api/space/AT"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_execute_generic_confluence

nodes:
  - id: invoke_execute_generic_confluence
    type: toolkit
    tool: execute_generic_confluence
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - method
      - relative_url
    input_mapping:
      method:
        type: variable
        value: method
      relative_url:
        type: variable
        value: relative_url
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - method
      - relative_url
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'execute_generic_confluence' tool.
          
          Tool Result: {tool_result}
          Method: {method}
          Relative URL: {relative_url}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output is formatted as: "HTTP: {{method}}{{url}} -> {{status_code}}...".
          3. Check if the HTTP status code is successful (200).
          4. Validate the response contains valid API data.
          5. Ensure the method and URL are correctly reflected in the response.
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if tool executed and returned successful API response),
            "tool_executed": boolean (true if tool ran without errors),
            "has_valid_format": boolean (true if output follows expected format),
            "status_code": string (extracted HTTP status code, e.g., "200"),
            "is_successful": boolean (true if status code is 200),
            "has_response_data": boolean (true if response contains data),
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: END
```

### Template 4: Create Operation with Cleanup

```yaml
name: "CF14 - Create Page with Wiki Representation"
description: "Verify create_page creates page with wiki representation and returns success"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  space:
    type: str
    value: "AT"
  page_title:
    type: str
    value: "TC_14_AutoTest_Page"
  page_body:
    type: str
    value: "# Test Page\n\nMarkdown content."
  status:
    type: str
    value: "current"
  representation:
    type: str
    value: "wiki"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_create_page

nodes:
  - id: invoke_create_page
    type: toolkit
    tool: create_page
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - space
      - page_title
      - page_body
      - status
      - representation
    input_mapping:
      space:
        type: variable
        value: space
      title:
        type: variable
        value: page_title
      body:
        type: variable
        value: page_body
      status:
        type: variable
        value: status
      representation:
        type: variable
        value: representation
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - page_title
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'create_page' tool.
          
          Tool Result: {tool_result}
          Page Title: {page_title}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output contains success message "The page '{page_title}' was created".
          3. Check if output includes details object with keys: title, id, space key, author, link.
          4. Validate all required fields are present in the response.
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if page created successfully),
            "tool_executed": boolean (true if tool ran without errors),
            "has_success_message": boolean (true if success message present),
            "has_details": boolean (true if details object present),
            "page_created": boolean (true if page was created),
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: cleanup_delete_page

  - id: cleanup_delete_page
    type: toolkit
    tool: delete_page
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - page_title
    input_mapping:
      page_title:
        type: variable
        value: page_title
    output:
      - tool_result
    structured_output: true
    transition: END
```

### Template 5: Bulk Operation with Multiple Cleanup

```yaml
name: "CF15 - Bulk Create Pages from JSON"
description: "Verify create_pages creates multiple pages from JSON list"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  space:
    type: str
    value: "AT"
  pages_info:
    type: str
    value: '[{"Page_A": "<h1>A</h1>"}, {"Page_B": "<p>B</p>"}]'
  status:
    type: str
    value: "current"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_create_pages

nodes:
  - id: invoke_create_pages
    type: toolkit
    tool: create_pages
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - space
      - pages_info
      - status
    input_mapping:
      space:
        type: variable
        value: space
      pages_info:
        type: variable
        value: pages_info
      status:
        type: variable
        value: status
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - pages_info
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'create_pages' tool.
          
          Tool Result: {tool_result}
          Pages Info: {pages_info}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output is a stringified list with per-page success messages.
          3. Check if each message includes page details (title, id, space key, author, link).
          4. Count the number of pages created (should be 2).
          5. Validate all pages have success confirmations.
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if all pages created successfully),
            "tool_executed": boolean (true if tool ran without errors),
            "is_list_format": boolean (true if output is list format),
            "pages_created_count": integer (number of pages created),
            "all_have_details": boolean (true if all pages have detail keys),
            "expected_count": 2,
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: cleanup_delete_page_a

  - id: cleanup_delete_page_a
    type: toolkit
    tool: delete_page
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input: []
    input_mapping:
      page_title:
        type: fixed
        value: "Page_A"
    output:
      - tool_result
    structured_output: true
    transition: cleanup_delete_page_b

  - id: cleanup_delete_page_b
    type: toolkit
    tool: delete_page
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input: []
    input_mapping:
      page_title:
        type: fixed
        value: "Page_B"
    output:
      - tool_result
    structured_output: true
    transition: END
```

```yaml
name: "CF13 - Execute Generic Confluence API"
description: "Verify execute_generic_confluence tool executes generic Confluence REST API calls"

toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

state:
  method:
    type: str
    value: "GET"
  relative_url:
    type: str
    value: "/rest/api/space/AT"
  tool_result:
    type: str
  test_results:
    type: dict

entry_point: invoke_execute_generic_confluence

nodes:
  - id: invoke_execute_generic_confluence
    type: toolkit
    tool: execute_generic_confluence
    toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
    input:
      - method
      - relative_url
    input_mapping:
      method:
        type: variable
        value: method
      relative_url:
        type: variable
        value: relative_url
    output:
      - tool_result
    structured_output: true
    transition: process_results

  - id: process_results
    type: llm
    model: gpt-4o
    input:
      - tool_result
      - method
      - relative_url
    input_mapping:
      system:
        type: fixed
        value: "You are a quality assurance validator."
      task:
        type: fstring
        value: |
          Analyze the output from the 'execute_generic_confluence' tool.
          
          Tool Result: {tool_result}
          Method: {method}
          Relative URL: {relative_url}
          
          Perform the following checks:
          
          1. Confirm the tool executed successfully (the result is not empty or null).
          2. Verify the output is formatted as: "HTTP: {{method}}{{url}} -> {{status_code}}...".
          3. Check if the HTTP status code is successful (200).
          4. Validate the response contains valid API data.
          5. Ensure the method and URL are correctly reflected in the response.
          
          Return a JSON object named test_results with the following structure:
          
          {{
            "test_passed": boolean (true if tool executed and returned successful API response),
            "tool_executed": boolean (true if tool ran without errors),
            "has_valid_format": boolean (true if output follows expected format),
            "status_code": string (extracted HTTP status code, e.g., "200"),
            "is_successful": boolean (true if status code is 200),
            "has_response_data": boolean (true if response contains data),
            "failed_checks": [string] // list of failed assertions
          }}
          
          Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
          Do not use markdown ```json when returning the json.
          Do not include any explanations, summaries, or additional text.
      chat_history:
        type: fixed
        value: []
    output:
      - test_results
    structured_output_dict:
        test_results: "dict"
    transition: END
```

---

## Common Pitfalls

### ❌ Pitfall 1: Inconsistent Variable Names

**Problem**:
```yaml
state:
  pageId:        # Camel case
    type: str
input_mapping:
  page_id:       # Snake case - MISMATCH!
    type: variable
    value: pageId
```

**Solution**: Use snake_case consistently
```yaml
state:
  page_id:
    type: str
input_mapping:
  page_id:
    type: variable
    value: page_id
```

### ❌ Pitfall 2: Missing structured_output

**Problem**:
```yaml
- id: invoke_get_page
  type: toolkit
  output:
    - tool_result
  # Missing: structured_output: true
```

**Solution**: Always add structured_output
```yaml
- id: invoke_get_page
  type: toolkit
  output:
    - tool_result
  structured_output: true  # ✅ Required
```

### ❌ Pitfall 3: Wrong Output Type for LLM Node

**Problem**:
```yaml
- id: process_results
  type: llm
  output:
    - test_results
  structured_output: true  # ❌ Wrong for LLM nodes
```

**Solution**: Use structured_output_dict for LLM
```yaml
- id: process_results
  type: llm
  output:
    - test_results
  structured_output_dict:  # ✅ Correct
    test_results: "dict"
```

### ❌ Pitfall 4: Incorrect Transition Chain

**Problem**:
```yaml
nodes:
  - id: invoke_tool
    transition: END      # ❌ Skips validation!
  
  - id: process_results
    transition: END
```

**Solution**: Proper transition flow
```yaml
nodes:
  - id: invoke_tool
    transition: process_results  # ✅ Go to validation
  
  - id: process_results
    transition: END              # ✅ End after validation
```

### ❌ Pitfall 5: Missing Critical Validation Instructions

**Problem**:
```yaml
task:
  value: |
    Validate the output.
    Return test_results JSON.
    # ❌ Missing critical instructions
```

**Solution**: Always include complete instructions
```yaml
task:
  value: |
    Validate the output.
    
    Return a JSON object named test_results...
    
    Return **EXACTLY** **NONNEGOTIATABLE** only the `test_results` JSON object.
    Do not use markdown ```json when returning the json.
    Do not include any explanations, summaries, or additional text.
```

### ❌ Pitfall 6: Undefined Variables in Input

**Problem**:
```yaml
input:
  - tool_result
  - query
input_mapping:
  task:
    type: fstring
    value: "Result: {tool_result}, ID: {page_id}"
    # ❌ page_id not in input list!
```

**Solution**: Include all variables used in fstring
```yaml
input:
  - tool_result
  - query
  - page_id      # ✅ Added
input_mapping:
  task:
    type: fstring
    value: "Result: {tool_result}, ID: {page_id}"
```

### ❌ Pitfall 7: Non-Atomic Tests

**Problem**:
```yaml
name: "CF-BAD - Create, Update, Search and Delete Page"
# Too many operations, unclear purpose
```

**Solution**: Split into atomic tests
```yaml
name: "CF07 - Create and Delete Page"      # Acceptable (create+cleanup)
name: "CF10 - Update Page by ID"           # Atomic
name: "CF04 - Search Pages"                # Atomic
```

### ❌ Pitfall 8: Incorrect Input Array with Fixed Values

**Problem**:
```yaml
- id: cleanup_delete_page
  input:
    - page_title           # ❌ Not needed for fixed values
  input_mapping:
    page_title:
      type: fixed
      value: "Test_Page"
```

**Solution**: Use empty input array for fixed-only mappings
```yaml
- id: cleanup_delete_page
  input: []                # ✅ Empty when all values are fixed
  input_mapping:
    page_title:
      type: fixed
      value: "Test_Page"
```

### ❌ Pitfall 9: Inconsistent Cleanup Ordering

**Problem**:
```yaml
nodes:
  - setup_create_page_1
  - setup_create_page_2
  - invoke_tool
  - cleanup_delete_page_2  # ❌ Wrong order!
  - cleanup_delete_page_1
```

**Solution**: Cleanup in reverse order of creation
```yaml
nodes:
  - setup_create_page_1
  - setup_create_page_2
  - invoke_tool
  - cleanup_delete_page_1  # ✅ Reverse order
  - cleanup_delete_page_2
```

### ❌ Pitfall 10: Missing ID Storage Variable

**Problem**:
```yaml
state:
  page_title_1: {type: str, value: "Page1"}
  page_title_2: {type: str, value: "Page2"}
  # ❌ Missing page_ids for ID storage

nodes:
  - id: get_page_id_1
    output:
      - page_ids           # ❌ Not defined in state!
```

**Solution**: Define ID storage in state
```yaml
state:
  page_title_1: {type: str, value: "Page1"}
  page_title_2: {type: str, value: "Page2"}
  page_ids: {type: str}    # ✅ Defined for ID storage
  
nodes:
  - id: get_page_id_1
    output:
      - page_ids           # ✅ Now defined in state
```

### ❌ Pitfall 11: JSON String Formatting Errors

**Problem**:
```yaml
state:
  pages_info:
    type: str
    value: "[{"title": "Page"}]"  # ❌ Nested quotes issue
```

**Solution**: Use single quotes for outer string, double quotes for JSON
```yaml
state:
  pages_info:
    type: str
    value: '[{"title": "Page"}]'  # ✅ Correct formatting
```

### ❌ Pitfall 12: Parameter Name Mismatch

**Problem**:
```yaml
state:
  page_title: {type: str, value: "Test"}

input_mapping:
  page_title:              # ❌ Should be 'title' (tool parameter)
    type: variable
    value: page_title
```

**Solution**: Use tool parameter name in mapping
```yaml
state:
  page_title: {type: str, value: "Test"}

input_mapping:
  title:                   # ✅ Tool parameter name
    type: variable
    value: page_title      # ✅ State variable name
```

---

## Standards & Best Practices

### YAML Formatting Standards

**Indentation**: 2 spaces (not tabs)
```yaml
state:
  page_id:        # 2 spaces
    type: str     # 4 spaces
```

**String Quoting**:
- Use quotes for values with special characters
- Use quotes for numeric strings (IDs)
- Use bare strings for simple words

```yaml
✅ value: "104038676"        # Quoted numeric string
✅ value: "GET"              # Quoted uppercase
✅ value: test-label         # Bare string OK
✅ value: |                  # Multi-line literal
    Long text here
```

**List Formatting**:
```yaml
input:
  - page_id
  - query
```

**Dict Formatting**:
```yaml
state:
  page_id:
    type: str
    value: "123"
```

### Documentation Standards

**Inline Comments**: Use sparingly, prefer clear naming
```yaml
# ✅ Good: Explains non-obvious behavior
# Convert matrix array to space-separated list
SUITES=$(echo ...)

# ❌ Bad: States the obvious
page_id: "123"  # This is the page ID
```

**Validation Check Comments**: Number and describe clearly
```
1. Confirm the tool executed successfully (the result is not empty or null).
2. Verify the output contains search results with page information.
```

### Environment Variable Standards

**Naming**:
```yaml
${CONFLUENCE_TOOLKIT_ID}      # ✅ Uppercase, descriptive
${CONFLUENCE_TOOLKIT_NAME}    # ✅ Consistent pattern
${JIRA_TOOLKIT_ID}            # ✅ Toolkit-specific
```

**Usage Pattern**:
```yaml
toolkits:
  - id: ${CONFLUENCE_TOOLKIT_ID}
    name: ${CONFLUENCE_TOOLKIT_NAME}

nodes:
  - toolkit_name: ${CONFLUENCE_TOOLKIT_NAME}
```

---

## Conversion Checklist

Use this checklist for every conversion:

### Pre-Conversion
- [ ] Read and understand source MD test case
- [ ] Identify tool name and parameters
- [ ] Identify expected output and validation criteria
- [ ] Determine if test is atomic (single operation)
- [ ] Check if similar tests exist for reference

### During Conversion
- [ ] Choose appropriate sequential number
- [ ] Create file with correct naming convention
- [ ] Define all required state variables
- [ ] Set correct initial values from MD
- [ ] Create toolkit node with proper structure
- [ ] Map all input parameters correctly
- [ ] Create validation node with comprehensive checks
- [ ] Define complete test_results JSON structure
- [ ] Include critical validation instructions

### Post-Conversion
- [ ] Verify YAML syntax is valid
- [ ] Check all variable references are defined
- [ ] Confirm transitions are correct
- [ ] Validate structured_output settings
- [ ] Review validation checks completeness
- [ ] Test locally if possible
- [ ] Update conversion tracking document

---

## Quick Reference Card

### File Structure
```
test_case_XX_[operation].yaml
```

### Minimal Valid Pipeline
```yaml
name: "CFXX - [Description]"
description: "Verify [tool] tool [what it does]"

toolkits:
  - id: ${TOOLKIT_ID}
    name: ${TOOLKIT_NAME}

state:
  [param]: {type: str, value: "..."}
  tool_result: {type: str}
  test_results: {type: dict}

entry_point: invoke_[tool]

nodes:
  - id: invoke_[tool]
    type: toolkit
    tool: [tool_name]
    toolkit_name: ${TOOLKIT_NAME}
    input: [[param]]
    input_mapping:
      [param]: {type: variable, value: [param]}
    output: [tool_result]
    structured_output: true
    transition: process_results
    
  - id: process_results
    type: llm
    model: gpt-4o
    input: [tool_result]
    input_mapping:
      system: {type: fixed, value: "You are a quality assurance validator."}
      task: {type: fstring, value: "[validation prompt]"}
      chat_history: {type: fixed, value: []}
    output: [test_results]
    structured_output_dict: {test_results: "dict"}
    transition: END
```

### Critical Elements Checklist
- [ ] `structured_output: true` on toolkit node
- [ ] `structured_output_dict` on LLM node
- [ ] `tool_result` and `test_results` in state
- [ ] Transitions: toolkit → process_results → END
- [ ] Critical validation instructions at end of prompt
- [ ] `test_passed` and `failed_checks` in JSON

---

## Conclusion

Following these standards ensures:
- ✅ **Consistency**: All tests follow same patterns
- ✅ **Maintainability**: Easy to understand and modify
- ✅ **Debuggability**: Clear failure points
- ✅ **Reliability**: Deterministic results
- ✅ **Scalability**: Easy to add new tests

**Remember**: Quality over quantity. A well-structured atomic test is more valuable than multiple poorly designed tests.

**When in doubt**: Refer to existing converted tests as examples and follow the two-node pattern strictly.

---

## Lessons Learned from CF14-CF21 Conversions

### What Works Well ✅

1. **Simple CRUD with Cleanup (3 nodes)**
   - Pattern: create → validate → cleanup
   - Success rate: 100% (CF14, CF15, CF16)
   - Best for: Create operations that need cleanup

2. **Read-Only Operations (2 nodes)**
   - Pattern: invoke → validate
   - Success rate: 100% (CF11, CF12, CF13)
   - Best for: Search, get, list operations

3. **Bulk Operations with Fixed Cleanup**
   - Multiple cleanup nodes with hardcoded targets
   - Success rate: 100% when pages don't need ID resolution
   - Best for: Known test data with predictable names

### Challenges Encountered ⚠️

1. **Multi-Step ID Resolution Tests**
   - Pattern: create → create → get_id → update → cleanup
   - Success rate: 0% (CF19, CF20, CF21)
   - Issue: Page ID extraction and propagation between nodes
   - Recommendation: Simplify or add intermediate validation

2. **Create-Update-Delete Chains**
   - Pattern: create → update → validate → cleanup
   - Success rate: 0% (CF18)
   - Issue: Update operations not finding recently created pages
   - Recommendation: Add wait/verification between create and update

3. **Validation Logic Edge Cases**
   - One test returned `test_passed: None` (CF17)
   - Issue: Validation prompt didn't handle all response formats
   - Recommendation: Always ensure boolean return for test_passed

### Key Takeaways

1. **Simpler is Better**: 2-3 node tests have 100% success rate
2. **State Propagation is Tricky**: ID resolution between nodes needs careful handling
3. **Cleanup is Essential**: Always clean up created resources
4. **Reverse Order Cleanup**: Delete in reverse order of creation
5. **Fixed Values for Cleanup**: Use hardcoded values when possible
6. **JSON Strings**: Remember to use type `str` for JSON-formatted parameters
7. **Parameter Mapping**: Tool parameter names may differ from state variable names

### Recommendations for Future Conversions

1. **Start Simple**: Begin with 2-node read operations
2. **Add Cleanup Gradually**: Move to 3-node create+cleanup tests
3. **Avoid Complex Chains**: Keep multi-step tests under 5 nodes if possible
4. **Test Incrementally**: Run tests after each conversion to catch issues early
5. **Document Failures**: Track failing patterns to improve conversion guide
6. **Use Templates**: Leverage provided templates for consistency

---

## Version History

- **v1.0** (2026-01-28): Initial comprehensive guide based on Confluence, Jira, and GitHub toolkit test analysis
- **v1.1** (2026-01-29): Enhanced with multi-node patterns, cleanup strategies, JSON string handling, parameter mapping rules, and lessons learned from CF14-CF21 conversion experience
