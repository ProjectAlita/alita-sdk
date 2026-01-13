Manual Testing Cases for Code Node State Serialization

  Test Setup

  Create a pipeline/agent with Code Node that uses state variables. Each test case includes:
  1. State variables to set (from previous nodes or initial state)
  2. Code to run in the code node
  3. Expected behavior

  ---
  Test Case 1: Basic Types

  Purpose: Verify basic primitive types are correctly passed

  State Variables:
  string_var: "Hello World"
  integer_var: 42
  float_var: 3.14159
  boolean_var: true

  Code Node:
  result = {
      "string_type": type(alita_state['string_var']).__name__,
      "integer_type": type(alita_state['integer_var']).__name__,
      "float_type": type(alita_state['float_var']).__name__,
      "boolean_type": type(alita_state['boolean_var']).__name__,
      "values_correct": (
          alita_state['string_var'] == "Hello World" and
          alita_state['integer_var'] == 42 and
          abs(alita_state['float_var'] - 3.14159) < 0.001 and
          alita_state['boolean_var'] == True
      )
  }
  result

  Expected Output:
  {"string_type": "str", "integer_type": "int", "float_type": "float", "boolean_type": "bool", "values_correct": true}

  ---
  Test Case 2: Multiline Strings with Newlines

  Purpose: Verify newlines in strings are preserved (the main bug fix)

  State Variables:
  code_snippet: "def hello():\n    print('Hello')\n    return 42"
  multiline_text: "Line 1\nLine 2\nLine 3"

  Code Node:
  # Check if alita_state is a dict (not a string!)
  is_dict = isinstance(alita_state, dict)

  # Check newlines are actual newline characters
  code = alita_state.get('code_snippet', '')
  text = alita_state.get('multiline_text', '')

  result = {
      "state_is_dict": is_dict,
      "code_has_newlines": '\n' in code,
      "code_line_count": len(code.split('\n')),
      "text_line_count": len(text.split('\n')),
      "code_preview": code[:50]
  }
  result

  Expected Output:
  {"state_is_dict": true, "code_has_newlines": true, "code_line_count": 3, "text_line_count": 3, "code_preview": "def hello():\n    print('Hello')\n    return 42"}

  🔴 Bug indicator: If state_is_dict is false, the old bug is present.

  ---
  Test Case 3: Special Characters and Quotes

  Purpose: Verify quotes, backslashes, and unicode are handled

  State Variables:
  sql_query: "SELECT * FROM users WHERE name = 'John' AND status = \"active\""
  file_path: "C:\\Users\\admin\\file.txt"
  unicode_text: "Привет мир! 你好世界 🎉"
  regex_pattern: "^\\d+\\.\\d+$"

  Code Node:
  result = {
      "sql_has_quotes": "'" in alita_state['sql_query'] and '"' in alita_state['sql_query'],
      "path_has_backslash": '\\' in alita_state['file_path'],
      "unicode_preserved": 'Привет' in alita_state['unicode_text'] and '🎉' in alita_state['unicode_text'],
      "regex_correct": alita_state['regex_pattern'] == r"^\d+\.\d+$"
  }
  result

  Expected Output:
  {"sql_has_quotes": true, "path_has_backslash": true, "unicode_preserved": true, "regex_correct": true}

  ---
  Test Case 4: Nested Structures (Lists and Dicts)

  Purpose: Verify nested data structures are properly serialized

  State Variables:
  user_data: {"name": "Alice", "age": 30, "email": "alice@example.com"}
  items_list: [1, 2, 3, "four", {"nested": true}]
  complex_data: {"users": [{"id": 1, "name": "Bob"}, {"id": 2, "name": "Carol"}], "meta": {"count": 2}}

  Code Node:
  user = alita_state['user_data']
  items = alita_state['items_list']
  complex_obj = alita_state['complex_data']

  result = {
      "user_is_dict": isinstance(user, dict),
      "user_name": user.get('name'),
      "items_is_list": isinstance(items, list),
      "items_length": len(items),
      "nested_in_list": items[4].get('nested') if len(items) > 4 else None,
      "complex_user_count": len(complex_obj.get('users', [])),
      "first_user_name": complex_obj['users'][0]['name'] if complex_obj.get('users') else None
  }
  result

  Expected Output:
  {"user_is_dict": true, "user_name": "Alice", "items_is_list": true, "items_length": 5, "nested_in_list": true, "complex_user_count": 2, "first_user_name": "Bob"}

  ---
  Test Case 5: JSON String Within State

  Purpose: Verify strings that contain JSON are not double-parsed

  State Variables:
  api_response: "{\"status\": \"ok\", \"data\": [1, 2, 3]}"
  config_json: "{\"debug\": true, \"timeout\": 30}"

  Code Node:
  import json

  api_resp = alita_state['api_response']
  config = alita_state['config_json']

  # These should be STRINGS, not dicts
  result = {
      "api_response_is_string": isinstance(api_resp, str),
      "config_is_string": isinstance(config, str),
      # Parse them manually to verify they're valid JSON strings
      "api_parsed": json.loads(api_resp) if isinstance(api_resp, str) else "NOT A STRING",
      "config_parsed": json.loads(config) if isinstance(config, str) else "NOT A STRING"
  }
  result

  Expected Output:
  {"api_response_is_string": true, "config_is_string": true, "api_parsed": {"status": "ok", "data": [1, 2, 3]}, "config_parsed": {"debug": true, "timeout": 30}}

  ---
  Test Case 6: LLM Output with Code Blocks

  Purpose: Verify LLM-generated content with markdown code blocks

  State Variables:
  llm_response: "Here's the code:\n```python\ndef add(a, b):\n    return a + b\n```\nThis function adds two numbers."

  Code Node:
  response = alita_state['llm_response']

  result = {
      "is_string": isinstance(response, str),
      "has_code_block": "```python" in response,
      "has_newlines": response.count('\n') >= 4,
      "preview": response[:100]
  }
  result

  Expected Output:
  {"is_string": true, "has_code_block": true, "has_newlines": true, "preview": "Here's the code:\n```python\ndef add(a, b):\n    return a + b\n```\nThis function adds two numbers."}

  ---
  Test Case 7: Empty and Null Values

  Purpose: Verify edge cases with empty/null values

  State Variables:
  empty_string: ""
  empty_list: []
  empty_dict: {}
  null_value: null

  Code Node:
  result = {
      "empty_string_ok": alita_state.get('empty_string') == "",
      "empty_list_ok": alita_state.get('empty_list') == [],
      "empty_dict_ok": alita_state.get('empty_dict') == {},
      "null_is_none": alita_state.get('null_value') is None,
      "all_types_correct": (
          isinstance(alita_state.get('empty_string'), str) and
          isinstance(alita_state.get('empty_list'), list) and
          isinstance(alita_state.get('empty_dict'), dict)
      )
  }
  result

  Expected Output:
  {"empty_string_ok": true, "empty_list_ok": true, "empty_dict_ok": true, "null_is_none": true, "all_types_correct": true}

  ---
  Test Case 8: Combined Pipeline Test

  Purpose: Full integration test simulating real usage

  Pipeline Flow:
  1. LLM Node → Generates response with code
  2. Code Node → Processes the response
  3. Verify state passes correctly between nodes

  Initial Input:
  user_query: "Write a Python function to calculate factorial"

  After LLM Node (simulated state):
  llm_output: "Here's a factorial function:\n\n```python\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n```\n\nExample: factorial(5) = 120"
  iteration_count: 1
  metadata: {"model": "gpt-4", "tokens": 150}

  Code Node:
  # Verify all state variables are accessible and correctly typed
  output = alita_state.get('llm_output', '')
  count = alita_state.get('iteration_count', 0)
  meta = alita_state.get('metadata', {})

  # Extract code from markdown
  import re
  code_match = re.search(r'```python\n(.*?)\n```', output, re.DOTALL)
  extracted_code = code_match.group(1) if code_match else None

  result = {
      "state_is_dict": isinstance(alita_state, dict),
      "llm_output_is_string": isinstance(output, str),
      "has_code_block": "```python" in output,
      "code_extracted": extracted_code is not None,
      "iteration_is_int": isinstance(count, int),
      "metadata_is_dict": isinstance(meta, dict),
      "model_name": meta.get('model'),
      "extracted_code_preview": extracted_code[:50] if extracted_code else None
  }
  result

  Expected Output:
  {
    "state_is_dict": true,
    "llm_output_is_string": true,
    "has_code_block": true,
    "code_extracted": true,
    "iteration_is_int": true,
    "metadata_is_dict": true,
    "model_name": "gpt-4",
    "extracted_code_preview": "def factorial(n):\n    if n <= 1:\n        return"
  }

  ---
  Quick Validation Check

  Run this code in any code node to quickly verify the fix is working:

  # Quick validation - if this returns a dict, the fix is working
  validation = {
      "fix_working": isinstance(alita_state, dict),
      "state_keys": list(alita_state.keys()) if isinstance(alita_state, dict) else "STATE IS NOT A DICT - BUG!",
      "test_string": alita_state.get('test', 'no test var') if isinstance(alita_state, dict) else None
  }
  validation