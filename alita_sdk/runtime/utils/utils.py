import re
from enum import Enum

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
