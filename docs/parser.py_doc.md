# parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/parser.py`

## Data Flow

The data flow within `parser.py` revolves around parsing feature files used in Behavior-Driven Development (BDD). The primary data elements are lines from feature files, which are read, stripped of comments, and parsed to identify BDD components such as features, scenarios, steps, and tags. The data flow begins with reading the feature file content, followed by line-by-line processing to detect and categorize different BDD elements. Intermediate variables like `mode`, `step`, and `scenario` are used to maintain the state of the parsing process. The parsed data is then structured into objects like `Feature`, `ScenarioTemplate`, and `Step`, which represent the hierarchical structure of a BDD feature file.

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
This snippet shows the reading of the file content and the initial processing of each line, including stripping comments and handling multiline steps.

## Functions Descriptions

### `split_line(line: str) -> list[str]`

Splits a given Examples line from a feature file into a list of strings, handling escaped pipe characters.

### `parse_line(line: str) -> tuple[str, str]`

Parses a step line to extract the step prefix (e.g., Scenario, Given, When, Then, And) and the actual step name.

### `strip_comments(line: str) -> str`

Removes comments from a line in the feature file.

### `get_step_type(line: str) -> str | None`

Detects the step type (e.g., SCENARIO, GIVEN, WHEN, THEN) based on the beginning of the line.

### `parse_feature(basedir: str, filename: str, encoding: str = "utf-8", is_jbehave_story=False) -> Feature`

Parses a feature file, identifying and structuring its components into a `Feature` object. This function handles the main parsing logic, including reading the file, processing each line, and constructing the hierarchical structure of the feature file.

Example:
```python
def parse_feature(basedir: str, filename: str, encoding: str = "utf-8", is_jbehave_story=False) -> Feature:
    abs_filename = os.path.abspath(os.path.join(basedir, filename))
    rel_filename = os.path.join(os.path.basename(basedir), filename)
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
    scenario: ScenarioTemplate | None = None
    mode: str | None = None
    prev_mode = None
    description: list[str] = []
    step = None
    multiline_step = False
    prev_line = None
    is_narrative = False
    is_already_visit_lifecycle = False

    tag_lines = []
    in_multiline_comment = False

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
This example shows the initial setup and line processing within the `parse_feature` function.

## Dependencies Used and Their Descriptions

### `os`

Used for file path manipulations and to get absolute paths.

### `re`

Used for regular expression operations, such as splitting lines and detecting comments.

### `textwrap`

Used for dedenting multiline strings.

### `typing`

Used for type annotations and type checking.

### `dataclasses`

Used to define data structures like `Feature`, `ScenarioTemplate`, `Scenario`, `Step`, `Background`, `Lifecycle`, and `Examples`.

### `functools`

Used for the `cached_property` decorator to cache the full name of a step.

### `feature_types`

Defines constants for different BDD components like FEATURE, SCENARIO, GIVEN, WHEN, THEN, etc.

### `FeatureError`

Custom exception used to handle errors specific to feature file parsing.

## Functional Flow

The functional flow of `parser.py` starts with the `parse_feature` function, which reads the content of a feature file and processes it line by line. The flow involves detecting the type of each line (e.g., feature, scenario, step), stripping comments, and handling multiline steps. The parsed data is structured into objects representing the feature file's components. The flow includes several helper functions like `split_line`, `parse_line`, `strip_comments`, and `get_step_type` to assist in processing each line and categorizing it correctly.

Example:
```python
mode = get_step_type(clean_line) or mode
if not in_multiline_comment and line.lstrip().startswith('"""'):
    in_multiline_comment = True
    continue
elif in_multiline_comment and line.rstrip().endswith('"""'):
    in_multiline_comment = False
    continue
elif in_multiline_comment:
    continue

allowed_prev_mode = (
    feature_types.BACKGROUND,
    feature_types.LIFECYCLE,
    feature_types.GIVEN,
    feature_types.WHEN,
    feature_types.THEN
)

if not scenario and prev_mode not in allowed_prev_mode and mode in feature_types.STEP_TYPES and not is_narrative:
    raise FeatureError(
        "Step definition outside of a Scenario or a Background", line_number, clean_line, filename
    )
```
This snippet shows part of the functional flow where the mode is determined, multiline comments are handled, and step definitions are validated.

## Endpoints Used/Created

The `parser.py` file does not explicitly define or call any endpoints. Its primary focus is on parsing feature files and structuring the parsed data into objects representing BDD components.