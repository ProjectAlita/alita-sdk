"""
Runtime clients package.
"""

try:
    from .client import AlitaClient
    __all__ = ['AlitaClient']
except ImportError as e:
    # Handle case where dependencies are not available
    import logging
    logging.getLogger(__name__).debug(f"Failed to import AlitaClient: {e}")
    __all__ = []