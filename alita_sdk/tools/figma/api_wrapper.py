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


# User-friendly error messages for common Figma API errors
FIGMA_ERROR_MESSAGES = {
    429: "Figma API rate limit exceeded. Please wait a moment and try again.",
    403: "Access denied. Please check your Figma API token has access to this file.",
    404: "File or node not found. Please verify the file key or node ID is correct.",
    401: "Authentication failed. Please check your Figma API token is valid.",
    500: "Figma server error. Please try again later.",
    503: "Figma service temporarily unavailable. Please try again later.",
}


def _handle_figma_error(e: ToolException) -> str:
    """
    Convert a ToolException from Figma API into a user-friendly error message.
    Returns a clean error string without technical details.
    """
    error_str = str(e)

    # Extract status code from error message
    for code, message in FIGMA_ERROR_MESSAGES.items():
        if f"error {code}:" in error_str.lower() or f"status\": {code}" in error_str:
            return message

    # Handle other common patterns
    if "rate limit" in error_str.lower():
        return FIGMA_ERROR_MESSAGES[429]
    if "not found" in error_str.lower():
        return FIGMA_ERROR_MESSAGES[404]
    if "forbidden" in error_str.lower() or "access denied" in error_str.lower():
        return FIGMA_ERROR_MESSAGES[403]
    if "unauthorized" in error_str.lower():
        return FIGMA_ERROR_MESSAGES[401]

    # Fallback: return a generic but clean message
    return f"Figma API request failed. Please try again or check your file key and permissions."

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools
from ..utils.content_parser import _load_content_from_bytes_with_prompt
from .figma_client import AlitaFigmaPy
from .toon_tools import (
    TOONSerializer,
    process_page_to_toon_data,
    process_frame_to_toon_data,
    extract_text_by_role,
    extract_components,
    detect_sequences,
    group_variants,
    infer_cta_destination,
    FrameDetailTOONSchema,
    AnalyzeFileSchema,
)

GLOBAL_LIMIT = 1000000
GLOBAL_RETAIN = ['id', 'name', 'type', 'document', 'children']
GLOBAL_REMOVE = []
GLOBAL_DEPTH_START = 1
GLOBAL_DEPTH_END = 6
DEFAULT_NUMBER_OF_THREADS = 5  # valid range for number_of_threads is 1..5
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
            number_of_threads: Optional[int] = None,
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
                # propagate per-call number_of_threads override via metadata so _process_document can respect it
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
                if isinstance(number_of_threads, int) and 1 <= number_of_threads <= 5:
                    metadata['number_of_threads_override'] = number_of_threads
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

        # Resolve number_of_threads override from document metadata, falling back to class field
        override_threads = document.metadata.get('number_of_threads_override')
        if isinstance(override_threads, int) and 1 <= override_threads <= 5:
            number_of_threads = override_threads
        else:
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
             'number_of_threads': (Optional[int], Field(
                 description=(
                     "Optional override for the number of worker threads used when indexing Figma images. "
                     f"Valid values are from 1 to 5. Default is {DEFAULT_NUMBER_OF_THREADS}."
                 ),
                 default=DEFAULT_NUMBER_OF_THREADS,
                 ge=1,
                 le=5,
             )),
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

    # -------------------------------------------------------------------------
    # TOON Format Tools (Token-Optimized Output)
    # -------------------------------------------------------------------------

    def get_file_structure_toon(
        self,
        url: Optional[str] = None,
        file_key: Optional[str] = None,
        include_pages: Optional[str] = None,
        exclude_pages: Optional[str] = None,
        max_frames: int = 50,
        **kwargs,
    ) -> str:
        """
        Get file structure in TOON format - optimized for LLM token consumption.

        Returns a compact, human-readable format with:
        - Page and frame hierarchy
        - Text content categorized (headings, labels, buttons, body, errors)
        - Component usage
        - Inferred screen types and states
        - Flow analysis (sequences, variants, CTA destinations)

        TOON format uses ~70% fewer tokens than JSON for the same data.

        Use this tool when you need to:
        - Understand overall file structure quickly
        - Generate user journey documentation
        - Analyze screen flows and navigation
        - Identify UI patterns and components
        """
        self._log_tool_event("Getting file structure in TOON format")

        # Parse URL or use file_key
        if url:
            file_key, node_ids_from_url = self._parse_figma_url(url)
            if node_ids_from_url and not include_pages:
                include_pages = ','.join(node_ids_from_url)

        if not file_key:
            raise ToolException("Either url or file_key must be provided")

        # Parse include/exclude pages
        include_ids = [p.strip() for p in include_pages.split(',')] if include_pages else None
        exclude_ids = [p.strip() for p in exclude_pages.split(',')] if exclude_pages else None

        # Get file structure (shallow fetch - only top-level pages, not full content)
        # This avoids "Request too large" errors for big files
        self._log_tool_event(f"Fetching file structure for {file_key}")
        file_data = self._client.get_file(file_key, geometry='depth=1')

        if not file_data:
            raise ToolException(f"Failed to retrieve file {file_key}")

        # Process pages
        pages_data = []
        all_pages = file_data.document.get('children', [])

        for page_node in all_pages:
            page_id = page_node.get('id', '')

            # Apply page filters
            if include_ids and page_id not in include_ids and page_id.replace(':', '-') not in include_ids:
                continue
            if exclude_ids and not include_ids:
                if page_id in exclude_ids or page_id.replace(':', '-') in exclude_ids:
                    continue

            self._log_tool_event(f"Processing page: {page_node.get('name', 'Untitled')}")

            # Fetch full page content individually (avoids large single request)
            try:
                page_full = self._get_file_nodes(file_key, page_id)
                if page_full:
                    page_content = page_full.get('nodes', {}).get(page_id, {}).get('document', page_node)
                else:
                    page_content = page_node
            except Exception as e:
                self._log_tool_event(f"Warning: Could not fetch full page content for {page_id}: {e}")
                page_content = page_node

            page_data = process_page_to_toon_data(page_content)

            # Limit frames per page
            if len(page_data['frames']) > max_frames:
                page_data['frames'] = page_data['frames'][:max_frames]
                page_data['truncated'] = True

            pages_data.append(page_data)

        # Build file data structure
        toon_data = {
            'name': file_data.name,
            'key': file_key,
            'pages': pages_data,
        }

        # Serialize to TOON format
        serializer = TOONSerializer()
        result = serializer.serialize_file(toon_data)

        self._log_tool_event("File structure extracted in TOON format")
        return result

    def get_page_flows_toon(
        self,
        url: Optional[str] = None,
        file_key: Optional[str] = None,
        page_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Analyze a single page for user flows in TOON format.

        Returns detailed flow analysis:
        - Frame sequence detection (from naming: 01_, Step 1, etc.)
        - Screen variant grouping (Login, Login_Error, Login_Loading)
        - CTA/button destination mapping
        - Spatial ordering hints

        Use this for in-depth flow analysis of a specific page.
        Requires a PAGE ID (not a frame ID). Use get_file_structure_toon to find page IDs.
        """
        self._log_tool_event("Analyzing page flows in TOON format")

        # Parse URL
        if url:
            file_key, node_ids_from_url = self._parse_figma_url(url)
            if node_ids_from_url:
                page_id = node_ids_from_url[0]

        if not file_key:
            raise ToolException("Either url or file_key must be provided")
        if not page_id:
            raise ToolException("page_id must be provided (or include node-id in URL)")

        # Fetch node content
        self._log_tool_event(f"Fetching node {page_id} from file {file_key}")
        node_full = self._get_file_nodes(file_key, page_id)

        if not node_full:
            raise ToolException(f"Failed to retrieve node {page_id}")

        node_content = node_full.get('nodes', {}).get(page_id, {}).get('document', {})
        if not node_content:
            raise ToolException(f"Node {page_id} has no content")

        # Check if this is a page (CANVAS) or a frame
        node_type = node_content.get('type', '').upper()
        if node_type != 'CANVAS':
            # This is a frame, not a page - provide helpful error
            raise ToolException(
                f"Node {page_id} is a {node_type}, not a PAGE. "
                f"This tool requires a page ID. Use get_file_structure_toon first to find page IDs "
                f"(look for PAGE: ... #<page_id>)"
            )

        page_content = node_content

        # Process page
        page_data = process_page_to_toon_data(page_content)
        frames = page_data.get('frames', [])

        # Build detailed flow analysis
        lines = []
        lines.append(f"PAGE: {page_data.get('name', 'Untitled')} [id:{page_id}]")
        lines.append(f"  frames: {len(frames)}")
        lines.append("")

        # Sequence analysis
        sequences = detect_sequences(frames)
        if sequences:
            lines.append("SEQUENCES (by naming):")
            for seq in sequences:
                lines.append(f"  {' > '.join(seq)}")
            lines.append("")

        # Variant analysis
        variants = group_variants(frames)
        if variants:
            lines.append("VARIANTS (grouped screens):")
            for base, variant_list in variants.items():
                lines.append(f"  {base}:")
                for v in variant_list:
                    v_name = v.get('name', '')
                    v_id = v.get('id', '')
                    state = next((f.get('state', 'default') for f in frames if f.get('name') == v_name), 'default')
                    lines.append(f"    - {v_name} [{state}] #{v_id}")
            lines.append("")

        # CTA mapping
        lines.append("CTA DESTINATIONS:")
        cta_map = {}
        for frame in frames:
            frame_name = frame.get('name', '')
            for btn in frame.get('buttons', []):
                dest = infer_cta_destination(btn)
                if dest not in cta_map:
                    cta_map[dest] = []
                cta_map[dest].append(f'"{btn}" in {frame_name}')

        for dest, ctas in cta_map.items():
            lines.append(f"  > {dest}:")
            for cta in ctas[:5]:  # Limit per destination
                lines.append(f"      {cta}")
        lines.append("")

        # Spatial ordering
        lines.append("SPATIAL ORDER (canvas position):")
        sorted_frames = sorted(frames, key=lambda f: (f['position']['y'], f['position']['x']))
        for i, frame in enumerate(sorted_frames[:20], 1):
            pos = frame.get('position', {})
            lines.append(f"  {i}. {frame.get('name', '')} [{int(pos.get('x', 0))},{int(pos.get('y', 0))}]")

        # Frame details
        lines.append("")
        lines.append("FRAME DETAILS:")

        serializer = TOONSerializer()
        for frame in frames[:30]:  # Limit frames
            frame_lines = serializer.serialize_frame(frame, level=1)
            lines.extend(frame_lines)

        self._log_tool_event("Page flow analysis complete")
        return '\n'.join(lines)

    def get_frame_detail_toon(
        self,
        file_key: str,
        frame_ids: str,
        **kwargs,
    ) -> str:
        """
        Get detailed information for specific frames in TOON format.

        Returns per-frame:
        - All text content (headings, labels, buttons, body, errors)
        - Component hierarchy
        - Inferred screen type and state
        - Position and size

        Use this to drill down into specific screens identified from file structure.
        """
        try:
            return self._get_frame_detail_toon_internal(file_key=file_key, frame_ids=frame_ids, **kwargs)
        except ToolException as e:
            raise ToolException(_handle_figma_error(e))

    def _get_frame_detail_toon_internal(
        self,
        file_key: str,
        frame_ids: str,
        **kwargs,
    ) -> str:
        """Internal implementation of get_frame_detail_toon without error handling wrapper."""
        self._log_tool_event("Getting frame details in TOON format")

        ids_list = [fid.strip() for fid in frame_ids.split(',') if fid.strip()]
        if not ids_list:
            raise ToolException("frame_ids must contain at least one frame ID")

        # Fetch frames
        self._log_tool_event(f"Fetching {len(ids_list)} frames from file {file_key}")
        nodes_data = self._get_file_nodes(file_key, ','.join(ids_list))

        if not nodes_data:
            raise ToolException(f"Failed to retrieve frames from file {file_key}")

        # Process each frame
        lines = [f"FRAMES [{len(ids_list)} requested]", ""]

        serializer = TOONSerializer()

        for frame_id in ids_list:
            node_data = nodes_data.get('nodes', {}).get(frame_id, {})
            frame_node = node_data.get('document', {})

            if not frame_node:
                lines.append(f"FRAME: {frame_id} [NOT FOUND]")
                lines.append("")
                continue

            frame_data = process_frame_to_toon_data(frame_node)
            frame_lines = serializer.serialize_frame(frame_data, level=0)
            lines.extend(frame_lines)

            # Add extra details for individual frames
            lines.append(f"  ID: {frame_id}")

            # Component breakdown
            components = frame_data.get('components', [])
            if components:
                # Count component usage
                from collections import Counter
                comp_counts = Counter(components)
                lines.append(f"  COMPONENT_COUNTS:")
                for comp, count in comp_counts.most_common(10):
                    lines.append(f"    {comp}: {count}")

            lines.append("")

        self._log_tool_event("Frame details extracted")
        return '\n'.join(lines)

    def analyze_file(
        self,
        url: Optional[str] = None,
        file_key: Optional[str] = None,
        node_id: Optional[str] = None,
        include_pages: Optional[str] = None,
        exclude_pages: Optional[str] = None,
        max_frames: int = 50,
        **kwargs,
    ) -> str:
        """
        Comprehensive Figma file analyzer with LLM-powered insights.

        Returns detailed analysis including:
        - File/page/frame structure with all content (text, buttons, components)
        - LLM-powered screen explanations with visual insights (using frame images)
        - LLM-powered user flow analysis identifying key user journeys
        - Design insights (patterns, gaps, recommendations)

        Drill-Down:
          - No node_id: Analyzes entire file (respecting include/exclude pages)
          - node_id=page_id: Focuses on specific page
          - node_id=frame_id: Returns detailed frame analysis

        For targeted analysis of specific frames (2-3 frames), use get_frame_detail_toon instead.
        """
        try:
            return self._analyze_file_internal(
                url=url,
                file_key=file_key,
                node_id=node_id,
                include_pages=include_pages,
                exclude_pages=exclude_pages,
                max_frames=max_frames,
                **kwargs,
            )
        except ToolException as e:
            raise ToolException(_handle_figma_error(e))

    def _analyze_file_internal(
        self,
        url: Optional[str] = None,
        file_key: Optional[str] = None,
        node_id: Optional[str] = None,
        include_pages: Optional[str] = None,
        exclude_pages: Optional[str] = None,
        max_frames: int = 50,
        **kwargs,
    ) -> str:
        """Internal implementation of analyze_file without error handling wrapper."""
        # Always use maximum detail level and LLM analysis
        detail_level = 3
        llm_analysis = 'detailed' if self.llm else 'none'
        self._log_tool_event(f"Getting file in TOON format (detail_level={detail_level}, llm_analysis={llm_analysis})")

        # Parse URL if provided
        if url:
            file_key, node_ids_from_url = self._parse_figma_url(url)
            if node_ids_from_url and not node_id:
                node_id = node_ids_from_url[0]

        if not file_key:
            raise ToolException("Either url or file_key must be provided")

        # Convert node_id from URL format (hyphen) to API format (colon)
        if node_id:
            node_id = node_id.replace('-', ':')

        # Check if node_id is a frame or page (for drill-down)
        node_id_is_page = False
        if node_id:
            try:
                nodes_data = self._get_file_nodes(file_key, node_id)
                if nodes_data:
                    node_info = nodes_data.get('nodes', {}).get(node_id, {})
                    node_doc = node_info.get('document', {})
                    node_type = node_doc.get('type', '').upper()

                    if node_type == 'FRAME':
                        # It's a frame - use frame detail tool (internal to avoid double-wrapping)
                        return self._get_frame_detail_toon_internal(file_key=file_key, frame_ids=node_id)
                    elif node_type == 'CANVAS':
                        # It's a page - we'll filter to this page
                        node_id_is_page = True
            except Exception:
                pass  # Fall through to page/file analysis

        # Get file structure
        file_data = self._client.get_file(file_key, geometry='depth=1')
        if not file_data:
            raise ToolException(f"Failed to retrieve file {file_key}")

        # Determine which pages to process
        # Check if document exists and has the expected structure
        if not hasattr(file_data, 'document') or file_data.document is None:
            self._log_tool_event(f"Warning: file_data has no document attribute. Type: {type(file_data)}")
            all_pages = []
        else:
            all_pages = file_data.document.get('children', [])
        self._log_tool_event(f"File has {len(all_pages)} pages, node_id={node_id}, node_id_is_page={node_id_is_page}")

        # Only filter by node_id if it's confirmed to be a page ID
        if node_id and node_id_is_page:
            include_pages = node_id

        include_ids = [p.strip() for p in include_pages.split(',')] if include_pages else None
        exclude_ids = [p.strip() for p in exclude_pages.split(',')] if exclude_pages else None

        pages_to_process = []
        for page_node in all_pages:
            page_id = page_node.get('id', '')
            if include_ids and page_id not in include_ids:
                continue
            if exclude_ids and page_id in exclude_ids:
                continue
            pages_to_process.append(page_node)

        # Build output based on detail level
        lines = [f"FILE: {file_data.name} [key:{file_key}]"]
        serializer = TOONSerializer()

        all_frames_for_flows = []  # Collect frames for flow analysis at Level 2+

        if not pages_to_process:
            if not all_pages:
                lines.append("  [No pages found in file - file may be empty or access restricted]")
            else:
                lines.append(f"  [All {len(all_pages)} pages filtered out by include/exclude settings]")
            self._log_tool_event(f"No pages to process. all_pages={len(all_pages)}, include_ids={include_ids}, exclude_ids={exclude_ids}")

        self._log_tool_event(f"Processing {len(pages_to_process)} pages at detail_level={detail_level}")

        for page_node in pages_to_process:
            page_id = page_node.get('id', '')
            page_name = page_node.get('name', 'Untitled')

            if detail_level == 1:
                # Level 1: Structure only - just hierarchy with IDs
                lines.append(f"  PAGE: {page_name} #{page_id}")
                frames = page_node.get('children', [])[:max_frames]
                for frame in frames:
                    if frame.get('type', '').upper() == 'FRAME':
                        frame_id = frame.get('id', '')
                        frame_name = frame.get('name', 'Untitled')
                        lines.append(f"    FRAME: {frame_name} #{frame_id}")
            else:
                # Level 2+: Need full page content - fetch via nodes API
                page_fetch_error = None
                try:
                    nodes_data = self._get_file_nodes(file_key, page_id)
                    if nodes_data:
                        full_page_node = nodes_data.get('nodes', {}).get(page_id, {}).get('document', {})
                        if full_page_node:
                            page_node = full_page_node
                except ToolException as e:
                    page_fetch_error = _handle_figma_error(e)
                    self._log_tool_event(f"Error fetching page {page_id}: {page_fetch_error}")
                except Exception as e:
                    page_fetch_error = str(e)
                    self._log_tool_event(f"Error fetching page {page_id}: {e}")

                # Process whatever data we have (full or shallow)
                page_data = process_page_to_toon_data(page_node, max_frames=max_frames)
                frames = page_data.get('frames', [])

                # If we had an error and got no frames, show the error
                if page_fetch_error and not frames:
                    lines.append(f"  PAGE: {page_name} #{page_id}")
                    lines.append(f"    [Error: {page_fetch_error}]")
                    continue

                if detail_level == 2:
                    # Level 2: Standard - content via serialize_page
                    page_lines = serializer.serialize_page(page_data, level=0)
                    lines.extend(page_lines)
                else:
                    # Level 3: Detailed - content + per-frame component counts
                    lines.append(f"PAGE: {page_data.get('name', 'Untitled')} #{page_data.get('id', '')}")
                    for frame_data in frames:
                        frame_lines = serializer.serialize_frame(frame_data, level=1)
                        lines.extend(frame_lines)

                        # Add detailed component counts
                        components = frame_data.get('components', [])
                        if components:
                            from collections import Counter
                            comp_counts = Counter(components)
                            lines.append(f"    COMPONENT_COUNTS:")
                            for comp, count in comp_counts.most_common(10):
                                lines.append(f"      {comp}: {count}")

                # Collect frames for flow analysis
                all_frames_for_flows.extend(frames)

            lines.append("")

        # Level 2+: Add global flow analysis at the end
        if detail_level >= 2 and all_frames_for_flows:
            flow_lines = serializer.serialize_flows(all_frames_for_flows, level=0)
            if flow_lines:
                lines.append("FLOWS:")
                lines.extend(flow_lines)

        toon_output = '\n'.join(lines)

        # Add LLM analysis if requested
        if llm_analysis and llm_analysis != 'none' and self.llm:
            self._log_tool_event(f"Running LLM analysis (level={llm_analysis})")
            try:
                # Build file_data structure for LLM analysis
                file_data_for_llm = {
                    'name': file_data.name,
                    'key': file_key,
                    'pages': [],
                }
                # Collect frame IDs for image fetching (for detailed analysis)
                all_frame_ids = []

                # Re-use processed page data
                for page_node in pages_to_process:
                    page_id = page_node.get('id', '')
                    try:
                        # Fetch full page if needed
                        nodes_data = self._get_file_nodes(file_key, page_id)
                        if nodes_data:
                            full_page_node = nodes_data.get('nodes', {}).get(page_id, {}).get('document', {})
                            if full_page_node:
                                page_node = full_page_node
                    except Exception:
                        pass  # Use shallow data
                    page_data = process_page_to_toon_data(page_node, max_frames=max_frames)
                    file_data_for_llm['pages'].append(page_data)

                    # Collect frame IDs for vision analysis
                    for frame in page_data.get('frames', []):
                        frame_id = frame.get('id')
                        if frame_id:
                            all_frame_ids.append(frame_id)

                # Fetch frame images for vision-based analysis (detailed mode only)
                frame_images = {}
                # Use max_frames parameter to limit LLM analysis (respects user setting)
                frames_to_analyze = min(max_frames, len(all_frame_ids))
                if llm_analysis == 'detailed' and all_frame_ids:
                    self._log_tool_event(f"Fetching images for {frames_to_analyze} frames (vision analysis)")
                    try:
                        frame_ids_to_fetch = all_frame_ids[:frames_to_analyze]
                        images_response = self._client.get_file_images(
                            file_key=file_key,
                            ids=frame_ids_to_fetch,
                            scale=1,  # Scale 1 is sufficient for analysis
                            format='png'
                        )
                        if images_response and hasattr(images_response, 'images'):
                            frame_images = images_response.images or {}
                            self._log_tool_event(f"Fetched {len(frame_images)} frame images")
                            self._log_tool_event("Processing images and preparing for LLM analysis...")
                    except Exception as img_err:
                        self._log_tool_event(f"Frame image fetch failed (continuing without vision): {img_err}")
                        # Continue without images - will fall back to text analysis

                # Create status callback for progress updates
                def _status_callback(msg: str):
                    self._log_tool_event(msg)

                # Import here to avoid circular imports
                from .toon_tools import enrich_toon_with_llm_analysis

                # Check if design insights should be included (default True)
                include_design_insights = kwargs.get('include_design_insights', True)

                # Get parallel workers from toolkit config (or default)
                parallel_workers = getattr(self, "number_of_threads", DEFAULT_NUMBER_OF_THREADS)
                if parallel_workers is None or not isinstance(parallel_workers, int):
                    parallel_workers = DEFAULT_NUMBER_OF_THREADS
                parallel_workers = max(1, min(parallel_workers, 5))

                self._log_tool_event(f"Starting LLM analysis of {frames_to_analyze} frames with {parallel_workers} parallel workers...")
                toon_output = enrich_toon_with_llm_analysis(
                    toon_output=toon_output,
                    file_data=file_data_for_llm,
                    llm=self.llm,
                    analysis_level=llm_analysis,
                    frame_images=frame_images,
                    status_callback=_status_callback,
                    include_design_insights=include_design_insights,
                    parallel_workers=parallel_workers,
                    max_frames_to_analyze=frames_to_analyze,
                )
                self._log_tool_event("LLM analysis complete")
            except Exception as e:
                self._log_tool_event(f"LLM analysis failed: {e}")
                # Return TOON output without LLM analysis on error
                toon_output += f"\n\n[LLM analysis failed: {e}]"

        self._log_tool_event(f"File analysis complete (detail_level={detail_level})")
        return toon_output

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
            # TODO disabled until new requirements
            # {
            #     "name": "get_file_summary",
            #     "description": self.get_file_summary.__doc__,
            #     "args_schema": ArgsSchema.FileSummary.value,
            #     "ref": self.get_file_summary,
            # },
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
            # TOON Format Tools (Token-Optimized)
            # Primary unified tool with configurable detail levels
            {
                "name": "analyze_file",
                "description": self.analyze_file.__doc__,
                "args_schema": AnalyzeFileSchema,
                "ref": self.analyze_file,
            },
            # Targeted drill-down for specific frames (more efficient than level 3 for 2-3 frames)
            {
                "name": "get_frame_detail_toon",
                "description": self.get_frame_detail_toon.__doc__,
                "args_schema": FrameDetailTOONSchema,
                "ref": self.get_frame_detail_toon,
            },
        ]
