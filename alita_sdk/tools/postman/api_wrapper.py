import json
import logging
import re
from typing import Any, Dict, List, Optional, Union
from traceback import format_exc

import requests
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, model_validator, create_model, SecretStr

from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

# Pydantic models for request schemas
PostmanGetCollections = create_model(
    "PostmanGetCollections"
)

PostmanGetCollection = create_model(
    "PostmanGetCollection",
    collection_id=(str, Field(
        description="The ID of the collection to retrieve"))
)

PostmanGetFolder = create_model(
    "PostmanGetFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(str, Field(
        description="The path to the folder (e.g., 'API/Users' for nested folders)"))
)

PostmanGetFolderRequests = create_model(
    "PostmanGetFolderRequests",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(str, Field(description="The path to the folder")),
    include_details=(bool, Field(
        description="Include detailed request information", default=False))
)

PostmanSearchRequests = create_model(
    "PostmanSearchRequests",
    collection_id=(str, Field(
        description="The ID of the collection to search in")),
    query=(str, Field(description="The search query")),
    search_in=(str, Field(
        description="Where to search: name, url, description, all", default="all")),
    method=(Optional[str], Field(
        description="Optional HTTP method filter", default=None))
)

PostmanAnalyzeCollection = create_model(
    "PostmanAnalyzeCollection",
    collection_id=(str, Field(
        description="The ID of the collection to analyze"))
)

PostmanAnalyzeFolder = create_model(
    "PostmanAnalyzeFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(str, Field(description="The path to the folder to analyze"))
)

PostmanGetImprovementSuggestions = create_model(
    "PostmanGetImprovementSuggestions",
    collection_id=(str, Field(
        description="The ID of the collection to get improvements for"))
)

PostmanCreateCollection = create_model(
    "PostmanCreateCollection",
    name=(str, Field(description="The name of the new collection")),
    description=(Optional[str], Field(
        description="Optional description for the collection", default=None)),
    variables=(Optional[List[Dict]], Field(
        description="Optional collection variables", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional default authentication", default=None))
)

PostmanUpdateCollection = create_model(
    "PostmanUpdateCollection",
    collection_id=(str, Field(
        description="The ID of the collection to update")),
    name=(Optional[str], Field(
        description="New name for the collection", default=None)),
    description=(Optional[str], Field(
        description="New description for the collection", default=None)),
    variables=(Optional[List[Dict]], Field(
        description="Updated collection variables", default=None)),
    auth=(Optional[Dict], Field(
        description="Updated authentication settings", default=None))
)

PostmanDeleteCollection = create_model(
    "PostmanDeleteCollection",
    collection_id=(str, Field(
        description="The ID of the collection to delete"))
)

PostmanDuplicateCollection = create_model(
    "PostmanDuplicateCollection",
    collection_id=(str, Field(
        description="The ID of the collection to duplicate")),
    new_name=(str, Field(description="Name for the new collection copy"))
)

PostmanCreateFolder = create_model(
    "PostmanCreateFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    name=(str, Field(description="Name of the new folder")),
    description=(Optional[str], Field(
        description="Optional description for the folder", default=None)),
    parent_path=(Optional[str], Field(
        description="Optional parent folder path", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional folder-level authentication", default=None))
)

PostmanUpdateFolder = create_model(
    "PostmanUpdateFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(str, Field(description="Path to the folder to update")),
    name=(Optional[str], Field(
        description="New name for the folder", default=None)),
    description=(Optional[str], Field(
        description="New description for the folder", default=None)),
    auth=(Optional[Dict], Field(
        description="Updated authentication settings", default=None))
)

PostmanDeleteFolder = create_model(
    "PostmanDeleteFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(str, Field(description="Path to the folder to delete"))
)

PostmanMoveFolder = create_model(
    "PostmanMoveFolder",
    collection_id=(str, Field(description="The ID of the collection")),
    source_path=(str, Field(description="Current path of the folder to move")),
    target_path=(Optional[str], Field(
        description="New parent folder path", default=None))
)

PostmanCreateRequest = create_model(
    "PostmanCreateRequest",
    collection_id=(str, Field(description="The ID of the collection")),
    folder_path=(Optional[str], Field(
        description="Path to the folder", default=None)),
    name=(str, Field(description="Name of the new request")),
    method=(str, Field(description="HTTP method for the request")),
    url=(str, Field(description="URL for the request")),
    description=(Optional[str], Field(
        description="Optional description for the request", default=None)),
    headers=(Optional[List[Dict]], Field(
        description="Optional request headers", default=None)),
    body=(Optional[Dict], Field(
        description="Optional request body", default=None)),
    auth=(Optional[Dict], Field(
        description="Optional request authentication", default=None)),
    tests=(Optional[str], Field(
        description="Optional test script code", default=None)),
    pre_request_script=(Optional[str], Field(
        description="Optional pre-request script code", default=None))
)

PostmanUpdateRequest = create_model(
    "PostmanUpdateRequest",
    collection_id=(str, Field(description="The ID of the collection")),
    request_path=(str, Field(
        description="Path to the request (folder/requestName)")),
    name=(Optional[str], Field(
        description="New name for the request", default=None)),
    method=(Optional[str], Field(
        description="HTTP method for the request", default=None)),
    url=(Optional[str], Field(
        description="URL for the request", default=None)),
    description=(Optional[str], Field(
        description="Description for the request", default=None)),
    headers=(Optional[List[Dict]], Field(
        description="Request headers", default=None)),
    body=(Optional[Dict], Field(description="Request body", default=None)),
    auth=(Optional[Dict], Field(
        description="Request authentication", default=None)),
    tests=(Optional[str], Field(description="Test script code", default=None)),
    pre_request_script=(Optional[str], Field(
        description="Pre-request script code", default=None))
)

PostmanDeleteRequest = create_model(
    "PostmanDeleteRequest",
    collection_id=(str, Field(description="The ID of the collection")),
    request_path=(str, Field(description="Path to the request to delete"))
)

PostmanDuplicateRequest = create_model(
    "PostmanDuplicateRequest",
    collection_id=(str, Field(description="The ID of the collection")),
    source_path=(str, Field(description="Path to the request to duplicate")),
    new_name=(str, Field(description="Name for the duplicated request")),
    target_path=(Optional[str], Field(
        description="Target folder path", default=None))
)

PostmanMoveRequest = create_model(
    "PostmanMoveRequest",
    collection_id=(str, Field(description="The ID of the collection")),
    source_path=(str, Field(
        description="Current path of the request to move")),
    target_path=(Optional[str], Field(
        description="New folder path", default=None))
)


class PostmanApiWrapper(BaseToolApiWrapper):
    """Wrapper for Postman API."""

    api_key: SecretStr
    base_url: str = "https://api.getpostman.com"
    collection_id: Optional[str] = None
    workspace_id: Optional[str] = None
    timeout: int = 30
    _session: requests.Session = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            import requests  # noqa: F401
        except ImportError:
            raise ImportError(
                "`requests` package not found, please run "
                "`pip install requests`"
            )
        return values

    def __init__(self, **data):
        super().__init__(**data)
        self._session = requests.Session()
        self._session.headers.update({
            'X-API-Key': self.api_key.get_secret_value(),
            'Content-Type': 'application/json',
        })
        # Removed ineffective timeout assignment. Timeout will be enforced in `_make_request`.

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Postman API."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"

        try:
            logger.info(f"Making {method.upper()} request to {url}")
            response = self._session.request(method, url, timeout=self.timeout, **kwargs)
            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise ToolException(f"Postman API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            raise ToolException(
                f"Invalid JSON response from Postman API: {str(e)}")

    def get_available_tools(self):
        """Return list of available tools with their configurations."""
        return [
            {
                "name": "get_collections",
                "mode": "get_collections",
                "description": "Get all Postman collections accessible to the user",
                "args_schema": PostmanGetCollections,
                "ref": self.get_collections
            },
            {
                "name": "get_collection",
                "mode": "get_collection",
                "description": "Get a specific Postman collection by ID",
                "args_schema": PostmanGetCollection,
                "ref": self.get_collection
            },
            {
                "name": "get_folder",
                "mode": "get_folder",
                "description": "Get folders from a collection by path (supports nested paths like 'API/Users')",
                "args_schema": PostmanGetFolder,
                "ref": self.get_folder
            },
            {
                "name": "get_folder_requests",
                "mode": "get_folder_requests",
                "description": "Get detailed information about all requests in a folder",
                "args_schema": PostmanGetFolderRequests,
                "ref": self.get_folder_requests
            },
            {
                "name": "search_requests",
                "mode": "search_requests",
                "description": "Search for requests across the collection",
                "args_schema": PostmanSearchRequests,
                "ref": self.search_requests
            },
            {
                "name": "analyze_collection",
                "mode": "analyze_collection",
                "description": "Analyze a collection for API quality, best practices, and issues",
                "args_schema": PostmanAnalyzeCollection,
                "ref": self.analyze_collection
            },
            {
                "name": "analyze_folder",
                "mode": "analyze_folder",
                "description": "Analyze a specific folder within a collection",
                "args_schema": PostmanAnalyzeFolder,
                "ref": self.analyze_folder
            },
            {
                "name": "get_improvement_suggestions",
                "mode": "get_improvement_suggestions",
                "description": "Get improvement suggestions for a collection",
                "args_schema": PostmanGetImprovementSuggestions,
                "ref": self.get_improvement_suggestions
            },
            {
                "name": "create_collection",
                "mode": "create_collection",
                "description": "Create a new Postman collection",
                "args_schema": PostmanCreateCollection,
                "ref": self.create_collection
            },
            {
                "name": "update_collection",
                "mode": "update_collection",
                "description": "Update an existing collection (name, description, variables, auth)",
                "args_schema": PostmanUpdateCollection,
                "ref": self.update_collection
            },
            {
                "name": "delete_collection",
                "mode": "delete_collection",
                "description": "Delete a collection permanently",
                "args_schema": PostmanDeleteCollection,
                "ref": self.delete_collection
            },
            {
                "name": "duplicate_collection",
                "mode": "duplicate_collection",
                "description": "Create a copy of an existing collection",
                "args_schema": PostmanDuplicateCollection,
                "ref": self.duplicate_collection
            },

            {
                "name": "create_folder",
                "mode": "create_folder",
                "description": "Create a new folder in a collection",
                "args_schema": PostmanCreateFolder,
                "ref": self.create_folder
            },
            {
                "name": "update_folder",
                "mode": "update_folder",
                "description": "Update folder properties (name, description, auth)",
                "args_schema": PostmanUpdateFolder,
                "ref": self.update_folder
            },
            {
                "name": "delete_folder",
                "mode": "delete_folder",
                "description": "Delete a folder and all its contents permanently",
                "args_schema": PostmanDeleteFolder,
                "ref": self.delete_folder
            },
            {
                "name": "move_folder",
                "mode": "move_folder",
                "description": "Move a folder to a different location within the collection",
                "args_schema": PostmanMoveFolder,
                "ref": self.move_folder
            },
            {
                "name": "create_request",
                "mode": "create_request",
                "description": "Create a new API request in a folder",
                "args_schema": PostmanCreateRequest,
                "ref": self.create_request
            },
            {
                "name": "update_request",
                "mode": "update_request",
                "description": "Update an existing API request",
                "args_schema": PostmanUpdateRequest,
                "ref": self.update_request
            },
            {
                "name": "delete_request",
                "mode": "delete_request",
                "description": "Delete an API request permanently",
                "args_schema": PostmanDeleteRequest,
                "ref": self.delete_request
            },
            {
                "name": "duplicate_request",
                "mode": "duplicate_request",
                "description": "Create a copy of an existing API request",
                "args_schema": PostmanDuplicateRequest,
                "ref": self.duplicate_request
            },
            {
                "name": "move_request",
                "mode": "move_request",
                "description": "Move an API request to a different folder",
                "args_schema": PostmanMoveRequest,
                "ref": self.move_request
            }
        ]

    # =================================================================
    # ANALYSIS AND READ-ONLY METHODS
    # =================================================================

    def get_collections(self, **kwargs) -> str:
        """Get all Postman collections accessible to the user."""
        try:
            response = self._make_request('GET', '/collections')
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when getting collections: {stacktrace}")
            raise ToolException(f"Unable to get collections: {str(e)}")

    def get_collection(self, collection_id: str, **kwargs) -> str:
        """Get a specific collection by ID."""
        try:
            response = self._make_request(
                'GET', f'/collections/{collection_id}')
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting collection {collection_id}: {stacktrace}")
            raise ToolException(
                f"Unable to get collection {collection_id}: {str(e)}")

    def get_folder(self, collection_id: str, folder_path: str, **kwargs) -> str:
        """Get folders from a collection by path."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            folders = self._find_folders_by_path(
                collection['collection']['item'], folder_path)
            return json.dumps(folders, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting folder {folder_path}: {stacktrace}")
            raise ToolException(
                f"Unable to get folder {folder_path} from collection {collection_id}: {str(e)}")

    def get_folder_requests(self, collection_id: str, folder_path: str, include_details: bool = False, **kwargs) -> str:
        """Get detailed information about all requests in a folder."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            folders = self._find_folders_by_path(
                collection['collection']['item'], folder_path)

            if not folders:
                raise ToolException(f"Folder '{folder_path}' not found in collection '{collection_id}'.")

            folder = folders[0]
            requests = self._extract_requests_from_items(
                folder.get('item', []), include_details)

            result = {
                "folder_name": folder['name'],
                "folder_path": folder_path,
                "request_count": len(requests),
                "requests": requests
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting folder requests: {stacktrace}")
            raise ToolException(
                f"Unable to get requests from folder {folder_path}: {str(e)}")

    def search_requests(self, collection_id: str, query: str, search_in: str = "all", method: str = None, **kwargs) -> str:
        """Search for requests across the collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            requests = self._search_requests_in_items(
                collection['collection']['item'], query, search_in, method)

            result = {
                "collection_id": collection_id,
                "query": query,
                "search_in": search_in,
                "method_filter": method,
                "results_count": len(requests),
                "results": requests
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when searching requests: {stacktrace}")
            raise ToolException(
                f"Unable to search requests in collection {collection_id}: {str(e)}")

    def analyze_collection(self, collection_id: str, **kwargs) -> str:
        """Analyze a collection for API quality and best practices."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            analysis = self._perform_collection_analysis(collection)
            return json.dumps(analysis, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing collection: {stacktrace}")
            raise ToolException(
                f"Unable to analyze collection {collection_id}: {str(e)}")

    def analyze_folder(self, collection_id: str, folder_path: str, **kwargs) -> str:
        """Analyze a specific folder within a collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            folders = self._find_folders_by_path(
                collection['collection']['item'], folder_path)

            if not folders:
                return json.dumps({"error": f"Folder '{folder_path}' not found"}, indent=2)

            folder_analyses = []
            for folder in folders:
                analysis = self._perform_folder_analysis(folder, folder_path)
                folder_analyses.append(analysis)

            return json.dumps(folder_analyses, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing folder: {stacktrace}")
            raise ToolException(
                f"Unable to analyze folder {folder_path}: {str(e)}")

    def get_improvement_suggestions(self, collection_id: str, **kwargs) -> str:
        """Get improvement suggestions for a collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            analysis = self._perform_collection_analysis(collection)
            improvements = self._generate_improvements(analysis)

            result = {
                "collection_id": collection_id,
                "collection_name": analysis["collection_name"],
                "improvement_count": len(improvements),
                "improvements": improvements
            }

            return json.dumps(result, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when generating improvements: {stacktrace}")
            raise ToolException(
                f"Unable to generate improvements for collection {collection_id}: {str(e)}")

    # =================================================================
    # COLLECTION MANAGEMENT METHODS
    # =================================================================

    def create_collection(self, name: str, description: str = None, variables: List[Dict] = None, auth: Dict = None, **kwargs) -> str:
        """Create a new Postman collection."""
        try:
            collection_data = {
                "collection": {
                    "info": {
                        "name": name,
                        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                    },
                    "item": []
                }
            }

            if description:
                collection_data["collection"]["info"]["description"] = description

            if variables:
                collection_data["collection"]["variable"] = variables

            if auth:
                collection_data["collection"]["auth"] = auth

            response = self._make_request(
                'POST', '/collections', json=collection_data)
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating collection: {stacktrace}")
            raise ToolException(
                f"Unable to create collection '{name}': {str(e)}")

    def update_collection(self, collection_id: str, name: str = None, description: str = None,
                          variables: List[Dict] = None, auth: Dict = None, **kwargs) -> str:
        """Update an existing collection."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = current["collection"]

            # Update fields if provided
            if name:
                collection_data["info"]["name"] = name
            if description is not None:
                collection_data["info"]["description"] = description
            if variables is not None:
                collection_data["variable"] = variables
            if auth is not None:
                collection_data["auth"] = auth

            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {collection_id}: {str(e)}")

    def delete_collection(self, collection_id: str, **kwargs) -> str:
        """Delete a collection permanently."""
        try:
            response = self._make_request(
                'DELETE', f'/collections/{collection_id}')
            return json.dumps({"message": f"Collection {collection_id} deleted successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting collection: {stacktrace}")
            raise ToolException(
                f"Unable to delete collection {collection_id}: {str(e)}")

    def duplicate_collection(self, collection_id: str, new_name: str, **kwargs) -> str:
        """Create a copy of an existing collection."""
        try:
            # Get the original collection
            original = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = original["collection"]

            # Update the name and remove IDs to create a new collection
            collection_data["info"]["name"] = new_name
            if "_postman_id" in collection_data["info"]:
                del collection_data["info"]["_postman_id"]

            # Remove item IDs recursively
            self._remove_item_ids(collection_data.get("item", []))

            response = self._make_request(
                'POST', '/collections', json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when duplicating collection: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate collection {collection_id}: {str(e)}")

    # =================================================================
    # FOLDER MANAGEMENT METHODS
    # =================================================================

    def create_folder(self, collection_id: str, name: str, description: str = None,
                      parent_path: str = None, auth: Dict = None, **kwargs) -> str:
        """Create a new folder in a collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Create folder item
            folder_item = {
                "name": name,
                "item": []
            }

            if description:
                folder_item["description"] = description
            if auth:
                folder_item["auth"] = auth

            # Add folder to appropriate location
            if parent_path:
                parent_folders = self._find_folders_by_path(
                    collection_data["item"], parent_path)
                if not parent_folders:
                    raise ToolException(
                        f"Parent folder '{parent_path}' not found")
                parent_folders[0]["item"].append(folder_item)
            else:
                collection_data["item"].append(folder_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating folder: {stacktrace}")
            raise ToolException(f"Unable to create folder '{name}': {str(e)}")

    def update_folder(self, collection_id: str, folder_path: str, name: str = None,
                      description: str = None, auth: Dict = None, **kwargs) -> str:
        """Update folder properties."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find the folder
            folders = self._find_folders_by_path(
                collection_data["item"], folder_path)
            if not folders:
                raise ToolException(f"Folder '{folder_path}' not found")

            folder = folders[0]

            # Update fields if provided
            if name:
                folder["name"] = name
            if description is not None:
                folder["description"] = description
            if auth is not None:
                folder["auth"] = auth

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder '{folder_path}' updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating folder: {stacktrace}")
            raise ToolException(
                f"Unable to update folder '{folder_path}': {str(e)}")

    def delete_folder(self, collection_id: str, folder_path: str, **kwargs) -> str:
        """Delete a folder and all its contents permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find and remove the folder
            if self._remove_folder_by_path(collection_data["item"], folder_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Folder '{folder_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Folder '{folder_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting folder: {stacktrace}")
            raise ToolException(
                f"Unable to delete folder '{folder_path}': {str(e)}")

    def move_folder(self, collection_id: str, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move a folder to a different location within the collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find source folder
            source_folder = self._find_folders_by_path(
                collection_data["item"], source_path)
            if not source_folder:
                raise ToolException(f"Source folder '{source_path}' not found")

            folder_data = source_folder[0].copy()

            # Remove from source location
            self._remove_folder_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                target_folders = self._find_folders_by_path(
                    collection_data["item"], target_path)
                if not target_folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                target_folders[0]["item"].append(folder_data)
            else:
                collection_data["item"].append(folder_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder moved from '{source_path}' to '{target_path or 'root'}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when moving folder: {stacktrace}")
            raise ToolException(
                f"Unable to move folder from '{source_path}': {str(e)}")

    # =================================================================
    # REQUEST MANAGEMENT METHODS
    # =================================================================

    def create_request(self, collection_id: str, name: str, method: str, url: str,
                       folder_path: str = None, description: str = None, headers: List[Dict] = None,
                       body: Dict = None, auth: Dict = None, tests: str = None,
                       pre_request_script: str = None, **kwargs) -> str:
        """Create a new API request in a folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Create request item
            request_item = {
                "name": name,
                "request": {
                    "method": method.upper(),
                    "header": headers or [],
                    "url": url
                }
            }

            if description:
                request_item["request"]["description"] = description
            if body:
                request_item["request"]["body"] = body
            if auth:
                request_item["request"]["auth"] = auth

            # Add events if provided
            events = []
            if pre_request_script:
                events.append({
                    "listen": "prerequest",
                    "script": {
                        "exec": pre_request_script.split('\n'),
                        "type": "text/javascript"
                    }
                })
            if tests:
                events.append({
                    "listen": "test",
                    "script": {
                        "exec": tests.split('\n'),
                        "type": "text/javascript"
                    }
                })
            if events:
                request_item["event"] = events

            # Add request to appropriate location
            if folder_path:
                folders = self._find_folders_by_path(
                    collection_data["item"], folder_path)
                if not folders:
                    raise ToolException(f"Folder '{folder_path}' not found")
                folders[0]["item"].append(request_item)
            else:
                collection_data["item"].append(request_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating request: {stacktrace}")
            raise ToolException(f"Unable to create request '{name}': {str(e)}")

    def update_request(self, collection_id: str, request_path: str, name: str = None,
                       method: str = None, url: str = None, description: str = None,
                       headers: List[Dict] = None, body: Dict = None, auth: Dict = None,
                       tests: str = None, pre_request_script: str = None, **kwargs) -> str:
        """Update an existing API request."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self._find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update fields if provided
            if name:
                request_item["name"] = name
            if method:
                request_item["request"]["method"] = method.upper()
            if url:
                request_item["request"]["url"] = url
            if description is not None:
                request_item["request"]["description"] = description
            if headers is not None:
                request_item["request"]["header"] = headers
            if body is not None:
                request_item["request"]["body"] = body
            if auth is not None:
                request_item["request"]["auth"] = auth

            # Update events
            if tests is not None or pre_request_script is not None:
                events = request_item.get("event", [])

                if pre_request_script is not None:
                    # Remove existing prerequest events
                    events = [e for e in events if e.get(
                        "listen") != "prerequest"]
                    if pre_request_script:
                        events.append({
                            "listen": "prerequest",
                            "script": {
                                "exec": pre_request_script.split('\n'),
                                "type": "text/javascript"
                            }
                        })

                if tests is not None:
                    # Remove existing test events
                    events = [e for e in events if e.get("listen") != "test"]
                    if tests:
                        events.append({
                            "listen": "test",
                            "script": {
                                "exec": tests.split('\n'),
                                "type": "text/javascript"
                            }
                        })

                request_item["event"] = events

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}': {str(e)}")

    def delete_request(self, collection_id: str, request_path: str, **kwargs) -> str:
        """Delete an API request permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find and remove the request
            if self._remove_request_by_path(collection_data["item"], request_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Request '{request_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Request '{request_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting request: {stacktrace}")
            raise ToolException(
                f"Unable to delete request '{request_path}': {str(e)}")

    def duplicate_request(self, collection_id: str, source_path: str, new_name: str,
                          target_path: str = None, **kwargs) -> str:
        """Create a copy of an existing API request."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self._find_request_by_path(
                collection_data["item"], source_path)
            if not source_request:
                raise ToolException(
                    f"Source request '{source_path}' not found")

            # Create copy
            request_copy = json.loads(json.dumps(source_request))  # Deep copy
            request_copy["name"] = new_name

            # Remove IDs if present
            if "id" in request_copy:
                del request_copy["id"]

            # Add to target location
            if target_path:
                folders = self._find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_copy)
            else:
                # Add to same location as source
                source_folder_path = "/".join(source_path.split("/")[:-1])
                if source_folder_path:
                    folders = self._find_folders_by_path(
                        collection_data["item"], source_folder_path)
                    folders[0]["item"].append(request_copy)
                else:
                    collection_data["item"].append(request_copy)

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request duplicated as '{new_name}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when duplicating request: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate request '{source_path}': {str(e)}")

    def move_request(self, collection_id: str, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move an API request to a different folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self._find_request_by_path(
                collection_data["item"], source_path)
            if not source_request:
                raise ToolException(
                    f"Source request '{source_path}' not found")

            request_data = json.loads(json.dumps(source_request))  # Deep copy

            # Remove from source location
            self._remove_request_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                folders = self._find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_data)
            else:
                collection_data["item"].append(request_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request moved from '{source_path}' to '{target_path or 'root'}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when moving request: {stacktrace}")
            raise ToolException(
                f"Unable to move request '{source_path}': {str(e)}")

    # =================================================================
    # HELPER METHODS
    # =================================================================

    def _find_folders_by_path(self, items: List[Dict], path: str) -> List[Dict]:
        """Find folders by path (supports nested paths like 'API/Users')."""
        path_parts = [part.strip() for part in path.split('/') if part.strip()]
        if not path_parts:
            return items

        results = []

        def find_in_items(current_items: List[Dict], current_path: List[str], depth: int = 0):
            if depth >= len(current_path):
                results.extend(current_items)
                return

            target_name = current_path[depth]
            for item in current_items:
                if (item.get('name', '').lower() == target_name.lower() or
                        target_name.lower() in item.get('name', '').lower()) and item.get('item'):
                    if depth == len(current_path) - 1:
                        # This is the target folder
                        results.append(item)
                    else:
                        # Continue searching in subfolders
                        find_in_items(item['item'], current_path, depth + 1)

        find_in_items(items, path_parts)
        return results

    def _extract_requests_from_items(self, items: List[Dict], include_details: bool = False) -> List[Dict]:
        """Extract requests from items recursively."""
        requests = []

        for item in items:
            if item.get('request'):
                # This is a request
                request_data = {
                    "name": item.get('name'),
                    "method": item['request'].get('method'),
                    "url": item['request'].get('url')
                }

                if include_details:
                    request_data.update({
                        "description": item.get('description'),
                        "headers": item['request'].get('header', []),
                        "body": item['request'].get('body'),
                        "auth": item['request'].get('auth'),
                        "tests": [e for e in item.get('event', []) if e.get('listen') == 'test'],
                        "pre_request_scripts": [e for e in item.get('event', []) if e.get('listen') == 'prerequest']
                    })

                requests.append(request_data)
            elif item.get('item'):
                # This is a folder, recurse
                requests.extend(self._extract_requests_from_items(
                    item['item'], include_details))

        return requests

    def _search_requests_in_items(self, items: List[Dict], query: str, search_in: str, method: str = None) -> List[Dict]:
        """Search for requests in items recursively."""
        results = []
        query_lower = query.lower()

        for item in items:
            if item.get('request'):
                # This is a request
                request = item['request']
                matches = False

                # Check method filter first
                if method and request.get('method', '').upper() != method.upper():
                    continue

                # Check search criteria
                if search_in == 'all' or search_in == 'name':
                    if query_lower in item.get('name', '').lower():
                        matches = True

                if search_in == 'all' or search_in == 'url':
                    url = request.get('url', '')
                    if isinstance(url, dict):
                        url = url.get('raw', '')
                    if query_lower in url.lower():
                        matches = True

                if search_in == 'all' or search_in == 'description':
                    description = item.get(
                        'description', '') or request.get('description', '')
                    if query_lower in description.lower():
                        matches = True

                if matches:
                    results.append({
                        "name": item.get('name'),
                        "method": request.get('method'),
                        "url": request.get('url'),
                        "description": item.get('description') or request.get('description'),
                        "path": self._get_item_path(items, item)
                    })

            elif item.get('item'):
                # This is a folder, recurse
                results.extend(self._search_requests_in_items(
                    item['item'], query, search_in, method))

        return results

    def _get_item_path(self, root_items: List[Dict], target_item: Dict, current_path: str = "") -> str:
        """Get the path of an item within the collection structure."""
        for item in root_items:
            item_path = f"{current_path}/{item['name']}" if current_path else item['name']

            if item == target_item:
                return item_path

            if item.get('item'):
                result = self._get_item_path(
                    item['item'], target_item, item_path)
                if result:
                    return result

        return ""

    def _find_request_by_path(self, items: List[Dict], request_path: str) -> Optional[Dict]:
        """Find a request by its path."""
        path_parts = [part.strip()
                      for part in request_path.split('/') if part.strip()]
        if not path_parts:
            return None

        current_items = items

        # Navigate through folders to the request
        for i, part in enumerate(path_parts):
            found = False
            for item in current_items:
                if item.get('name', '').lower() == part.lower():
                    if i == len(path_parts) - 1:
                        # This should be the request
                        if item.get('request'):
                            return item
                        else:
                            return None
                    else:
                        # This should be a folder
                        if item.get('item'):
                            current_items = item['item']
                            found = True
                            break
                        else:
                            return None

            if not found:
                return None

        return None

    def _remove_folder_by_path(self, items: List[Dict], folder_path: str) -> bool:
        """Remove a folder by its path."""
        path_parts = [part.strip()
                      for part in folder_path.split('/') if part.strip()]
        if not path_parts:
            return False

        if len(path_parts) == 1:
            # Remove from current level
            for i, item in enumerate(items):
                if item.get('name', '').lower() == path_parts[0].lower() and item.get('item') is not None:
                    del items[i]
                    return True
            return False
        else:
            # Navigate to parent folder
            parent_path = '/'.join(path_parts[:-1])
            parent_folders = self._find_folders_by_path(items, parent_path)
            if parent_folders:
                return self._remove_folder_by_path(parent_folders[0]['item'], path_parts[-1])
            return False

    def _remove_request_by_path(self, items: List[Dict], request_path: str) -> bool:
        """Remove a request by its path."""
        path_parts = [part.strip()
                      for part in request_path.split('/') if part.strip()]
        if not path_parts:
            return False

        if len(path_parts) == 1:
            # Remove from current level
            for i, item in enumerate(items):
                if item.get('name', '').lower() == path_parts[0].lower() and item.get('request'):
                    del items[i]
                    return True
            return False
        else:
            # Navigate to parent folder
            parent_path = '/'.join(path_parts[:-1])
            parent_folders = self._find_folders_by_path(items, parent_path)
            if parent_folders:
                return self._remove_request_by_path(parent_folders[0]['item'], path_parts[-1])
            return False

    def _remove_item_ids(self, items: List[Dict]):
        """Remove IDs from items recursively for duplication."""
        for item in items:
            if 'id' in item:
                del item['id']
            if item.get('item'):
                self._remove_item_ids(item['item'])

    # =================================================================
    # ANALYSIS HELPER METHODS
    # =================================================================

    def _perform_collection_analysis(self, collection: Dict) -> Dict:
        """Perform comprehensive analysis of a collection."""
        collection_data = collection['collection']
        folders = self._analyze_folders(collection_data.get('item', []))
        total_requests = self._count_requests(collection_data.get('item', []))
        issues = self._identify_collection_issues(collection_data)
        score = self._calculate_quality_score(collection_data, folders, issues)
        recommendations = self._generate_recommendations(issues)

        return {
            "collection_id": collection_data['info'].get('_postman_id', ''),
            "collection_name": collection_data['info'].get('name', ''),
            "total_requests": total_requests,
            "folders": folders,
            "issues": issues,
            "recommendations": recommendations,
            "score": score,
            "overall_security_score": self._calculate_overall_security_score(folders),
            "overall_performance_score": self._calculate_overall_performance_score(folders),
            "overall_documentation_score": self._calculate_overall_documentation_score(folders)
        }

    def _analyze_folders(self, items: List[Dict], base_path: str = "") -> List[Dict]:
        """Analyze all folders in a collection."""
        folders = []

        for item in items:
            if item.get('item') is not None:  # This is a folder
                folder_path = f"{base_path}/{item['name']}" if base_path else item['name']
                analysis = self._perform_folder_analysis(item, folder_path)
                folders.append(analysis)

                # Recursively analyze subfolders
                subfolders = self._analyze_folders(item['item'], folder_path)
                folders.extend(subfolders)

        return folders

    def _perform_folder_analysis(self, folder: Dict, path: str) -> Dict:
        """Perform analysis of a specific folder."""
        requests = self._analyze_requests(folder.get('item', []))
        request_count = self._count_requests(folder.get('item', []))
        issues = self._identify_folder_issues(folder, requests)

        return {
            "name": folder['name'],
            "path": path,
            "request_count": request_count,
            "requests": requests,
            "issues": issues,
            "has_consistent_naming": self._check_consistent_naming(folder.get('item', [])),
            "has_proper_structure": bool(folder.get('description') and folder.get('item')),
            "auth_consistency": self._check_auth_consistency(requests),
            "avg_documentation_quality": self._calculate_avg_documentation_quality(requests),
            "avg_security_score": self._calculate_avg_security_score(requests),
            "avg_performance_score": self._calculate_avg_performance_score(requests)
        }

    def _analyze_requests(self, items: List[Dict]) -> List[Dict]:
        """Analyze requests within a folder."""
        requests = []

        for item in items:
            if item.get('request'):  # This is a request
                analysis = self._perform_request_analysis(item)
                requests.append(analysis)

        return requests

    def _perform_request_analysis(self, item: Dict) -> Dict:
        """Perform comprehensive analysis of a specific request."""
        request = item['request']
        issues = []

        # Basic checks
        has_auth = bool(request.get('auth')
                        or self._has_auth_in_headers(request))
        has_description = bool(item.get('description')
                               or request.get('description'))
        has_tests = bool([e for e in item.get('event', [])
                         if e.get('listen') == 'test'])
        has_examples = bool(item.get('response', []))

        # Enhanced analysis
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        has_hardcoded_url = self._detect_hardcoded_url(url)
        has_hardcoded_data = self._detect_hardcoded_data(request)
        has_proper_headers = self._validate_headers(request)
        has_variables = self._detect_variable_usage(request)
        has_error_handling = self._detect_error_handling(item)
        follows_naming_convention = self._validate_naming_convention(
            item['name'])
        has_security_issues = self._detect_security_issues(request)
        has_performance_issues = self._detect_performance_issues(request)

        # Calculate scores
        security_score = self._calculate_security_score(
            request, has_auth, has_security_issues)
        performance_score = self._calculate_performance_score(
            request, has_performance_issues)

        # Generate issues
        self._generate_request_issues(issues, item, {
            'has_description': has_description,
            'has_auth': has_auth,
            'has_tests': has_tests,
            'has_hardcoded_url': has_hardcoded_url,
            'has_hardcoded_data': has_hardcoded_data,
            'has_proper_headers': has_proper_headers,
            'has_security_issues': has_security_issues,
            'follows_naming_convention': follows_naming_convention
        })

        return {
            "name": item['name'],
            "method": request.get('method'),
            "url": url,
            "has_auth": has_auth,
            "has_description": has_description,
            "has_tests": has_tests,
            "has_examples": has_examples,
            "issues": issues,
            "has_hardcoded_url": has_hardcoded_url,
            "has_hardcoded_data": has_hardcoded_data,
            "has_proper_headers": has_proper_headers,
            "has_variables": has_variables,
            "has_error_handling": has_error_handling,
            "follows_naming_convention": follows_naming_convention,
            "has_security_issues": has_security_issues,
            "has_performance_issues": has_performance_issues,
            "auth_type": request.get('auth', {}).get('type'),
            "response_examples": len(item.get('response', [])),
            "test_coverage": self._assess_test_coverage(item),
            "documentation_quality": self._assess_documentation_quality(item),
            "security_score": security_score,
            "performance_score": performance_score
        }

    def _count_requests(self, items: List[Dict]) -> int:
        """Count total requests in items."""
        count = 0
        for item in items:
            if item.get('request'):
                count += 1
            elif item.get('item'):
                count += self._count_requests(item['item'])
        return count

    def _has_auth_in_headers(self, request: Dict) -> bool:
        """Check if request has authentication in headers."""
        headers = request.get('header', [])
        auth_headers = ['authorization', 'x-api-key', 'x-auth-token']
        return any(h.get('key', '').lower() in auth_headers for h in headers)

    def _detect_hardcoded_url(self, url: str) -> bool:
        """Detect hardcoded URLs that should use variables."""
        hardcoded_patterns = [
            r'^https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP addresses
            r'^https?://localhost',  # localhost
            # Direct domains
            r'^https?://[a-zA-Z0-9.-]+\.(com|org|net|io|dev)',
            r'api\.example\.com',  # Example domains
            r'staging\.|dev\.|test\.'  # Environment-specific
        ]
        return any(re.search(pattern, url) for pattern in hardcoded_patterns) and '{{' not in url

    def _detect_hardcoded_data(self, request: Dict) -> bool:
        """Detect hardcoded data in request body and headers."""
        # Check headers
        headers = request.get('header', [])
        has_hardcoded_headers = any(
            ('token' in h.get('key', '').lower() or
             'key' in h.get('key', '').lower() or
             'secret' in h.get('key', '').lower()) and
            '{{' not in h.get('value', '')
            for h in headers
        )

        # Check body
        has_hardcoded_body = False
        body = request.get('body', {})
        if body.get('raw'):
            try:
                body_data = json.loads(body['raw'])
                has_hardcoded_body = self._contains_hardcoded_values(body_data)
            except json.JSONDecodeError:
                # If not JSON, check for common patterns
                has_hardcoded_body = re.search(
                    r'("api_key"|"token"|"password"):\s*"[^{]', body['raw']) is not None

        return has_hardcoded_headers or has_hardcoded_body

    def _contains_hardcoded_values(self, obj: Any) -> bool:
        """Check if object contains hardcoded values that should be variables."""
        if not isinstance(obj, dict):
            return False

        for key, value in obj.items():
            if isinstance(value, str):
                # Check for sensitive keys
                if key.lower() in ['token', 'key', 'secret', 'password', 'api_key', 'client_id', 'client_secret']:
                    if '{{' not in value:
                        return True
                # Check for email patterns, URLs
                if re.search(r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', value) or value.startswith('http'):
                    if '{{' not in value:
                        return True
            elif isinstance(value, dict):
                if self._contains_hardcoded_values(value):
                    return True

        return False

    def _validate_headers(self, request: Dict) -> bool:
        """Validate request headers."""
        headers = request.get('header', [])
        header_names = [h.get('key', '').lower() for h in headers]
        method = request.get('method', '').upper()

        # Check for essential headers
        if method in ['POST', 'PUT', 'PATCH'] and request.get('body'):
            if 'content-type' not in header_names:
                return False

        if method in ['GET', 'POST', 'PUT', 'PATCH']:
            if 'accept' not in header_names:
                return False

        return True

    def _detect_variable_usage(self, request: Dict) -> bool:
        """Detect variable usage in request."""
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        has_url_variables = '{{' in url
        has_header_variables = any('{{' in h.get('value', '')
                                   for h in request.get('header', []))

        has_body_variables = False
        body = request.get('body', {})
        if body.get('raw'):
            has_body_variables = '{{' in body['raw']

        return has_url_variables or has_header_variables or has_body_variables

    def _detect_error_handling(self, item: Dict) -> bool:
        """Detect error handling in tests."""
        test_scripts = [e for e in item.get(
            'event', []) if e.get('listen') == 'test']

        for script in test_scripts:
            script_code = '\n'.join(script.get('script', {}).get('exec', []))
            if ('4' in script_code or '5' in script_code or
                    'error' in script_code.lower() or 'fail' in script_code.lower()):
                return True

        return False

    def _validate_naming_convention(self, name: str) -> bool:
        """Validate naming convention."""
        has_consistent_case = re.match(
            r'^[a-zA-Z][a-zA-Z0-9\s\-_]*$', name) is not None
        has_descriptive_name = len(
            name) > 3 and 'test' not in name.lower() and 'temp' not in name.lower()
        return has_consistent_case and has_descriptive_name

    def _detect_security_issues(self, request: Dict) -> bool:
        """Detect security issues."""
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        # Check for exposed credentials in URL
        if re.search(r'[?&](token|key|password|secret)=([^&\s]+)', url):
            return True

        # Check for weak authentication
        auth = request.get('auth', {})
        if auth.get('type') == 'basic' and not url.startswith('https'):
            return True

        # Check headers for exposed credentials
        headers = request.get('header', [])
        return any('secret' in h.get('key', '').lower() or 'password' in h.get('key', '').lower()
                   for h in headers)

    def _detect_performance_issues(self, request: Dict) -> bool:
        """Detect performance issues."""
        # Large request body
        body = request.get('body', {})
        if body.get('raw') and len(body['raw']) > 10000:
            return True

        # Too many headers
        if len(request.get('header', [])) > 20:
            return True

        # Too many query parameters
        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        query_params = url.split('?')[1] if '?' in url else ''
        if query_params and len(query_params.split('&')) > 15:
            return True

        return False

    def _calculate_security_score(self, request: Dict, has_auth: bool, has_security_issues: bool) -> int:
        """Calculate security score."""
        score = 100
        method = request.get('method', '').upper()

        if not has_auth and method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            score -= 40

        if has_security_issues:
            score -= 30

        url = request.get('url', '')
        if isinstance(url, dict):
            url = url.get('raw', '')

        if url.startswith('http://'):
            score -= 20

        auth = request.get('auth', {})
        if auth.get('type') == 'basic':
            score -= 10

        return max(0, score)

    def _calculate_performance_score(self, request: Dict, has_performance_issues: bool) -> int:
        """Calculate performance score."""
        score = 100

        if has_performance_issues:
            score -= 50

        headers = request.get('header', [])
        header_names = [h.get('key', '').lower() for h in headers]

        if 'cache-control' not in header_names:
            score -= 10

        if 'accept-encoding' not in header_names:
            score -= 10

        return max(0, score)

    def _assess_test_coverage(self, item: Dict) -> str:
        """Assess test coverage."""
        test_scripts = [e for e in item.get(
            'event', []) if e.get('listen') == 'test']

        if not test_scripts:
            return 'none'

        all_test_code = '\n'.join([
            '\n'.join(script.get('script', {}).get('exec', []))
            for script in test_scripts
        ])

        checks = [
            'pm.response.code' in all_test_code or 'status' in all_test_code,
            'responseTime' in all_test_code,
            'pm.response.json' in all_test_code or 'body' in all_test_code,
            '4' in all_test_code or '5' in all_test_code
        ]

        check_count = sum(checks)

        if check_count >= 3:
            return 'comprehensive'
        elif check_count >= 1:
            return 'basic'

        return 'none'

    def _assess_documentation_quality(self, item: Dict) -> str:
        """Assess documentation quality."""
        description = item.get('description', '') or item.get(
            'request', {}).get('description', '')

        if not description:
            return 'none'

        description_lower = description.lower()
        quality_factors = [
            'parameter' in description_lower,
            'response' in description_lower,
            'example' in description_lower,
            'auth' in description_lower,
            'error' in description_lower
        ]

        factor_count = sum(quality_factors)

        if factor_count >= 4:
            return 'excellent'
        elif factor_count >= 2:
            return 'good'
        elif factor_count >= 1 or len(description) > 50:
            return 'minimal'

        return 'none'

    def _check_consistent_naming(self, items: List[Dict]) -> bool:
        """Check if items have consistent naming."""
        if len(items) <= 1:
            return True

        naming_patterns = []
        for item in items:
            name = item.get('name', '').lower()
            if re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name):
                naming_patterns.append('snake_case')
            elif re.match(r'^[a-z][a-zA-Z0-9]*$', name):
                naming_patterns.append('camelCase')
            elif re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', name):
                naming_patterns.append('kebab-case')
            else:
                naming_patterns.append('mixed')

        unique_patterns = set(naming_patterns)
        return len(unique_patterns) == 1 and 'mixed' not in unique_patterns

    def _check_auth_consistency(self, requests: List[Dict]) -> str:
        """Check authentication consistency across requests."""
        if not requests:
            return 'none'

        auth_types = set(req.get('auth_type') or 'none' for req in requests)

        if len(auth_types) == 1:
            return 'none' if 'none' in auth_types else 'consistent'

        return 'mixed'

    def _calculate_avg_documentation_quality(self, requests: List[Dict]) -> int:
        """Calculate average documentation quality score."""
        if not requests:
            return 0

        quality_scores = {
            'excellent': 100,
            'good': 75,
            'minimal': 50,
            'none': 0
        }

        scores = [quality_scores.get(
            req.get('documentation_quality', 'none'), 0) for req in requests]
        return round(sum(scores) / len(scores))

    def _calculate_avg_security_score(self, requests: List[Dict]) -> int:
        """Calculate average security score."""
        if not requests:
            return 0

        scores = [req.get('security_score', 0) for req in requests]
        return round(sum(scores) / len(scores))

    def _calculate_avg_performance_score(self, requests: List[Dict]) -> int:
        """Calculate average performance score."""
        if not requests:
            return 0

        scores = [req.get('performance_score', 0) for req in requests]
        return round(sum(scores) / len(scores))

    def _identify_collection_issues(self, collection_data: Dict) -> List[Dict]:
        """Identify collection-level issues."""
        issues = []

        if not collection_data.get('info', {}).get('description'):
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Collection lacks description',
                'location': 'Collection root',
                'suggestion': 'Add a description explaining the purpose of this collection'
            })

        if not collection_data.get('auth'):
            issues.append({
                'type': 'info',
                'severity': 'low',
                'message': 'Collection lacks default authentication',
                'location': 'Collection root',
                'suggestion': 'Consider setting up collection-level authentication'
            })

        return issues

    def _identify_folder_issues(self, folder: Dict, requests: List[Dict]) -> List[Dict]:
        """Identify folder-level issues."""
        issues = []

        if not folder.get('description'):
            issues.append({
                'type': 'warning',
                'severity': 'low',
                'message': 'Folder lacks description',
                'location': folder['name'],
                'suggestion': 'Add a description explaining the purpose of this folder'
            })

        if not requests and (not folder.get('item') or len(folder['item']) == 0):
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Empty folder',
                'location': folder['name'],
                'suggestion': 'Consider removing empty folders or adding requests'
            })

        return issues

    def _generate_request_issues(self, issues: List[Dict], item: Dict, analysis: Dict):
        """Generate request-specific issues."""
        if not analysis['has_description']:
            issues.append({
                'type': 'warning',
                'severity': 'medium',
                'message': 'Request lacks description',
                'location': item['name'],
                'suggestion': 'Add a clear description explaining what this request does'
            })

        if not analysis['has_auth'] and item['request']['method'] in ['POST', 'PUT', 'PATCH', 'DELETE']:
            issues.append({
                'type': 'warning',
                'severity': 'high',
                'message': 'Sensitive operation without authentication',
                'location': item['name'],
                'suggestion': 'Add authentication for this request'
            })

        if not analysis['has_tests']:
            issues.append({
                'type': 'info',
                'severity': 'high',
                'message': 'Request lacks test scripts',
                'location': item['name'],
                'suggestion': 'Add test scripts to validate response'
            })

        if analysis['has_hardcoded_url']:
            issues.append({
                'type': 'warning',
                'severity': 'high',
                'message': 'Request contains hardcoded URL',
                'location': item['name'],
                'suggestion': 'Replace hardcoded URLs with environment variables'
            })

        if analysis['has_security_issues']:
            issues.append({
                'type': 'error',
                'severity': 'high',
                'message': 'Security vulnerabilities detected',
                'location': item['name'],
                'suggestion': 'Address security issues such as exposed credentials'
            })

    def _calculate_quality_score(self, collection_data: Dict, folders: List[Dict], issues: List[Dict]) -> int:
        """Calculate quality score (0-100)."""
        score = 100

        # Deduct points for issues
        for issue in issues:
            severity = issue.get('severity', 'low')
            if severity == 'high':
                score -= 10
            elif severity == 'medium':
                score -= 5
            elif severity == 'low':
                score -= 2

        # Deduct points for folder and request issues
        for folder in folders:
            for issue in folder.get('issues', []):
                severity = issue.get('severity', 'low')
                if severity == 'high':
                    score -= 5
                elif severity == 'medium':
                    score -= 3
                elif severity == 'low':
                    score -= 1

            for request in folder.get('requests', []):
                for issue in request.get('issues', []):
                    severity = issue.get('severity', 'low')
                    if severity == 'high':
                        score -= 3
                    elif severity == 'medium':
                        score -= 2
                    elif severity == 'low':
                        score -= 1

        return max(0, min(100, score))

    def _generate_recommendations(self, issues: List[Dict]) -> List[str]:
        """Generate recommendations based on issues."""
        recommendations = []
        suggestion_counts = {}

        # Count similar suggestions
        for issue in issues:
            suggestion = issue.get('suggestion', '')
            if suggestion:
                suggestion_counts[suggestion] = suggestion_counts.get(
                    suggestion, 0) + 1

        # Generate recommendations from most common suggestions
        sorted_suggestions = sorted(
            suggestion_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        for suggestion, count in sorted_suggestions:
            if count > 1:
                recommendations.append(f"{suggestion} ({count} instances)")
            else:
                recommendations.append(suggestion)

        return recommendations

    def _calculate_overall_security_score(self, folders: List[Dict]) -> int:
        """Calculate overall security score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_security_score', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    def _calculate_overall_performance_score(self, folders: List[Dict]) -> int:
        """Calculate overall performance score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_performance_score', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    def _calculate_overall_documentation_score(self, folders: List[Dict]) -> int:
        """Calculate overall documentation score."""
        if not folders:
            return 0

        scores = []
        for folder in folders:
            avg_score = folder.get('avg_documentation_quality', 0)
            if avg_score > 0:
                scores.append(avg_score)

        return round(sum(scores) / len(scores)) if scores else 0

    def _generate_improvements(self, analysis: Dict) -> List[Dict]:
        """Generate improvement suggestions with enhanced analysis."""
        improvements = []

        # Collection-level improvements
        if analysis['score'] < 80:
            improvements.append({
                'id': 'collection-quality',
                'title': 'Improve Overall Collection Quality',
                'description': f"Collection quality score is {analysis['score']}/100. Focus on addressing high-priority issues.",
                'priority': 'high',
                'category': 'quality',
                'impact': 'high'
            })

        if analysis['overall_security_score'] < 70:
            improvements.append({
                'id': 'security-enhancement',
                'title': 'Enhance Security Practices',
                'description': f"Security score is {analysis['overall_security_score']}/100. Review authentication and data handling.",
                'priority': 'high',
                'category': 'security',
                'impact': 'high'
            })

        if analysis['overall_documentation_score'] < 60:
            improvements.append({
                'id': 'documentation-improvement',
                'title': 'Improve Documentation',
                'description': f"Documentation score is {analysis['overall_documentation_score']}/100. Add descriptions and examples.",
                'priority': 'medium',
                'category': 'documentation',
                'impact': 'medium'
            })

        # Add specific improvements based on common issues
        issue_counts = {}
        for folder in analysis.get('folders', []):
            for request in folder.get('requests', []):
                for issue in request.get('issues', []):
                    issue_type = issue.get('message', '')
                    issue_counts[issue_type] = issue_counts.get(
                        issue_type, 0) + 1

        # Generate improvements for most common issues
        if issue_counts.get('Request lacks test scripts', 0) > 3:
            improvements.append({
                'id': 'add-test-scripts',
                'title': 'Add Test Scripts to Requests',
                'description': f"Found {issue_counts['Request lacks test scripts']} requests without test scripts.",
                'priority': 'medium',
                'category': 'testing',
                'impact': 'medium'
            })

        if issue_counts.get('Request contains hardcoded URL', 0) > 2:
            improvements.append({
                'id': 'use-environment-variables',
                'title': 'Use Environment Variables',
                'description': f"Found {issue_counts['Request contains hardcoded URL']} requests with hardcoded URLs.",
                'priority': 'high',
                'category': 'maintainability',
                'impact': 'high'
            })

        return improvements