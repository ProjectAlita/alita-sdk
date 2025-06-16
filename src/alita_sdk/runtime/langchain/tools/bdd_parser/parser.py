from __future__ import annotations

import os.path
import re
import textwrap
import typing
from dataclasses import dataclass, field
from functools import cached_property
from typing import cast

from ..bdd_parser import feature_types
from ..bdd_parser.bdd_exceptions import FeatureError

SPLIT_LINE_RE = re.compile(r"(?<!\\)\|")
STEP_PARAM_RE = re.compile(r"<(.+?)>")
COMMENT_RE = re.compile(r"(^|(?<=\s))#")
STEP_PREFIXES = [
    ("Feature:", feature_types.FEATURE),
    ("Narrative:", feature_types.NARRATIVE),
    ("Scenario Outline:", feature_types.SCENARIO_OUTLINE),
    ("Examples:", feature_types.EXAMPLES),
    ("Scenario:", feature_types.SCENARIO),
    ("Lifecycle:", feature_types.LIFECYCLE),
    ("Background:", feature_types.BACKGROUND),
    ("Given ", feature_types.GIVEN),
    ("When ", feature_types.WHEN),
    ("Then ", feature_types.THEN),
    ("@", feature_types.TAG),
    # Continuation of the previously mentioned step type
    ("And ", None),
    ("But ", None),
]

TYPES_WITH_DESCRIPTIONS = [feature_types.FEATURE, feature_types.SCENARIO, feature_types.SCENARIO_OUTLINE,
                           feature_types.NARRATIVE]

if typing.TYPE_CHECKING:
    from typing import Any, Iterable, Mapping, Match, Sequence


def split_line(line: str) -> list[str]:
    """Split the given Examples line.

    :param str|unicode line: Feature file Examples line.

    :return: List of strings.
    """
    return [cell.replace("\\|", "|").strip() for cell in SPLIT_LINE_RE.split(line)[1:-1]]


def parse_line(line: str) -> tuple[str, str]:
    """Parse step line to get the step prefix (Scenario, Given, When, Then or And) and the actual step name.

    :param line: Line of the Feature file.

    :return: `tuple` in form ("<prefix>", "<Line without the prefix>").
    """
    for prefix, _ in STEP_PREFIXES:
        if line.startswith(prefix):
            return prefix.strip(), line[len(prefix):].strip()
    return "", line


def strip_comments(line: str) -> str:
    """Remove comments.

    :param str line: Line of the Feature file.

    :return: Stripped line.
    """
    res = COMMENT_RE.search(line)
    if res:
        line = line[: res.start()]
    return line.strip()


def get_step_type(line: str) -> str | None:
    """Detect step type by the beginning of the line.

    :param str line: Line of the Feature file.

    :return: SCENARIO, GIVEN, WHEN, THEN, or `None` if can't be detected.
    """
    for prefix, _type in STEP_PREFIXES:
        if line.startswith(prefix):
            return _type
    return None


def parse_feature(basedir: str, filename: str, encoding: str = "utf-8", is_jbehave_story=False) -> Feature:
    """Parse the feature file.

    :param is_jbehave_story: Identifying if JBehave story is parsed right now or not.
    :param str basedir: Feature files base directory.
    :param str filename: Relative path to the feature file.
    :param str encoding: Feature file encoding (utf-8 by default).
    """
    __tracebackhide__ = True
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
    # in_examples_block = False  # A flag to track whether we're in an Examples block
    in_multiline_comment = False  # A flag to track if parser reached multiline comment or not

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
            # multiline step, so just add line and continue
            step.add_line(line)
            continue
        else:
            step = None
            multiline_step = False
        stripped_line = line.strip()
        clean_line = strip_comments(line)
        if not clean_line and (not prev_mode or prev_mode not in TYPES_WITH_DESCRIPTIONS):
            # Blank lines are included in feature and scenario descriptions
            continue
        # Ignore the meta instructions
        if "Meta" in clean_line:
            continue
        # check if the line has Narrative section in JBehave story file
        if "Narrative" in clean_line:
            is_narrative = True
            continue
        # check if the line has tags
        if clean_line.startswith('@'):
            # split the line into separate tags, strip the "@" and add to the list
            tags_in_line = clean_line.split()
            tag_lines += [tag.lstrip("@") for tag in tags_in_line]
        mode = get_step_type(clean_line) or mode
        # mode = get_step_type(clean_line) or mode

        # if mode == feature_types.EXAMPLES:
        #     in_examples_block = True  # We've entered an Examples block
        # elif mode and mode != feature_types.TAG and in_examples_block:
        #     in_examples_block = False  # We've exited an Examples block

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
                # Do not include comments in descriptions
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

        # Remove Feature, Given, When, Then, And
        keyword, parsed_line = parse_line(clean_line)

        if mode in [feature_types.SCENARIO, feature_types.SCENARIO_OUTLINE]:
            is_narrative = False
            # Lines between the scenario declaration
            # and the scenario's first step line
            # are considered part of the scenario description.
            if scenario and not keyword:
                # Do not include comments in descriptions
                if not stripped_line.startswith("#") or not stripped_line.startswith("!--"):
                    scenario.add_description_line(clean_line)
                continue
            # tags = get_tags(' '.join(tag_lines))
            tags = {tag.lstrip("@") for tag in tag_lines}
            scenario = ScenarioTemplate(
                feature=feature,
                name=parsed_line,
                line_number=line_number,
                tags=tags,
                templated=mode == feature_types.SCENARIO_OUTLINE,
            )
            feature.scenarios.append(scenario)
            tag_lines = []  # Reset the tag_lines
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
        # elif mode == feature_types.TAG and not in_examples_block:
        #     tag_lines.append(clean_line)
        prev_line = clean_line

    feature.description = "\n".join(description).strip()
    return feature


@dataclass
class Feature:
    scenarios: list[ScenarioTemplate]
    filename: str
    rel_filename: str
    name: str | None
    tags: set[str]
    background: Background | None
    lifecycle: Lifecycle | None
    line_number: int
    description: str


@dataclass
class ScenarioTemplate:
    """A scenario template.

    Created when parsing the feature file, it will then be combined with the examples to create a Scenario.
    """

    feature: Feature
    name: str
    line_number: int
    templated: bool
    tags: set[str] = field(default_factory=set)
    examples: Examples | None = field(default_factory=lambda: Examples())
    _steps: list[Step] = field(init=False, default_factory=list)
    _description_lines: list[str] = field(init=False, default_factory=list)

    def add_step(self, step: Step) -> None:
        step.scenario = self
        self._steps.append(step)

    @property
    def steps(self) -> list[Step]:
        background = self.feature.background
        return (background.steps if background else []) + self._steps

    def render(self, context: Mapping[str, Any]) -> Scenario:
        background_steps = self.feature.background.steps if self.feature.background else []
        if not self.templated:
            scenario_steps = self._steps
        else:
            scenario_steps = [
                Step(
                    name=step.render(context),
                    type=step.type,
                    indent=step.indent,
                    line_number=step.line_number,
                    keyword=step.keyword,
                )
                for step in self._steps
            ]
        steps = background_steps + scenario_steps
        return Scenario(
            feature=self.feature,
            name=self.name,
            line_number=self.line_number,
            steps=steps,
            tags=self.tags,
            description=self._description_lines,
        )

    def add_description_line(self, description_line):
        """Add a description line to the scenario.
        :param str description_line:
        """
        self._description_lines.append(description_line)

    @property
    def description(self):
        """Get the scenario's description.
        :return: The scenario description
        """
        return "\n".join(self._description_lines)


@dataclass
class Scenario:
    feature: Feature
    name: str
    line_number: int
    steps: list[Step]
    tags: set[str] = field(default_factory=set)
    description: list[str] = field(default_factory=list)


@dataclass
class Step:
    type: str
    _name: str
    line_number: int
    indent: int
    keyword: str
    failed: bool = field(init=False, default=False)
    scenario: ScenarioTemplate | None = field(init=False, default=None)
    background: Background | None = field(init=False, default=None)
    lifecycle: Lifecycle | None = field(init=False, default=None)
    lines: list[str] = field(init=False, default_factory=list)

    def __init__(self, name: str, type: str, indent: int, line_number: int, keyword: str) -> None:
        self.name = name
        self.type = type
        self.indent = indent
        self.line_number = line_number
        self.keyword = keyword

        self.failed = False
        self.scenario = None
        self.background = None
        self.lifecycle = None
        self.lines = []

    def add_line(self, line: str) -> None:
        """Add line to the multiple step.

        :param str line: Line of text - the continuation of the step name.
        """
        self.lines.append(line)
        self._invalidate_full_name_cache()

    @cached_property
    def full_name(self) -> str:
        multilines_content = textwrap.dedent("\n".join(self.lines)) if self.lines else ""

        # Remove the multiline quotes, if present.
        multilines_content = re.sub(
            pattern=r'^"""\n(?P<content>.*)\n"""$',
            repl=r"\g<content>",
            string=multilines_content,
            flags=re.DOTALL,  # Needed to make the "." match also new lines
        )

        lines = [self._name] + [multilines_content]
        return "\n".join(lines).strip()

    def _invalidate_full_name_cache(self) -> None:
        """Invalidate the full_name cache."""
        if "full_name" in self.__dict__:
            del self.full_name

    @property
    def name(self) -> str:
        return self.full_name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value
        self._invalidate_full_name_cache()

    def __str__(self) -> str:
        """Full step name including the type."""
        return f'{self.type.capitalize()} "{self.name}"'

    @property
    def params(self) -> tuple[str, ...]:
        return tuple(frozenset(STEP_PARAM_RE.findall(self.name)))

    def render(self, context: Mapping[str, Any]) -> str:
        def replacer(m: Match):
            varname = m.group(1)
            return str(context[varname])

        return STEP_PARAM_RE.sub(replacer, self.name)


@dataclass
class Background:
    feature: Feature
    line_number: int
    steps: list[Step] = field(init=False, default_factory=list)

    def add_step(self, step: Step) -> None:
        """Add step to the background."""
        step.background = self
        self.steps.append(step)


@dataclass
class Lifecycle:
    line_number: int
    lifecycle_type: str | None = None
    steps: list[Step] = field(init=False, default_factory=list)

    def add_step(self, step: Step) -> None:
        """Add step to the lifecycle."""
        step.lifecycle = self
        self.steps.append(step)


@dataclass
class Examples:
    """Example table."""

    line_number: int | None = field(default=None)
    name: str | None = field(default=None)

    example_params: list[str] = field(init=False, default_factory=list)
    examples: list[Sequence[str]] = field(init=False, default_factory=list)

    def set_param_names(self, keys: Iterable[str]) -> None:
        self.example_params = [str(key) for key in keys]

    def add_example(self, values: Sequence[str]) -> None:
        self.examples.append(values)

    def as_contexts(self) -> Iterable[dict[str, Any]]:
        if not self.examples:
            return

        header, rows = self.example_params, self.examples

        for row in rows:
            assert len(header) == len(row)
            yield dict(zip(header, row))

    def __bool__(self) -> bool:
        return bool(self.examples)


def get_tags(line: str | None) -> set[str]:
    """Get tags out of the given line.

    :param str line: Feature file text line.

    :return: List of tags.
    """
    if not line or not line.strip().startswith("@"):
        return set()
    return {tag.lstrip("@") for tag in line.strip().split(" @") if len(tag) > 1}
