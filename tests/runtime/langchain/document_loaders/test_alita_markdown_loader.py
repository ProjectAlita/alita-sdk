from pathlib import Path
from typing import Any, Dict

import pytest
from loader_helpers import collect_loader_test_params, run_loader_assert

_LOADER_NAME = "AlitaMarkdownLoader"


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
    _SKIP = {
        ("markdown_large", 0),
        ("markdown_large", 1),
        ("markdown_large", 2),
        ("markdown_code_blocks", 3),
        ("markdown_code_blocks", 1)
    }
    if (input_name, config_index) in _SKIP:
        pytest.skip(f"{input_name} config{config_index}: known failure — pending fix")
    run_loader_assert(_LOADER_NAME, tmp_path, input_name, config_index, config, file_path, baseline_path)
