# Pipeline State Retrieval Tests

Test pipelines for verifying state variable handling in code nodes, specifically testing the base64 encoding fix for passing state from Python to Pyodide sandbox.

## Test Cases

| Test | File | Description |
|------|------|-------------|
| 1 | `test_case_1_basic_types.yaml` | Basic types (str, int, float, bool) |
| 2 | `test_case_2_multiline_strings.yaml` | Multiline strings with newlines |
| 3 | `test_case_3_special_characters.yaml` | Special characters, quotes, unicode, regex |
| 4 | `test_case_4_nested_structures.yaml` | Nested lists and dicts |
| 5 | `test_case_5_json_strings.yaml` | JSON strings within state (not auto-parsed) |
| 6 | `test_case_6_llm_code_blocks.yaml` | LLM output with markdown code blocks |
| 7 | `test_case_7_empty_null_values.yaml` | Empty strings, lists, dicts, and null |
| 8 | `test_case_8_combined_pipeline.yaml` | Full integration (LLM + code nodes) |
| 9 | `test_case_9_code_from_variable.yaml` | Code stored in state variable (`code.type: variable`) |
| 10 | `test_case_10_large_strings.yaml` | Large string payloads (JSON, HTML) |
| 11 | `test_case_11_alita_client_access.yaml` | `alita_client` access from code nodes |

## Running Tests

1. Create a new Pipeline in the platform
2. Copy the YAML content from a test case file into the pipeline configuration
3. Run the pipeline and verify the output shows `test_passed: true`

## Key Fixes Tested

These tests verify the following fixes in `alita_sdk`:

- **Base64 encoding** for state injection into Pyodide (avoids string escaping issues)
- **Type preservation** for `type: str` values (prevents auto-parsing of JSON-like strings)
- **Multiline string handling** with proper newline preservation
- **Large payload support** for API responses and HTML content
- **`alita_client` availability** in code execution context

## Test Case Details

### Test Case 1: Basic Types
Verifies primitive types are correctly passed to code nodes:
- String values
- Integer values
- Float values
- Boolean values

### Test Case 2: Multiline Strings
Tests the main bug fix - newlines in strings must be preserved:
- Code snippets with indentation
- Multi-line text blocks
- Verifies `\n` characters are actual newlines, not escaped strings

### Test Case 3: Special Characters
Tests edge cases with character escaping:
- SQL queries with single and double quotes
- Windows file paths with backslashes
- Unicode text (Cyrillic, Chinese, emoji)
- Regex patterns with escape sequences

### Test Case 4: Nested Structures
Verifies complex data structures:
- Dictionaries with nested keys
- Lists with mixed types
- Nested dicts inside lists
- Deep object traversal

### Test Case 5: JSON Strings
Critical test for type preservation:
- JSON strings declared as `type: str` must remain strings
- Should NOT be auto-parsed into dicts by `ast.literal_eval()`
- Manual `json.loads()` should work on the string values

### Test Case 6: LLM Code Blocks
Tests LLM-generated content handling:
- Uses actual LLM node to generate code
- Verifies markdown code blocks (` ``` `) are preserved
- Tests newlines within code blocks

### Test Case 7: Empty and Null Values
Tests edge cases:
- Empty string `""`
- Empty list `[]`
- Empty dict `{}`
- Null/None values

### Test Case 8: Combined Pipeline
Full integration test:
- LLM node generates code with markdown
- Code node processes the output
- Verifies state passes correctly between nodes
- Tests regex extraction of code blocks

### Test Case 9: Code from Variable
Tests dynamic code execution:
- Code stored in state variable
- Uses `code.type: variable` to execute it
- Verifies the code can access state and return results

### Test Case 10: Large Strings
Stress test for payload size:
- Large JSON response (~1KB)
- Large HTML document (~2KB)
- Repeated pattern strings
- Verifies no truncation or corruption

### Test Case 11: alita_client Access
Tests SDK client availability:
- Verifies `alita_client` is in scope
- Checks for expected methods (`unsecret`, `get_prompt`)
- Tests method calls work without errors

## Quick Validation

Run this code in any code node to quickly verify the fix is working:

```python
validation = {
    "fix_working": isinstance(alita_state, dict),
    "state_keys": list(alita_state.keys()) if isinstance(alita_state, dict) else "STATE IS NOT A DICT - BUG!",
}
validation
```

If `fix_working` is `false`, the base64 encoding fix is not applied.

## Bug Indicators

| Symptom | Likely Cause |
|---------|--------------|
| `alita_state` is a string | Base64 decoding not working |
| Newlines are `\\n` instead of actual newlines | String escaping issue |
| JSON strings are dicts | `ast.literal_eval()` auto-parsing |
| `test_passed: false` | Check individual field results |
