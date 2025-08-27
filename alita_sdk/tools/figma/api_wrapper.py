import functools
import json
import logging
import re
from enum import Enum
from typing import Dict, List, Generator, Optional, Union

import requests
from FigmaPy import FigmaPy
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, create_model, model_validator, SecretStr

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools
from ..utils.content_parser import load_content_from_bytes

GLOBAL_LIMIT = 10000


class ArgsSchema(Enum):
    NoInput = create_model("NoInput")
    FileNodes = create_model(
        "FileNodes",
        file_key=(
            str,
            Field(
                description="Specifies file key id", examples=["Fp24FuzPwH0L74ODSrCnQo"]
            ),
        ),
        ids=(
            str,
            Field(
                description="Specifies id of file nodes separated by comma",
                examples=["8:6,1:7"],
            ),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    File = create_model(
        "FileNodes",
        file_key=(
            str,
            Field(
                description="Specifies file key id.",
                examples=["Fp24FuzPwH0L74ODSrCnQo"],
            ),
        ),
        geometry=(
            Optional[str],
            Field(description="Sets to 'paths' to export vector data"),
        ),
        version=(
            Optional[str],
            Field(description="Sets version of file"),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    FileKey = create_model(
        "FileKey",
        file_key=(
            str,
            Field(
                description="Specifies file key id.",
                examples=["Fp24FuzPwH0L74ODSrCnQo"],
            ),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    FileComment = create_model(
        "FileComment",
        file_key=(
            str,
            Field(
                description="Specifies file key id.",
                examples=["Fp24FuzPwH0L74ODSrCnQo"],
            ),
        ),
        message=(
            str,
            Field(description="Message for the comment."),
        ),
        client_meta=(
            Optional[dict],
            Field(
                description="Positioning information of the comment (Vector, FrameOffset, Region, FrameOffsetRegion)"
            ),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    FileImages = create_model(
        "FileImages",
        file_key=(
            str,
            Field(
                description="Specifies file key id.",
                examples=["Fp24FuzPwH0L74ODSrCnQo"],
            ),
        ),
        ids=(
            str,
            Field(
                description="Specifies id of file images separated by comma",
                examples=["8:6,1:7"],
            ),
        ),
        scale=(
            Optional[str],
            Field(description="A number between 0.01 and 4, the image scaling factor"),
        ),
        format=(
            Optional[str],
            Field(
                description="A string enum for the image output format",
                examples=["jpg", "png", "svg", "pdf"],
            ),
        ),
        version=(
            Optional[str],
            Field(description="A specific version ID to use"),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    TeamProjects = create_model(
        "TeamProjects",
        team_id=(
            str,
            Field(
                description="ID of the team to list projects from",
                examples=["1101853299713989222"],
            ),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )
    ProjectFiles = create_model(
        "ProjectFiles",
        project_id=(
            str,
            Field(
                description="ID of the project to list files from",
                examples=["55391681"],
            ),
        ),
        extra_params=(
            Optional[Dict[str, Union[str, int, None]]],
            Field(
                description="Additional parameters including limit and regex pattern to be removed from response",
                default={"limit": GLOBAL_LIMIT, "regexp": None},
                examples=[
                    {
                        "limit": "1000",
                        "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                    }
                ],
            ),
        ),
    )


class FigmaApiWrapper(NonCodeIndexerToolkit):
    token: Optional[SecretStr] = Field(default=None)
    oauth2: Optional[SecretStr] = Field(default=None)
    global_limit: Optional[int] = Field(default=GLOBAL_LIMIT)
    global_regexp: Optional[str] = Field(default=None)
    _client: Optional[FigmaPy] = PrivateAttr()

    def _base_loader(
            self,
            project_id: Optional[str] = None,
            file_keys_include: Optional[List[str]] = None,
            file_keys_exclude: Optional[List[str]] = None,
            node_ids_include: Optional[List[str]] = None,
            node_ids_exclude: Optional[List[str]] = None,
            node_types_include: Optional[List[str]] = None,
            node_types_exclude: Optional[List[str]] = None,
            **kwargs
    ) -> Generator[Document, None, None]:
        # If both include and exclude are provided, use only include
        if file_keys_include:
            self._log_tool_event(f"Loading files: {file_keys_include}")
            for file_key in file_keys_include:
                self._log_tool_event(f"Loading file `{file_key}`")
                file = self._client.get_file(file_key)
                if not file:
                    raise ToolException(f"Unexpected error while retrieving file {file_key}. Probably file is under editing. Try again later.")
                metadata = {
                    'id': file_key,
                    'file_key': file_key,
                    'name': file.name,
                    'updated_on': file.last_modified,
                    'figma_pages_include': node_ids_include or [],
                    'figma_pages_exclude': node_ids_exclude or [],
                    'figma_nodes_include': node_types_include or [],
                    'figma_nodes_exclude': node_types_exclude or []
                }
                yield Document(page_content=json.dumps(metadata), metadata=metadata)
        elif project_id:
            self._log_tool_event(f"Loading project files from project `{project_id}`")
            files = json.loads(self.get_project_files(project_id)).get('files', [])
            for file in files:
                if file_keys_exclude and file.get('key', '') in file_keys_exclude:
                    continue
                yield Document(page_content=json.dumps(file), metadata={
                    'id': file.get('key', ''),
                    'file_key': file.get('key', ''),
                    'name': file.get('name', ''),
                    'updated_on': file.get('last_modified', ''),
                    'figma_pages_include': node_ids_include or [],
                    'figma_pages_exclude': node_ids_exclude or [],
                    'figma_nodes_include': node_types_include or [],
                    'figma_nodes_exclude': node_types_exclude or []
                })
        elif file_keys_exclude or node_ids_exclude:
            raise ValueError("Excludes without parent (project_id or file_keys_include) do not make sense.")
        else:
            raise ValueError("You must provide at least project_id or file_keys_include.")

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        file_key = document.metadata.get('id', '')
        self._log_tool_event(f"Loading details (images) for `{file_key}`")
        #
        figma_pages = self._client.get_file(file_key).document.get('children', [])
        node_ids_include = document.metadata.pop('figma_pages_include', [])
        node_ids_exclude = document.metadata.pop('figma_pages_exclude', [])
        node_types_include = [t.lower() for t in document.metadata.pop('figma_nodes_include', [])]
        node_types_exclude = [t.lower() for t in document.metadata.pop('figma_nodes_exclude', [])]
        self._log_tool_event(f"Included pages: {node_ids_include}. Excluded pages: {node_ids_exclude}.")
        if node_ids_include:
            figma_pages = [node for node in figma_pages if ('id' in node and node['id'].replace(':', '-') in node_ids_include)]
        elif node_ids_exclude:
            figma_pages = [node for node in figma_pages if ('id' in node and node['id'].replace(':', '-') not in node_ids_exclude)]
        node_ids = [
            child['id']
            for page in figma_pages
            if 'children' in page
            for child in page['children']
            if 'id' in child
            and (
                (node_types_include and child.get('type').lower() in node_types_include)
                or (node_types_exclude and child.get('type').lower() not in node_types_exclude)
                or (not node_types_include and not node_types_exclude)
            )
        ]

        images = self._client.get_file_images(file_key, node_ids).images or {}
        total_images = len(images)
        if total_images == 0:
            logging.info(f"No images found for file {file_key}.")
            return
        progress_step = max(1, total_images // 10)
        for idx, (node_id, image_url) in enumerate(images.items(), 1):
            if not image_url:
                logging.warning(f"Image URL not found for node_id {node_id} in file {file_key}. Skipping.")
                continue
            response = requests.get(image_url)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type.lower():
                    extension = f".{content_type.split('/')[-1]}" if content_type.startswith('image') else '.txt'
                    page_content = load_content_from_bytes(
                        file_content=response.content,
                        extension=extension, llm=self.llm)
                    yield Document(
                        page_content=page_content,
                        metadata={
                            'id': node_id,
                            'updated_on': document.metadata.get('updated_on', ''),
                            'file_key': file_key,
                            'node_id': node_id,
                            'image_url': image_url
                        }
                    )
            if idx % progress_step == 0 or idx == total_images:
                percent = int((idx / total_images) * 100)
                msg = f"Processed {idx}/{total_images} images ({percent}%) for file {file_key}."
                logging.info(msg)
                self._log_tool_event(msg)

    def _remove_metadata_keys(self):
        return super()._remove_metadata_keys() + ['figma_pages_include', 'figma_pages_exclude', 'figma_nodes_include', 'figma_nodes_exclude']

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            "project_id": (Optional[str], Field(
                description="ID of the project to list files from: i.e. 55391681'",
                default=None)),
            'file_keys_include': (Optional[List[str]], Field(
                description="List of file keys to include in index if project_id is not provided: i.e. ['Fp24FuzPwH0L74ODSrCnQo', 'jmhAr6q78dJoMRqt48zisY']",
                default=None)),
            'file_keys_exclude': (Optional[List[str]], Field(
                description="List of file keys to exclude from index. It is applied only if project_id is provided and file_keys_include is not provided: i.e. ['Fp24FuzPwH0L74ODSrCnQo', 'jmhAr6q78dJoMRqt48zisY']",
                default=None)),
            'node_ids_include': (Optional[List[str]], Field(
                description="List of top-level nodes (pages) in file to include in index. It is node-id from figma url: i.e. ['123-56', '7651-9230'].",
                default=None)),
            'node_ids_exclude': (Optional[List[str]], Field(
                description="List of top-level nodes (pages) in file to exclude from index. It is applied only if node_ids_include is not provided. It is node-id from figma url: i.e. ['Fp24FuzPwH0L74ODSrCnQo', 'jmhAr6q78dJoMRqt48zisY']",
                default=None)),
            'node_types_include': (Optional[List[str]], Field(
                description="List type of nodes to include in index: i.e. ['FRAME', 'COMPONENT', 'RECTANGLE', 'COMPONENT_SET', 'INSTANCE', 'VECTOR', ...].",
                default=None)),
            'node_types_exclude': (Optional[List[str]], Field(
                description="List type of nodes to exclude from index. It is applied only if node_types_include is not provided: i.e. ['FRAME', 'COMPONENT', 'RECTANGLE', 'COMPONENT_SET', 'INSTANCE', 'VECTOR', ...]",
                default=None))
        }

    def _send_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """Send HTTP request to a specified URL with automated headers."""
        headers = {"Content-Type": "application/json"}

        if self.oauth2:
            headers["Authorization"] = f"Bearer {self.oauth2}"
        else:
            headers["X-Figma-Token"] = self.token

        if extra_headers:
            headers.update(extra_headers)

        try:
            response = requests.request(method, url, headers=headers, json=payload)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            msg = f"HTTP request failed: {e}"
            logging.error(msg)
            raise ToolException(msg)

    @model_validator(mode='before')
    @classmethod
    def check_before(cls, values):
        return super().validate_toolkit(values)

    @model_validator(mode="after")
    @classmethod
    def validate_toolkit(cls, values):
        token = values.token.get_secret_value() if values.token else None
        oauth2 = values.oauth2.get_secret_value() if values.oauth2 else None
        global_regexp = values.global_regexp

        if global_regexp is None:
            logging.warning("No regex pattern provided. Skipping regex compilation.")
            cls.global_regexp = None
        else:
            try:
                re.compile(global_regexp)
                cls.global_regexp = global_regexp
            except re.error as e:
                msg = f"Failed to compile regex pattern: {str(e)}"
                logging.error(msg)
                return ToolException(msg)

        try:
            if token:
                cls._client = FigmaPy(token=token, oauth2=False)
                logging.info("Authenticated with Figma token")
            elif oauth2:
                cls._client = FigmaPy(token=oauth2, oauth2=True)
                logging.info("Authenticated with OAuth2 token")
            else:
                return ToolException("You have to define Figma token.")
            logging.info("Successfully authenticated to Figma.")
        except Exception as e:
            msg = f"Failed to authenticate with Figma: {str(e)}"
            logging.error(msg)
            return ToolException(msg)

        return values

    @staticmethod
    def process_output(func):
        def simplified_dict(obj, depth=1, max_depth=3, seen=None):
            """Convert object to a dictionary, limit recursion depth and manage cyclic references."""
            if seen is None:
                seen = set()

            if id(obj) in seen:
                pass
            seen.add(id(obj))

            if depth > max_depth:
                return str(obj)

            if isinstance(obj, list):
                return [
                    simplified_dict(item, depth + 1, max_depth, seen) for item in obj
                ]
            elif hasattr(obj, "__dict__"):
                return {
                    key: simplified_dict(getattr(obj, key), depth + 1, max_depth, seen)
                    for key in obj.__dict__
                    if not key.startswith("__") and not callable(getattr(obj, key))
                }
            elif isinstance(obj, dict):
                return {
                    k: simplified_dict(v, depth + 1, max_depth, seen)
                    for k, v in obj.items()
                }
            return obj

        def fix_trailing_commas(json_string):
            json_string = re.sub(r",\s*,+", ",", json_string)
            json_string = re.sub(r",\s*([\]}])", r"\1", json_string)
            json_string = re.sub(r"([\[{])\s*,", r"\1", json_string)
            return json_string

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            extra_params = kwargs.pop("extra_params", {})

            limit = extra_params.get("limit", self.global_limit)
            regexp = extra_params.get("regexp", self.global_regexp)

            try:
                limit = int(limit)
                result = func(self, *args, **kwargs)
                if result and "__dict__" in dir(result):
                    result = result.__dict__
                elif not result:
                    return ToolException(
                        "Response result is empty. Check your input parameters or credentials"
                    )

                if isinstance(result, (dict, list)):
                    processed_result = simplified_dict(result)
                    result = json.dumps(processed_result)
                else:
                    result = json.dumps(result)

                if regexp:
                    regexp = re.compile(regexp)
                    result = re.sub(regexp, "", result)
                    result = fix_trailing_commas(result)
                result = result[:limit]
                return result
            except Exception as e:
                msg = f"Error in '{func.__name__}': {str(e)}"
                logging.error(msg)
                return ToolException(msg)

        return wrapper

    @process_output
    def get_file_nodes(self, file_key: str, ids: str, **kwargs):
        """Reads a specified file nodes by field key from Figma."""
        return self._client.api_request(
            f"files/{file_key}/nodes?ids={str(ids)}", method="get"
        )

    @process_output
    def get_file(
        self,
        file_key: str,
        geometry: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs,
    ):
        """Reads a specified file by field key from Figma."""
        return self._client.get_file(file_key, geometry, version)

    @process_output
    def get_file_versions(self, file_key: str, **kwargs):
        """Retrieves the version history of a specified file from Figma."""
        return self._client.get_file_versions(file_key)

    @process_output
    def get_file_comments(self, file_key: str, **kwargs):
        """Retrieves comments on a specified file from Figma."""
        return self._client.get_comments(file_key)

    @process_output
    def post_file_comment(
        self, file_key: str, message: str, client_meta: Optional[dict] = None
    ):
        """Posts a comment to a specific file in Figma."""
        payload = {"message": message}
        if client_meta:
            payload["client_meta"] = client_meta

        url = f"{self._client.api_uri}files/{file_key}/comments"

        try:
            response = self._send_request("POST", url, payload)
            return response.json()
        except ToolException as e:
            msg = f"Failed to post comment. Error: {str(e)}"
            logging.error(msg)
            return ToolException(msg)

    @process_output
    def get_file_images(
        self,
        file_key: str,
        ids: str = "0:0",
        scale: Optional[str] = None,
        format: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs,
    ):
        """Fetches URLs for server-rendered images from a Figma file based on node IDs."""
        ids_list = ids.split(",")
        return self._client.get_file_images(
            file_key=file_key, ids=ids_list, scale=scale, format=format, version=version
        )

    @process_output
    def get_team_projects(self, team_id: str, **kwargs):
        """Retrieves all projects for a specified team ID from Figma."""
        return self._client.get_team_projects(team_id)

    @process_output
    def get_project_files(self, project_id: str, **kwargs):
        """Retrieves all files for a specified project ID from Figma."""
        return self._client.get_project_files(project_id)

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "get_file_nodes",
                "description": self.get_file_nodes.__doc__,
                "args_schema": ArgsSchema.FileNodes.value,
                "ref": self.get_file_nodes,
            },
            {
                "name": "get_file",
                "description": self.get_file.__doc__,
                "args_schema": ArgsSchema.File.value,
                "ref": self.get_file,
            },
            {
                "name": "get_file_versions",
                "description": self.get_file_versions.__doc__,
                "args_schema": ArgsSchema.FileKey.value,
                "ref": self.get_file_versions,
            },
            {
                "name": "get_file_comments",
                "description": self.get_file_comments.__doc__,
                "args_schema": ArgsSchema.FileKey.value,
                "ref": self.get_file_comments,
            },
            {
                "name": "post_file_comment",
                "description": self.post_file_comment.__doc__,
                "args_schema": ArgsSchema.FileComment.value,
                "ref": self.post_file_comment,
            },
            {
                "name": "get_file_images",
                "description": self.get_file_images.__doc__,
                "args_schema": ArgsSchema.FileImages.value,
                "ref": self.get_file_images,
            },
            {
                "name": "get_team_projects",
                "description": self.get_team_projects.__doc__,
                "args_schema": ArgsSchema.TeamProjects.value,
                "ref": self.get_team_projects,
            },
            {
                "name": "get_project_files",
                "description": self.get_project_files.__doc__,
                "args_schema": ArgsSchema.ProjectFiles.value,
                "ref": self.get_project_files,
            },
        ]
