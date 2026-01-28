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

**Rules**:
- Toolkit nodes: Use `structured_output: true`
- LLM nodes: Use `structured_output_dict` with type specification
- Variable names must match state definitions

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

## Version History

- v1.0 (2026-01-28): Initial comprehensive guide based on Confluence, Jira, and GitHub toolkit test analysis
