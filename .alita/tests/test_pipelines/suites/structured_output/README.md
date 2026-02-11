# Structured Output Type Tests

Test pipelines for verifying structured output type handling in LLM nodes, specifically testing the fix in commit e45a9003 that allows `list[dict]` and other complex types.

## Test Pipelines

| Test | File | Description |
|------|------|-------------|
| 1 | `test_case_1_basic_types.yaml` | Basic types (str, int, bool, float) in structured output |
| 2 | `test_case_2_list_types.yaml` | List type variations (list, list[str], list[int]) |
| 3 | `test_case_3_list_of_objects.yaml` | **PRIMARY FIX** - list[dict] support |
| 4 | `test_case_4_dict_format.yaml` | Dict format with type/description/default |
| 5 | `test_case_5_field_name_bug.yaml` | Field name "blacklist" bug fix verification |
| 6 | `test_case_6_mixed_definitions.yaml` | Mixed string and dict type definitions |
| 7 | `test_case_7_nested_types.yaml` | Complex nested types (dict[str, list], etc.) |
| 8 | `test_case_8_implicit_structured_output.yaml` | Implicit structured output without explicit schema |
| 9 | `test_case_9_complex_state_initialization.yaml` | Pre-populated list state with complex objects |
| 10 | `test_case_10_fstring_templates.yaml` | fstring templates with structured output |

## Running Tests

1. Create a new Pipeline in the platform
2. Copy the YAML content from a test case file into the pipeline configuration
3. Run the pipeline and verify the output shows `test_passed: true`

## Key Fixes Tested

These tests verify the following fixes in `alita_sdk/runtime/tools/llm.py`:

- **list[dict] support** - Lists can now contain objects, not just strings
- **Field name bug fix** - Field names containing "list" (blacklist, playlist) no longer trigger false type conversion
- **Dict format support** - Type definitions can use `{type, description, default}` format
- **Type preservation** - Explicit types like `list[str]` are preserved, not auto-converted

## Additional Scenarios (Tests 8-10)

### Test 8: Implicit Structured Output
Tests `structured_output: true` **without** `structured_output_dict`. Verifies:
- Type inference from state variable declarations
- Output variables are correctly populated without explicit schema
- Useful for simpler use cases where schema is implied by state

### Test 9: Complex State Initialization
Tests pre-populated list state containing complex dict objects:
```yaml
state:
  source_data:
    type: list
    value:
      - id: "item_1"
        name: "First Item"
        value: 100
```
Verifies:
- Complex initial values are accessible in LLM nodes
- Structured output can process and transform pre-populated data
- List of dicts in state works with structured output

### Test 10: fstring Templates
Tests `fstring` type task templates with structured output:
```yaml
task:
  type: fstring
  value: |
    Generate {num_items} items in {category} category.
    Output format: {output_format}
```
Verifies:
- Multiple variable types interpolated (str, int, bool)
- fstring works in both system and task prompts
- Structured output correctly processes templated requests

---

# Comprehensive Test Plan for Commit e45a900

**Commit**: https://github.com/ProjectAlita/alita-sdk/commit/e45a9003f0409117490af2c6d3dcd812329db235
**Issue**: #3068
**Component**: `alita_sdk/runtime/tools/llm.py`
**Date Created**: 2025-01-17

---

## Change Summary

This commit updates the `_prepare_structured_output_params` method to properly handle list types that can contain various element types (objects, strings, etc.), not just strings.

### Key Changes:
1. **Type hint updated**: `structured_output_dict` field changed from `Optional[dict[str, str]]` to `Optional[Dict[str, Any]]` (lines 4, 68)
2. **Type handling improved**: Better handling of non-string types in the parameter dictionary
3. **Removed auto-conversion bug**: Removed the problematic `if 'list' in value` check that incorrectly converted words containing "list" (like "blacklist")
4. **Default method changed**: `__get_struct_output_model` default changed from `"json_schema"` to `"function_calling"`

---

## 🎯 Test Objectives

1. Verify the primary fix: list types can now contain objects, not just strings
2. Ensure the "blacklist" substring bug is fixed
3. Maintain backward compatibility with existing configurations
4. Test edge cases with dynamically generated types
5. Validate type string handling consistency
6. Ensure secure handling of type strings from various sources

---

## ✅ Core Functionality Tests

### **Test 1: Basic Structured Output with Simple String Types**
**Objective**: Verify that simple string type definitions still work correctly

**Test cases**:
```python
# TC1.1: Single string type
{"field1": "str"} 
# Expected: Field with type str

# TC1.2: Multiple simple types
{"field1": "int", "field2": "bool", "field3": "float"}
# Expected: Multiple fields with correct types

# TC1.3: Any type
{"result": "any"}
# Expected: Field with type Any

# TC1.4: Boolean type
{"is_active": "bool"}
# Expected: Field with type bool
```

**Expected behavior**: All simple type strings should be processed correctly without regression

**Priority**: 🔴 **CRITICAL**

---

### **Test 2: Structured Output with List Types**
**Objective**: Verify the primary fix - list types can now be objects, not just strings

**Test cases**:
```python
# TC2.1: Backward compatibility - bare "list"
{"items": "list"}
# Expected: Auto-convert to list[str]

# TC2.2: Explicit list of strings
{"items": "list[str]"}
# Expected: Preserve as list[str]

# TC2.3: NEW - List of dicts
{"items": "list[dict]"}
# Expected: Support list of dicts (PRIMARY FIX)

# TC2.4: NEW - List of any type
{"items": "list[any]"}
# Expected: Support list[Any]

# TC2.5: List of integers
{"items": "list[int]"}
# Expected: Support list[int]

# TC2.6: List of objects
{"items": "list[object]"}
# Expected: Support list of objects

# TC2.7: List of booleans
{"flags": "list[bool]"}
# Expected: Support list[bool]
```

**Expected behavior**: All list type variations should be handled properly without forcing conversion to `list[str]`

**Priority**: 🔴 **CRITICAL**

---

### **Test 3: Structured Output with Object/Dict Types in List**
**Objective**: Verify the fix allows complex object types in lists

**Test cases**:
```python
# TC3.1: Complex structure
structured_output_dict = {
    "users": "list[dict]",
    "metadata": "dict",
    "tags": "list[str]",
    "counts": "list[int]"
}
# Expected: Generate proper Pydantic model with all types

# TC3.2: Nested structures
{
    "results": "list[dict]",
    "summary": "dict",
    "errors": "list[str]"
}
# Expected: All types preserved correctly
```

**Expected behavior**: Should generate proper Pydantic model with complex types

**Priority**: 🔴 **CRITICAL**

---

### **Test 4: Structured Output with Dict Format (type, description, default)**
**Objective**: Ensure dict-based type definitions still work

**Test cases**:
```python
# TC4.1: Full dict definition
{
    "field1": {"type": "str", "description": "A string field"},
    "field2": {"type": "list[dict]", "description": "List of objects", "default": []},
    "field3": {"type": "int", "default": 0}
}
# Expected: Type extracted from "type" key, description and defaults preserved

# TC4.2: Mixed with defaults
{
    "required_field": {"type": "str", "description": "Required"},
    "optional_field": {"type": "str", "default": "default_value"}
}
# Expected: Required vs optional fields handled correctly

# TC4.3: Complex types in dict format
{
    "data": {"type": "list[dict[str, any]]", "description": "Complex nested"}
}
# Expected: Complex type string parsed correctly
```

**Expected behavior**: 
- Type should be extracted from "type" key
- String conversion should happen with `str(value.get("type"))` 
- Description and defaults should be preserved

**Priority**: 🔴 **CRITICAL**

---

### **Test 5: Type Normalization Logic (Bug Fix Verification)**
**Objective**: Verify the "blacklist" bug is fixed

**Test cases**:
```python
# TC5.1: Exact match "list" - should convert
{"items": "list"}
# Expected: Convert to list[str]

# TC5.2: Substring "list" in field name - should NOT affect type
{"blacklist": "list"}
# Expected: Convert to list[str] (ONLY because value is "list", not because field name contains "list")

# TC5.3: Type is explicitly list[str]
{"blacklist": "list[str]"}
# Expected: Keep as list[str], no double conversion

# TC5.4: Word containing "list" as field name, different type
{"allowlist": "str"}
# Expected: Keep as str (no false conversion)

# TC5.5: Word containing "list" as field name, different type
{"playlist": "str"}
# Expected: Keep as str (PRIMARY BUG FIX - was incorrectly converted)

# TC5.6: Word containing "list" with list type
{"checklist": "list[dict]"}
# Expected: Keep as list[dict], not convert to list[str]

# TC5.7: Case variations
{"items": "LIST"}  # Uppercase
{"items": "List"}  # PascalCase
{"items": " list "}  # With spaces
# Expected: All should convert to list[str] after normalization
```

**Expected behavior**: Only exact string "list" (case-insensitive, stripped) should be converted to `list[str]`. Field names should not affect type conversion.

**Priority**: 🔴 **CRITICAL**

---

### **Test 6: Structured Output with Mixed Type Definitions**
**Objective**: Verify combination of string types and dict definitions

**Test cases**:
```python
# TC6.1: Mixed formats
{
    "simple_field": "str",
    "complex_field": {"type": "list[dict]", "description": "Complex list"},
    "list_field": "list[int]",
    "default_field": {"type": "str", "default": "default_value"}
}
# Expected: Both formats work together seamlessly

# TC6.2: All dict format
{
    "field1": {"type": "str"},
    "field2": {"type": "list[dict]"},
    "field3": {"type": "int"}
}
# Expected: Works correctly

# TC6.3: All string format
{
    "field1": "str",
    "field2": "list[dict]",
    "field3": "int"
}
# Expected: Works correctly
```

**Expected behavior**: Both formats should work together seamlessly

**Priority**: 🟡 **HIGH**

---

### **Test 7: Backward Compatibility with Existing Configurations**
**Objective**: Ensure existing agent configurations don't break

**Test cases**:
```python
# TC7.1: Legacy simple list
{"items": "list"}
# Expected: Still auto-converts to list[str] (backward compatible)

# TC7.2: Legacy simple types
{"name": "str", "age": "int", "active": "bool"}
# Expected: Works exactly as before

# TC7.3: Run actual existing agents
# - Find agents in .alita/agents/ with structured_output
# - Run them with old configurations
# - Verify no breaking changes
```

**Test method**:
- Identify existing agents using structured output
- Run them with current configurations
- Compare outputs before/after change
- Ensure no regressions

**Expected behavior**: No breaking changes for existing workflows

**Priority**: 🔴 **CRITICAL**

---

### **Test 8: Structured Output Method Selection**
**Objective**: Verify the default method change from "json_schema" to "function_calling"

**Test cases**:
```python
# TC8.1: Default method
# Create LLMNode without specifying structured_output_method
# Expected: Should use "function_calling" by default

# TC8.2: Explicit method override
structured_output_method = "json_schema"
# Expected: Should respect explicit setting

# TC8.3: Fallback chain
# Test when function_calling fails
# Expected: Should fall back to json_mode

# TC8.4: Json mode fallback
# Test when json_mode also fails
# Expected: Should fall back to json extraction

# TC8.5: Method compatibility with different LLM providers
# Test with OpenAI, Anthropic, Azure, etc.
# Expected: Each provider should use appropriate method
```

**Expected behavior**: 
- Default should use "function_calling" 
- Fallback chain should work: function_calling → json_mode → json extraction
- Provider-specific behavior should be correct

**Priority**: 🟡 **HIGH**

---

### **Test 9: Edge Cases and Error Handling**
**Objective**: Handle unusual inputs gracefully

**Test cases**:
```python
# TC9.1: None values
{"field": None}
# Expected: Handle gracefully, skip or use default

# TC9.2: Empty dict
{}
# Expected: No fields, but no crash

# TC9.3: Empty string type
{"field": ""}
# Expected: Handle gracefully, log warning

# TC9.4: Special characters in field names
{"field-name": "str", "field.name": "int", "field_name": "bool"}
# Expected: Valid Python identifiers only, or sanitize

# TC9.5: Unicode in descriptions
{"field": {"type": "str", "description": "Unicode: 你好 🎉"}}
# Expected: Handle Unicode correctly

# TC9.6: Very long type strings
{"field": "list[dict[str, list[dict[str, list[int]]]]]"}
# Expected: Handle deep nesting without crash

# TC9.7: Whitespace variations
{"field": "  str  ", "field2": "\tint\n"}
# Expected: Strip and normalize whitespace
```

**Expected behavior**: Should handle gracefully without crashes, log warnings where appropriate

**Priority**: 🟡 **HIGH**

---

### **Test 10: Integration with LLM Invocation and Tool Calls**
**Objective**: Verify end-to-end functionality

**Test cases**:
```python
# TC10.1: Create LLMNode with new list[dict] types
llm_node = LLMNode(
    structured_output=True,
    structured_output_dict={"results": "list[dict]", "summary": "str"}
)
# Expected: Node created successfully

# TC10.2: Invoke LLM with tool calls
response = llm_node.invoke({"input": "test"})
# Expected: Structured output properly parsed

# TC10.3: Verify ELITEA_RS field
# Check that ELITEA_RS field is still added to response
# Expected: Field present in output

# TC10.4: Test with actual LLM providers
# Test with: OpenAI GPT-4, Anthropic Claude, Azure OpenAI
# Expected: All providers work correctly

# TC10.5: Fallback mechanisms
# Simulate structured output failure
# Expected: Falls back gracefully, returns unstructured

# TC10.6: Verify Pydantic model generation
# Inspect generated model
# Expected: Valid Pydantic model with correct field types
```

**Expected behavior**: Complete workflow from input to structured output should work correctly

**Priority**: 🔴 **CRITICAL**

---

## 🔬 Extended Tests: Dynamically Generated Types

### **Test 11: Other Collection Types (Similar to "list")**
**Objective**: Check if other collection types have the same auto-conversion behavior

**Test cases**:
```python
# TC11.1: Set types
{"tags": "set"}
# Expected: Auto-convert to set[str]? Or remain as set? DECISION NEEDED

{"tags": "set[str]"}
# Expected: Preserve as set[str]

{"ids": "set[int]"}
# Expected: Preserve as set[int]

# TC11.2: Words containing "set" - should NOT trigger conversion
{"offset": "int", "asset": "str", "subset": "str"}
# Expected: Types unchanged

# TC11.3: Tuple types
{"coords": "tuple"}
# Expected: Behavior unclear - might need tuple[Any, ...]

{"coords": "tuple[int, int]"}
# Expected: Fixed-length tuple

{"coords": "tuple[str, ...]"}
# Expected: Variable-length tuple

# TC11.4: Words containing "tuple"
{"quintuple": "str"}
# Expected: Type unchanged

# TC11.5: Dict types
{"metadata": "dict"}
# Expected: Should this be dict[str, Any]? DECISION NEEDED

{"metadata": "dict[str, str]"}
# Expected: Preserve as dict[str, str]

{"nested": "dict[str, list[int]]"}
# Expected: Complex nested type preserved

# TC11.6: Words containing "dict"
{"predict": "str", "dictate": "str", "contradict": "bool"}
# Expected: Types unchanged
```

**Expected behavior**: Clarify auto-conversion rules for all collection types, ensure consistency with "list" handling

**Priority**: 🟡 **HIGH**

**Decision needed**: Should bare collection types auto-convert?
- `"list"` → `"list[str]"` (current behavior)
- `"dict"` → `"dict[str, Any]"` (for consistency?)
- `"set"` → `"set[str]"` (for consistency?)
- `"tuple"` → `"tuple[Any, ...]"` (for consistency?)

---

### **Test 12: Python Type Objects (Not Strings)**
**Objective**: Handle cases where actual Python type objects are passed

**Test cases**:
```python
# TC12.1: Basic type objects
{
    "field1": str,           # Type object, not string
    "field2": int,
    "field3": list,
    "field4": dict,
}
# Expected: Convert to string via str(type) or reject with clear error

# TC12.2: Typing module types
from typing import List, Dict, Optional

{
    "field5": List[str],     # typing module types
    "field6": Optional[int],
    "field7": Dict[str, int],
}
# Expected: Handle gracefully or document as unsupported

# TC12.3: Mixed type objects and strings
{
    "string_type": "str",
    "object_type": str,
}
# Expected: Both should work or clear error for type objects
```

**Expected behavior**: 
- Should gracefully handle type objects via `str(value)` if possible
- Or raise clear error if not supported
- Document expected input format (strings only? types allowed?)

**Priority**: 🟡 **HIGH**

---

### **Test 13: Complex Typing Module Types**
**Objective**: Verify support for advanced typing constructs

**Test cases**:
```python
from typing import Optional, Union, Any, Literal

# TC13.1: Optional types
{"optional_field": "Optional[str]"}
# Expected: Parse correctly as Optional[str]

# TC13.2: Union types
{"union_field": "Union[str, int]"}
# Expected: Parse correctly as Union[str, int]

# TC13.3: Any type
{"any_field": "Any"}
# Expected: Parse as Any

# TC13.4: Literal types (enums)
{"literal_field": "Literal['red', 'green', 'blue']"}
# Expected: Parse correctly or document limitation

# TC13.5: None type
{"none_field": "None"}
# Expected: Handle NoneType

# TC13.6: Complex combinations
{"complex": "Optional[Union[str, list[int]]]"}
# Expected: Parse nested typing constructs or document limitation
```

**Potential issues**:
- Will `"Optional[str]"` be parsed correctly by Pydantic?
- Does the code handle `Union` types?
- What about `Literal` enums?

**Expected behavior**: Document which typing constructs are supported, handle or reject gracefully

**Priority**: 🟢 **MEDIUM**

---

### **Test 14: Nested and Complex Generic Types**
**Objective**: Verify deeply nested type definitions work

**Test cases**:
```python
# TC14.1: Simple nested
{"simple_nested": "list[dict[str, str]]"}
# Expected: Handle 2-level nesting

# TC14.2: Complex nested
{"complex_nested": "dict[str, list[dict[str, any]]]"}
# Expected: Handle 3-level nesting

# TC14.3: Triple nested
{"triple_nested": "list[dict[str, list[int]]]"}
# Expected: Handle 3-level nesting

# TC14.4: Mixed types nested
{"mixed": "dict[str, Union[str, int, list[str]]]"}
# Expected: Handle Union in nested structure

# TC14.5: Very deep nesting
{"deep": "list[dict[str, list[dict[str, list[dict[str, int]]]]]]"}
# Expected: Handle arbitrary depth or document limit

# TC14.6: All collection types nested
{"all_types": "dict[str, list[set[tuple[str, int]]]]"}
# Expected: Handle mixed collection types
```

**Expected behavior**: 
- Should handle arbitrary nesting depth (within reason)
- Pydantic model generation should not fail
- Type validation should work correctly
- Document any nesting limits

**Priority**: 🟢 **MEDIUM**

---

### **Test 15: Type String Variations and Casing**
**Objective**: Ensure consistent handling of type string formats

**Test cases**:
```python
# TC15.1: Case variations
{"lowercase": "str"}
{"uppercase": "STR"}
{"mixed_case": "StrIng"}
# Expected: Define canonical format, normalize consistently

# TC15.2: Whitespace variations
{"with_spaces": " str "}
{"with_tabs": "\tint\t"}
{"with_newlines": "\nlist[str]\n"}
# Expected: Strip whitespace

# TC15.3: List case variations
{"list_upper": "LIST"}
{"list_mixed": "List"}
{"list_lower": "list"}
# Expected: All should auto-convert to list[str]

# TC15.4: Generic type casing
{"list_generic": "List[str]"}  # Capital L
{"list_generic2": "list[Str]"}  # Capital S
# Expected: Define and document canonical format

# TC15.5: Python builtin vs typing module
{"from_builtin": "list[str]"}  # lowercase
{"from_typing": "List[str]"}   # PascalCase
# Expected: Both should work or document preference
```

**Expected behavior**: 
- Define canonical format (lowercase? PascalCase?)
- Normalize consistently (case-insensitive or case-sensitive?)
- Document format requirements
- Strip whitespace consistently

**Priority**: 🟡 **HIGH**

---

### **Test 16: Special Python Types**
**Objective**: Handle uncommon but valid Python types

**Test cases**:
```python
# TC16.1: Byte types
{"bytes_field": "bytes"}
{"bytearray_field": "bytearray"}
# Expected: Handle or document limitation

# TC16.2: Other collection types
{"frozenset_field": "frozenset"}
{"frozenset_typed": "frozenset[int]"}
# Expected: Handle or document limitation

# TC16.3: Numeric types
{"complex_number": "complex"}
{"decimal_number": "Decimal"}
{"fraction": "Fraction"}
# Expected: Handle or document limitation

# TC16.4: Range and memory types
{"range_field": "range"}
{"memoryview_field": "memoryview"}
# Expected: Likely not supported, should fail gracefully

# TC16.5: Callable types
{"callback": "Callable"}
{"typed_callback": "Callable[[int, str], bool]"}
# Expected: Document limitation or support

# TC16.6: Generator types
{"generator": "Generator[int, None, None]"}
# Expected: Likely not supported for structured output
```

**Expected behavior**: 
- Should not crash
- May not be fully supported by Pydantic
- Should document limitations clearly
- Fail gracefully with clear error messages

**Priority**: 🟢 **MEDIUM**

---

### **Test 17: Dynamically Generated Type Strings**
**Objective**: Simulate programmatic type string construction

**Test cases**:
```python
# TC17.1: String formatting
base_type = "list"
element_type = "dict"
generated_type = f"{base_type}[{element_type}]"  # "list[dict]"
structured_output_dict = {"field": generated_type}
# Expected: Should work correctly

# TC17.2: String concatenation
type_str = "list" + "[" + "str" + "]"  # "list[str]"
structured_output_dict = {"field": type_str}
# Expected: Should work correctly

# TC17.3: From configuration files
import json
config = json.loads('{"type": "list[dict]"}')
structured_output_dict = {"field": config["type"]}
# Expected: Should work correctly

# TC17.4: From YAML
import yaml
yaml_config = yaml.safe_load('type: list[dict]')
structured_output_dict = {"field": yaml_config["type"]}
# Expected: Should work correctly

# TC17.5: Dynamic construction based on conditions
def get_type(is_list=True, element_type="str"):
    if is_list:
        return f"list[{element_type}]"
    return element_type

structured_output_dict = {"field": get_type(True, "dict")}
# Expected: Should work correctly

# TC17.6: From database/API
# Simulating retrieval from external source
api_response = {"schema": {"field_type": "list[dict]"}}
structured_output_dict = {"field": api_response["schema"]["field_type"]}
# Expected: Should work correctly
```

**Expected behavior**: 
- Should handle any valid type string format regardless of how it was constructed
- Should not have special behavior based on construction method
- String content is what matters, not source

**Priority**: 🔴 **CRITICAL**

---

### **Test 18: Type String Injection and Security**
**Objective**: Ensure malicious type strings don't cause issues

**Test cases**:
```python
# TC18.1: Code injection attempts
{"malicious1": "list]; import os; os.system('rm -rf /'); #"}
# Expected: Should not execute code, treat as invalid type

# TC18.2: Import injection
{"malicious2": "dict[str, __import__('os').system('whoami')]"}
# Expected: Should not execute code

# TC18.3: Eval injection
{"malicious3": "eval('1+1')"}
# Expected: Should not execute eval

# TC18.4: SQL-like injection
{"sql_injection": "str'; DROP TABLE users; --"}
# Expected: Treat as invalid type string

# TC18.5: Path traversal
{"path_traversal": "../../etc/passwd"}
# Expected: Treat as invalid type string

# TC18.6: XSS-like attempts
{"xss": "<script>alert('xss')</script>"}
# Expected: Treat as invalid type string

# TC18.7: Serialization attacks
{"pickle": "__import__('pickle').loads(b'...')"}
# Expected: Should not execute
```

**Expected behavior**: 
- Should NOT execute arbitrary code under any circumstances
- Should sanitize or validate type strings before use
- Should fail safely on invalid input with clear error
- Consider using allowlist of valid type patterns

**Priority**: 🔴 **CRITICAL** (Security)

---

### **Test 19: Pydantic-Specific Field Types**
**Objective**: Check if Pydantic field types are supported

**Test cases**:
```python
# TC19.1: String validators
{"email": "EmailStr"}
{"url": "HttpUrl"}
{"ipv4": "IPvAnyAddress"}
# Expected: Document support or limitation

# TC19.2: Identifier types
{"uuid": "UUID"}
{"uuid4": "UUID4"}
# Expected: Document support or limitation

# TC19.3: Datetime types
{"datetime": "datetime"}
{"date": "date"}
{"time": "time"}
{"timedelta": "timedelta"}
# Expected: Document support or limitation

# TC19.4: Numeric constraints
{"positive_int": "PositiveInt"}
{"negative_float": "NegativeFloat"}
{"decimal": "Decimal"}
# Expected: Document support or limitation

# TC19.5: Path types
{"filepath": "FilePath"}
{"dirpath": "DirectoryPath"}
# Expected: Document support or limitation

# TC19.6: JSON types
{"json_str": "Json"}
{"json_any": "Json[Any]"}
# Expected: Document support or limitation

# TC19.7: Secret types
{"secret_str": "SecretStr"}
{"secret_bytes": "SecretBytes"}
# Expected: Document support or limitation
```

**Expected behavior**: 
- Document which Pydantic types are supported
- Test if they work with dynamic model creation
- Provide examples in documentation
- Some may require additional imports or configuration

**Priority**: 🟢 **MEDIUM**

---

### **Test 20: Invalid and Malformed Type Strings**
**Objective**: Graceful error handling for bad input

**Test cases**:
```python
# TC20.1: Bracket mismatches
{"unclosed_bracket": "list[str"}
{"extra_bracket": "list[str]]"}
{"wrong_bracket": "list<str>"}
{"curly_bracket": "list{str}"}
# Expected: Clear error message, don't crash

# TC20.2: Empty or malformed generics
{"empty_generic": "list[]"}
{"double_generic": "list[str][int]"}
{"comma_error": "list[str,]"}
# Expected: Clear error message

# TC20.3: Invalid separators
{"pipe_separator": "list|str"}
{"semicolon": "list;str"}
{"slash": "list/str"}
# Expected: Treat as invalid type

# TC20.4: Nonsense strings
{"nonsense": "asdfghjkl"}
{"random": "xyz123abc"}
{"gibberish": "foobarbazconsumer"}
# Expected: Invalid type error

# TC20.5: Numeric and special chars
{"numeric": "123"}
{"special_chars": "str@#$%"}
{"emoji": "str🎉"}
# Expected: Invalid type error

# TC20.6: Empty strings
{"empty_string": ""}
{"just_spaces": "   "}
# Expected: Handle gracefully, possibly skip field

# TC20.7: Very long strings
{"too_long": "a" * 10000}
# Expected: Handle or reject with length limit

# TC20.8: Null bytes and control characters
{"null_byte": "str\x00int"}
{"control_chars": "str\x01\x02\x03"}
# Expected: Sanitize or reject
```

**Expected behavior**: 
- Should NOT crash or raise unhandled exceptions
- Should log clear, actionable error messages
- Should either skip invalid fields or raise ValueError with details
- Should NOT silently fail or produce unexpected behavior
- Consider providing suggestions for fixes

**Priority**: 🔴 **CRITICAL**

---

### **Test 21: Auto-Conversion Consistency Across All Types**
**Objective**: Define consistent rules for bare collection types

**Decision table**:

| Input Type | Current Behavior | Proposed Behavior | Rationale |
|------------|-----------------|-------------------|-----------|
| `"list"` | → `"list[str]"` | ✅ Keep | Backward compatibility, reasonable default |
| `"dict"` | → `"dict"` (unchanged) | → `"dict[str, Any]"`? | Consistency with list auto-conversion |
| `"set"` | → `"set"` (unchanged) | → `"set[str]"`? | Consistency with list auto-conversion |
| `"tuple"` | → `"tuple"` (unchanged) | → `"tuple[Any, ...]"`? | Consistency with list auto-conversion |
| `"frozenset"` | → `"frozenset"` (unchanged) | → `"frozenset[str]"`? | Consistency with list auto-conversion |

**Test cases**:
```python
# TC21.1: Test current behavior
structured_output_dict = {
    "list_field": "list",
    "dict_field": "dict",
    "set_field": "set",
    "tuple_field": "tuple",
}
# Document current behavior for each

# TC21.2: Test with explicit types
structured_output_dict = {
    "list_field": "list[int]",
    "dict_field": "dict[str, int]",
    "set_field": "set[int]",
    "tuple_field": "tuple[int, ...]",
}
# Expected: All explicit types preserved

# TC21.3: Test consistency across providers
# Test with different LLM providers to ensure consistent behavior
# Expected: Same behavior regardless of LLM provider
```

**Decision needed**: Should all bare collection types auto-convert to sensible defaults?

**Recommendation**: 
- Document current behavior clearly
- Consider consistent auto-conversion for better developer experience
- Provide configuration option to disable auto-conversion if needed

**Priority**: 🟡 **HIGH**

---

### **Test 22: Type String Sources and Serialization**
**Objective**: Verify types from various sources work correctly

**Test cases**:

**TC22.1: From JSON**
```python
import json
json_str = '{"users": "list[dict]", "count": "int"}'
structured_output_dict = json.loads(json_str)
# Expected: Works correctly
```

**TC22.2: From YAML**
```python
import yaml
yaml_str = """
users: list[dict]
count: int
nested:
  field: str
"""
structured_output_dict = yaml.safe_load(yaml_str)
# Expected: Works correctly, handles nesting
```

**TC22.3: From environment variables**
```python
import os
os.environ['OUTPUT_TYPE'] = 'list[dict]'
structured_output_dict = {"field": os.getenv('OUTPUT_TYPE')}
# Expected: Works correctly
```

**TC22.4: From API/database**
```python
# Simulating data from external source
api_response = {"schema": {"type": "list[dict]"}}
structured_output_dict = {"field": api_response["schema"]["type"]}
# Expected: Works correctly
```

**TC22.5: From .agent.md files**
```yaml
# In YAML frontmatter of .agent.md
structured_output_dict:
  results: list[dict]
  summary: str
```
```python
# Load and parse .agent.md
# Expected: Works correctly when agent is loaded
```

**TC22.6: Serialization round-trip**
```python
# Create structured output dict
original = {"field": "list[dict]"}

# Serialize to JSON
json_str = json.dumps(original)

# Deserialize
deserialized = json.loads(json_str)

# Use in LLMNode
# Expected: Should work identically to original
```

**Expected behavior**: 
- All sources should work identically
- Serialization format should not affect behavior
- String content is what matters

**Priority**: 🟡 **HIGH**

---

## 🎯 Test Execution Priority

### **Priority 1: CRITICAL** (Must pass before merge)
- ✅ Test 2: List types (primary fix)
- ✅ Test 3: Complex object types
- ✅ Test 5: Bug fix verification (blacklist)
- ✅ Test 7: Backward compatibility
- ✅ Test 10: End-to-end integration
- ✅ Test 17: Dynamically generated types
- ✅ Test 18: Security (injection attacks)
- ✅ Test 20: Invalid input handling

### **Priority 2: HIGH** (Should pass before release)
- ✅ Test 1: Simple types (regression check)
- ✅ Test 4: Dict format definitions
- ✅ Test 6: Mixed definitions
- ✅ Test 8: Method selection
- ✅ Test 9: Edge cases
- ✅ Test 11: Other collection types
- ✅ Test 12: Type objects vs strings
- ✅ Test 15: Case sensitivity
- ✅ Test 21: Auto-conversion consistency
- ✅ Test 22: Serialization sources

### **Priority 3: MEDIUM** (Good to have)
- ✅ Test 13: Advanced typing constructs
- ✅ Test 14: Nested generics
- ✅ Test 16: Special Python types
- ✅ Test 19: Pydantic field types

---

## 📝 Additional Verification

### **Regression Testing**
1. ✅ Run existing test suite for `LLMNode`
2. ✅ Run existing integration tests
3. ✅ Verify no changes in behavior for non-list types
4. ✅ Check logging output for type conversion warnings
5. ✅ Run tests against multiple Python versions (3.8, 3.9, 3.10, 3.11)

### **Manual Testing**
1. ✅ Create test agents with various structured output configurations
2. ✅ Test with real LLMs (Claude, GPT-4, GPT-3.5)
3. ✅ Verify generated Pydantic models are valid
4. ✅ Check that LLMs can populate list[dict] fields correctly
5. ✅ Test with different structured output methods
6. ✅ Test fallback behavior when structured output fails

### **Code Review Checklist**
- [ ] Type hints are correct throughout
- [ ] No code execution vulnerabilities
- [ ] Error messages are clear and actionable
- [ ] Logging is appropriate (level and content)
- [ ] Documentation comments are updated
- [ ] No performance regressions
- [ ] Thread-safety if applicable

### **Documentation Updates**
- [ ] Update `structured_output_dict` parameter documentation
- [ ] Add examples of new list type formats
- [ ] Document the "list" auto-conversion behavior
- [ ] Document supported type strings (canonical reference)
- [ ] Document limitations and unsupported types
- [ ] Add migration guide for existing users
- [ ] Update API reference
- [ ] Add troubleshooting section

---

## 📊 Success Criteria

### **Functionality**
✅ All Priority 1 (CRITICAL) tests pass  
✅ At least 95% of Priority 2 (HIGH) tests pass  
✅ No regression in existing functionality  
✅ New list type formats work as expected  
✅ "Blacklist" bug is completely fixed  

### **Quality**
✅ Code coverage ≥ 80% for modified code  
✅ No new security vulnerabilities  
✅ Performance impact < 5% (structured output preparation time)  
✅ All edge cases handled gracefully  

### **Documentation**
✅ All new features documented with examples  
✅ Migration guide available for breaking changes  
✅ API reference updated  
✅ Limitations clearly documented  

### **User Experience**
✅ Clear error messages for invalid inputs  
✅ Backward compatibility maintained  
✅ Intuitive behavior for common use cases  
✅ Examples cover real-world scenarios  

---

## 🚀 Test Implementation Strategy

### **Phase 1: Core Functionality (Week 1)**
1. Implement Tests 1-5 (basic types, lists, bug fix)
2. Implement Test 7 (backward compatibility)
3. Implement Test 10 (integration)
4. Run against existing test suite

### **Phase 2: Edge Cases and Security (Week 1-2)**
1. Implement Tests 9, 18, 20 (edge cases, security, invalid input)
2. Implement Test 17 (dynamic generation)
3. Security audit and penetration testing

### **Phase 3: Extended Coverage (Week 2)**
1. Implement Tests 11-16 (other types, typing module, special types)
2. Implement Tests 21-22 (consistency, serialization)
3. Performance benchmarking

### **Phase 4: Documentation and Polish (Week 2-3)**
1. Update all documentation
2. Create migration guide
3. Add examples and tutorials
4. Final regression testing

---

## 🔧 Testing Tools and Frameworks

### **Unit Testing**
- `pytest` for test execution
- `pytest-cov` for coverage reporting
- `pytest-mock` for mocking LLM responses

### **Property-Based Testing**
- `hypothesis` for generating test cases
- Especially useful for Tests 17, 20 (dynamic/invalid inputs)

### **Security Testing**
- Manual code review for injection vulnerabilities
- Static analysis with `bandit`
- Test with malicious inputs (Test 18)

### **Integration Testing**
- Test with real LLM providers (OpenAI, Anthropic)
- Test with mock LLM responses
- Test agent execution end-to-end

### **Performance Testing**
- Benchmark type string parsing time
- Measure Pydantic model creation overhead
- Profile memory usage

---

## 📋 Test Tracking

### **Test Results Template**
```
Test ID: TC[X].[Y]
Test Name: [Name]
Status: ✅ Pass / ❌ Fail / ⚠️ Blocked / ⏭️ Skipped
Priority: Critical / High / Medium / Low
Execution Date: YYYY-MM-DD
Tester: [Name]
Environment: [Python version, OS, LLM provider]
Notes: [Any observations]
```

### **Bug Template**
```
Bug ID: BUG-[X]
Related Test: TC[X].[Y]
Severity: Critical / High / Medium / Low
Description: [What went wrong]
Steps to Reproduce: [Steps]
Expected: [Expected behavior]
Actual: [Actual behavior]
Root Cause: [If known]
Fix Status: Open / In Progress / Fixed / Verified
```

---

## 🤝 Collaboration

### **Code Review Focus Areas**
1. Type handling logic in `_prepare_structured_output_params`
2. String matching for auto-conversion (exact "list" only)
3. Security: no code execution from type strings
4. Error handling: graceful failures
5. Backward compatibility: existing configs work

### **Stakeholder Sign-off Required**
- [ ] Engineering lead (code quality)
- [ ] Security team (vulnerability assessment)
- [ ] Documentation team (docs complete)
- [ ] QA lead (test coverage adequate)
- [ ] Product owner (acceptance criteria met)

---

## 📚 References

- **Commit**: https://github.com/ProjectAlita/alita-sdk/commit/e45a9003f0409117490af2c6d3dcd812329db235
- **Issue**: #3068
- **File**: `alita_sdk/runtime/tools/llm.py`
- **Related Docs**: 
  - Pydantic documentation: https://docs.pydantic.dev/
  - Python typing module: https://docs.python.org/3/library/typing.html
  - LangChain structured output: https://python.langchain.com/docs/how_to/structured_output/

---

**Document Version**: 1.0  
**Created**: 2025-01-17  
**Last Updated**: 2025-01-17  
**Status**: Draft - Ready for Review  
**Next Review Date**: Before merge to main

---

## 📝 Notes and Open Questions

1. **Auto-conversion consistency**: Should `dict`, `set`, `tuple` auto-convert like `list` does?
2. **Type object support**: Should we accept actual Python type objects (e.g., `str` instead of `"str"`)?
3. **Typing module support**: Which `typing` constructs should be officially supported?
4. **Nesting limits**: Is there a practical limit to type nesting depth?
5. **Performance**: Any performance impact from more complex type parsing?
6. **Provider compatibility**: Do all LLM providers support structured output equally?

---

**END OF TEST PLAN**