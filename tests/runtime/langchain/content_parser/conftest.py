"""
Pytest configuration for content_parser tests.

Pre-imports alita_sdk.tools to warm up the toolkit registry and avoid
circular-import issues when document_loaders.constants is imported during
test collection (same pattern as document_loaders/conftest.py).
"""

import logging
import sys
from pathlib import Path

# Make helpers.py importable as `from helpers import ...`
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def pytest_sessionstart(session):
    import alita_sdk.tools  # noqa: F401


class _SuppressOptionalToolkitImportWarnings(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "alita_sdk.tools"
            and record.levelno == logging.WARNING
            and record.getMessage().startswith("Failed imports:")
        )


def pytest_configure(config):
    filter_instance = _SuppressOptionalToolkitImportWarnings()
    logging.getLogger().addFilter(filter_instance)
    logging.getLogger("alita_sdk.tools").addFilter(filter_instance)
