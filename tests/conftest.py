"""
Pytest configuration for the tests/ package.

Adds the project root and the loader test scripts/ directory to sys.path so that:
  - alita_sdk package is importable (project root)
  - loader_test_runner / loader_test_utils are importable (scripts/)

Custom markers
--------------
  Tags defined in input/*.json (e.g. "loader:csv", "feature:chunking") are
  automatically converted to pytest marks by sanitize_tag() and registered
  in pyproject.toml. Use -m to filter: pytest -m "loader_csv and feature_chunking"

Shared helpers
--------------
  See tests/runtime/langchain/document_loaders/test_data/scripts/loader_helpers.py
  for collect_loader_test_params() and run_loader_assert().
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_TESTS_DIR = Path(__file__).parent.resolve()
_SCRIPTS_DIR = (
  _PROJECT_ROOT
  / "tests"
  / "runtime"
  / "langchain"
  / "document_loaders"
  / "test_data"
  / "scripts"
)

load_dotenv(_PROJECT_ROOT / ".env")

for _p in [str(_PROJECT_ROOT), str(_TESTS_DIR)]:
  if _p not in sys.path:
    sys.path.insert(0, _p)

if _SCRIPTS_DIR.exists():
  p = str(_SCRIPTS_DIR)
  if p not in sys.path:
    sys.path.insert(0, p)


_RP_ENV_MAP = {
  "rp_endpoint": "RP_ENDPOINT",
  "rp_project": "RP_PROJECT",
  "rp_launch": "RP_LAUNCH",
  "rp_api_key": "RP_API_KEY",
}


def pytest_configure(config):
  config.addinivalue_line(
    "markers",
    "risky: known-unstable or non-critical test; skip with -m 'not risky'",
  )
  for ini_key, env_key in _RP_ENV_MAP.items():
    val = os.environ.get(env_key)
    if val and not config.inicfg.get(ini_key):
      config.inicfg[ini_key] = val
