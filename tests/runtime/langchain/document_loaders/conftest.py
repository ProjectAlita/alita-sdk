"""
Pytest configuration for document_loaders tests.

Warms up the toolkit registry to avoid circular-import issues during early
collection, and suppresses noisy optional-toolkit import warnings that are
irrelevant to loader-focused tests.
"""

import logging


def pytest_sessionstart(session):
    """Warm up toolkit registry before loader constants are imported.

    Some test paths import ``document_loaders.constants`` very early, which can
    indirectly traverse ``alita_sdk.tools.chunkers`` and trigger a partial-init
    circular import window around ``loaders_map``. Preloading ``alita_sdk.tools``
    once at session start avoids that timing issue in tests without changing
    production code paths.
    """
    import alita_sdk.tools  # noqa: F401


class _SuppressOptionalToolkitImportWarnings(logging.Filter):
    """Hide optional toolkit import warnings during tests.

    Loader tests import chunkers through ``alita_sdk.tools`` which may attempt
    optional toolkit discovery and emit a warning listing failed imports.
    That warning is noisy and irrelevant for loader-focused tests, so suppress
    only that specific log record here instead of changing runtime behavior.
    """

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
