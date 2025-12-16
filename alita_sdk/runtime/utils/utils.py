import base64
import logging
import re
from enum import Enum
from typing import Any

# DEPRECATED: Tool names no longer use prefixes
# Kept for backward compatibility only
TOOLKIT_SPLITTER = "___"

class IndexerKeywords(Enum):
    # TODO: remove these fields when the indexer is updated
    DEPENDENT_DOCS = 'dependent_docs'
    PARENT = 'parent_id'
    # DEPENDENCY_ID = 'dependency_id'
    UPDATED_ON = 'updated_on'
    CONTENT_IN_BYTES = 'loader_content'
    CONTENT_FILE_NAME = 'loader_content_type'
    INDEX_META_TYPE = 'index_meta'
    INDEX_META_IN_PROGRESS = 'in_progress'
    INDEX_META_COMPLETED = 'completed'
    INDEX_META_FAILED = 'failed'

# This pattern matches characters that are NOT alphanumeric, underscores, or hyphens
clean_string_pattern = re.compile(r'[^a-zA-Z0-9_.-]')


def clean_string(s: str) -> str:
    # Replace these characters with an empty string
    cleaned_string = re.sub(clean_string_pattern, '', s)
    return cleaned_string


def clean_node_str(s: str) -> str:
    """Cleans a node string by removing all non-alphanumeric characters except underscores and spaces."""
    cleaned_string = re.sub(r'[^\w\s]', '', s)
    return cleaned_string


def resolve_image_from_cache(client: Any, cached_image_id: str) -> bytes:
    """
    Resolve cached_image_id from client's image cache and return decoded binary data.

    Args:
        client: AlitaClient instance with _generated_images_cache attribute
        cached_image_id: The cached image ID to resolve

    Returns:
        bytes: Decoded binary image data

    Raises:
        ValueError: If cached_image_id not found or decoding fails
    """
    cache = getattr(client, '_generated_images_cache', {})

    if cached_image_id not in cache:
        raise ValueError(f"Image reference '{cached_image_id}' not found. The image may have expired.")

    cached_data = cache[cached_image_id]
    base64_data = cached_data.get('base64_data', '')
    logging.debug(f"Resolved cached_image_id '{cached_image_id}' from cache (length: {len(base64_data)} chars)")
    # Decode base64 to binary data for image files
    try:
        binary_data = base64.b64decode(base64_data)
        logging.debug(f"Decoded base64 to binary data ({len(binary_data)} bytes)")
        return binary_data
    except Exception as e:
        raise ValueError(f"Failed to decode image data for '{cached_image_id}': {e}")
