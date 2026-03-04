"""
Test runner engine for document loader tests.

Directory layout (base_dir = .alita/tests/test_loaders/):
  base_dir/
    [LOADER]/
      input/   - input JSON definitions
      output/  - stable baseline files (committed, compared against actual)
      files/   - test data files for this loader
    test_results/        - test run outputs
      output_[TIMESTAMP]/  - actual run results, created each test run
        [LOADER]/
          [input_name]_config_[i].json
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _load_documents_with_production_config(file_path: Path, config: Dict[str, Any]) -> List:
    """Load documents using production configuration logic.
    
    This replicates the logic from process_content_by_type but uses the actual
    file path instead of creating a temp file, so metadata contains correct paths.
    """
    from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map, LoaderProperties
    
    extension = file_path.suffix.lower()
    loader_config = loaders_map.get(extension)
    if not loader_config:
        raise ValueError(f"No loader found for extension: {extension}")
    
    loader_cls = loader_config['class']
    loader_kwargs = dict(loader_config.get('kwargs', {}))
    
    # Apply chunking_config override logic (same as process_content_by_type)
    allowed_to_override = loader_config.get('allowed_to_override', loader_kwargs)
    
    # Start with production defaults from allowed_to_override
    loader_kwargs.update(allowed_to_override)
    
    # Apply user overrides (filtered by allowed_to_override keys)
    if config:
        for key in set(config.keys()) & set(allowed_to_override.keys()):
            loader_kwargs[key] = config[key]
    
    # Handle LLM and prompt placeholders
    if LoaderProperties.LLM.value in loader_kwargs and loader_kwargs.pop(LoaderProperties.LLM.value):
        loader_kwargs['llm'] = None  # No LLM in tests
    if LoaderProperties.PROMPT_DEFAULT.value in loader_kwargs and loader_kwargs.pop(LoaderProperties.PROMPT_DEFAULT.value):
        from alita_sdk.tools.utils.content_parser import image_processing_prompt
        loader_kwargs[LoaderProperties.PROMPT.value] = image_processing_prompt
    
    # Instantiate and load
    loader = loader_cls(file_path=str(file_path), **loader_kwargs)
    return list(loader.load())

OUTPUT_DIR_PREFIX = "output_"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LoaderTestInput:
    """Parsed content of a single input JSON file from [LOADER]/input/."""
    file_path: str
    configs: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_file(cls, json_path: Path) -> "LoaderTestInput":
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "file_path" not in data:
            raise ValueError(f"Missing 'file_path' key in {json_path}")
        configs = data.get("configs", [{}])
        if not configs:
            configs = [{}]
        return cls(file_path=data["file_path"], configs=configs)

    def resolved_file_path(self, input_json_path: Path) -> Path:
        """Resolve file_path relative to the input JSON location."""
        p = Path(self.file_path)
        if p.is_absolute():
            return p
        return (input_json_path.parent / p).resolve()


@dataclass
class TestResult:
    loader_name: str
    input_name: str
    config_index: int
    config: Dict[str, Any]
    passed: bool
    actual_doc_count: int = 0
    expected_doc_count: int = 0
    error: Optional[str] = None
    diffs_summary: Optional[str] = None
    baseline_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loader": self.loader_name,
            "input": self.input_name,
            "config_index": self.config_index,
            "config": self.config,
            "passed": self.passed,
            "actual_doc_count": self.actual_doc_count,
            "expected_doc_count": self.expected_doc_count,
            "error": self.error,
            "diffs": self.diffs_summary,
        }

    def short_name(self) -> str:
        return f"{self.loader_name}/{self.input_name}[{self.config_index}]"


# ---------------------------------------------------------------------------
# Run directory helpers  (output_[TIMESTAMP] at loader_tests root)
# ---------------------------------------------------------------------------

def _run_dir_name(timestamp: str) -> str:
    return f"{OUTPUT_DIR_PREFIX}{timestamp}"


def find_all_run_dirs(root: Path) -> List[Path]:
    """Return all output_[TIMESTAMP] dirs inside test_results/, sorted oldest-first."""
    results_dir = root / "test_results"
    if not results_dir.is_dir():
        return []
    return sorted(
        (d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith(OUTPUT_DIR_PREFIX)),
        key=lambda d: d.name,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_loader_tests(base_dir: Path) -> Dict[str, Dict[str, LoaderTestInput]]:
    """
    Scan base_dir/<LOADER_NAME>/input/*.json and build:
      {loader_name: {input_basename: LoaderTestInput}}
    """
    results: Dict[str, Dict[str, LoaderTestInput]] = {}
    for loader_dir in sorted(base_dir.iterdir()):
        if not loader_dir.is_dir():
            continue
        input_dir = loader_dir / "input"
        if not input_dir.is_dir():
            continue
        loader_inputs: Dict[str, LoaderTestInput] = {}
        for json_file in sorted(input_dir.glob("*.json")):
            try:
                loader_inputs[json_file.stem] = LoaderTestInput.from_file(json_file)
            except Exception as exc:
                logger.warning(f"Skipping {json_file}: {exc}")
        if loader_inputs:
            results[loader_dir.name] = loader_inputs
    return results


# ---------------------------------------------------------------------------
# Loader lookup
# ---------------------------------------------------------------------------

def _get_loader_class_and_config(loader_name: str, file_path: Path):
    """Return (loader_cls, loader_config_dict) by class name then extension fallback."""
    from alita_sdk.runtime.langchain.document_loaders.constants import loaders_map

    for config in loaders_map.values():
        cls = config.get("class")
        if cls is not None and cls.__name__ == loader_name:
            return cls, config

    ext = file_path.suffix.lower()
    if ext in loaders_map:
        return loaders_map[ext]["class"], loaders_map[ext]

    raise ValueError(f"No loader found for '{loader_name}' and extension '{ext}'")


def _build_kwargs(loader_config: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge loader default kwargs with the config override dict."""
    base = dict(loader_config.get("kwargs", {}))
    base.update(override)
    return base


# ---------------------------------------------------------------------------
# Single test execution
# ---------------------------------------------------------------------------

def run_single_config_test(
    loader_name: str,
    input_name: str,
    config_index: int,
    config: Dict[str, Any],
    file_path: Path,
    baseline_path: Path,
    actual_output_path: Path,
) -> TestResult:
    """Execute loader for one config, save actual output, compare against baseline.

    baseline_path      - data/[LOADER]/output/[filename]  (expected/stable)
    actual_output_path - output_[TIMESTAMP]/[LOADER]/[filename]  (this run)
    """
    from .loader_test_utils import compare_documents, load_expected_documents, save_documents

    result = TestResult(
        loader_name=loader_name,
        input_name=input_name,
        config_index=config_index,
        config=config,
        passed=False,
        baseline_path=baseline_path,
    )

    if not baseline_path.exists():
        result.error = (
            f"Baseline not found: {baseline_path}  "
            f"(run 'generate-expected {loader_name} {input_name}' first)"
        )
        return result

    try:
        expected_docs = load_expected_documents(baseline_path)
        result.expected_doc_count = len(expected_docs)
    except Exception as exc:
        result.error = f"Failed to load baseline {baseline_path}: {exc}"
        return result

    try:
        # Use production configuration logic while preserving file paths
        actual_docs = _load_documents_with_production_config(file_path, config)
        result.actual_doc_count = len(actual_docs)
    except Exception as exc:
        result.error = f"Loader exception: {exc}"
        return result

    # Save actual output
    try:
        actual_output_path.parent.mkdir(parents=True, exist_ok=True)
        save_documents(actual_docs, actual_output_path)
    except Exception as exc:
        logger.warning(f"Could not save actual output to {actual_output_path}: {exc}")

    cmp = compare_documents(actual_docs, expected_docs, loader_name=loader_name)
    result.passed = cmp.passed
    result.diffs_summary = cmp.summary() if not cmp.passed else None
    return result


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------

def run_input_tests(
    loader_name: str,
    input_name: str,
    test_input: LoaderTestInput,
    base_dir: Path,
    input_json_path: Path,
    run_output_dir: Path,
    config_index: Optional[int] = None,
) -> List[TestResult]:
    """Run tests for all (or one) config entries of a single input JSON.

    base_dir       - data/ dir (baselines at base_dir/[LOADER]/output/)
    run_output_dir - output_[TIMESTAMP]/[LOADER]/ (actual output for this run)
    """
    file_path = test_input.resolved_file_path(input_json_path)
    baseline_dir = base_dir / loader_name / "output"
    results = []

    for i, cfg in enumerate(test_input.configs):
        if config_index is not None and i != config_index:
            continue
        filename = f"{input_name}_config_{i}.json"
        baseline_path = baseline_dir / filename
        actual_output_path = run_output_dir / filename
        results.append(run_single_config_test(
            loader_name=loader_name,
            input_name=input_name,
            config_index=i,
            config=cfg,
            file_path=file_path,
            baseline_path=baseline_path,
            actual_output_path=actual_output_path,
        ))
    return results


def run_all_tests(
    base_dir: Path,
    loader_filter: Optional[str] = None,
    input_filter: Optional[str] = None,
    config_index: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> Tuple[Dict[str, List[TestResult]], Path]:
    """Discover and run all matching tests.

    Creates a single output_[TIMESTAMP] dir inside test_results/ with
    [LOADER]/ subdirs for actual outputs.

    Returns (all_results, run_dir).
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    root = base_dir
    run_dir = root / "test_results" / _run_dir_name(timestamp)
    discovery = discover_loader_tests(base_dir)
    all_results: Dict[str, List[TestResult]] = {}

    for loader_name, inputs in discovery.items():
        if loader_filter and loader_name != loader_filter:
            continue
        run_output_dir = run_dir / loader_name
        loader_results = []
        for input_name, test_input in inputs.items():
            if input_filter and input_name != input_filter:
                continue
            input_json_path = base_dir / loader_name / "input" / f"{input_name}.json"
            loader_results.extend(run_input_tests(
                loader_name=loader_name,
                input_name=input_name,
                test_input=test_input,
                base_dir=base_dir,
                input_json_path=input_json_path,
                run_output_dir=run_output_dir,
                config_index=config_index,
            ))
        if loader_results:
            all_results[loader_name] = loader_results

    return all_results, run_dir


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_results_text(all_results: Dict[str, List[TestResult]], run_dir: Optional[Path] = None) -> str:
    """Render a human-readable test summary."""
    lines = []
    if run_dir:
        lines.append(f"Actual output: {run_dir}")
    total_pass = total_fail = total_error = 0

    for loader_name, results in all_results.items():
        lines.append(f"\n{loader_name}")
        lines.append("-" * len(loader_name))
        for r in results:
            # Add delimiter before each test case for better readability
            lines.append("")  # Blank line before each test case
            lines.append(f"  ┌─ {r.input_name}[{r.config_index}] ─────────────────────────────────────")
            
            if r.error:
                icon, total_error = "E", total_error + 1
            elif r.passed:
                icon, total_pass = "+", total_pass + 1
            else:
                icon, total_fail = "F", total_fail + 1
            label = f"  [{icon}] {r.input_name}[{r.config_index}]"
            detail = f"docs: {r.actual_doc_count}/{r.expected_doc_count}"
            lines.append(f"{label:<45} {detail}")
            if r.error:
                lines.append(f"       ERROR: {r.error}")
                if r.baseline_path:
                    lines.append(f"       Baseline: {r.baseline_path}")
            elif r.diffs_summary:
                if r.baseline_path:
                    lines.append(f"       Baseline: {r.baseline_path}")
                for dl in r.diffs_summary.splitlines():
                    lines.append(f"       {dl}")

    total = total_pass + total_fail + total_error
    lines.append(f"\nResults: {total_pass}/{total} passed  ({total_fail} failed, {total_error} errors)")
    return "\n".join(lines)


def format_results_json(all_results: Dict[str, List[TestResult]], run_dir: Optional[Path] = None) -> str:
    """Render JSON output for CI."""
    total_pass = sum(1 for rs in all_results.values() for r in rs if r.passed and not r.error)
    total_fail = sum(1 for rs in all_results.values() for r in rs if not r.passed or r.error)
    output = {
        "passed": total_pass,
        "failed": total_fail,
        "run_dir": str(run_dir) if run_dir else None,
        "results": {loader: [r.to_dict() for r in rs] for loader, rs in all_results.items()},
    }
    return json.dumps(output, indent=2, ensure_ascii=False)
