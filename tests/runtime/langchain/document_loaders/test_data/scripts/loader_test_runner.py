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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    # Recommended pytest integration path from ReportPortal docs:
    # use Python logging with RPLogger and run pytest with --reportportal.
    from reportportal_client import RPLogger
    from reportportal_client import step as rp_step
except Exception:  # pragma: no cover - RP is optional in local runs
    RPLogger = None  # type: ignore[assignment]
    rp_step = None  # type: ignore[assignment]


def _get_loader_rp_logger() -> logging.Logger:
    """Create logger compatible with pytest-reportportal integration.

    With ``--reportportal`` enabled, INFO+ records are forwarded by the plugin
    handler to ReportPortal. Without RP plugin or package, this still logs
    locally through normal Python logging.
    """
    if RPLogger is not None:
        current_logger_cls = logging.getLoggerClass()
        if not issubclass(current_logger_cls, RPLogger):
            logging.setLoggerClass(RPLogger)
    rp_logger = logging.getLogger("tests.document_loaders")
    rp_logger.setLevel(logging.INFO)
    return rp_logger


_RP_LOGGER = _get_loader_rp_logger()


if rp_step is None:  # pragma: no cover - fallback when RP is unavailable
    @contextmanager
    def rp_step(_message: str):  # type: ignore[misc]
        yield


def _rp_log(msg: str, *, attachment: Optional[Dict[str, Any]] = None) -> None:
    """Emit loader logs through the RP-compatible Python logger.

    If attachment is provided and RPLogger is active, attach artifact to the log
    item (per ReportPortal pytest integration docs). Otherwise log plain text.
    """
    if (
        attachment is not None
        and RPLogger is not None
        and isinstance(_RP_LOGGER, RPLogger)
    ):
        _RP_LOGGER.info(msg, attachment=attachment)
        return
    _RP_LOGGER.info(msg)


def _get_llm_for_tests():
    """Create LLM instance for image loader tests using env var.
    
    Returns None if DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS is not set or if
    AlitaClient credentials are not configured.
    
    Requires environment variables:
    - DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS: Model name
    - ELITEA_DEPLOYMENT_URL: Alita deployment URL
    - ELITEA_PROJECT_ID: Project ID
    - ELITEA_TOKEN: API key
    """
    model_name = os.getenv('DEFAULT_LLM_MODEL_FOR_CODE_ANALYSIS')
    if not model_name:
        return None
    
    # Check if required client credentials are available
    deployment_url = os.getenv('ELITEA_DEPLOYMENT_URL')
    project_id = os.getenv('ELITEA_PROJECT_ID')
    api_key = os.getenv('ELITEA_TOKEN')
    
    if not all([deployment_url, project_id, api_key]):
        _rp_log(f"Warning: Cannot create LLM - missing credentials (ELITEA_DEPLOYMENT_URL, ELITEA_PROJECT_ID, or ELITEA_TOKEN)")
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


def _load_documents_directly(loader_name: str, file_path: Path, config: Dict[str, Any], llm=None) -> List:
    """Instantiate loader class directly with config as constructor kwargs.

    Config values from input JSON are passed as-is to the loader constructor.
    No intermediary transformations through loaders_map or allowed_to_override.

    Keys starting with '_' are stripped (reserved for test metadata like _name).
    """
    import importlib
    module = importlib.import_module(f'alita_sdk.runtime.langchain.document_loaders.{loader_name}')
    loader_cls = getattr(module, loader_name)

    kwargs = {k: v for k, v in config.items() if not k.startswith('_')}
    kwargs['file_path'] = str(file_path)

    if llm is not None:
        kwargs['llm'] = llm
        # If config specifies default prompt and no explicit prompt provided, inject image_processing_prompt
        # This mirrors the logic in content_parser.process_content_by_type for consistency
        if config.get('_prompt_default') and 'prompt' not in kwargs:
            from alita_sdk.tools.utils.content_parser import image_processing_prompt
            kwargs['prompt'] = image_processing_prompt

    loader = loader_cls(**kwargs)
    return list(loader.load())


def _load_expected_documents_for_test(baseline_path: Path) -> List:
    with rp_step(f"Load expected baseline from {baseline_path}"):
        from loader_test_utils import load_expected_documents, serialize_documents
        docs = load_expected_documents(baseline_path)
        _rp_log(f"Loaded {len(docs)} expected document(s) from {baseline_path}")
        _rp_log(
            f"Expected documents ({len(docs)})",
            attachment={
                "name": "expected_docs.json",
                "data": serialize_documents(docs).encode("utf-8"),
                "mime": "application/json",
            },
        )
        return docs


def _load_actual_documents_for_test(file_path: Path, config: Dict[str, Any], loader_name: str, llm=None) -> List:
    with rp_step(f"Load actual documents from source {file_path}"):
        from loader_test_utils import serialize_documents
        # Only pass LLM if config explicitly requests it
        actual_llm = llm if config.get('_use_llm') else None
        docs = _load_documents_directly(loader_name, file_path, config, llm=actual_llm)
        llm_info = f" with LLM={type(actual_llm).__name__}" if actual_llm else " (OCR only)"
        _rp_log(f"Loaded {len(docs)} actual document(s) with config: {config or {}}{llm_info}")
        _rp_log(
            f"Actual documents ({len(docs)})",
            attachment={
                "name": "actual_docs.json",
                "data": serialize_documents(docs).encode("utf-8"),
                "mime": "application/json",
            },
        )
        return docs


def _save_actual_documents_for_test(actual_docs: List, actual_output_path: Path) -> None:
    with rp_step(f"Save actual output to {actual_output_path}"):
        from loader_test_utils import save_documents
        actual_output_path.parent.mkdir(parents=True, exist_ok=True)
        save_documents(actual_docs, actual_output_path)
        _rp_log(f"Saved {len(actual_docs)} document(s) to {actual_output_path}")


def _compare_documents_for_test(actual_docs: List, expected_docs: List, loader_name: str, llm=None, debug_log_path: str = None, input_context: str = None):
    with rp_step(f"Compare actual output with baseline for {loader_name}"):
        from loader_test_utils import compare_documents
        
        # Log validation method
        validation_method = "LLM-based semantic validation" if llm is not None else "Similarity-based comparison"
        if input_context and llm:
            validation_method += f" (with input context: {input_context[:50]}...)"
        _rp_log(f"Using {validation_method} for content comparison")
        
        cmp = compare_documents(actual_docs, expected_docs, loader_name=loader_name, llm=llm, debug_log_path=debug_log_path, input_context=input_context)
        status = "PASSED" if cmp.passed else "FAILED"
        _rp_log(f"Result: {status} | actual={cmp.actual_count} docs, expected={cmp.expected_count} docs")
        if cmp.diffs:
            diffs_text = "\n".join(str(d) for d in cmp.diffs)
            _rp_log("Diffs:\n" + diffs_text)
        else:
            diffs_text = f"No diffs — {cmp.actual_count} doc(s) matched baseline exactly."
        _rp_log(
            "Comparison result",
            attachment={
                "name": f"{loader_name}_comparison.txt",
                "data": diffs_text.encode("utf-8"),
                "mime": "text/plain",
            },
        )
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
        actual_docs = _load_actual_documents_for_test(file_path, config, loader_name=loader_name, llm=llm)
        result.actual_doc_count = len(actual_docs)
    except Exception as exc:
        result.error = f"Loader exception: {exc}"
        return result

    # Save actual output
    try:
        _save_actual_documents_for_test(actual_docs, actual_output_path)
    except Exception as exc:
        logger.warning(f"Could not save actual output to {actual_output_path}: {exc}")

    # Only use LLM for comparison if config explicitly uses LLM for loading
    # This ensures OCR-only configs (_use_llm: false) use similarity-based comparison
    comparison_llm = None
    debug_log_path = None
    input_context = None

    if config.get("_use_llm"):
        # Config uses LLM - use LLM for semantic validation in comparison
        comparison_llm = llm

        # Construct debug log path for LLM validation comparison
        if llm is not None:
            debug_log_path = str(actual_output_path.parent / f"llm_validation_debug_{input_name}_config_{config_index}.jsonl")

        # Extract input context (prompt) from config for better LLM validation
        if "prompt" in config:
            input_context = config["prompt"]
        elif config.get("_prompt_default"):
            from alita_sdk.tools.utils.content_parser import image_processing_prompt
            input_context = image_processing_prompt

    cmp = _compare_documents_for_test(actual_docs, expected_docs, loader_name=loader_name, llm=comparison_llm, debug_log_path=debug_log_path, input_context=input_context)
    result.passed = cmp.passed
    result.diffs_summary = cmp.summary() if not cmp.passed else None
    return result
