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

# This pattern matches characters that are NOT alphanumeric, underscores, or hyphens
clean_string_pattern = re.compile(r'[^a-zA-Z0-9_.-]')


def clean_string(s: str) -> str:
    # Replace these characters with an empty string
    cleaned_string = re.sub(clean_string_pattern, '', s)
    return cleaned_string
