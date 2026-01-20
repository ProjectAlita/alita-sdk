"""
Shared tool prompt constants for file operations across toolkits.

These constants provide consistent descriptions for update_file and edit_file tools.
"""

# Base description for OLD/NEW marker format - used by all file editing operations
UPDATE_FILE_MARKERS_DESCRIPTION = """
**Marker format:**
- OLD block: starts with `OLD <<<<` and ends with `>>>> OLD`
- NEW block: starts with `NEW <<<<` and ends with `>>>> NEW`
- **IMPORTANT:** Markers must be on their own dedicated line (not inline with other content)
- Content must be on separate lines between opening and closing markers
- Leading/trailing whitespace in content is stripped
- Multiple OLD/NEW pairs are supported for multiple edits in a single request

**Examples:**

Example 1 - Replace single line:
```
OLD <<<<
old contents
>>>> OLD
NEW <<<<
new contents
>>>> NEW
```

Example 2 - Add new lines:
```
OLD <<<<
existing line
>>>> OLD
NEW <<<<
existing line
added line
>>>> NEW
```

Example 3 - Replace multiple lines:
```
OLD <<<<
old line 1
old line 2
>>>> OLD
NEW <<<<
new line 1
new line 2
new line 3
>>>> NEW
```

Example 4 - Multiple edits in one request:
```
OLD <<<<
first old content
>>>> OLD
NEW <<<<
first new content
>>>> NEW
OLD <<<<
second old content
>>>> OLD
NEW <<<<
second new content
>>>> NEW
```"""

# Description for update_file when file_path is a separate parameter
UPDATE_FILE_PROMPT_NO_PATH = f"""Updates a file using OLD/NEW markers.
{UPDATE_FILE_MARKERS_DESCRIPTION}"""

# Description for update_file when file_path is in the first line of file_query
UPDATE_FILE_PROMPT_WITH_PATH = f"""Updates a file in repository.

**Input format:**
First non-empty line must be the file path (must not start with a slash), followed by OLD/NEW markers.

Example:
```
path/to/file.txt
OLD <<<<
old content
>>>> OLD
NEW <<<<
new content
>>>> NEW
```
{UPDATE_FILE_MARKERS_DESCRIPTION}"""

# Common description for edit_file/update_file operations
EDIT_FILE_DESCRIPTION = """Edit file by path using OLD/NEW markers for precise replacements.
        
Only works with text files (markdown, txt, csv, json, xml, html, yaml, code files).
"""

