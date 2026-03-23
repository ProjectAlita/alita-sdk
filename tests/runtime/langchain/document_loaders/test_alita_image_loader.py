"""
Pytest tests for AlitaImageLoader.

Test cases are auto-discovered from:
  tests/runtime/langchain/document_loaders/test_data/AlitaImageLoader/input/*.json

Each (input_name, config_index) pair becomes a standalone test.
Tags declared in the input JSON are applied as pytest marks for -m filtering.

Run:
  pytest tests/runtime/langchain/document_loaders/test_alita_image_loader.py -v
  pytest tests/runtime/langchain/document_loaders/test_alita_image_loader.py -v -k "image_simple"
  pytest -m "loader_image" -v
  pytest -m "loader_image and feature_llm" -v

Note: This loader requires LLM support. Set DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS env var
      to enable LLM-based image analysis. Without it, tests will use OCR only.
"""

from pathlib import Path
from typing import Any, Dict

import pytest
from loader_helpers import collect_loader_test_params, run_loader_assert
from loader_test_runner import _get_llm_for_tests

_LOADER_NAME = "AlitaImageLoader"


@pytest.fixture(scope="module")
def llm_instance():
    """Create LLM instance once per module for multimodal image analysis."""
    return _get_llm_for_tests()


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
    llm_instance,
) -> None:
    run_loader_assert(
        _LOADER_NAME, tmp_path, input_name, config_index, config, file_path, baseline_path, llm=llm_instance
    )
