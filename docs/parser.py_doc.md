# parser.py

**Path:** `src/alita_sdk/langchain/tools/bdd_parser/parser.py`

## Data Flow

The data flow within `parser.py` revolves around parsing feature files used in Behavior-Driven Development (BDD). The primary data elements are lines from the feature files, which are read, stripped of comments, and then parsed to identify different BDD components such as features, scenarios, steps, and tags. The data flow can be summarized as follows:

1. **Reading the File:** The feature file is read line by line.
2. **Stripping Comments:** Comments are removed from each line.
3. **Identifying Components:** Each line is analyzed to identify BDD components (e.g., Feature, Scenario, Given, When, Then).
4. **Storing Components:** Identified components are stored in appropriate data structures (e.g., `Feature`, `ScenarioTemplate`, `Step`).
5. **Handling Multiline Steps:** Multiline steps are handled by appending subsequent lines to the current step.
6. **Returning Parsed Data:** The parsed data is returned as a `Feature` object containing all identified components.

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
    if "Meta" in clean_line:
        continue
    if "Narrative" in clean_line:
        is_narrative = True
        continue
    if clean_line.startswith('@'):
        tags_in_line = clean_line.split()
        tag_lines += [tag.lstrip("@") for tag in tags_in_line]
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
    if mode == feature_types.FEATURE:
        if prev_mode is None or prev_mode == feature_types.TAG:
            _, feature.name = parse_line(clean_line)
            feature.line_number = line_number
            feature.tags = get_tags(prev_line)
        elif prev_mode == feature_types.FEATURE:
            if not stripped_line.startswith("#") or not stripped_line.startswith("!--"):
                description.append(clean_line)
        else:
            raise FeatureError(
                "Multiple features1 are not allowed in a single feature file",
                line_number,
                clean_line,
                filename,
            )
    prev_mode = mode
    keyword, parsed_line = parse_line(clean_line)
    if mode in [feature_types.SCENARIO, feature_types.SCENARIO_OUTLINE]:
        is_narrative = False
        if scenario and not keyword:
            if not stripped_line.startswith("#") or not stripped_line.startswith("!--"):
                scenario.add_description_line(clean_line)
            continue
        tags = {tag.lstrip("@") for tag in tag_lines}
        scenario = ScenarioTemplate(
            feature=feature,
            name=parsed_line,
            line_number=line_number,
            tags=tags,
            templated=mode == feature_types.SCENARIO_OUTLINE,
        )
        feature.scenarios.append(scenario)
        tag_lines = []
    elif mode == feature_types.BACKGROUND:
        feature.background = Background(feature=feature, line_number=line_number)
    elif mode == feature_types.LIFECYCLE and not is_already_visit_lifecycle:
        feature.lifecycle = Lifecycle(lifecycle_type=None, line_number=line_number)
        is_already_visit_lifecycle = True
    elif mode == feature_types.EXAMPLES:
        if not is_jbehave_story:
            mode = feature_types.EXAMPLES_HEADERS
            scenario.examples.line_number = line_number
        continue
    elif mode == feature_types.EXAMPLES_HEADERS:
        scenario.examples.set_param_names([l for l in split_line(parsed_line) if l])
        mode = feature_types.EXAMPLE_LINE
    elif mode == feature_types.EXAMPLE_LINE:
        scenario.examples.add_example([l for l in split_line(stripped_line)])
    elif mode and mode not in (feature_types.FEATURE, feature_types.TAG):
        step = Step(name=parsed_line, type=mode, indent=line_indent, line_number=line_number, keyword=keyword)
        if feature.background and not scenario:
            feature.background.add_step(step)
        elif feature.lifecycle and not scenario:
            if "Before" in clean_line:
                feature.lifecycle.lifecycle_type = "Before:"
                continue
            elif "After" in clean_line:
                feature.lifecycle.lifecycle_type = "After:"
                continue
            else:
                feature.lifecycle.add_step(step)
        else:
            if stripped_line.startswith('#') or stripped_line.startswith('!--'):
                continue
            if not is_narrative:
                scenario = cast(ScenarioTemplate, scenario)
                scenario.add_step(step)
    prev_line = clean_line
feature.description = "\n".join(description).strip()
return feature
```

## Functions Descriptions

### `split_line(line: str) -> list[str]`

This function splits a given line from the Examples section of a feature file into individual cells. It uses a regular expression to split the line by unescaped pipe characters (`|`). The resulting cells are stripped of leading and trailing whitespace and returned as a list of strings.

**Parameters:**
- `line` (str): The line from the Examples section to be split.

**Returns:**
- `list[str]`: A list of strings representing the individual cells in the Examples line.

Example:
```python
def split_line(line: str) -> list[str]:
    return [cell.replace("\\|", "|").strip() for cell in SPLIT_LINE_RE.split(line)[1:-1]]
```

### `parse_line(line: str) -> tuple[str, str]`

This function parses a step line to extract the step prefix (e.g., Scenario, Given, When, Then, And) and the actual step name. It iterates through predefined step prefixes and checks if the line starts with any of them. If a match is found, the prefix and the remaining part of the line are returned as a tuple.

**Parameters:**
- `line` (str): The line from the feature file to be parsed.

**Returns:**
- `tuple[str, str]`: A tuple containing the step prefix and the remaining part of the line.

Example:
```python
def parse_line(line: str) -> tuple[str, str]:
    for prefix, _ in STEP_PREFIXES:
        if line.startswith(prefix):
            return prefix.strip(), line[len(prefix):].strip()
    return "", line
```

### `strip_comments(line: str) -> str`

This function removes comments from a given line. It uses a regular expression to search for comment markers (`#`) and strips the line up to the start of the comment. The resulting line is then stripped of leading and trailing whitespace and returned.

**Parameters:**
- `line` (str): The line from which comments should be removed.

**Returns:**
- `str`: The line with comments removed.

Example:
```python
def strip_comments(line: str) -> str:
    res = COMMENT_RE.search(line)
    if res:
        line = line[: res.start()]
    return line.strip()
```

### `get_step_type(line: str) -> str | None`

This function detects the step type by examining the beginning of a given line. It iterates through predefined step prefixes and checks if the line starts with any of them. If a match is found, the corresponding step type is returned.

**Parameters:**
- `line` (str): The line to be checked for step type.

**Returns:**
- `str | None`: The detected step type or `None` if no match is found.

Example:
```python
def get_step_type(line: str) -> str | None:
    for prefix, _type in STEP_PREFIXES:
        if line.startswith(prefix):
            return _type
    return None
```

### `parse_feature(basedir: str, filename: str, encoding: str = "utf-8", is_jbehave_story=False) -> Feature`

This function parses a feature file and returns a `Feature` object containing all identified components such as scenarios, steps, and tags. It reads the file, processes each line to identify BDD components, and stores them in appropriate data structures.

**Parameters:**
- `basedir` (str): The base directory of the feature files.
- `filename` (str): The relative path to the feature file.
- `encoding` (str): The encoding of the feature file (default is "utf-8").
- `is_jbehave_story` (bool): Flag to identify if a JBehave story is being parsed (default is False).

**Returns:**
- `Feature`: A `Feature` object containing all identified components.

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
        if "Meta" in clean_line:
            continue
        if "Narrative" in clean_line:
            is_narrative = True
            continue
        if clean_line.startswith('@'):
            tags_in_line = clean_line.split()
            tag_lines += [tag.lstrip("@") for tag in tags_in_line]
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
        if mode == feature_types.FEATURE:
            if prev_mode is None or prev_mode == feature_types.TAG:
                _, feature.name = parse_line(clean_line)
                feature.line_number = line_number
                feature.tags = get_tags(prev_line)
            elif prev_mode == feature_types.FEATURE:
                if not stripped_line.startswith("#") or not stripped_line.startswith("!--"):
                    description.append(clean_line)
            else:
                raise FeatureError(
                    "Multiple features1 are not allowed in a single feature file",
                    line_number,
                    clean_line,
                    filename,
                )
        prev_mode = mode
        keyword, parsed_line = parse_line(clean_line)
        if mode in [feature_types.SCENARIO, feature_types.SCENARIO_OUTLINE]:
            is_narrative = False
            if scenario and not keyword:
                if not stripped_line.startswith("#") or not stripped_line.startswith("!--"):
                    scenario.add_description_line(clean_line)
                continue
            tags = {tag.lstrip("@") for tag in tag_lines}
            scenario = ScenarioTemplate(
                feature=feature,
                name=parsed_line,
                line_number=line_number,
                tags=tags,
                templated=mode == feature_types.SCENARIO_OUTLINE,
            )
            feature.scenarios.append(scenario)
            tag_lines = []
        elif mode == feature_types.BACKGROUND:
            feature.background = Background(feature=feature, line_number=line_number)
        elif mode == feature_types.LIFECYCLE and not is_already_visit_lifecycle:
            feature.lifecycle = Lifecycle(lifecycle_type=None, line_number=line_number)
            is_already_visit_lifecycle = True
        elif mode == feature_types.EXAMPLES:
            if not is_jbehave_story:
                mode = feature_types.EXAMPLES_HEADERS
                scenario.examples.line_number = line_number
            continue
        elif mode == feature_types.EXAMPLES_HEADERS:
            scenario.examples.set_param_names([l for l in split_line(parsed_line) if l])
            mode = feature_types.EXAMPLE_LINE
        elif mode == feature_types.EXAMPLE_LINE:
            scenario.examples.add_example([l for l in split_line(stripped_line)])
        elif mode and mode not in (feature_types.FEATURE, feature_types.TAG):
            step = Step(name=parsed_line, type=mode, indent=line_indent, line_number=line_number, keyword=keyword)
            if feature.background and not scenario:
                feature.background.add_step(step)
            elif feature.lifecycle and not scenario:
                if "Before" in clean_line:
                    feature.lifecycle.lifecycle_type = "Before:"
                    continue
                elif "After" in clean_line:
                    feature.lifecycle.lifecycle_type = "After:"
                    continue
                else:
                    feature.lifecycle.add_step(step)
            else:
                if stripped_line.startswith('#') or stripped_line.startswith('!--'):
                    continue
                if not is_narrative:
                    scenario = cast(ScenarioTemplate, scenario)
                    scenario.add_step(step)
        prev_line = clean_line
    feature.description = "\n".join(description).strip()
    return feature
```

## Dependencies Used and Their Descriptions

### `os`

The `os` module is used for interacting with the operating system. In this file, it is used to construct absolute and relative file paths.

### `re`

The `re` module provides support for regular expressions. It is used extensively in this file for parsing lines, stripping comments, and identifying step prefixes.

### `textwrap`

The `textwrap` module is used to manipulate multiline strings, particularly for dedenting multiline step content.

### `typing`

The `typing` module provides support for type hints. It is used to specify the expected types of function parameters and return values.

### `dataclasses`

The `dataclasses` module provides a decorator and functions for creating data classes. It is used to define the `Feature`, `ScenarioTemplate`, `Scenario`, `Step`, `Background`, `Lifecycle`, and `Examples` classes.

### `functools`

The `functools` module is used to provide higher-order functions. In this file, it is used to cache the `full_name` property of the `Step` class.

### `feature_types`

The `feature_types` module is imported from the parent `bdd_parser` package. It provides constants representing different BDD components such as `FEATURE`, `SCENARIO`, `GIVEN`, `WHEN`, `THEN`, etc.

### `FeatureError`

The `FeatureError` class is imported from the `bdd_exceptions` module in the parent `bdd_parser` package. It is used to raise exceptions when there are errors in the feature file.

##