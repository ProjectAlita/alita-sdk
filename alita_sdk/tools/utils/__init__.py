import builtins
import functools
from typing import Any, List

import re
import requests
from pydantic import create_model, Field


# DEPRECATED: Tool names no longer use prefixes
# Kept for backward compatibility only
TOOLKIT_SPLITTER = "___"
TOOL_NAME_LIMIT = 64


def clean_string(s: str, max_length: int = 0):
    # This pattern matches characters that are NOT alphanumeric, underscores, or hyphens
    pattern = '[^a-zA-Z0-9_.-]'

    # Replace these characters with an empty string
    cleaned_string = re.sub(pattern, '', s).replace('.', '_')

    return cleaned_string[:max_length] if max_length > 0 else cleaned_string


def get_max_toolkit_length(selected_tools: Any):
    """DEPRECATED: Calculates the maximum length of the toolkit name.
    
    This function is deprecated as tool names no longer use prefixes.
    Returns a fixed value for backward compatibility.
    """
    # Return a reasonable default since we no longer use prefixes
    return 50


def parse_list(list_str: str = None) -> List[str]:
    """Parses a string of comma or semicolon separated items into a list of items."""

    if list_str:
        # Split the labels by either ',' or ';'
        items_list = [item.strip() for item in re.split(r'[;,]', list_str)]
        return items_list
    return []

# Atlassian related utilities
def is_cookie_token(token: str) -> bool:
    """
    Checks if the given token string contains a cookie session identifier.
    """
    return "JSESSIONID" in token

def parse_cookie_string(cookie_str: str) -> dict:
    """
    Parses a cookie string into a dictionary of cookie key-value pairs.
    """
    return dict(item.split("=", 1) for item in cookie_str.split("; ") if "=" in item)


def parse_type(type_str):
    """Parse a type string into an actual Python type."""
    try:
        # Evaluate the type string using builtins and imported modules
        if type_str == 'number':
            type_str = 'int'
        return eval(type_str, {**vars(builtins), **globals()})
    except Exception as e:
        print(f"Error parsing type: {e}")
        return Any


def create_pydantic_model(model_name: str, variables: dict[str, dict]):
    fields = {}
    for var_name, var_data in variables.items():
        fields[var_name] = (parse_type(var_data['type']), Field(description=var_data.get('description', None)))
    return create_model(model_name, **fields)

from pydantic import BaseModel
from pydantic_core import SchemaValidator

def check_schema(model: BaseModel) -> None:
    schema_validator = SchemaValidator(schema=model.__pydantic_core_schema__)
    schema_validator.validate_python(model.__dict__)


def check_connection_response(check_fun):
    @functools.wraps(check_fun)
    def _wrapper(*args, **kwargs):
        try:
            response = check_fun(*args, **kwargs)
        except requests.exceptions.Timeout:
            return "Service Unreachable: timeout"
        except requests.exceptions.ConnectionError:
            return "Service Unreachable: connectivity issue"
        if response.status_code == 200:
            return
        elif response.status_code == 401:
            return "Authentication Failed"
        elif response.status_code == 403:
            return "Insufficient Permissions"
        elif response.status_code == 404:
            return "Invalid URL"
        else:
            return f"Service Unreachable: return code {response.status_code}"
    return _wrapper


def make_json_serializable(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    if isinstance(obj, bool):
        return bool(obj)
    if isinstance(obj, (str, int, float)) or obj is None:
        return obj
    # Fallback: handle objects that look like booleans but were not caught above
    if str(obj) in ("True", "False"):
        return str(obj) == "True"
    return str(obj)


# Artifact and file handling utilities
def get_file_bytes_from_artifact(alita, artifact_id: str) -> tuple:
    """Get file bytes and filename from artifact storage.
    
    Retrieves a file from Alita artifact storage using its artifact ID.
    This is a shared utility used across multiple toolkits (Jira, Confluence, SharePoint, etc.).
    
    Args:
        alita: Alita client instance (should have artifact() method)
        artifact_id: UUID of the artifact to retrieve
        
    Returns:
        tuple: (file_bytes: bytes, filename: str)
        
    Raises:
        Exception: If artifact retrieval fails or artifact not found
    """
    if not alita:
        raise ValueError("Alita client is required for artifact operations")
    
    # Get artifact client - bucket name doesn't matter for download by ID
    artifact_client = alita.artifact('__temp__')
    
    # Get raw file bytes from artifact storage
    try:
        file_bytes, artifact_filename = artifact_client.get_raw_content_by_artifact_id(artifact_id)
        return file_bytes, artifact_filename
    except Exception as e:
        raise Exception(f"Failed to retrieve artifact '{artifact_id}': {str(e)}")


def detect_mime_type(file_bytes: bytes, filename: str) -> str:
    """Detect MIME type of file from bytes and filename.
    
    Uses filetype library for robust detection from file signature,
    with fallback to extension-based detection if signature detection fails.
    
    Args:
        file_bytes: File content as bytes
        filename: Filename with extension
        
    Returns:
        str: MIME type (e.g., 'image/png', 'application/pdf', 'application/octet-stream')
    """
    try:
        import filetype
        kind = filetype.guess(file_bytes)
        if kind:
            return kind.mime
    except Exception:
        pass  # Fall through to extension-based detection
    
    # Fallback to basic detection from extension
    filename_lower = filename.lower()
    
    # Images
    if filename_lower.endswith(('.png',)):
        return 'image/png'
    if filename_lower.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    if filename_lower.endswith('.gif'):
        return 'image/gif'
    if filename_lower.endswith('.bmp'):
        return 'image/bmp'
    if filename_lower.endswith('.webp'):
        return 'image/webp'
    if filename_lower.endswith('.svg'):
        return 'image/svg+xml'
    
    # Documents
    if filename_lower.endswith('.pdf'):
        return 'application/pdf'
    if filename_lower.endswith(('.doc', '.docx')):
        return 'application/msword'
    if filename_lower.endswith(('.xls', '.xlsx')):
        return 'application/vnd.ms-excel'
    if filename_lower.endswith(('.ppt', '.pptx')):
        return 'application/vnd.ms-powerpoint'
    
    # Text
    if filename_lower.endswith('.txt'):
        return 'text/plain'
    if filename_lower.endswith('.csv'):
        return 'text/csv'
    if filename_lower.endswith('.html'):
        return 'text/html'
    if filename_lower.endswith('.json'):
        return 'application/json'
    if filename_lower.endswith('.xml'):
        return 'application/xml'
    
    # Archives
    if filename_lower.endswith('.zip'):
        return 'application/zip'
    if filename_lower.endswith('.tar'):
        return 'application/x-tar'
    if filename_lower.endswith('.gz'):
        return 'application/gzip'
    
    # Video
    if filename_lower.endswith(('.mp4', '.m4v')):
        return 'video/mp4'
    if filename_lower.endswith(('.avi',)):
        return 'video/x-msvideo'
    if filename_lower.endswith(('.mov',)):
        return 'video/quicktime'
    
    # Default fallback
    return 'application/octet-stream'
