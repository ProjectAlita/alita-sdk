"""
Shared helpers for document loader pytest tests.

Imported by all test_alita_*_loader.py modules.
The sys.path setup required to import loader_test_runner happens
in conftest.py, which pytest loads automatically before this module is used.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

# This module lives in: .../document_loaders/test_data/scripts/
# test_data directory is one level up from here.
LOADERS_DIR = Path(__file__).resolve().parent.parent


def collect_loader_test_params(loader_name: str) -> List:
    """
    Scan <loader_name>/input/*.json and return a list of pytest.param entries.

    Each entry carries: input_name, config_index, config, file_path, baseline_path.

    Supports ``"_marks": ["risky"]`` inside any config dict — the key is
    stripped before the config is passed to the loader.
    """
    from loader_test_runner import LoaderTestInput  # on sys.path via conftest

    input_dir = LOADERS_DIR / loader_name / "input"
    params = []

    for json_file in sorted(input_dir.glob("*.json")):
        try:
            test_input = LoaderTestInput.from_file(json_file)
        except Exception as exc:
            params.append(
                pytest.param(
                    json_file.stem, 0, {}, json_file, json_file,
                    id=f"{json_file.stem}-COLLECTION_ERROR",
                    marks=pytest.mark.xfail(
                        reason=f"Could not parse input JSON: {exc}", strict=True
                    ),
                )
            )
            continue

        resolved_file = test_input.resolved_file_path(json_file)
        from loader_test_runner import sanitize_tag
        tag_marks = [getattr(pytest.mark, sanitize_tag(t)) for t in test_input.tags]

        for i, config in enumerate(test_input.configs):
            baseline = (
                LOADERS_DIR / loader_name / "output"
                / f"{json_file.stem}_config_{i}.json"
            )
            params.append(
                pytest.param(
                    json_file.stem,
                    i,
                    config,
                    resolved_file,
                    baseline,
                    id=f"{json_file.stem}-config{i}",
                    marks=tag_marks,
                )
            )

    return params


def run_loader_assert(
    loader_name: str,
    tmp_path: Path,
    input_name: str,
    config_index: int,
    config: Dict[str, Any],
    file_path: Path,
    baseline_path: Path,
) -> None:
    """
    Execute the loader for one (input, config) pair and assert it matches the
    committed baseline. Produces a rich failure message on mismatch.
    """
    from loader_test_runner import run_single_config_test  # on sys.path via conftest

    actual_output_path = tmp_path / f"{input_name}_config_{config_index}.json"

    result = run_single_config_test(
        loader_name=loader_name,
        input_name=input_name,
        config_index=config_index,
        config=config,
        file_path=file_path,
        baseline_path=baseline_path,
        actual_output_path=actual_output_path,
    )

    if result.passed:
        print(
            f"\n  [PASS] {loader_name} | {input_name}[{config_index}]"
            + (f" config={config}" if config else " config={}")
            + f" | docs matched: {result.actual_doc_count}"
        )
    else:
        lines = [
            "",
            f"  Loader   : {loader_name}",
            f"  Input    : {input_name}",
            f"  Config   : [{config_index}] {config}",
            f"  Baseline : {baseline_path}",
            f"  Actual   : {actual_output_path}",
            f"  Docs     : actual={result.actual_doc_count}  expected={result.expected_doc_count}",
        ]
        if result.error:
            lines.append(f"\n  ERROR: {result.error}")
        if result.diffs_summary:
            lines.append(f"\n  DIFFS:\n{result.diffs_summary}")
        pytest.fail("\n".join(lines))
