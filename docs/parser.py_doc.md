# parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/parser.py`

## Data Flow

The data flow within `parser.py` revolves around parsing feature files used in Behavior-Driven Development (BDD). The primary data elements are lines from feature files, which are read, stripped of comments, and then parsed to identify different BDD components such as features, scenarios, steps, and tags. The data flow can be summarized as follows:

1. **Reading the File:** The feature file is read line by line.
2. **Stripping Comments:** Comments are removed from each line.
3. **Identifying Components:** Each line is analyzed to identify BDD components (e.g., Feature, Scenario, Given, When, Then).
4. **Storing Components:** Identified components are stored in appropriate data structures (e.g., `Feature`, `ScenarioTemplate`, `Step`).
5. **Handling Multiline Steps:** Multiline steps are handled by appending subsequent lines until the step is complete.

Example:
```python
with open(abs_filename, encoding=encoding) as f:
    content = f.read()

for line_number, line in enumerate(content.splitlines(), start=1):
    unindented_line = line.lstrip()
    if unindented_line.startswith('#'):
        continue
    line_indent = len(line) - len(unindented_line)
    if step and ((step.indent < line_indent or ((not unindented_line) and multiline_step)) or (
            is_jbehave_story and (unindented_line.startswith('|') or unindented_line.endswith(')')))):
        multiline_step = True
        step.add_line(line)
        continue
    else:
        step = None
        multiline_step = False
    stripped_line = line.strip()
    clean_line = strip_comments(line)
    if not clean_line and (not prev_mode or prev_mode not in TYPES_WITH_DESCRIPTIONS):
        continue
```

## Functions Descriptions

### `split_line(line: str) -> list[str]`

Splits a given Examples line into a list of strings. It removes escaped pipe characters and trims whitespace.

- **Input:** A string representing a line from the Examples section.
- **Output:** A list of strings representing the split line.

### `parse_line(line: str) -> tuple[str, str]`

Parses a step line to extract the step prefix (e.g., Scenario, Given, When, Then) and the actual step name.

- **Input:** A string representing a line from the feature file.
- **Output:** A tuple containing the step prefix and the line without the prefix.

### `strip_comments(line: str) -> str`

Removes comments from a given line.

- **Input:** A string representing a line from the feature file.
- **Output:** A string with comments removed.

### `get_step_type(line: str) -> str | None`

Detects the step type by examining the beginning of the line.

- **Input:** A string representing a line from the feature file.
- **Output:** A string representing the step type or `None` if it cannot be detected.

### `parse_feature(basedir: str, filename: str, encoding: str = "utf-8", is_jbehave_story=False) -> Feature`

Parses the feature file and constructs a `Feature` object containing all parsed components.

- **Input:**
  - `basedir`: Base directory of the feature files.
  - `filename`: Relative path to the feature file.
  - `encoding`: Encoding of the feature file (default is utf-8).
  - `is_jbehave_story`: Boolean indicating if a JBehave story is being parsed.
- **Output:** A `Feature` object containing parsed components.

## Dependencies Used and Their Descriptions

### `os.path`

Used for handling file paths, such as joining paths and getting absolute paths.

### `re`

Used for regular expression operations, such as compiling patterns and searching for matches.

### `textwrap`

Used for dedenting multiline strings.

### `typing`

Used for type hinting and checking.

### `dataclasses`

Used for creating data classes, which are used to store parsed components like `Feature`, `ScenarioTemplate`, `Step`, etc.

### `functools`

Used for caching properties, specifically with `cached_property`.

### `feature_types`

Contains constants representing different BDD components (e.g., FEATURE, SCENARIO, GIVEN, WHEN, THEN).

### `bdd_exceptions`

Contains custom exceptions used for error handling during parsing.

## Functional Flow

The functional flow of `parser.py` involves reading a feature file, stripping comments, identifying BDD components, and storing them in appropriate data structures. The main function `parse_feature` orchestrates this process by iterating through each line of the file and applying various helper functions to parse and store components.

1. **Initialize Parsing:** Set up initial variables and read the file content.
2. **Iterate Through Lines:** For each line, strip comments and identify the component type.
3. **Store Components:** Depending on the identified component, store it in the appropriate data structure (e.g., `Feature`, `ScenarioTemplate`, `Step`).
4. **Handle Multiline Steps:** If a step spans multiple lines, continue appending lines until the step is complete.
5. **Return Parsed Feature:** After parsing all lines, return the constructed `Feature` object.

Example:
```python
feature = Feature(
    scenarios=[],
    filename=abs_filename,
    rel_filename=rel_filename,
    line_number=1,
    name=None,
    tags=set(),
    background=None,
    lifecycle=None,
    description="",
)

for line_number, line in enumerate(content.splitlines(), start=1):
    unindented_line = line.lstrip()
    if unindented_line.startswith('#'):
        continue
    line_indent = len(line) - len(unindented_line)
    if step and ((step.indent < line_indent or ((not unindented_line) and multiline_step)) or (
            is_jbehave_story and (unindented_line.startswith('|') or unindented_line.endswith(')')))):
        multiline_step = True
        step.add_line(line)
        continue
    else:
        step = None
        multiline_step = False
    stripped_line = line.strip()
    clean_line = strip_comments(line)
    if not clean_line and (not prev_mode or prev_mode not in TYPES_WITH_DESCRIPTIONS):
        continue
```

## Endpoints Used/Created

No explicit endpoints are defined or used within `parser.py`. The functionality is focused on parsing local feature files and does not involve network communication or API calls.