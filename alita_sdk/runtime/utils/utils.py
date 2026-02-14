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


def deduplicate_tool_names(tools: list, context: str = "") -> int:
    """
    Deduplicate tool names by appending numeric suffixes (_1, _2, etc.).

    LLM providers (especially Anthropic) require unique tool names in bind_tools().
    When multiple toolkits share the same tool name (e.g. 'index_data' in both
    Confluence and GitHub toolkits), this function renames duplicates by appending
    a counter suffix. The first occurrence keeps its original name.

    The suffixes are stripped at execution time by BaseAction._run() using
    re.sub(r'_\\d+$', '', name) to route to the correct api_wrapper method.

    A 'is_duplicate' flag is added to tool.metadata for frontend display purposes,
    allowing the UI to distinguish between duplicate tool suffixes (e.g. 'index_data_1')
    and legitimate user-chosen names (e.g. 'Agent_123').

    Args:
        tools: List of tool objects with 'name' attribute. Modified in place.
        context: Optional label for log messages (e.g. "lazy-auto-disable", "swarm").

    Returns:
        Number of tools that were renamed.
    """
    logger = logging.getLogger(__name__)
    prefix = f"[{context}] " if context else ""
    renamed_count = 0
    tool_name_counts = {}
    for tool in tools:
        if hasattr(tool, 'name'):
            base_name = tool.name
            if base_name in tool_name_counts:
                tool_name_counts[base_name] += 1
                new_name = f"{base_name}_{tool_name_counts[base_name]}"
                tool.name = new_name

                # Mark as duplicate for frontend display
                if not hasattr(tool, 'metadata'):
                    tool.metadata = {}
                tool.metadata['is_duplicate'] = True

                renamed_count += 1
                logger.info(f"{prefix}Tool name collision: '{base_name}' -> '{new_name}'")
            else:
                tool_name_counts[base_name] = 0
    return renamed_count
