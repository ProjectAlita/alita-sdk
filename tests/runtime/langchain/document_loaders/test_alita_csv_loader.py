"""
Pytest tests for AlitaCSVLoader.

Test cases are auto-discovered from:
  tests/runtime/langchain/document_loaders/test_data/AlitaCSVLoader/input/*.json

Each (input_name, config_index) pair becomes a standalone test.
Tags declared in the input JSON are applied as pytest marks for -m filtering.

Run:
  pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v
  pytest tests/runtime/langchain/document_loaders/test_alita_csv_loader.py -v -k "csv_simple"
  pytest -m "loader_csv" -v
  pytest -m "loader_csv and feature_chunking" -v
"""

from pathlib import Path
from typing import Any, Dict

import pytest
from loader_helpers import collect_loader_test_params, run_loader_assert

_LOADER_NAME = "AlitaCSVLoader"


@pytest.mark.parametrize(
    "input_name, config_index, config, file_path, baseline_path",
    collect_loader_test_params(_LOADER_NAME),
)
def test_loader(
    tmp_path: Path,
    input_name: str,
    config_index: int,
    config: Dict[str, Any],
    file_path: Path,
    baseline_path: Path,
) -> None:
    run_loader_assert(_LOADER_NAME, tmp_path, input_name, config_index, config, file_path, baseline_path)
