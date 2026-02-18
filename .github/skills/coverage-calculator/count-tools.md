# Count Tools in Toolkit

This procedure counts the total number of tools available in a toolkit by analyzing the `get_available_tools()` method in the toolkit's wrapper file.

## Purpose

Extract an accurate tool count for calculating test coverage metrics. The count must reflect the actual number of tools users can access.

## Step-by-Step Procedure

### Step 1: Locate Toolkit Directory

Navigate to: `alita_sdk/tools/{toolkit_name}/`

**Example**:
- GitHub toolkit: `alita_sdk/tools/github/`
- JIRA toolkit: `alita_sdk/tools/jira/`
- Postman toolkit: `alita_sdk/tools/postman/`

### Step 2: Find Wrapper File

Search for the wrapper file in this order of priority:

1. `api_wrapper.py` (most common)
2. `*_wrapper.py` (e.g., `jira_wrapper.py`)
3. `*_client.py` (e.g., `github_client.py`)
4. Special cases:
   - LocalGit: `local_git.py`
   - Some toolkits: Check `__init__.py` for wrapper import

**Not found?** Check if it's a container directory (see [categorize-toolkit.md](./categorize-toolkit.md))

### Step 3: Locate get_available_tools() Method

Search the wrapper file for:

```python
def get_available_tools(self):
    return [
        {"name": "tool_name_1", ...},
        {"name": "tool_name_2", ...},
        ...
    ]
```

**Variations**:
- Method might return a list comprehension
- List might be built dynamically from `self._actions` or similar
- Some toolkits have multiple tool groups concatenated

### Step 4: Count Tool Definitions

**Rules for Counting**:

✅ **Count These**:
- Each `{"name": "tool_name", ...}` dictionary in the return list
- Tools defined in list comprehensions
- Tools dynamically added to the list

❌ **Don't Count These**:
- Commented-out tools (lines starting with `#`)
- Tools inside comment blocks (`# {` ... `# }`)
- Disabled tools (explicitly marked as disabled)
- Placeholder/example entries

**Example**:

```python
def get_available_tools(self):
    return [
        {"name": "get_issue", "description": "..."},      # ✅ COUNT
        {"name": "create_issue", "description": "..."},  # ✅ COUNT
        # {"name": "old_tool", "description": "..."},   # ❌ DON'T COUNT (commented)
        {"name": "update_issue", "description": "..."},  # ✅ COUNT
    ]
# Total: 3 tools
```

### Step 5: Extract Tool Names

Create a list of all active tool names:

1. Find each `"name":` field in tool definitions
2. Extract the exact string value (preserve underscores, case)
3. Build a list of tool names

### Step 6: Document Disabled Tools (Optional)

If there are commented/disabled tools, note them separately:

- Tool name
- Reason for disabling (if documented)
- Location in file (line number)

## Expected Output

Provide results in this format:

```json
{
  "toolkit": "github",
  "wrapper_file": "api_wrapper.py",
  "location": "alita_sdk/tools/github/api_wrapper.py",
  "tool_count": 15,
  "tools": [
    {"name": "get_issue", "description": "Fetch issue details"},
    {"name": "create_issue", "description": "Create new issue"},
    {"name": "list_issues", "description": "List repository issues"}
  ],
  "disabled_tools": [
    {"name": "deprecated_tool", "reason": "Replaced by new_tool", "line": 145}
  ]
}
```

## Common Patterns

### Pattern 1: Simple List

```python
def get_available_tools(self):
    return [
        {"name": "tool1", ...},
        {"name": "tool2", ...},
    ]
```

**Count**: 2 tools

### Pattern 2: List Comprehension

```python
def get_available_tools(self):
    return [
        {"name": action.name, ...}
        for action in self._actions
    ]
```

**Count**: Count items in `self._actions`

### Pattern 3: Multiple Lists Concatenated

```python
def get_available_tools(self):
    base_tools = [{"name": "tool1", ...}]
    admin_tools = [{"name": "tool2", ...}]
    return base_tools + admin_tools
```

**Count**: Sum of all lists

### Pattern 4: Conditional Tools

```python
def get_available_tools(self):
    tools = [{"name": "tool1", ...}]
    if self.has_admin:
        tools.append({"name": "admin_tool", ...})
    return tools
```

**Count**: All possible tools (assume conditions can be met)

## Validation Checklist

- [ ] Found correct wrapper file
- [ ] Located `get_available_tools()` method
- [ ] Counted all non-commented tool definitions
- [ ] Excluded commented/disabled tools
- [ ] Extracted exact tool names
- [ ] Noted any disabled tools
- [ ] Cross-referenced with toolkit's `__init__.py` if needed

## Troubleshooting

**Problem**: Can't find wrapper file  
**Solution**: Check if it's a container directory or framework utility

**Problem**: `get_available_tools()` returns empty list  
**Solution**: Check if tools are registered differently (look at `get_toolkit()` method)

**Problem**: Dynamic tool generation  
**Solution**: Trace back to source of tool definitions (e.g., `self._actions`)

**Problem**: Unclear if tool is active  
**Solution**: If not clearly commented out, count it as active

## Related Procedures

- [categorize-toolkit.md](./categorize-toolkit.md) - Determine toolkit category
- [count-tests.md](./count-tests.md) - Count test cases
- [skill.md](./skill.md) - Main coverage calculator skill
