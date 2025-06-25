import json
import logging
import re
from typing import Any, Dict, List, Optional
from traceback import format_exc

import requests
from langchain_core.tools import ToolException
from pydantic import Field, model_validator, create_model, SecretStr

from ..elitea_base import BaseToolApiWrapper
from .postman_analysis import PostmanAnalyzer

logger = logging.getLogger(__name__)

# Pydantic models for request schemas
PostmanGetCollections = create_model(
    "PostmanGetCollections"
)

PostmanGetCollection = create_model(
    "PostmanGetCollection"
)

PostmanGetFolder = create_model(
    "PostmanGetFolder",
    folder_path=(str, Field(
        description="The path to the folder (e.g., 'API/Users' for nested folders)"))
)

PostmanGetFolderRequests = create_model(
    "PostmanGetFolderRequests",
    folder_path=(str, Field(description="The path to the folder")),
    include_details=(bool, Field(
        description="Include detailed request information", default=False))
)

PostmanSearchRequests = create_model(
    "PostmanSearchRequests",
    query=(str, Field(description="The search query")),
    search_in=(str, Field(
        description="Where to search: name, url, description, all", default="all")),
    method=(Optional[str], Field(
        description="Optional HTTP method filter", default=None))
)

PostmanAnalyzeCollection = create_model(
    "PostmanAnalyzeCollection",
    include_improvements=(bool, Field(
        description="Include improvement suggestions in the analysis", default=False))
)

PostmanAnalyzeFolder = create_model(
    "PostmanAnalyzeFolder",
    folder_path=(str, Field(description="The path to the folder to analyze")),
    include_improvements=(bool, Field(
        description="Include improvement suggestions in the analysis", default=False))
)

PostmanAnalyzeRequest = create_model(
    "PostmanAnalyzeRequest",
    request_path=(str, Field(description="The path to the request to analyze")),
    include_improvements=(bool, Field(
        description="Include improvement suggestions in the analysis", default=False))
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

PostmanUpdateCollectionName = create_model(
    "PostmanUpdateCollectionName",
    name=(str, Field(description="New name for the collection"))
)

PostmanUpdateCollectionDescription = create_model(
    "PostmanUpdateCollectionDescription",
    description=(str, Field(description="New description for the collection"))
)

PostmanUpdateCollectionVariables = create_model(
    "PostmanUpdateCollectionVariables",
    variables=(List[Dict], Field(description="Updated collection variables"))
)

PostmanUpdateCollectionAuth = create_model(
    "PostmanUpdateCollectionAuth",
    auth=(Dict, Field(description="Updated authentication settings"))
)

PostmanDeleteCollection = create_model(
    "PostmanDeleteCollection"
)

PostmanDuplicateCollection = create_model(
    "PostmanDuplicateCollection",
    new_name=(str, Field(description="Name for the new collection copy"))
)

PostmanCreateFolder = create_model(
    "PostmanCreateFolder",
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
    folder_path=(str, Field(description="Path to the folder to delete"))
)

PostmanMoveFolder = create_model(
    "PostmanMoveFolder",
    source_path=(str, Field(description="Current path of the folder to move")),
    target_path=(Optional[str], Field(
        description="New parent folder path", default=None))
)

PostmanCreateRequest = create_model(
    "PostmanCreateRequest",
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

PostmanUpdateRequestName = create_model(
    "PostmanUpdateRequestName",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    name=(str, Field(description="New name for the request"))
)

PostmanUpdateRequestMethod = create_model(
    "PostmanUpdateRequestMethod",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    method=(str, Field(description="HTTP method for the request"))
)

PostmanUpdateRequestUrl = create_model(
    "PostmanUpdateRequestUrl",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    url=(str, Field(description="URL for the request"))
)

PostmanUpdateRequestDescription = create_model(
    "PostmanUpdateRequestDescription",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    description=(str, Field(description="Description for the request"))
)

PostmanUpdateRequestHeaders = create_model(
    "PostmanUpdateRequestHeaders",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    headers=(List[Dict], Field(description="Request headers"))
)

PostmanUpdateRequestBody = create_model(
    "PostmanUpdateRequestBody",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    body=(Dict, Field(description="Request body"))
)

PostmanUpdateRequestAuth = create_model(
    "PostmanUpdateRequestAuth",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    auth=(Dict, Field(description="Request authentication"))
)

PostmanUpdateRequestTests = create_model(
    "PostmanUpdateRequestTests",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    tests=(str, Field(description="Test script code"))
)

PostmanUpdateRequestPreScript = create_model(
    "PostmanUpdateRequestPreScript",
    request_path=(str, Field(description="Path to the request (folder/requestName)")),
    pre_request_script=(str, Field(description="Pre-request script code"))
)

PostmanDeleteRequest = create_model(
    "PostmanDeleteRequest",
    request_path=(str, Field(description="Path to the request to delete"))
)

PostmanDuplicateRequest = create_model(
    "PostmanDuplicateRequest",
    source_path=(str, Field(description="Path to the request to duplicate")),
    new_name=(str, Field(description="Name for the duplicated request")),
    target_path=(Optional[str], Field(
        description="Target folder path", default=None))
)

PostmanMoveRequest = create_model(
    "PostmanMoveRequest",
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
    session: Any = None
    analyzer: PostmanAnalyzer = None

    model_config = {
        "arbitrary_types_allowed": True
    }

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
        values["session"] = requests.Session()
        values["session"].headers.update({
            'X-API-Key': values.get('api_key'),
            'Content-Type': 'application/json'
        })
        values["analyzer"] = PostmanAnalyzer()
        return values


    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Postman API."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"

        try:
            logger.info(f"Making {method.upper()} request to {url}")
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
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
                "name": "analyze_request",
                "mode": "analyze_request",
                "description": "Analyze a specific request within a collection",
                "args_schema": PostmanAnalyzeRequest,
                "ref": self.analyze_request
            },
            {
                "name": "create_collection",
                "mode": "create_collection",
                "description": "Create a new Postman collection",
                "args_schema": PostmanCreateCollection,
                "ref": self.create_collection
            },
            {
                "name": "update_collection_name",
                "mode": "update_collection_name",
                "description": "Update collection name",
                "args_schema": PostmanUpdateCollectionName,
                "ref": self.update_collection_name
            },
            {
                "name": "update_collection_description",
                "mode": "update_collection_description",
                "description": "Update collection description",
                "args_schema": PostmanUpdateCollectionDescription,
                "ref": self.update_collection_description
            },
            {
                "name": "update_collection_variables",
                "mode": "update_collection_variables",
                "description": "Update collection variables",
                "args_schema": PostmanUpdateCollectionVariables,
                "ref": self.update_collection_variables
            },
            {
                "name": "update_collection_auth",
                "mode": "update_collection_auth",
                "description": "Update collection authentication settings",
                "args_schema": PostmanUpdateCollectionAuth,
                "ref": self.update_collection_auth
            },
            # {
            #     "name": "delete_collection",
            #     "mode": "delete_collection",
            #     "description": "Delete a collection permanently",
            #     "args_schema": PostmanDeleteCollection,
            #     "ref": self.delete_collection
            # },
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
            # {
            #     "name": "delete_folder",
            #     "mode": "delete_folder",
            #     "description": "Delete a folder and all its contents permanently",
            #     "args_schema": PostmanDeleteFolder,
            #     "ref": self.delete_folder
            # },
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
                "name": "update_request_name",
                "mode": "update_request_name",
                "description": "Update request name",
                "args_schema": PostmanUpdateRequestName,
                "ref": self.update_request_name
            },
            {
                "name": "update_request_method",
                "mode": "update_request_method",
                "description": "Update request HTTP method",
                "args_schema": PostmanUpdateRequestMethod,
                "ref": self.update_request_method
            },
            {
                "name": "update_request_url",
                "mode": "update_request_url",
                "description": "Update request URL",
                "args_schema": PostmanUpdateRequestUrl,
                "ref": self.update_request_url
            },
            {
                "name": "update_request_description",
                "mode": "update_request_description",
                "description": "Update request description",
                "args_schema": PostmanUpdateRequestDescription,
                "ref": self.update_request_description
            },
            {
                "name": "update_request_headers",
                "mode": "update_request_headers",
                "description": "Update request headers",
                "args_schema": PostmanUpdateRequestHeaders,
                "ref": self.update_request_headers
            },
            {
                "name": "update_request_body",
                "mode": "update_request_body",
                "description": "Update request body",
                "args_schema": PostmanUpdateRequestBody,
                "ref": self.update_request_body
            },
            {
                "name": "update_request_auth",
                "mode": "update_request_auth",
                "description": "Update request authentication",
                "args_schema": PostmanUpdateRequestAuth,
                "ref": self.update_request_auth
            },
            {
                "name": "update_request_tests",
                "mode": "update_request_tests",
                "description": "Update request test scripts",
                "args_schema": PostmanUpdateRequestTests,
                "ref": self.update_request_tests
            },
            {
                "name": "update_request_pre_script",
                "mode": "update_request_pre_script",
                "description": "Update request pre-request scripts",
                "args_schema": PostmanUpdateRequestPreScript,
                "ref": self.update_request_pre_script
            },
            # {
            #     "name": "delete_request",
            #     "mode": "delete_request",
            #     "description": "Delete an API request permanently",
            #     "args_schema": PostmanDeleteRequest,
            #     "ref": self.delete_request
            # },
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

    def get_collection(self, **kwargs) -> str:
        """Get a specific collection by ID."""
        try:
            response = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting collection {self.collection_id}: {stacktrace}")
            raise ToolException(
                f"Unable to get collection {self.collection_id}: {str(e)}")

    def get_folder(self, folder_path: str, **kwargs) -> str:
        """Get folders from a collection by path."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            folders = self.analyzer.find_folders_by_path(
                collection['collection']['item'], folder_path)
            return json.dumps(folders, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when getting folder {folder_path}: {stacktrace}")
            raise ToolException(
                f"Unable to get folder {folder_path} from collection {self.collection_id}: {str(e)}")

    def get_folder_requests(self, folder_path: str, include_details: bool = False, **kwargs) -> str:
        """Get detailed information about all requests in a folder."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            folders = self.analyzer.find_folders_by_path(
                collection['collection']['item'], folder_path)

            if not folders:
                raise ToolException(f"Folder '{folder_path}' not found in collection '{self.collection_id}'.")

            folder = folders[0]
            requests = self.analyzer.extract_requests_from_items(
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

    def search_requests(self, query: str, search_in: str = "all", method: str = None, **kwargs) -> str:
        """Search for requests across the collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            requests = self.analyzer.search_requests_in_items(
                collection['collection']['item'], query, search_in, method)

            result = {
                "collection_id": self.collection_id,
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
                f"Unable to search requests in collection {self.collection_id}: {str(e)}")

    def analyze_collection(self, include_improvements: bool = False, **kwargs) -> str:
        """Analyze a collection for API quality and best practices."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            analysis = self.analyzer.perform_collection_analysis(collection)
            
            if include_improvements:
                improvements = self.analyzer.generate_improvements(analysis)
                analysis["improvements"] = improvements
                analysis["improvement_count"] = len(improvements)
            
            return json.dumps(analysis, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing collection: {stacktrace}")
            raise ToolException(
                f"Unable to analyze collection {self.collection_id}: {str(e)}")

    def analyze_folder(self, folder_path: str, include_improvements: bool = False, **kwargs) -> str:
        """Analyze a specific folder within a collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            folders = self.analyzer.find_folders_by_path(
                collection['collection']['item'], folder_path)

            if not folders:
                return json.dumps({"error": f"Folder '{folder_path}' not found"}, indent=2)

            folder_analyses = []
            for folder in folders:
                analysis = self.analyzer.perform_folder_analysis(folder, folder_path)
                
                if include_improvements:
                    improvements = self.analyzer.generate_folder_improvements(analysis)
                    analysis["improvements"] = improvements
                    analysis["improvement_count"] = len(improvements)
                
                folder_analyses.append(analysis)

            return json.dumps(folder_analyses, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing folder: {stacktrace}")
            raise ToolException(
                f"Unable to analyze folder {folder_path}: {str(e)}")

    def analyze_request(self, request_path: str, include_improvements: bool = False, **kwargs) -> str:
        """Analyze a specific request within a collection."""
        try:
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Perform request analysis
            analysis = self.analyzer.perform_request_analysis(request_item)
            analysis["request_path"] = request_path
            analysis["collection_id"] = self.collection_id
            
            if include_improvements:
                improvements = self.analyzer.generate_request_improvements(analysis)
                analysis["improvements"] = improvements
                analysis["improvement_count"] = len(improvements)

            return json.dumps(analysis, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when analyzing request: {stacktrace}")
            raise ToolException(
                f"Unable to analyze request {request_path}: {str(e)}")

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

    def update_collection_name(self, name: str, **kwargs) -> str:
        """Update collection name."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update name
            collection_data["info"]["name"] = name

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection name: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} name: {str(e)}")

    def update_collection_description(self, description: str, **kwargs) -> str:
        """Update collection description."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update description
            collection_data["info"]["description"] = description

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection description: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} description: {str(e)}")

    def update_collection_variables(self, variables: List[Dict], **kwargs) -> str:
        """Update collection variables."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update variables
            collection_data["variable"] = variables

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection variables: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} variables: {str(e)}")

    def update_collection_auth(self, auth: Dict, **kwargs) -> str:
        """Update collection authentication settings."""
        try:
            # Get current collection
            current = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = current["collection"]

            # Update auth
            collection_data["auth"] = auth

            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating collection auth: {stacktrace}")
            raise ToolException(
                f"Unable to update collection {self.collection_id} auth: {str(e)}")

    def delete_collection(self, **kwargs) -> str:
        """Delete a collection permanently."""
        try:
            response = self._make_request(
                'DELETE', f'/collections/{self.collection_id}')
            return json.dumps({"message": f"Collection {self.collection_id} deleted successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting collection: {stacktrace}")
            raise ToolException(
                f"Unable to delete collection {self.collection_id}: {str(e)}")

    def duplicate_collection(self, new_name: str, **kwargs) -> str:
        """Create a copy of an existing collection."""
        try:
            # Get the original collection
            original = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = original["collection"]

            # Update the name and remove IDs to create a new collection
            collection_data["info"]["name"] = new_name
            if "_postman_id" in collection_data["info"]:
                del collection_data["info"]["_postman_id"]

            # Remove item IDs recursively
            self.analyzer.remove_item_ids(collection_data.get("item", []))

            response = self._make_request(
                'POST', '/collections', json={"collection": collection_data})
            return json.dumps(response, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(
                f"Exception when duplicating collection: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate collection {self.collection_id}: {str(e)}")

    # =================================================================
    # FOLDER MANAGEMENT METHODS
    # =================================================================

    def create_folder(self, name: str, description: str = None,
                      parent_path: str = None, auth: Dict = None, **kwargs) -> str:
        """Create a new folder in a collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
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
                parent_folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], parent_path)
                if not parent_folders:
                    raise ToolException(
                        f"Parent folder '{parent_path}' not found")
                parent_folders[0]["item"].append(folder_item)
            else:
                collection_data["item"].append(folder_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating folder: {stacktrace}")
            raise ToolException(f"Unable to create folder '{name}': {str(e)}")

    def update_folder(self, folder_path: str, name: str = None,
                      description: str = None, auth: Dict = None, **kwargs) -> str:
        """Update folder properties."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the folder
            folders = self.analyzer.find_folders_by_path(
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
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Folder '{folder_path}' updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating folder: {stacktrace}")
            raise ToolException(
                f"Unable to update folder '{folder_path}': {str(e)}")

    def delete_folder(self, folder_path: str, **kwargs) -> str:
        """Delete a folder and all its contents permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find and remove the folder
            if self.analyzer.remove_folder_by_path(collection_data["item"], folder_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Folder '{folder_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Folder '{folder_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting folder: {stacktrace}")
            raise ToolException(
                f"Unable to delete folder '{folder_path}': {str(e)}")

    def move_folder(self, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move a folder to a different location within the collection."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source folder
            source_folder = self.analyzer.find_folders_by_path(
                collection_data["item"], source_path)
            if not source_folder:
                raise ToolException(f"Source folder '{source_path}' not found")

            folder_data = source_folder[0].copy()

            # Remove from source location
            self.analyzer.remove_folder_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                target_folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not target_folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                target_folders[0]["item"].append(folder_data)
            else:
                collection_data["item"].append(folder_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
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

    def create_request(self, name: str, method: str, url: str,
                       folder_path: str = None, description: str = None, headers: List[Dict] = None,
                       body: Dict = None, auth: Dict = None, tests: str = None,
                       pre_request_script: str = None, **kwargs) -> str:
        """Create a new API request in a folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
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
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], folder_path)
                if not folders:
                    raise ToolException(f"Folder '{folder_path}' not found")
                folders[0]["item"].append(request_item)
            else:
                collection_data["item"].append(request_item)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{name}' created successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when creating request: {stacktrace}")
            raise ToolException(f"Unable to create request '{name}': {str(e)}")

    def update_request_name(self, request_path: str, name: str, **kwargs) -> str:
        """Update request name."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update name
            request_item["name"] = name

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' name updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request name: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' name: {str(e)}")

    def update_request_method(self, request_path: str, method: str, **kwargs) -> str:
        """Update request HTTP method."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update method
            request_item["request"]["method"] = method.upper()

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' method updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request method: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' method: {str(e)}")

    def update_request_url(self, request_path: str, url: str, **kwargs) -> str:
        """Update request URL."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update URL
            request_item["request"]["url"] = url

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' URL updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request URL: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' URL: {str(e)}")

    def update_request_description(self, request_path: str, description: str, **kwargs) -> str:
        """Update request description."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update description
            request_item["request"]["description"] = description

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' description updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request description: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' description: {str(e)}")

    def update_request_headers(self, request_path: str, headers: List[Dict], **kwargs) -> str:
        """Update request headers."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update headers
            request_item["request"]["header"] = headers

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' headers updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request headers: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' headers: {str(e)}")

    def update_request_body(self, request_path: str, body: Dict, **kwargs) -> str:
        """Update request body."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update body
            request_item["request"]["body"] = body

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' body updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request body: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' body: {str(e)}")

    def update_request_auth(self, request_path: str, auth: Dict, **kwargs) -> str:
        """Update request authentication."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update auth
            request_item["request"]["auth"] = auth

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' auth updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request auth: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' auth: {str(e)}")

    def update_request_tests(self, request_path: str, tests: str, **kwargs) -> str:
        """Update request test scripts."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update test events
            events = request_item.get("event", [])
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
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' tests updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request tests: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' tests: {str(e)}")

    def update_request_pre_script(self, request_path: str, pre_request_script: str, **kwargs) -> str:
        """Update request pre-request scripts."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find the request
            request_item = self.analyzer.find_request_by_path(
                collection_data["item"], request_path)
            if not request_item:
                raise ToolException(f"Request '{request_path}' not found")

            # Update prerequest events
            events = request_item.get("event", [])
            # Remove existing prerequest events
            events = [e for e in events if e.get("listen") != "prerequest"]
            if pre_request_script:
                events.append({
                    "listen": "prerequest",
                    "script": {
                        "exec": pre_request_script.split('\n'),
                        "type": "text/javascript"
                    }
                })
            request_item["event"] = events

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request '{request_path}' pre-script updated successfully"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when updating request pre-script: {stacktrace}")
            raise ToolException(
                f"Unable to update request '{request_path}' pre-script: {str(e)}")

    def delete_request(self, request_path: str, **kwargs) -> str:
        """Delete an API request permanently."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find and remove the request
            if self.analyzer.remove_request_by_path(collection_data["item"], request_path):
                # Update collection
                response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                              json={"collection": collection_data})
                return json.dumps({"message": f"Request '{request_path}' deleted successfully"}, indent=2)
            else:
                raise ToolException(f"Request '{request_path}' not found")
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when deleting request: {stacktrace}")
            raise ToolException(
                f"Unable to delete request '{request_path}': {str(e)}")

    def duplicate_request(self, source_path: str, new_name: str,
                          target_path: str = None, **kwargs) -> str:
        """Create a copy of an existing API request."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self.analyzer.find_request_by_path(
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
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_copy)
            else:
                # Add to same location as source
                source_folder_path = "/".join(source_path.split("/")[:-1])
                if source_folder_path:
                    folders = self.analyzer.find_folders_by_path(
                        collection_data["item"], source_folder_path)
                    folders[0]["item"].append(request_copy)
                else:
                    collection_data["item"].append(request_copy)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
                                          json={"collection": collection_data})
            return json.dumps({"message": f"Request duplicated as '{new_name}'"}, indent=2)
        except Exception as e:
            stacktrace = format_exc()
            logger.error(f"Exception when duplicating request: {stacktrace}")
            raise ToolException(
                f"Unable to duplicate request '{source_path}': {str(e)}")

    def move_request(self, source_path: str, target_path: str = None, **kwargs) -> str:
        """Move an API request to a different folder."""
        try:
            # Get current collection
            collection = self._make_request(
                'GET', f'/collections/{self.collection_id}')
            collection_data = collection["collection"]

            # Find source request
            source_request = self.analyzer.find_request_by_path(
                collection_data["item"], source_path)
            if not source_request:
                raise ToolException(
                    f"Source request '{source_path}' not found")

            request_data = json.loads(json.dumps(source_request))  # Deep copy

            # Remove from source location
            self.analyzer.remove_request_by_path(collection_data["item"], source_path)

            # Add to target location
            if target_path:
                folders = self.analyzer.find_folders_by_path(
                    collection_data["item"], target_path)
                if not folders:
                    raise ToolException(
                        f"Target folder '{target_path}' not found")
                folders[0]["item"].append(request_data)
            else:
                collection_data["item"].append(request_data)

            # Update collection
            response = self._make_request('PUT', f'/collections/{self.collection_id}',
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



    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to Postman API."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"

        try:
            logger.info(f"Making {method.upper()} request to {url}")
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
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





    # =================================================================
    # HELPER METHODS
    # =================================================================

        for item in items:
            if item.get('request'):  # This is a request
                analysis = self.analyzer.perform_request_analysis(item)
                requests.append(analysis)

        return requests

