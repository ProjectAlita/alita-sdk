"""
FAQ Fetcher Module

Fetches and parses FAQ content from toolkit documentation hosted on GitHub.
Provides fallback mechanisms when documentation is unavailable.

Example:
    from alita_sdk.runtime.middleware.faq_fetcher import get_toolkit_faq

    faq = get_toolkit_faq('github')
    if faq:
        print(faq)
"""

import logging
import re
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Base URL for toolkit documentation
TOOLKIT_DOCS_BASE_URL = "https://raw.githubusercontent.com/ProjectAlita/projectalita.github.io/refs/heads/main/docs/integrations/toolkits"

# Cache for FAQ content to avoid repeated network calls
_faq_cache: dict[str, Optional[str]] = {}


def get_toolkit_faq(toolkit_type: Optional[str], use_cache: bool = True) -> Optional[str]:
    """
    Fetch FAQ content for a specific toolkit type from GitHub documentation.

    Args:
        toolkit_type: Type of toolkit (e.g., 'github', 'jira', 'confluence')
        use_cache: Whether to use cached FAQ content

    Returns:
        FAQ content as string, or None if unavailable

    Example:
        >>> faq = get_toolkit_faq('github')
        >>> if faq:
        ...     print(faq)
    """
    if not toolkit_type:
        logger.debug("No toolkit_type provided, skipping FAQ fetch")
        return None

    # Check cache first
    if use_cache and toolkit_type in _faq_cache:
        logger.debug(f"Returning cached FAQ for toolkit '{toolkit_type}'")
        return _faq_cache[toolkit_type]

    # Fetch FAQ from GitHub
    faq_content = _fetch_faq_from_github(toolkit_type)

    # Cache the result (even if None)
    if use_cache:
        _faq_cache[toolkit_type] = faq_content

    return faq_content


def _fetch_faq_from_github(toolkit_type: str) -> Optional[str]:
    """
    Fetch and parse FAQ section from toolkit documentation on GitHub.

    Args:
        toolkit_type: Type of toolkit

    Returns:
        FAQ content as string, or None if unavailable
    """
    try:
        # Build documentation URL
        doc_filename = f"{toolkit_type}_toolkit.md"
        doc_url = f"{TOOLKIT_DOCS_BASE_URL}/{quote(doc_filename)}"

        logger.debug(f"Fetching FAQ for toolkit '{toolkit_type}' from {doc_url}")

        # Fetch documentation content
        import urllib.request
        import urllib.error

        try:
            with urllib.request.urlopen(doc_url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(
                        f"Failed to fetch toolkit documentation for '{toolkit_type}': "
                        f"HTTP {response.status}"
                    )
                    return None

                content = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.info(
                    f"Documentation not found for toolkit '{toolkit_type}' "
                    f"(404 - this is normal for toolkits without docs)"
                )
            else:
                logger.warning(
                    f"HTTP error fetching FAQ for toolkit '{toolkit_type}': {e.code}"
                )
            return None
        except urllib.error.URLError as e:
            logger.warning(
                f"Network error fetching FAQ for toolkit '{toolkit_type}': {e.reason}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Unexpected error fetching FAQ for toolkit '{toolkit_type}': {e}"
            )
            return None

        # Parse FAQ section from markdown
        faq_content = _parse_faq_section(content)

        if faq_content:
            logger.debug(
                f"Successfully extracted FAQ for toolkit '{toolkit_type}' "
                f"({len(faq_content)} chars)"
            )
        else:
            logger.debug(
                f"No FAQ section found in documentation for toolkit '{toolkit_type}'"
            )

        return faq_content

    except Exception as e:
        logger.error(
            f"Unexpected error processing FAQ for toolkit '{toolkit_type}': {e}",
            exc_info=True
        )
        return None


def _parse_faq_section(markdown_content: str) -> Optional[str]:
    """
    Parse FAQ section from markdown documentation.

    Extracts content after '## FAQ' heading until the next heading or end of file.

    Args:
        markdown_content: Full markdown documentation content

    Returns:
        FAQ section content, or None if no FAQ section found
    """
    # Pattern to match FAQ section
    # Matches: ## FAQ (with optional whitespace/case variations)
    # Captures everything after it until next ## heading or end of content
    faq_pattern = r'##\s+FAQ\s*\n(.*?)(?=\n##\s+|\Z)'

    match = re.search(faq_pattern, markdown_content, re.IGNORECASE | re.DOTALL)

    if match:
        faq_content = match.group(1).strip()

        # Filter out empty FAQ sections
        if faq_content:
            return faq_content

    return None


def clear_faq_cache() -> None:
    """
    Clear the FAQ cache.

    Useful for testing or forcing fresh fetches.
    """
    global _faq_cache
    _faq_cache.clear()
    logger.info("FAQ cache cleared")


def get_cache_stats() -> dict[str, int]:
    """
    Get FAQ cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'cached_toolkits': len(_faq_cache),
        'cache_hits': len([v for v in _faq_cache.values() if v is not None]),
        'cache_misses': len([v for v in _faq_cache.values() if v is None]),
    }


# Fallback FAQ content for common issues
FALLBACK_FAQ = """
### Common Issues

**Q: Authentication Error**
A: Check that your API credentials are valid and have not expired. Update the toolkit configuration with fresh credentials.

**Q: Permission Denied**
A: Verify that your API token or credentials have the necessary permissions/scopes for the operation you're attempting.

**Q: Rate Limited**
A: You've exceeded the API rate limit. Wait a few minutes before retrying, or implement exponential backoff.

**Q: Network Error**
A: Check your internet connection and verify that the API endpoint is accessible. Corporate firewalls may block certain domains.

For more help, contact support at https://elitea.ai/docs/support/contact-support/
"""


def get_fallback_faq() -> str:
    """
    Get fallback FAQ content for when toolkit-specific FAQ is unavailable.

    Returns:
        Generic fallback FAQ content
    """
    return FALLBACK_FAQ.strip()
