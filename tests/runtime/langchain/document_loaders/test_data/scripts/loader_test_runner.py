"""
Test runner engine for document loader tests.

Directory layout (base_dir = tests/runtime/langchain/document_loaders/test_data/):
  base_dir/
    [LOADER]/
      input/   - input JSON definitions
      output/  - stable baseline files (committed, compared against actual)
      files/   - test data files for this loader
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from reportportal_client import step as rp_step
    from reportportal_client import current as _rp_current
    from reportportal_client.helpers import timestamp as _rp_timestamp

    def _rp_log(msg: str) -> None:
        """Log directly to the current RP item, bypassing Python log-level filters."""
        rp = _rp_current()
        if rp:
            item_id = rp.current_item()
            if item_id:
                rp.log(_rp_timestamp(), msg, level="INFO", item_id=item_id)
                # Ensure logs are sent immediately by flushing the batcher
                if hasattr(rp, '_log_batcher'):
                    rp._log_batcher.flush()

except Exception as e:  # pragma: no cover - test fallback when RP is unavailable
    import sys
    print(f"Failed to import RP logging: {e}", file=sys.stderr)
    from contextlib import contextmanager

    @contextmanager
    def rp_step(_message: str):  # type: ignore[misc]
        yield

    def _rp_log(msg: str) -> None:  # type: ignore[misc]
        pass


def _get_llm_for_tests():
    """Create LLM instance for image loader tests using env var.
    
    Returns None if DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS is not set or if
    AlitaClient credentials are not configured.
    
    Requires environment variables:
    - DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS: Model name
    - DEPLOYMENT_URL: Alita deployment URL
    - PROJECT_ID: Project ID
    - API_KEY: API key
    """
    model_name = os.getenv('DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS')
    if not model_name:
        return None
    
    # Check if required client credentials are available
    deployment_url = os.getenv('DEPLOYMENT_URL')
    project_id = os.getenv('PROJECT_ID')
    api_key = os.getenv('API_KEY')
    
    if not all([deployment_url, project_id, api_key]):
        _rp_log(f"Warning: Cannot create LLM - missing credentials (DEPLOYMENT_URL, PROJECT_ID, or API_KEY)")
        return None
    
    try:
        from alita_sdk.runtime.clients.client import AlitaClient
        client = AlitaClient(
            base_url=deployment_url,
            project_id=int(project_id),
            auth_token=api_key
        )
        llm = client.get_llm(
            model_name=model_name,
            model_config={
                'temperature': 0.7,
                'max_tokens': 2000
            }
        )
        _rp_log(f"LLM instance created: {model_name}")
        return llm
    except Exception as e:
        _rp_log(f"Warning: Failed to create LLM instance: {e}")
        return None


def _load_documents_with_production_config(file_path: Path, config: Dict[str, Any], llm=None) -> List:
    """Load documents using production configuration logic.
    
    This replicates the logic from process_content_by_type but uses the actual
    file path instead of creating a temp file, so metadata contains correct paths.
    
    Args:
        file_path: Path to the file to load
        config: Configuration dict from test input
        llm: Optional LLM instance for image/multimodal loaders
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
        loader_kwargs['llm'] = llm  # Use provided LLM instance
    if LoaderProperties.PROMPT_DEFAULT.value in loader_kwargs and loader_kwargs.pop(LoaderProperties.PROMPT_DEFAULT.value):
        from alita_sdk.tools.utils.content_parser import image_processing_prompt
        loader_kwargs[LoaderProperties.PROMPT.value] = image_processing_prompt
    
    # Instantiate and load
    loader = loader_cls(file_path=str(file_path), **loader_kwargs)
    return list(loader.load())


def _load_expected_documents_for_test(baseline_path: Path) -> List:
    with rp_step(f"Load expected baseline from {baseline_path}"):
        from loader_test_utils import load_expected_documents
        docs = load_expected_documents(baseline_path)
        _rp_log(f"Loaded {len(docs)} expected document(s) from {baseline_path}")
        return docs


def _load_actual_documents_for_test(file_path: Path, config: Dict[str, Any], llm=None) -> List:
    with rp_step(f"Load actual documents from source {file_path}"):
        docs = _load_documents_with_production_config(file_path, config, llm=llm)
        llm_info = f" with LLM={type(llm).__name__}" if llm else ""
        _rp_log(f"Loaded {len(docs)} actual document(s) with config: {config or {}}{llm_info}")
        return docs


def _save_actual_documents_for_test(actual_docs: List, actual_output_path: Path) -> None:
    with rp_step(f"Save actual output to {actual_output_path}"):
        from loader_test_utils import save_documents
        actual_output_path.parent.mkdir(parents=True, exist_ok=True)
        save_documents(actual_docs, actual_output_path)
        _rp_log(f"Saved {len(actual_docs)} document(s) to {actual_output_path}")


def _compare_documents_for_test(actual_docs: List, expected_docs: List, loader_name: str, llm=None, debug_log_path: str = None):
    with rp_step(f"Compare actual output with baseline for {loader_name}"):
        from loader_test_utils import compare_documents
        
        # Log validation method
        validation_method = "LLM-based semantic validation" if llm is not None else "Similarity-based comparison"
        _rp_log(f"Using {validation_method} for content comparison")
        
        cmp = compare_documents(actual_docs, expected_docs, loader_name=loader_name, llm=llm, debug_log_path=debug_log_path)
        status = "PASSED" if cmp.passed else "FAILED"
        _rp_log(f"Result: {status} | actual={cmp.actual_count} docs, expected={cmp.expected_count} docs")
        if cmp.diffs:
            _rp_log("Diffs:\n" + "\n".join(str(d) for d in cmp.diffs))
        return cmp

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

def sanitize_tag(tag: str) -> str:
    """Convert a tag string to a valid pytest mark name (replace non-alnum with _)."""
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '_', tag)


@dataclass
class LoaderTestInput:
    """Parsed content of a single input JSON file from [LOADER]/input/."""
    file_path: str
    configs: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, json_path: Path) -> "LoaderTestInput":
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "file_path" not in data:
            raise ValueError(f"Missing 'file_path' key in {json_path}")
        configs = data.get("configs", [{}])
        if not configs:
            configs = [{}]
        tags = data.get("tags", [])
        return cls(file_path=data["file_path"], configs=configs, tags=tags)

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
    llm=None,
) -> TestResult:
    """Execute loader for one config, save actual output, compare against baseline.

    baseline_path      - data/[LOADER]/output/[filename]  (expected/stable)
    actual_output_path - output_[TIMESTAMP]/[LOADER]/[filename]  (this run)
    llm                - Optional LLM instance for multimodal loaders
    """

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
        expected_docs = _load_expected_documents_for_test(baseline_path)
        result.expected_doc_count = len(expected_docs)
    except Exception as exc:
        result.error = f"Failed to load baseline {baseline_path}: {exc}"
        return result

    try:
        # Use production configuration logic while preserving file paths
        actual_docs = _load_actual_documents_for_test(file_path, config, llm=llm)
        result.actual_doc_count = len(actual_docs)
    except Exception as exc:
        result.error = f"Loader exception: {exc}"
        return result

    # Save actual output
    try:
        _save_actual_documents_for_test(actual_docs, actual_output_path)
    except Exception as exc:
        logger.warning(f"Could not save actual output to {actual_output_path}: {exc}")

    # Construct debug log path for LLM validation comparison
    debug_log_path = None
    if llm is not None:
        # Place debug log in same directory as actual output
        debug_log_path = str(actual_output_path.parent / f"llm_validation_debug_{input_name}_config_{config_index}.jsonl")

    cmp = _compare_documents_for_test(actual_docs, expected_docs, loader_name=loader_name, llm=llm, debug_log_path=debug_log_path)
    result.passed = cmp.passed
    result.diffs_summary = cmp.summary() if not cmp.passed else None
    return result
