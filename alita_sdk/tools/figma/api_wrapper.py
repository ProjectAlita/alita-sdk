import functools
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import Dict, List, Generator, Optional, Union
from urllib.parse import urlparse, parse_qs

import requests
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, create_model, model_validator, SecretStr

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools
from ..utils.content_parser import _load_content_from_bytes_with_prompt
from .figma_client import AlitaFigmaPy

GLOBAL_LIMIT = 1000000
GLOBAL_RETAIN = ['id', 'name', 'type', 'document', 'children']
GLOBAL_REMOVE = []
GLOBAL_DEPTH_START = 1
GLOBAL_DEPTH_END = 6
DEFAULT_NUMBER_OF_THREADS = 3  # valid range for number_of_threads is 1..5
# Default prompts for image analysis and summarization reused across toolkit and wrapper
DEFAULT_FIGMA_IMAGES_PROMPT: Dict[str, str] = {
    "prompt": (
        "You are an AI model for image analysis. For each image, first identify its type "
        "(diagram, screenshot, photograph, illustration/drawing, text-centric, or mixed), "
        "then describe all visible elements and extract any readable text. For diagrams, "
        "capture titles, labels, legends, axes, and all numerical values, and summarize key "
        "patterns or trends. For screenshots, describe the interface or page, key UI elements, "
        "and any conversations or messages with participants and timestamps if visible. For "
        "photos and illustrations, describe the setting, main objects/people, their actions, "
        "style, colors, and composition. Be precise and thorough; when something is unclear or "
        "illegible, state that explicitly instead of guessing."
    )
}
DEFAULT_FIGMA_SUMMARY_PROMPT: Dict[str, str] = {
    "prompt": (
        "You are summarizing a visual design document exported from Figma as a sequence of images and text. "
        "Provide a clear, concise overview of the main purpose, key elements, and notable changes or variations in the screens. "
        "Infer a likely user flow or sequence of steps across the screens, calling out entry points, decisions, and outcomes. "
        "Explain how this design could impact planning, development, testing, and review activities in a typical software lifecycle. "
        "Return the result as structured Markdown with headings and bullet lists so it can be reused in SDLC documentation."
    )
}
EXTRA_PARAMS = (
    Optional[Dict[str, Union[str, int, List, None]]],
    Field(
        description=(
            "Optional output controls: `limit` (max characters, always applied), `regexp` (regex cleanup on text), "
            "`fields_retain`/`fields_remove` (which keys to keep or drop), and `depth_start`/`depth_end` (depth range "
            "where that key filtering is applied). Field/depth filters are only used when the serialized JSON result "
            "exceeds `limit` to reduce its size."
        ),
        default={
            "limit": GLOBAL_LIMIT, "regexp": None,
            "fields_retain": GLOBAL_RETAIN, "fields_remove": GLOBAL_REMOVE,
            "depth_start": GLOBAL_DEPTH_START, "depth_end": GLOBAL_DEPTH_END,
        },
        examples=[
            {
                "limit": "1000",
                "regexp": r'("strokes"|"fills")\s*:\s*("[^"]*"|[^\s,}\[]+)\s*(?=,|\}|\n)',
                "fields_retain": GLOBAL_RETAIN, "fields_remove": GLOBAL_REMOVE,
                "depth_start": GLOBAL_DEPTH_START, "depth_end": GLOBAL_DEPTH_END,
            }
        ],
    ),
)


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
        extra_params=EXTRA_PARAMS,
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
            Field(description="Sets to 'paths' to export vector data", default=None),
        ),
        version=(
            Optional[str],
            Field(description="Sets version of file", default=None),
        ),
        extra_params=EXTRA_PARAMS,
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
        extra_params=EXTRA_PARAMS,
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
                description="Positioning information of the comment (Vector, FrameOffset, Region, FrameOffsetRegion)",
                default=None,
            ),
        ),
        extra_params=EXTRA_PARAMS,
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
            Optional[str],
            Field(
                description="Specifies id of file images separated by comma",
                examples=["8:6,1:7"],
                default="0:0",
            ),
        ),
        scale=(
            Optional[str],
            Field(description="A number between 0.01 and 4, the image scaling factor", default=None),
        ),
        format=(
            Optional[str],
            Field(
                description="A string enum for the image output format",
                examples=["jpg", "png", "svg", "pdf"],
                default=None,
            ),
        ),
        version=(
            Optional[str],
            Field(description="A specific version ID to use", default=None),
        ),
        extra_params=EXTRA_PARAMS,
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
        extra_params=EXTRA_PARAMS,
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
        extra_params=EXTRA_PARAMS,
    )
    FileSummary = create_model(
        "FileSummary",
        url=(
            Optional[str],
            Field(
                description=(
                    "Full Figma URL with file key and optional node-id. "
                    "Example: 'https://www.figma.com/file/<FILE_KEY>/...?...node-id=<NODE_ID>'. "
                    "If provided and valid, URL is used and file_key/node_ids arguments are ignored."
                ),
                default=None,
            ),
        ),
        file_key=(
            Optional[str],
            Field(
                description=(
                    "Explicit file key used only when URL is not provided."
                ),
                default=None,
                examples=["Fp24FuzPwH0L74ODSrCnQo"],
            ),
        ),
        include_node_ids=(
            Optional[str],
            Field(
                description=(
                    "Optional comma-separated top-level node ids (pages) to include when URL has no node-id and URL is not set. "
                    "Example: '8:6,1:7'."
                ),
                default=None,
                examples=["8:6,1:7"],
            ),
        ),
        exclude_node_ids=(
            Optional[str],
            Field(
                description=(
                    "Optional comma-separated top-level node ids (pages) to exclude when URL has no node-id and URL is not set. "
                    "Applied only when include_node_ids is not provided."
                ),
                default=None,
                examples=["8:6,1:7"],
            ),
        ),
    )


class FigmaApiWrapper(NonCodeIndexerToolkit):
    token: Optional[SecretStr] = Field(default=None)
    oauth2: Optional[SecretStr] = Field(default=None)
    global_limit: Optional[int] = Field(default=GLOBAL_LIMIT)
    global_regexp: Optional[str] = Field(default=None)
    global_fields_retain: Optional[List[str]] = GLOBAL_RETAIN
    global_fields_remove: Optional[List[str]] = GLOBAL_REMOVE
    global_depth_start: Optional[int] = Field(default=GLOBAL_DEPTH_START)
    global_depth_end: Optional[int] = Field(default=GLOBAL_DEPTH_END)
    # prompt-related configuration, populated from FigmaToolkit.toolkit_config_schema
    apply_images_prompt: Optional[bool] = Field(default=True)
    images_prompt: Optional[Dict[str, str]] = Field(default=DEFAULT_FIGMA_IMAGES_PROMPT)
    apply_summary_prompt: Optional[bool] = Field(default=True)
    summary_prompt: Optional[Dict[str, str]] = Field(default=DEFAULT_FIGMA_SUMMARY_PROMPT)
    # concurrency configuration, populated from toolkit config like images_prompt
    number_of_threads: Optional[int] = Field(default=DEFAULT_NUMBER_OF_THREADS, ge=1, le=5)
    _client: Optional[AlitaFigmaPy] = PrivateAttr()

    def _parse_figma_url(self, url: str) -> tuple[str, Optional[List[str]]]:
        """Parse and validate a Figma URL.

        Returns a tuple of (file_key, node_ids_from_url or None).
        Raises ToolException with a clear message if the URL is malformed.
        """
        try:
            parsed = urlparse(url)

            # Basic structural validation
            if not parsed.scheme or not parsed.netloc:
                raise ToolException(
                    "Figma URL must include protocol and host (e.g., https://www.figma.com/file/...). "
                    f"Got: {url}"
                )

            path_parts = parsed.path.strip('/').split('/') if parsed.path else []

            # Supported URL patterns:
            #  - /file/<file_key>/...
            #  - /design/<file_key>/... (older / embedded variant)
            if len(path_parts) < 2 or path_parts[0] not in {"file", "design"}:
                raise ToolException(
                    "Unsupported Figma URL format. Expected path like '/file/<FILE_KEY>/...' or "
                    "'/design/<FILE_KEY>/...'. "
                    f"Got path: '{parsed.path}' from URL: {url}"
                )

            file_key = path_parts[1]
            if not file_key:
                raise ToolException(
                    "Figma URL is missing the file key segment after '/file/' or '/design/'. "
                    f"Got path: '{parsed.path}' from URL: {url}"
                )

            # Optional node-id is passed via query parameter
            query_params = parse_qs(parsed.query or "")
            node_ids_from_url = query_params.get("node-id", []) or None

            return file_key, node_ids_from_url

        except ToolException:
            # Re-raise our own clear ToolException as-is
            raise
        except Exception as e:
            # Catch any unexpected parsing issues and wrap them clearly
            raise ToolException(
                "Unexpected error while processing Figma URL. "
                "Please provide a valid Figma file or page URL, for example: "
                "'https://www.figma.com/file/<FILE_KEY>/...'? "
                f"Original error: {e}"
            )

    def _base_loader(
            self,
            url: Optional[str] = None,
            file_keys_include: Optional[List[str]] = None,
            file_keys_exclude: Optional[List[str]] = None,
            node_ids_include: Optional[List[str]] = None,
            node_ids_exclude: Optional[List[str]] = None,
            node_types_include: Optional[List[str]] = None,
            node_types_exclude: Optional[List[str]] = None,
            **kwargs
    ) -> Generator[Document, None, None]:
        if url:
            file_key, node_ids_from_url = self._parse_figma_url(url)
            # Override include params based on URL
            file_keys_include = [file_key]
            if node_ids_from_url and not node_ids_include:
                node_ids_include = node_ids_from_url
        
        # If both include and exclude are provided, use only include
        if file_keys_include:
            self._log_tool_event(f"Loading files: {file_keys_include}")
            for file_key in file_keys_include:
                self._log_tool_event(f"Loading file `{file_key}`")
                file = self._client.get_file(file_key, geometry='depth=1') # fetch only top-level structure (only pages without inner components)
                if not file:
                    raise ToolException(f"Unexpected error while retrieving file {file_key}. Please try specifying the node-id of an inner page.")
                metadata = {
                    'id': file_key,
                    'file_key': file_key,
                    'name': file.name,
                    'updated_on': file.last_modified,
                    'figma_pages_include': node_ids_include or [],
                    'figma_pages_exclude': node_ids_exclude or [],
                    'figma_nodes_include': node_types_include or [],
                    'figma_nodes_exclude': node_types_exclude or [],
                }
                yield Document(page_content=json.dumps(metadata), metadata=metadata)
        elif file_keys_exclude or node_ids_exclude:
            raise ValueError("Excludes without parent (file_keys_include) do not make sense.")
        else:
            raise ValueError("You must provide file_keys_include or a URL.")

    def has_image_representation(self, node):
        node_type = node.get('type', '').lower()
        default_images_types = [
            'image', 'canvas', 'frame', 'vector', 'table', 'slice', 'sticky', 'shape_with_text', 'connector'
        ]
        # filter nodes of type which has image representation
        # or rectangles with image as background
        if (node_type in default_images_types
                or (node_type == 'rectangle' and 'fills' in node and any(
                    fill.get('type') == 'IMAGE' for fill in node['fills'] if isinstance(fill, dict)))):
            return True
        return False

    def get_texts_recursive(self, node):
        texts = []
        node_type = node.get('type', '').lower()
        if node_type == 'text':
            texts.append(node.get('characters', ''))
        if 'children' in node:
            for child in node['children']:
                texts.extend(self.get_texts_recursive(child))
        return texts
    
    def _load_pages(self, document: Document):
        file_key = document.metadata.get('id', '')
        node_ids_include = document.metadata.pop('figma_pages_include', [])
        node_ids_exclude = document.metadata.pop('figma_pages_exclude', [])
        self._log_tool_event(f"Included pages: {node_ids_include}. Excluded pages: {node_ids_exclude}.")
        if node_ids_include:
            # try to fetch only specified pages/nodes in one request
            file = self._get_file_nodes(file_key,','.join(node_ids_include)) # attempt to fetch only specified pages/nodes in one request
            if file:
                return [
                    node["document"]
                    for node in (file.get("nodes") or {}).values()
                    if node is not None and "document" in node
                ]
        else:
            # 
            file = self._client.get_file(file_key)
            if file:
                figma_pages = file.document.get('children', [])
                return [node for node in figma_pages if ('id' in node and node['id'].replace(':', '-') not in node_ids_exclude)]
        # fallback to loading all pages and filtering them one by one
        file = self._client.get_file(file_key, geometry='depth=1')
        if not file:
            raise ToolException(
                f"Unexpected error while retrieving file {file_key}. Please try specifying the node-id of an inner page.")
        figma_pages_raw = file.document.get('children', [])
        # extract pages one by one
        if node_ids_include:
            return [self._get_file_nodes(file_key, node_id) for node_id in node_ids_include]
        else:
            # return [self._get_file_nodes(file_key, page["id"]) for page in figma_pages_raw if ('id' in page and page['id'].replace(':', '-') not in node_ids_exclude)]
            result = []
            for page in figma_pages_raw:
                if 'id' in page and page['id'].replace(':', '-') not in node_ids_exclude:
                    page_res = self._get_file_nodes(file_key, page["id"]).get('nodes', {}).get(page["id"], {}).get("document", {})
                    result.append(page_res)
            return result

    def _process_single_image(
            self,
            file_key: str,
            document: Document,
            node_id: str,
            image_url: str,
            prompt: str,
    ) -> Optional[Document]:
        """Download and process a single Figma image node.
        This helper is used by `_process_document` (optionally in parallel via threads).
        """
        if not image_url:
            logging.warning(f"Image URL not found for node_id {node_id} in file {file_key}. Skipping.")
            return None

        logging.info(f"File {file_key}: downloading image node {node_id}.")

        try:
            response = requests.get(image_url)
        except Exception as exc:
            logging.warning(f"Failed to download image for node {node_id} in file {file_key}: {exc}")
            return None

        if response.status_code != 200:
            logging.warning(
                f"Unexpected status code {response.status_code} when downloading image "
                f"for node {node_id} in file {file_key}."
            )
            return None

        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type.lower():
            logging.warning(f"Received HTML instead of image content for node {node_id} in file {file_key}.")
            return None

        extension = (f".{content_type.split('/')[-1]}" if content_type.startswith('image') else '.txt')
        logging.info(f"File {file_key}: processing image node {node_id}.")
        page_content = _load_content_from_bytes_with_prompt(
            file_content=response.content,
            extension=extension,
            llm=self.llm,
            prompt=prompt,
        )

        logging.info(f"File {file_key}: finished image node {node_id}.")

        return Document(
            page_content=page_content,
            metadata={
                'id': node_id,
                'updated_on': document.metadata.get('updated_on', ''),
                'file_key': file_key,
                'node_id': node_id,
                'image_url': image_url,
                'type': 'image',
            },
        )

    def _process_document(
        self,
        document: Document,
        prompt: str = "",
    ) -> Generator[Document, None, None]:
        file_key = document.metadata.get('id', '')
        self._log_tool_event(f"Loading details (images) for `{file_key}`")
        figma_pages = self._load_pages(document)
        node_types_include = [t.strip().lower() for t in document.metadata.pop('figma_nodes_include', [])]
        node_types_exclude = [t.strip().lower() for t in document.metadata.pop('figma_nodes_exclude', [])]

        image_nodes = []
        text_nodes = {}
        for page in figma_pages:
            for node in page.get('children', []):
                # filter by node_type if specified any include or exclude
                node_type = node.get('type', '').lower()
                include = node_types_include and node_type in node_types_include
                exclude = node_types_exclude and node_type not in node_types_exclude
                no_filter = not node_types_include and not node_types_exclude

                if include or exclude or no_filter:
                    node_id = node.get('id')
                    if node_id:
                        if self.has_image_representation(node):
                            image_nodes.append(node['id'])
                        else:
                            text_nodes[node['id']] = self.get_texts_recursive(node)
        total_nodes = len(image_nodes) + len(text_nodes)
        # mutable counter so it can be updated from helper calls (even when used in threads)
        counted_nodes_ref: Dict[str, int] = {"value": 0}

        # Resolve number_of_threads from class field, falling back to DEFAULT_NUMBER_OF_THREADS
        threads_cfg = getattr(self, "number_of_threads", DEFAULT_NUMBER_OF_THREADS)
        if isinstance(threads_cfg, int) and 1 <= threads_cfg <= 5:
            number_of_threads = threads_cfg
        else:
            number_of_threads = DEFAULT_NUMBER_OF_THREADS

        # --- Process image nodes (potential bottleneck) with optional threading ---
        if image_nodes:
            file_images = self._client.get_file_images(file_key, image_nodes)
            images = self._client.get_file_images(file_key, image_nodes).images or {} if file_images else {}
            total_images = len(images)
            if total_images == 0:
                logging.info(f"No images found for file {file_key}.")
            else:
                self._log_tool_event(
                    f"File {file_key}: starting download/processing for total {total_nodes} nodes"
                )

                # Decide how many workers to use (bounded by total_images and configuration).
                max_workers = number_of_threads
                max_workers = max(1, min(max_workers, total_images))

                if max_workers == 1:
                    # Keep original sequential behavior
                    for node_id, image_url in images.items():
                        doc = self._process_single_image(
                            file_key=file_key,
                            document=document,
                            node_id=node_id,
                            image_url=image_url,
                            prompt=prompt,
                        )
                        counted_nodes_ref["value"] += 1
                        if doc is not None:
                            self._log_tool_event(
                                f"File {file_key}: processing image node {node_id} "
                                f"({counted_nodes_ref['value']}/{total_nodes} in {max_workers} threads)."
                            )
                            yield doc
                else:
                    # Parallelize image download/processing with a thread pool
                    self._log_tool_event(
                        f"File {file_key}: using up to {max_workers} worker threads for image nodes."
                    )
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_node = {
                            executor.submit(
                                self._process_single_image,
                                file_key,
                                document,
                                node_id,
                                image_url,
                                prompt,
                            ): node_id
                            for node_id, image_url in images.items()
                        }
                        for future in as_completed(future_to_node):
                            node_id = future_to_node[future]
                            try:
                                doc = future.result()
                            except Exception as exc:  # safeguard
                                logging.warning(
                                    f"File {file_key}: unexpected error while processing image node {node_id}: {exc}"
                                )
                                continue
                            finally:
                                # Count every attempted node, even if it failed or produced no doc,
                                # so that progress always reaches total_nodes.
                                counted_nodes_ref["value"] += 1

                            if doc is not None:
                                self._log_tool_event(
                                    f"File {file_key}: processing image node {node_id} "
                                    f"({counted_nodes_ref['value']}/{total_nodes} in {max_workers} threads)."
                                )
                                yield doc

                logging.info(
                    f"File {file_key}: completed processing of {total_images} image nodes."
                )

        # --- Process text nodes (fast) ---
        if text_nodes:
            for node_id, texts in text_nodes.items():
                counted_nodes_ref["value"] += 1
                current_index = counted_nodes_ref["value"]
                if texts:
                    self._log_tool_event(
                        f"File {file_key} : processing text node {node_id} ({current_index}/{total_nodes})."
                    )
                    yield Document(
                        page_content="\n".join(texts),
                        metadata={
                            'id': node_id,
                            'updated_on': document.metadata.get('updated_on', ''),
                            'file_key': file_key,
                            'node_id': node_id,
                            'type': 'text',
                        },
                    )

    def _index_tool_params(self):
         """Return the parameters for indexing data."""
         return {
             "url": (Optional[str], Field(
                 description=(
                     "Full Figma file or page URL to index. Must be in one of the following formats: "
                     "'https://www.figma.com/file/<FILE_KEY>/...' or 'https://www.figma.com/design/<FILE_KEY>/...'. "
                     "If present, the 'node-id' query parameter (e.g. '?node-id=<PAGE_ID>') will be used to limit "
                     "indexing to that page or node. When this URL is provided, it overrides 'file_keys_include' ('node_ids_include')."
                 ),
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
                 default=None)),
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
                raise ToolException(msg)

        try:
            if token:
                cls._client = AlitaFigmaPy(token=token, oauth2=False)
                logging.info("Authenticated with Figma token")
            elif oauth2:
                cls._client = AlitaFigmaPy(token=oauth2, oauth2=True)
                logging.info("Authenticated with OAuth2 token")
            else:
                raise ToolException("You have to define Figma token.")
            logging.info("Successfully authenticated to Figma.")
        except Exception as e:
            msg = f"Failed to authenticate with Figma: {str(e)}"
            logging.error(msg)
            raise ToolException(msg)

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

        def process_fields(obj, fields_retain=None, fields_remove=None, depth_start=1, depth_end=2, depth=1):
            """
            Reduces a nested dictionary or list by retaining or removing specified fields at certain depths.

            - At each level, starting from `depth_start`, only fields in `fields_retain` are kept; fields in `fields_remove` are excluded unless also retained.
            - Recursion stops at `depth_end`, ignoring all fields at or beyond this depth.
            - Tracks which fields were retained and removed during processing.
            - Returns a JSON string of the reduced object, plus lists of retained and removed fields.
            """
            fields_retain = set(fields_retain or [])
            fields_remove = set(fields_remove or []) - fields_retain # fields in remove have lower priority than in retain

            retained = set()
            removed = set()

            def _process(o, d):
                if depth_end is not None and d >= depth_end:
                    return None  # Ignore keys at or beyond cut_depth
                if isinstance(o, dict):
                    result = {}
                    for k, v in o.items():
                        if k in fields_remove:
                            removed.add(k)
                            continue
                        if d >= depth_start:
                            if k in fields_retain:
                                retained.add(k)
                                result[k] = _process(v, d + 1)  # process recursively
                            else:
                                # else: skip keys not in retain/default/to_process
                                removed.add(k) # remember skipped keys
                        else:
                            # retained.add(k) # remember retained keys
                            result[k] = _process(v, d + 1)
                    return result
                elif isinstance(o, list):
                    return [_process(item, d + 1) for item in o]
                else:
                    return o

            new_obj = _process(obj, depth)
            return {
                "result": json.dumps(new_obj),
                "retained_fields": list(retained),
                "removed_fields": list(removed)
            }

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
            fields_retain = extra_params.get("fields_retain", self.global_fields_retain)
            fields_remove = extra_params.get("fields_remove", self.global_fields_remove)
            depth_start = extra_params.get("depth_start", self.global_depth_start)
            depth_end = extra_params.get("depth_end", self.global_depth_end)
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
                    raw_result = result
                    processed_result = simplified_dict(raw_result)
                    raw_str_result = json.dumps(processed_result)
                    str_result = raw_str_result
                    if regexp:
                        regexp = re.compile(regexp)
                        str_result = re.sub(regexp, "", raw_str_result)
                        str_result = fix_trailing_commas(str_result)
                    if len(str_result) > limit:
                        reduced = process_fields(raw_result, fields_retain=fields_retain, fields_remove=fields_remove, depth_start=depth_start, depth_end=depth_end)
                        note = (f"Size of the output exceeds limit {limit}. Data reducing has been applied. "
                                f"Starting from the depth_start = {depth_start} the following object fields were removed: {reduced['removed_fields']}. "
                                f"The following fields were retained: {reduced['retained_fields']}. "
                                f"Starting from depth_end = {depth_end} all fields were ignored. "
                                f"You can adjust fields_retain, fields_remove, depth_start, depth_end, limit and regexp parameters to get more precise output")
                        return f"## NOTE:\n{note}.\n## Result: {reduced['result']}"[:limit]
                    return str_result
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

    def _get_file_nodes(self, file_key: str, ids: str, **kwargs):
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
    def get_file_summary(
            self,
            url: Optional[str] = None,
            file_key: Optional[str] = None,
            include_node_ids: Optional[str] = None,
            exclude_node_ids: Optional[str] = None,
             **kwargs,
    ):
        """Summarizes a Figma file by loading pages and nodes via URL or file key.

        Configuration for image processing and summarization is taken from the toolkit
        configuration (see FigmaToolkit.toolkit_config_schema):

          - self.apply_images_prompt: if True, pass self.images_prompt to the image-processing step.
          - self.images_prompt: instruction string for how to treat image-based nodes.
          - self.apply_summary_prompt: if True and self.summary_prompt is set and an LLM is configured,
            return a single summarized string; otherwise return the raw list of node documents.
          - self.summary_prompt: instruction string for LLM summarization.

        Tool arguments mirror ArgsSchema.FileSummary and control only which file/pages are loaded.
        """
        # Prepare params for _base_loader without evaluating any logic here
        node_ids_include_list = None
        node_ids_exclude_list = None

        if include_node_ids:
            node_ids_include_list = [nid.strip() for nid in include_node_ids.split(',') if nid.strip()]

        if exclude_node_ids:
            node_ids_exclude_list = [nid.strip() for nid in exclude_node_ids.split(',') if nid.strip()]

        # Delegate URL and file_key handling to _base_loader
        base_docs = self._base_loader(
            url=url,
            file_keys_include=[file_key] if file_key else None,
            node_ids_include=node_ids_include_list,
            node_ids_exclude=node_ids_exclude_list,
        )

        # Read prompt-related configuration from toolkit instance (set via wrapper_payload)
        apply_images_prompt = getattr(self, "apply_images_prompt", False)
        images_prompt = getattr(self, "images_prompt", None)
        apply_summary_prompt = getattr(self, "apply_summary_prompt", True)
        summary_prompt = getattr(self, "summary_prompt", None)

        # Decide whether to apply images_prompt. Expect dict with 'prompt'.
        if (
            apply_images_prompt
            and isinstance(images_prompt, dict)
            and isinstance(images_prompt.get("prompt"), str)
            and images_prompt["prompt"].strip()
        ):
            images_prompt_str = images_prompt["prompt"].strip()
        else:
            images_prompt_str = ""

        results: List[Dict] = []
        for base_doc in base_docs:
            for dep in self._process_document(
                base_doc,
                images_prompt_str,
            ):
                 results.append({
                     "page_content": dep.page_content,
                     "metadata": dep.metadata,
                 })

        # Decide whether to apply summary_prompt
        has_summary_prompt = bool(
            isinstance(summary_prompt, dict)
            and isinstance(summary_prompt.get("prompt"), str)
            and summary_prompt["prompt"].strip()
        )
        if not apply_summary_prompt or not has_summary_prompt:
            # Return raw docs when summary is disabled or no prompt provided
            self._log_tool_event("Summary prompt not provided: returning raw documents.")
            return results

        # If summary_prompt is enabled, generate an LLM-based summary over the loaded docs
        try:
            # Build a structured, ordered view of images and texts to help the LLM infer flows.
            blocks = []
            for item in results:
                metadata = item.get("metadata", {}) or {}
                node_type = str(metadata.get("type", "")).lower()
                node_id = metadata.get("node_id") or metadata.get("id", "")
                page_content = str(item.get("page_content", "")).strip()

                if not page_content:
                    continue

                if node_type == "image":
                    image_url = metadata.get("image_url", "")
                    header = f"Image ({node_id}), {image_url}".strip().rstrip(',')
                    body = page_content
                else:
                    header = f"Text ({node_id})".strip()
                    body = page_content

                block = f"{header}\n{body}\n--------------------"
                blocks.append(block)

            full_content = "\n".join(blocks) if blocks else "(no content)"
            self._log_tool_event("Invoking LLM for Figma file summary.")

            if not getattr(self, "llm", None):
                raise RuntimeError("LLM is not configured for this toolkit; cannot apply summary_prompt.")

            # Use the 'prompt' field from the summary_prompt dict as the instruction block
            summary_prompt_text = summary_prompt["prompt"].strip()
            prompt_text = f"{summary_prompt_text}\n\nCONTENT BEGIN\n{full_content}\nCONTENT END"
            llm_response = self.llm.invoke(prompt_text) if hasattr(self.llm, "invoke") else self.llm(prompt_text)

            if hasattr(llm_response, "content"):
                summary_text = str(llm_response.content)
            else:
                summary_text = str(llm_response)

            self._log_tool_event("Successfully generated LLM-based file summary.")
            return summary_text
        except Exception as e:
            logging.warning(f"Failed to apply summary_prompt in get_file_summary: {e}")
            self._log_tool_event("Falling back to raw documents due to summary_prompt failure.")
            return results

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
        ids: Optional[str] = "0:0",
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
                "name": "get_file_summary",
                "description": self.get_file_summary.__doc__,
                "args_schema": ArgsSchema.FileSummary.value,
                "ref": self.get_file_summary,
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
