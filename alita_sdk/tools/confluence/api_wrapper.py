import base64
import json
import logging
import re
import traceback
from json import JSONDecodeError
from typing import Optional, List, Any, Dict, Callable, Generator, Literal

import requests
from atlassian.errors import ApiError
from langchain_community.document_loaders.confluence import ContentFormat
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.tools import ToolException
from markdownify import markdownify
from pydantic import Field, PrivateAttr, model_validator, create_model, SecretStr
from requests import HTTPError
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from alita_sdk.tools.non_code_indexer_toolkit import NonCodeIndexerToolkit
from alita_sdk.tools.utils.available_tools_decorator import extend_with_parent_available_tools
from ..llm.img_utils import ImageDescriptionCache
from ..utils import is_cookie_token, parse_cookie_string
from ...runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

createPage = create_model(
    "createPage",
    space=(Optional[str], Field(description="Confluence space that is used for page's creation", default=None)),
    title=(str, Field(description="Title of the page")),
    body=(str, Field(description="Body of the page")),
    status=(Optional[str],
            Field(description="Page publishing option: 'current' for publish page, 'draft' to create draft.",
                  default='current')),
    parent_id=(Optional[str], Field(description="Page parent id (optional)", default=None)),
    representation=(Optional[str],
                    Field(description="Content representation format: storage for html, wiki for markdown",
                          default='storage')),
    label=(Optional[str], Field(description="Page label (optional)", default=None)),
)

createPages = create_model(
    "createPages",
    space=(Optional[str], Field(description="Confluence space that is used for pages creation", default=None)),
    pages_info=(str, Field(
        description="""JSON string containing information about page name and its content per syntax: [{"page1_name": "page1_content"}, {"page2_name": "page2_content"}]""")),
    parent_id=(Optional[str], Field(description="Page parent id (optional)", default=None)),
    status=(Optional[str],
            Field(description="Page publishing option: 'current' for publish page, 'draft' to create draft.",
                  default='current')),
)

deletePage = create_model(
    "deletePage",
    page_id=(Optional[str], Field(description="Page id", default=None)),
    page_title=(Optional[str], Field(description="Page title", default=None)),
)

updatePageById = create_model(
    "updatePageById",
    page_id=(str, Field(description="Page id")),
    representation=(Optional[str],
                    Field(description="Content representation format: storage for html, wiki for markdown",
                          default='storage')),
    new_title=(Optional[str], Field(description="New page title", default=None)),
    new_body=(Optional[str], Field(description="New page content", default=None)),
    new_labels=(Optional[list], Field(description="Page labels", default=None)),
)

updatePageByTitle = create_model(
    "updatePageByTitle",
    page_title=(str, Field(description="Page title")),
    representation=(Optional[str],
                    Field(description="Content representation format: storage for html, wiki for markdown",
                          default='storage')),
    new_title=(Optional[str], Field(description="New page title", default=None)),
    new_body=(Optional[str], Field(description="New page content", default=None)),
    new_labels=(Optional[list], Field(description="Page labels", default=None)),
)

updatePages = create_model(
    "updatePages",
    page_ids=(Optional[list], Field(description="List of ids of pages to be updated", default=None)),
    new_contents=(Optional[list], Field(
        description="List of new contents for each page. If content the same for all the pages then it should be a list with a single entry",
        default=None)),
    new_labels=(Optional[list], Field(description="Page labels", default=None)),
)

updateLabels = create_model(
    "updateLabels",
    page_ids=(Optional[list], Field(description="List of ids of pages to be updated", default=None)),
    new_labels=(Optional[list], Field(description="Page labels", default=None)),
)

getPageTree = create_model(
    "getPageTree",
    page_id=(str, Field(description="Page id")),
)

getPageIdByTitleInput = create_model(
    "getPageIdByTitleInput",
    title=(str, Field(description="Page title")),
    type=(Optional[str], Field(description="Jira type of content: Page or Blogpost. Defaults to page", default="page")),

)

pageExists = create_model(
    "pageExists",
    title=(str, Field(description="Title of the page")),
)

getPagesWithLabel = create_model(
    "getPagesWithLabel",
    label=(str, Field(description="Label of the pages")),
)

searchPages = create_model(
    "searchPages",
    query=(str, Field(description="Query text to search pages")),
    skip_images=(Optional[bool], Field(description="Whether we need to skip existing images or not", default=False))
)

siteSearch = create_model(
    "siteSearch",
    query=(str, Field(description="Query text to execute site search in Confluence")),
)

pageId = create_model(
    "pageId",
    page_id=(str, Field(description="Id of page to be read")),
    skip_images=(Optional[bool], Field(description="Whether we need to skip existing images or not", default=False)),
)

сonfluenceInput = create_model(
    "сonfluenceInput",
    method=(str, Field(
        description="The HTTP method to use for the request (GET, POST, PUT, DELETE, etc.). Required parameter.")),
    relative_url=(str, Field(
        description="Required parameter: The relative URI for Confluence API. URI must start with a forward slash and '/rest/...'. Do not include query parameters in the URL, they must be provided separately in 'params'.")),
    params=(Optional[str], Field(default="",
                                 description="Optional JSON of parameters to be sent in request body or query params. MUST be string with valid JSON. For search/read operations, you MUST always get minimum fields and set max results, until users ask explicitly for more fields. For search/read operations you must generate CQL query string and pass it as params."))
)

GetPageWithImageDescriptions = create_model(
    "GetPageWithImageDescriptionsModel",
    page_id=(str, Field(description="Confluence page ID from which content with images will be extracted")),
    prompt=(Optional[str], Field(
        description="Custom prompt to use for image description generation. If not provided, a default prompt will be used",
        default=None)),
    context_radius=(Optional[int], Field(
        description="Number of characters to include before and after each image for context. Default is 500",
        default=500))
)

GetPageAttachmentsInput = create_model(
    "GetPageAttachmentsInput",
    page_id=(str, Field(description="Confluence page ID from which attachments will be retrieved")),
    max_content_length=(int, Field(default=10000, description="Maximum number of characters to return for attachment content. Content will be truncated if longer. Default is 10000.")),
    custom_prompt=(Optional[str], Field(default=None, description="Custom prompt to use for LLM-based analysis of attachments (images, pdfs, etc). If not provided, a default prompt will be used.")),
    allowed_extensions=(Optional[List[str]], Field(default=None, description="List of file extensions to include (e.g. ['pdf', 'docx']). If None, all extensions are included.", examples=[["pdf", "docx"]])),
    name_pattern=(Optional[str], Field(default=None, description="Regex pattern to filter attachment names (e.g. '^report_.*\\.pdf$'). If None, all names are included.", examples=["^report_.*\\.pdf$"])),
)


def parse_payload_params(params: Optional[str]) -> Dict[str, Any]:
    if params:
        try:
            return json.loads(params)
        except JSONDecodeError:
            stacktrace = traceback.format_exc()
            return ToolException(f"Confluence tool exception. Passed params are not valid JSON. {stacktrace}")
    return {}


class ConfluenceAPIWrapper(NonCodeIndexerToolkit):
    # Changed from PrivateAttr to Optional field with exclude=True
    client: Optional[Any] = Field(default=None, exclude=True)
    base_url: str
    api_key: Optional[SecretStr] = None,
    username: Optional[str] = None
    token: Optional[SecretStr] = None
    cloud: Optional[bool] = True
    limit: Optional[int] = 5
    labels: Optional[List[str]] = []
    space: Optional[str] = None
    max_pages: Optional[int] = 10
    content_format: Optional[ContentFormat] = ContentFormat.VIEW
    include_attachments: Optional[bool] = False
    include_comments: Optional[bool] = False
    include_restricted_content: Optional[bool] = False
    number_of_retries: Optional[int] = 3
    min_retry_seconds: Optional[int] = 2
    max_retry_seconds: Optional[int] = 10
    keep_markdown_format: Optional[bool] = True
    ocr_languages: Optional[str] = None
    keep_newlines: Optional[bool] = True
    _errors: Optional[list[str]] = None
    _image_cache: ImageDescriptionCache = PrivateAttr(default_factory=ImageDescriptionCache)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            from atlassian import Confluence  # noqa: F401
        except ImportError:
            raise ImportError(
                "`atlassian` package not found, please run "
                "`pip install atlassian-python-api`"
            )
        if not values.get('base_url'):
            raise ValueError("Base URL is required for Confluence API Wrapper.")
        url = values['base_url']
        if not (values.get('token') or (values.get('api_key') and values.get('username'))):
            raise ValueError("Either 'token' or both 'api_key' and 'username' must be provided for authentication.")
        api_key = values.get('api_key')
        username = values.get('username')
        token = values.get('token')
        cloud = values.get('cloud')
        if token and is_cookie_token(token):
            session = requests.Session()
            session.cookies.update(parse_cookie_string(token))
            client_instance = Confluence(url=url, session=session, cloud=cloud)
        elif token:
            client_instance = Confluence(url=url, token=token, cloud=cloud)
        else:
            client_instance = Confluence(url=url, username=username, password=api_key, cloud=cloud)

        custom_headers = values.get('custom_headers') or {}
        logger.info(f"Confluence tool: custom headers length: {len(custom_headers)}")
        for header, value in custom_headers.items():
            client_instance._update_header(header, value)

        values['client'] = client_instance
        return super().validate_toolkit(values)

    def __unquote_confluence_space(self) -> str | None:
        if self.space:
            # Remove single quotes or backticks if present
            if (self.space.startswith("'") and self.space.endswith("'")) or (
                    self.space.startswith("`") and self.space.endswith("`")):
                return self.space[1:-1]
            else:
                return self.space
        else:
            return None

    def __sanitize_confluence_space(self) -> str:
        """Ensure the space parameter is enclosed in double quotes."""
        unquoted_space = self.__unquote_confluence_space()
        if unquoted_space:
            # Add double quotes if not already present
            if not (unquoted_space.startswith('"') and unquoted_space.endswith('"')):
                unquoted_space = f'"{unquoted_space}"'
        return unquoted_space

    def create_page(self, title: str, body: str, status: str = 'current', space: str = None, parent_id: str = None,
                    representation: str = 'storage', label: str = None):
        """ Creates a page in the Confluence space. Represents content in html (storage) or wiki (wiki) formats
            Page could be either published status='current' or make a draft with status='draft'
        """
        if self.client.get_page_by_title(space=self.space, title=title) is not None:
            return f"Page with title {title} already exists, please use other title."

        # normal user flow: put pages in the Space Home, not in the root of the Space
        user_space = space if space else self.space
        logger.info(f"Page will be created within the space {user_space}")
        parent_id_filled = parent_id if parent_id else self.client.get_space(user_space)['homepage']['id']

        created_page = self.temp_create_page(space=user_space, title=title, body=body, status=status,
                                             parent_id=parent_id_filled, representation=representation)

        page_details = {
            'title': created_page['title'],
            'id': created_page['id'],
            'space key': created_page['space']['key'],
            'author': created_page['version']['by']['displayName'],
            'link': created_page['_links']['base'] + (
                created_page['_links']['edit'] if status == 'draft' else created_page['_links']['webui'])
        }

        logger.info(f"Page created: {page_details['link']}")

        if label:
            self.client.set_page_label(page_id=created_page['id'], label=label)
            logger.info(f"Label '{label}' added to the page '{title}'.")
            page_details['label'] = label

        self._add_default_labels(page_id=created_page['id'])

        return f"The page '{title}' was created under the parent page '{parent_id_filled}': '{page_details['link']}'. \nDetails: {str(page_details)}"

    def create_pages(self, pages_info: str, status: str = 'current', space: str = None, parent_id: str = None):
        """ Creates a batch of pages in the Confluence space."""
        created_pages = []
        user_space = space if space else self.space
        logger.info(f"Pages will be created within the space {user_space}")
        # duplicate action to avoid extra api calls in downstream function
        parent_id_filled = parent_id if parent_id else self.client.get_space(user_space)['homepage']['id']
        for page_item in json.loads(pages_info):
            for title, body in page_item.items():
                created_page = self.create_page(title=title, body=body, status=status, parent_id=parent_id_filled,
                                                space=user_space)
                created_pages.append(created_page)
        return str(created_pages)

    # delete after https://github.com/atlassian-api/atlassian-python-api/pull/1452 will be merged
    def temp_create_page(self, space, title, body, parent_id=None, type="page", representation="storage", editor=None,
                         full_width=False, status='current'):
        logger.info('Creating %s "%s" -> "%s"', type, space, title)
        url = "rest/api/content/"
        data = {
            "type": type,
            "title": title,
            "status": status,
            "space": {"key": space},
            "body": self.client._create_body(body, representation),
            "metadata": {"properties": {}},
        }
        if parent_id:
            data["ancestors"] = [{"type": type, "id": parent_id}]
        if editor is not None and editor in ["v1", "v2"]:
            data["metadata"]["properties"]["editor"] = {"value": editor}
        if full_width is True:
            data["metadata"]["properties"]["content-appearance-draft"] = {"value": "full-width"}
            data["metadata"]["properties"]["content-appearance-published"] = {"value": "full-width"}
        else:
            data["metadata"]["properties"]["content-appearance-draft"] = {"value": "fixed-width"}
            data["metadata"]["properties"]["content-appearance-published"] = {"value": "fixed-width"}

        return self.client.post(url, data=data)

    def delete_page(self, page_id: str = None, page_title: str = None):
        """ Deletes a page by its defined page_id or page_title """
        if not page_id and not page_title:
            raise ValueError("Either page_id or page_title is required to delete the page")
        resolved_page_id = page_id if page_id else (
                self.client.get_page_by_title(space=self.space, title=page_title) or {}).get('id')
        if resolved_page_id:
            self.client.remove_page(resolved_page_id)
            message = f"Page with ID '{resolved_page_id}' has been successfully deleted."
        else:
            message = f"Page instance could not be resolved with id '{page_id}' and/or title '{page_title}'"
        return message

    def update_page_by_id(self, page_id: str, representation: str = 'storage', new_title: str = None,
                          new_body: str = None, new_labels: list = None):
        """ Updates an existing Confluence page (using id or title) by replacing its content, title, labels """
        current_page = self.client.get_page_by_id(page_id, expand='version,body.view')
        if not current_page:
            return f"Page with ID {page_id} not found."

        if new_title and current_page['title'] != new_title and self.client.get_page_by_title(space=self.space,
                                                                                              title=new_title):
            return f"Page with title {new_title} already exists."

        current_version = current_page['version']['number']
        title_to_use = new_title if new_title else current_page['title']
        body_to_use = new_body if new_body else current_page['body']['view']['value']
        representation_to_use = representation if representation else current_page['body']['view']['representation']

        updated_page = self.client.update_page(page_id=page_id, title=title_to_use, body=body_to_use,
                                               representation=representation_to_use)
        webui_link = updated_page['_links']['base'] + updated_page['_links']['webui']
        logger.info(f"Page updated: {webui_link}")

        next_version = updated_page['version']['number']
        diff_link = f"{updated_page['_links']['base']}/pages/diffpagesbyversion.action?pageId={page_id}&selectedPageVersions={current_version}&selectedPageVersions={next_version}"
        logger.info(f"Link to diff: {diff_link}")

        update_details = {
            'title': updated_page['title'],
            'id': updated_page['id'],
            'space key': updated_page['space']['key'],
            'author': updated_page['version']['by']['displayName'],
            'link': updated_page['_links']['base'] + updated_page['_links']['webui'],
            'version': next_version,
            'diff': diff_link
        }

        if new_labels is not None:
            current_labels = self.client.get_page_labels(page_id)
            for label in current_labels['results']:
                self.client.remove_page_label(page_id, label['name'])
            for label in new_labels:
                self.client.set_page_label(page_id, label)
            logger.info(f"Labels updated for the page '{title_to_use}'.")
            update_details['labels'] = new_labels

        self._add_default_labels(page_id=page_id)

        return f"The page '{page_id}' was updated successfully: '{webui_link}'. \nDetails: {str(update_details)}"

    def update_page_by_title(self, page_title: str, representation: str = 'storage', new_title: str = None,
                             new_body: str = None, new_labels: list = None):
        """ Updates an existing Confluence page (using id or title) by replacing its content, title, labels """
        current_page = self.client.get_page_by_title(space=self.space, title=page_title)
        if not current_page:
            return f"Page with title {page_title} not found."

        return self.update_page_by_id(page_id=current_page['id'], representation=representation, new_title=new_title,
                                      new_body=new_body, new_labels=new_labels)

    def update_pages(self, page_ids: list = None, new_contents: list = None, new_labels: list = None):
        """ Update a batch of pages in the Confluence space. """
        statuses = []
        if len(page_ids) != len(new_contents) and len(new_contents) != 1:
            raise ValueError(
                "New content should be provided for all the pages or it should contain only 1 new body for bulk update")
        if page_ids:
            for index, page_id in enumerate(page_ids):
                status = self.update_page_by_id(page_id=page_id,
                                                new_body=new_contents[index if len(new_contents) != 1 else 0],
                                                new_labels=new_labels)
                statuses.append(status)
            return str(statuses)
        else:
            return "Either list of page_ids or parent_id (to update descendants) should be provided."

    def _add_default_labels(self, page_id: str):
        """ Add default labels to the pages that has been created or modified by agent."""

        if self.labels:
            logger.info(f'Add pre-defined labels to the issue: {self.labels}')
            for label in self.labels:
                self.client.set_page_label(page_id, label)

    def update_labels(self, page_ids: list = None, new_labels: list = None):
        """ Update a batch of pages in the Confluence space. """
        statuses = []
        if page_ids:
            for index, page_id in enumerate(page_ids):
                status = self.update_page_by_id(page_id=page_id, new_labels=new_labels)
                statuses.append(status)
            return str(statuses)
        else:
            return "Either list of page_ids should be provided."

    def get_page_tree(self, page_id: str):
        """ Gets page tree for the Confluence space """
        descendant_pages = self.get_all_descendants(page_id)  # Pass None as the parent for the root
        for page in descendant_pages:
            logger.info(f"Page ID: {page['id']}, Title: {page['title']}, Parent ID: {page['parent_id']}")
        descendants = {page['id']: (page['title'], page['parent_id']) for page in descendant_pages}
        return f"The list of pages under the '{page_id}' was extracted: {descendants}"

    def get_all_descendants(self, page_id: str):
        """ Recursively gets all descendant pages of a given page. """
        descendants = []
        limit = 100
        start = 0

        while True:
            children = self.client.get_page_child_by_type(page_id, type='page', start=start, limit=limit)
            if not children:
                break
            for child in children:
                child_info = {'id': child['id'], 'title': child['title'], 'parent_id': page_id}
                descendants.append(child_info)
                descendants.extend(self.get_all_descendants(child['id']))
            start += limit

        return descendants

    def page_exists(self, title: str):
        """ Checks if a page exists in the Confluence space."""
        status = self.client.page_exists(space=self.space, title=title)
        return status

    def get_pages_with_label(self, label: str):
        """ Gets pages with specific label in the Confluence space."""
        return str(self._get_labeled_page(label))

    def list_pages_with_label(self, label: str):
        """ Lists the pages with specific label in the Confluence space."""
        return [{'id': page['page_id'], 'title': page['page_title']} for page in self._get_labeled_page(label)]

    def _get_labeled_page(self, label: str):
        """Gets pages with specific label in the Confluence space."""

        start = 0
        pages_info = []
        for _ in range((self.max_pages + self.limit - 1) // self.limit):
            pages = self.client.get_all_pages_by_label(label, start=start,
                                                       limit=self.limit)  # , expand="body.view.value"
            if not pages:
                break

            pages_info += [{
                'page_id': page.metadata['id'],
                'page_title': page.metadata['title'],
                'page_url': page.metadata['source'],
                'content': page.page_content
            } for page in self.get_pages_by_id([page["id"] for page in pages])]
            start += self.limit
        return pages_info

    def is_public_page(self, page: dict) -> bool:
        """Check if a page is publicly accessible."""
        restrictions = self.client.get_all_restrictions_for_content(page["id"])

        return (
                (page["status"] == "current"
                # allow user to see archived content if needed
                 or page["status"] == "archived")
                and not restrictions["read"]["restrictions"]["user"]["results"]
                and not restrictions["read"]["restrictions"]["group"]["results"]
        )

    def get_pages_by_id(self, page_ids: List[str], skip_images: bool = False):
        """ Gets pages by id in the Confluence space."""
        for page_id in page_ids:
            get_page = retry(
                reraise=True,
                stop=stop_after_attempt(
                    self.number_of_retries  # type: ignore[arg-type]
                ),
                wait=wait_exponential(
                    multiplier=1,  # type: ignore[arg-type]
                    min=self.min_retry_seconds,  # type: ignore[arg-type]
                    max=self.max_retry_seconds,  # type: ignore[arg-type]
                ),
                before_sleep=before_sleep_log(logger, logging.WARNING),
            )(self.client.get_page_by_id)
            try:
                page = get_page(
                    page_id=page_id, expand=f"{self.content_format.value},version"
                )
            except (ApiError, HTTPError) as e:
                logger.error(f"Error fetching page with ID {page_id}: {e}")
                page_content_temp = f"Confluence API Error: cannot fetch the page with ID {page_id}: {e}"
                # store errors
                if self._errors is None:
                    self._errors = []
                self._errors.append(page_content_temp)
                return Document(page_content=page_content_temp,
                                metadata={})
            # TODO: update on toolkit advanced settings level as a separate feature
            # if not self.include_restricted_content and not self.is_public_page(page):
            #     continue
            yield self.process_page(page, skip_images)

    def _log_errors(self):
        """ Log errors encountered during toolkit execution. """
        if self._errors:
            logger.info(f"Errors encountered during toolkit execution: {self._errors}")

    def read_page_by_id(self, page_id: str, skip_images: bool = False):
        """Reads a page by its id in the Confluence space. If id is not available, but there is a title - use get_page_id first."""
        result = list(self.get_pages_by_id([page_id], skip_images))
        if not result:
            return f"Pages not found. Errors: {self._errors}" if self._errors \
                else "Pages not found or you do not have access to them."
        return result[0].page_content
        # return self._strip_base64_images(result[0].page_content) if skip_images else result[0].page_content

    def get_page_id_by_title(self, title: str, type: str = "page"):
        """
        Provide page id from search result by title.
        :param title: title
        :param type: type of content: page or blogpost. Defaults to page
        """

        result = self.client.get_page_id(space=self.space, title=title, type=type)
        return result if result else "Page not found. Check the title or space."

    def _strip_base64_images(self, content):
        base64_md_pattern = r'data:image/(png|jpeg|gif);base64,[a-zA-Z0-9+/=]+'
        return re.sub(base64_md_pattern, "[Image Removed]", content)

    def _process_search(self, cql, skip_images: bool = False):
        start = 0
        pages_info = []
        for _ in range((self.max_pages + self.limit - 1) // self.limit):
            pages = self.client.cql(cql, start=start, limit=self.limit).get("results", [])
            if not pages:
                break
            page_ids = [page['content']['id'] for page in pages]
            for page in self.get_pages_by_id(page_ids, skip_images):
                page_info = {
                    'content': page.page_content,
                    'page_id': page.metadata['id'],
                    'page_title': page.metadata['title'],
                    'page_url': page.metadata['source']
                }
                pages_info.append(page_info)
            start += self.limit
        return str(pages_info) if pages_info else f"Unable to find anything using query {cql}. Check space or query."

    def search_pages(self, query: str, skip_images: bool = False):
        """Search pages in Confluence by query text in title or page content."""
        if not self.space:
            cql = f'(type=page) and (title~"{query}" or text~"{query}")'
        else:
            cql = f'(type=page and space={self.__sanitize_confluence_space()}) and (title~"{query}" or text~"{query}")'
        return self._process_search(cql, skip_images)

    def search_by_title(self, query: str, skip_images: bool = False):
        """Search pages in Confluence by query text in title."""

        query = self._escape_cql_query(query)
        if not self.space:
            cql = f'(type=page) and (title~"{query}")'
        else:
            cql = f'(type=page and space={self.__sanitize_confluence_space()}) and (title~"{query}")'
        return self._process_search(cql, skip_images)

    def _escape_cql_query(self, query: str) -> str:
        """Escape special characters in a CQL query string."""
        # List of special characters in CQL that need escaping
        special_chars = r'\\|+*?[]{}()^$~#:'
        # Escape each special character with a backslash
        return re.sub(r'([{}])'.format(re.escape(special_chars)), r'\\\1', query)

    def site_search(self, query: str):
        """Search for pages in Confluence using site search by query text."""
        content = []
        query = self._escape_cql_query(query)
        if not self.space:
            cql = f'(type=page) and (siteSearch~"{query}")'
        else:
            cql = f'(type=page and space={self.__sanitize_confluence_space()}) and (siteSearch~"{query}")'
        pages = self.client.cql(cql, start=0, limit=10).get("results", [])
        if not pages:
            return f"Unable to find anything using query {query}"
        # extract id, title, url and preview text
        for page in pages:
            page_data = {
                'page_id': page['content']['id'],
                'page_title': page['content']['title'],
                'page_url': page['content']['_links']['self']
            }
            page_data['preview'] = page['excerpt'] if page['excerpt'] else ""
            content.append(page_data)
        return '---'.join([str(page_data) for page_data in content])

    def process_page(self, page: dict, skip_images: bool = False) -> Document:
        if self.keep_markdown_format:
            try:
                from markdownify import markdownify
            except ImportError:
                raise ImportError(
                    "`markdownify` package not found, please run "
                    "`pip install markdownify`"
                )
        if self.include_comments or not self.keep_markdown_format:
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                raise ImportError(
                    "`beautifulsoup4` package not found, please run "
                    "`pip install beautifulsoup4`"
                )
        if self.include_attachments:
            attachment_texts = self.process_attachment(page["id"], self.ocr_languages)
        else:
            attachment_texts = []

        content = self.content_format.get_content(page)
        if self.keep_markdown_format:
            # Use markdownify to keep the page Markdown style
            text = markdownify(content, heading_style="ATX") + "".join(attachment_texts)

        else:
            if self.keep_newlines:
                text = BeautifulSoup(
                    content.replace("</p>", "\n</p>").replace("<br />", "\n"), "lxml"
                ).get_text(" ") + "".join(attachment_texts)
            else:
                text = BeautifulSoup(content, "lxml").get_text(
                    " ", strip=True
                ) + "".join(attachment_texts)

        if self.include_comments:
            comments = self.client.get_page_comments(
                page["id"], expand="body.view.value", depth="all"
            )["results"]
            comment_texts = [
                BeautifulSoup(comment["body"]["view"]["value"], "lxml").get_text(
                    " ", strip=True
                )
                for comment in comments
            ]
            text = text + "".join(comment_texts)

        metadata = {
            "title": page["title"],
            "id": page["id"],
            "source": self.base_url.strip("/") + page["_links"]["webui"],
        }

        if "version" in page and "when" in page["version"]:
            metadata["when"] = page["version"]["when"]

        return Document(
            page_content=self._strip_base64_images(text) if skip_images else text,
            metadata=metadata,
        )

    # todo: refactor this method since file processing is not working (self.process_pdf, self.process_image, etc. are not defined)
    def process_attachment(
            self,
            page_id: str,
            ocr_languages: Optional[str] = None,
    ) -> List[str]:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            raise ImportError(
                "`Pillow` package not found, " "please run `pip install Pillow`"
            )

        # depending on setup you may also need to set the correct path for
        # poppler and tesseract
        attachments = self.client.get_attachments_from_content(page_id)["results"]
        texts = []
        for attachment in attachments:
            media_type = attachment["metadata"]["mediaType"]
            absolute_url = self.base_url + attachment["_links"]["download"]
            title = attachment["title"]
            try:
                if media_type == "application/pdf":
                    text = title + self.process_pdf(absolute_url, ocr_languages)
                elif (
                        media_type == "image/png"
                        or media_type == "image/jpg"
                        or media_type == "image/jpeg"
                ):
                    text = title + self.process_image(absolute_url, ocr_languages)
                elif (
                        media_type == "application/vnd.openxmlformats-officedocument"
                                      ".wordprocessingml.document"
                ):
                    text = title + self.process_doc(absolute_url)
                elif media_type == "application/vnd.ms-excel":
                    text = title + self.process_xls(absolute_url)
                elif media_type == "image/svg+xml":
                    text = title + self.process_svg(absolute_url, ocr_languages)
                else:
                    continue
                texts.append(text)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"Attachment not found at {absolute_url}")  # noqa: T201
                    continue
                else:
                    raise

        return texts

    def execute_generic_confluence(self, method: str, relative_url: str, params: Optional[str] = "") -> str:
        """Generic Confluence Tool for Official Atlassian Confluence REST API to call, searching, creating, updating pages, etc."""
        payload_params = parse_payload_params(params)
        if method == "GET":
            response = self.client.request(
                method=method,
                path=relative_url,
                params=payload_params,
                advanced_mode=True
            )
            response_text = self.process_search_response(relative_url, response)
        else:
            response = self.client.request(
                method=method,
                path=relative_url,
                data=payload_params,
                advanced_mode=True
            )
            response_text = response.text
        response_string = f"HTTP: {method}{relative_url} -> {response.status_code}{response.reason}{response_text}"
        logger.debug(response_string)
        return response_string

    def process_search_response(self, relative_url: str, response) -> str:
        page_search_pattern = r'/rest/api/content/\d+'
        if re.match(page_search_pattern, relative_url):
            body = markdownify(response.text, heading_style="ATX")
            return body
        return response.text

    def paginate_request(self, retrieval_method: Callable, **kwargs: Any) -> List:
        """Paginate the various methods to retrieve groups of pages.

        Unfortunately, due to page size, sometimes the Confluence API
        doesn't match the limit value. If `limit` is >100 confluence
        seems to cap the response to 100. Also, due to the Atlassian Python
        package, we don't get the "next" values from the "_links" key because
        they only return the value from the result key. So here, the pagination
        starts from 0 and goes until the max_pages, getting the `limit` number
        of pages with each request. We have to manually check if there
        are more docs based on the length of the returned list of pages, rather than
        just checking for the presence of a `next` key in the response like this page
        would have you do:
        https://developer.atlassian.com/server/confluence/pagination-in-the-rest-api/

        :param retrieval_method: Function used to retrieve docs
        :type retrieval_method: callable
        :return: List of documents
        :rtype: List
        """

        max_pages = kwargs.pop("max_pages")
        docs: List[dict] = []
        next_url: str = ""
        while len(docs) < max_pages:
            get_pages = retry(
                reraise=True,
                stop=stop_after_attempt(
                    self.number_of_retries  # type: ignore[arg-type]
                ),
                wait=wait_exponential(
                    multiplier=1,
                    min=self.min_retry_seconds,  # type: ignore[arg-type]
                    max=self.max_retry_seconds,  # type: ignore[arg-type]
                ),
                before_sleep=before_sleep_log(logger, logging.WARNING),
            )(retrieval_method)
            if self.cql:  # cursor pagination for CQL
                batch, next_url = get_pages(**kwargs, next_url=next_url)
                if not next_url:
                    docs.extend(batch)
                    break
            else:
                batch = get_pages(**kwargs, start=len(docs))
                if not batch:
                    break
            docs.extend(batch)
        return docs[:max_pages]

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        """
        Loads content from Confluence based on parameters.
        Returns:
            Generator: A generator that yields content of pages that match specified criteria
        """
        from .loader import AlitaConfluenceLoader
        from copy import copy
        content_format = kwargs.get('content_format', 'view').lower()

        self._index_include_attachments = kwargs.get('include_attachments', False)
        self._include_extensions = kwargs.get('include_extensions', [])
        self._skip_extensions = kwargs.get('skip_extensions', [])
        base_params = {
            'url': self.base_url,
            'space_key': self.space,
            'min_retry_seconds': self.min_retry_seconds,
            'max_retry_seconds': self.max_retry_seconds,
            'number_of_retries': self.number_of_retries
        }
        confluence_loader_params = copy(kwargs)
        confluence_loader_params.update(base_params)
        mapping = {
            'view': ContentFormat.VIEW,
            'storage': ContentFormat.STORAGE,
            'export_view': ContentFormat.EXPORT_VIEW,
            'editor': ContentFormat.EDITOR,
            'anonymous': ContentFormat.ANONYMOUS_EXPORT_VIEW
        }
        confluence_loader_params['content_format'] = mapping.get(content_format, ContentFormat.VIEW)
        confluence_loader_params['url'] = self.base_url
        confluence_loader_params['space_key'] = self.space
        confluence_loader_params['min_retry_seconds'] = self.min_retry_seconds
        confluence_loader_params['max_retry_seconds'] = self.max_retry_seconds
        confluence_loader_params['number_of_retries'] = self.number_of_retries
        bins_with_llm = confluence_loader_params.pop('bins_with_llm', False)
        loader = AlitaConfluenceLoader(self.client, self.llm, bins_with_llm, **confluence_loader_params)

        for document in loader._lazy_load(kwargs={}):
            if 'updated_on' not in document.metadata and 'when' in document.metadata:
                document.metadata['updated_on'] = document.metadata['when']
            yield document

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        try:
            if self._index_include_attachments:
                page_id = document.metadata.get('id')
                attachments = self.client.get_attachments_from_content(page_id)
                if not attachments or not attachments.get('results'):
                    return f"No attachments found for page ID {page_id}."

                # Get attachment history for created/updated info
                history_map = {}
                for attachment in attachments['results']:
                    try:
                        hist = self.client.history(attachment['id'])
                        history_map[attachment['id']] = hist
                    except Exception as e:
                        logger.warning(f"Failed to fetch history for attachment {attachment.get('title', '')}: {str(e)}")
                        history_map[attachment['id']] = None

                import re
                for attachment in attachments['results']:
                    title = attachment.get('title', '')
                    file_ext = title.lower().split('.')[-1] if '.' in title else ''

                    # Re-verify extension filters
                    # Check if file should be skipped based on skip_extensions
                    if any(re.match(pattern.replace('*', '.*') + '$', title, re.IGNORECASE)
                           for pattern in self._skip_extensions):
                        continue

                    # Check if file should be included based on include_extensions
                    # If include_extensions is empty, process all files (that weren't skipped)
                    if self._include_extensions and not (
                    any(re.match(pattern.replace('*', '.*') + '$', title, re.IGNORECASE)
                        for pattern in self._include_extensions)):
                        continue

                    media_type = attachment.get('metadata', {}).get('mediaType', '')
                    # Core metadata extraction with history
                    hist = history_map.get(attachment['id']) or {}
                    created_by = hist.get('createdBy', {}).get('displayName', '') if hist else attachment.get('creator', {}).get('displayName', '')
                    created_date = hist.get('createdDate', '') if hist else attachment.get('created', '')
                    last_updated = hist.get('lastUpdated', {}).get('when', '') if hist else ''

                    metadata = {
                        'name': title,
                        'size': attachment.get('extensions', {}).get('fileSize', None),
                        'creator': created_by,
                        'created': created_date,
                        'updated': last_updated,
                        'media_type': media_type,
                        'labels': [label['name'] for label in
                                   attachment.get('metadata', {}).get('labels', {}).get('results', [])],
                        'download_url': self.base_url.rstrip('/') + attachment['_links']['download'] if attachment.get(
                            '_links', {}).get('download') else None
                    }

                    download_url = self.base_url.rstrip('/') + attachment['_links']['download']

                    try:
                        resp = self.client.request(method="GET", path=download_url[len(self.base_url):], advanced_mode=True)
                        if resp.status_code == 200:
                            content = resp.content
                        else:
                            content = f"[Failed to download {download_url}: HTTP status code {resp.status_code}]"
                    except Exception as e:
                        content = f"[Error downloading content: {str(e)}]"

                    if isinstance(content, str):
                        yield Document(page_content=content, metadata=metadata)
                    else:
                        yield Document(page_content="", metadata={
                            **metadata,
                            IndexerKeywords.CONTENT_FILE_NAME.value: f".{file_ext}",
                            IndexerKeywords.CONTENT_IN_BYTES.value: content
                        })
        except Exception as e:
            yield from ()

    def _download_image(self, image_url):
        """
        Download an image from a URL using the already authenticated Confluence client

        Args:
            image_url: URL to download the image from

        Returns:
            Binary image data or None if download fails
        """
        try:
            # Handle blob URLs by extracting the content ID and attachment name
            if 'blob:' in image_url or 'media-blob-url=true' in image_url:
                logger.info(f"Detected blob URL: {image_url}")
                # Extract content ID from the URL if possible
                content_id_match = re.search(r'contentId-(\d+)', image_url)
                attachment_name_match = re.search(r'name=([^&]+)', image_url)

                if content_id_match and attachment_name_match:
                    content_id = content_id_match.group(1)
                    attachment_name = attachment_name_match.group(1)
                    # URL decode the attachment name if needed
                    import urllib.parse
                    attachment_name = urllib.parse.unquote(attachment_name)

                    logger.info(f"Extracted content ID: {content_id}, attachment name: {attachment_name}")

                    # Find the attachment in the page
                    try:
                        attachments = self.client.get_attachments_from_content(content_id)['results']
                        attachment = None

                        # Find the attachment that matches the filename
                        for att in attachments:
                            if att['title'] == attachment_name:
                                attachment = att
                                break

                        if attachment:
                            # Get the download URL and retry with that
                            download_url = self.base_url.rstrip('/') + attachment['_links']['download']
                            logger.info(f"Found attachment, using download URL: {download_url}")
                            # Recursive call with the direct download URL
                            return self._download_image(download_url)
                    except Exception as e:
                        logger.warning(f"Error resolving blob URL attachment: {str(e)}")

            # Clean up the URL by removing query parameters if causing issues
            parsed_url = image_url
            if '?' in image_url and ('version=' in image_url or 'modificationDate=' in image_url):
                # Keep only the path part for Confluence server URLs
                parsed_url = image_url.split('?')[0]
                logger.info(f"Removed query parameters from URL: {parsed_url}")

            # Extract the path from the URL - the client is already configured with base URL
            # and authentication, so we just need the path part
            relative_path = None
            if parsed_url.startswith(self.base_url):
                relative_path = parsed_url[len(self.base_url):]
            else:
                # Handle case where URL uses different base URL format
                # Try common Confluence URL patterns
                for pattern in ['/download/attachments/', '/download/thumbnails/']:
                    if pattern in parsed_url:
                        path_idx = parsed_url.find(pattern)
                        if path_idx != -1:
                            relative_path = parsed_url[path_idx:]
                            break

                # If still no match, try to use the URL as is
                if not relative_path:
                    if parsed_url.startswith('http'):
                        # For fully qualified URLs that don't match our base URL,
                        # try a direct request as fallback
                        logger.info(f"Using direct request for external URL: {parsed_url}")
                        response = requests.get(
                            parsed_url,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; ConfluenceAPI/1.0; Python)"},
                            cookies=self.client.session.cookies.get_dict(),
                            verify=True,
                            allow_redirects=True,
                            timeout=30
                        )

                        if response.status_code == 200:
                            content_type = response.headers.get('Content-Type', '')
                            if 'text/html' in content_type.lower():
                                logger.warning(f"Received HTML content instead of image from direct request")
                                return None
                            return response.content
                        else:
                            logger.error(f"Direct request failed: {response.status_code}")
                            return None
                    else:
                        relative_path = parsed_url

            # Remove leading slash if present
            if relative_path and relative_path.startswith('/'):
                relative_path = relative_path[1:]

            logger.info(f"Downloading image using relative path: {relative_path}")

            # Use the existing authenticated client to get the image
            response = self.client.request(
                method="GET",
                path=relative_path,
                advanced_mode=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ConfluenceAPI/1.0; Python)"}
            )

            # Check if we got a successful response
            if response.status_code == 200:
                content = response.content
                content_type = response.headers.get('Content-Type', '')
                logger.info(f"Downloaded image successfully. Content type: {content_type}")

                # Check for HTML content which likely indicates an error or login page
                if 'text/html' in content_type.lower():
                    logger.warning(f"Received HTML content instead of image. Authentication issue likely.")
                    return None

                # Basic validation of image data - ensure we actually got image data
                if len(content) < 100:
                    logger.warning(
                        f"Downloaded content suspiciously small ({len(content)} bytes), might not be a valid image")
                    return None

                return content
            else:
                logger.error(f"Failed to download image: HTTP {response.status_code} - {response.reason}")
                return None

        except Exception as e:
            logger.error(f"Error downloading image from {image_url}: {str(e)}")
            return None

    def _get_default_image_analysis_prompt(self) -> str:
        """
        Get a default prompt for image analysis

        Returns:
            Default prompt string
        """
        return """
        ## Image Analysis Task:
        Analyze this image in detail, paying special attention to contextual information provided about it.
        Focus on:
        1. Visual elements and their arrangement
        2. Any text visible in the image
        3. UI components if it's a screenshot
        4. Diagrams, charts, or technical illustrations
        5. The overall context and purpose of the image

        ## Instructions:
        - Begin your description by referencing the image name provided
        - Provide a comprehensive description that could substitute for the image
        - Incorporate the surrounding content in your analysis to provide contextual relevance
        - Explain how this image relates to the content being discussed
        - Format your response clearly with appropriate paragraph breaks
        - Make it short
        """

    def _collect_context_for_image(self, content: str, image_marker: str, context_radius: int = 500) -> str:
        """
        Collect text context around an image reference

        Args:
            content: The full content text
            image_marker: The image reference marker
            context_radius: Number of characters to include before and after each image for context

        Returns:
            Context text
        """
        try:
            start_idx = max(0, content.find(image_marker) - context_radius)
            end_idx = min(len(content), content.find(image_marker) + len(image_marker) + context_radius)

            # Extract the surrounding text
            context = content[start_idx:end_idx]

            # Clean up the context by removing excessive whitespace
            context = re.sub(r'\s+', ' ', context).strip()

            return context
        except Exception as e:
            logger.error(f"Error collecting context for image: {str(e)}")
            return ""

    def _process_image_with_llm(self, image_data, image_name: str = "", context_text: str = "",
                                custom_prompt: str = None):
        """
        Process an image with LLM including surrounding context

        Args:
            image_data: Binary image data
            image_name: Name of the image for reference
            context_text: Surrounding text context
            custom_prompt: Optional custom prompt for the LLM

        Returns:
            Generated description from the LLM
        """
        # Check cache first to avoid redundant processing
        cached_description = self._image_cache.get(image_data, image_name)
        if cached_description:
            logger.info(f"Using cached description for image: {image_name}")
            return cached_description

        try:
            # Get the LLM instance
            llm = self.llm
            if not llm:
                return "[LLM not available for image processing]"

            # If image_data is empty or None, do text-only analysis
            if not image_data:
                prompt = custom_prompt if custom_prompt else self._get_default_image_analysis_prompt()
                if image_name or context_text:
                    prompt += "\n\n## Additional Context Information:\n"
                    if image_name:
                        prompt += f"- Image Name/Reference: {image_name}\n"
                    if context_text:
                        prompt += f"- Surrounding Content: {context_text}\n"
                    prompt += "\nPlease incorporate this contextual information in your description when relevant."
                result = llm.invoke([
                    HumanMessage(
                        content=[{"type": "text", "text": prompt}]
                    )
                ])
                description = result.content
                self._image_cache.set(image_data, description, image_name)
                return description

            from io import BytesIO
            from PIL import Image, UnidentifiedImageError
            # Try to load and validate the image with PIL
            try:
                bio = BytesIO(image_data)
                bio.seek(0)
                image = Image.open(bio)
                # Force load the image to validate it
                image.load()
                # Get format directly from PIL
                image_format = image.format.lower() if image.format else "png"
            except UnidentifiedImageError:
                logger.warning(f"PIL cannot identify the image format for {image_name}")
                return f"[Could not identify image format for {image_name}]"
            except Exception as img_error:
                logger.warning(f"Error loading image {image_name}: {str(img_error)}")
                return f"[Error loading image {image_name}: {str(img_error)}]"

            try:
                # Convert image to base64
                buffer = BytesIO()
                image.save(buffer, format=image_format.upper())
                buffer.seek(0)
                base64_string = base64.b64encode(buffer.read()).decode('utf-8')
            except Exception as conv_error:
                logger.warning(f"Error converting image {image_name}: {str(conv_error)}")
                return f"[Error converting image {image_name}: {str(conv_error)}]"

            # Use default or custom prompt
            prompt = custom_prompt if custom_prompt else self._get_default_image_analysis_prompt()

            # Add context information if available
            if image_name or context_text:
                prompt += "\n\n## Additional Context Information:\n"

                if image_name:
                    prompt += f"- Image Name/Reference: {image_name}\n"

                if context_text:
                    prompt += f"- Surrounding Content: {context_text}\n"

                prompt += "\nPlease incorporate this contextual information in your description when relevant."

            # Perform LLM invocation with image
            result = llm.invoke([
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{image_format};base64,{base64_string}"},
                        },
                    ]
                )
            ])

            description = result.content

            # Cache the result for future use
            self._image_cache.set(image_data, description, image_name)

            return description
        except Exception as e:
            logger.error(f"Error processing image with LLM: {str(e)}")
            return f"[Image processing error: {str(e)}]"

    def get_page_with_image_descriptions(self, page_id: str, prompt: Optional[str] = None, context_radius: int = 500):
        """
        Get a Confluence page and augment any images in it with textual descriptions that include
        image names and contextual information from surrounding text.

        This method will:
        1. Extract the specified page content from Confluence
        2. Detect images in the content (both attachments and embedded/linked images)
        3. Retrieve and process each image with an LLM, providing surrounding context
        4. Replace image references with the generated text descriptions

        Args:
            page_id: The Confluence page ID to retrieve
            prompt: Custom prompt for the LLM when analyzing images. If None, a default prompt will be used.
            context_radius: Number of characters to include before and after each image for context. Default is 500.

        Returns:
            The page content with image references replaced with contextual descriptions
        """
        try:
            # Get the page content
            page = self.client.get_page_by_id(page_id, expand="body.storage")
            if not page:
                return f"Page with ID {page_id} not found."

            page_title = page['title']
            page_content = page['body']['storage']['value']

            # Regular expressions to find different types of image references in Confluence markup:

            # 1. Attachment-based images - <ac:image><ri:attachment ri:filename="image.png" /></ac:image>
            attachment_image_pattern = r'<ac:image[^>]*>(?:.*?)<ri:attachment ri:filename="([^"]+)"[^>]*/>(?:.*?)</ac:image>'

            # 2. URL-based images - <ac:image><ri:url ri:value="http://example.com/image.png" /></ac:image>
            url_image_pattern = r'<ac:image[^>]*>(?:.*?)<ri:url ri:value="([^"]+)"[^>]*/>(?:.*?)</ac:image>'

            # 3. Base64 embedded images - <ac:image><ac:resource>...<ac:media-type>image/png</ac:media-type><ac:data>(base64 data)</ac:data></ac:resource></ac:image>
            base64_image_pattern = r'<ac:image[^>]*>(?:.*?)<ac:resource>(?:.*?)<ac:media-type>([^<]+)</ac:media-type>(?:.*?)<ac:data>([^<]+)</ac:data>(?:.*?)</ac:resource>(?:.*?)</ac:image>'

            # Process attachment-based images
            def process_attachment_image(match):
                """Process attachment-based image references and get contextual descriptions"""
                image_filename = match.group(1)
                full_match = match.group(0)  # The complete image reference

                logger.info(f"Processing attachment image reference: {image_filename}")

                try:
                    # Get the image attachment from the page
                    attachments = self.client.get_attachments_from_content(page_id)['results']
                    attachment = None

                    # Find the attachment that matches the filename
                    for att in attachments:
                        if att['title'] == image_filename:
                            attachment = att
                            break

                    if not attachment:
                        logger.warning(f"Could not find attachment for image: {image_filename}")
                        return f"[Image: {image_filename} - attachment not found]"

                    # Get the download URL and download the image
                    download_url = self.base_url.rstrip('/') + attachment['_links']['download']
                    logger.info(f"Downloading image from URL: {download_url}")
                    image_data = self._download_image(download_url)

                    if not image_data:
                        logger.error(f"Failed to download image from URL: {download_url}")
                        return f"[Image: {image_filename} - download failed]"

                    # Collect surrounding context
                    context_text = self._collect_context_for_image(page_content, full_match, context_radius)

                    # Process with LLM (will use cache if available)
                    description = self._process_image_with_llm(image_data, image_filename, context_text, prompt)
                    return f"[Image {image_filename} Description: {description}]"

                except Exception as e:
                    logger.error(f"Error processing attachment image {image_filename}: {str(e)}")
                    return f"[Image: {image_filename} - Error: {str(e)}]"

            # Process URL-based images
            def process_url_image(match):
                """Process URL-based image references and get contextual descriptions"""
                image_url = match.group(1)
                full_match = match.group(0)  # The complete image reference

                logger.info(f"Processing URL image reference: {image_url}")

                try:
                    # Extract image name from URL for better reference
                    image_name = image_url.split('/')[-1]

                    # Download the image
                    logger.info(f"Downloading image from URL: {image_url}")
                    image_data = self._download_image(image_url)

                    if not image_data:
                        logger.error(f"Failed to download image from URL: {image_url}")
                        return f"[Image: {image_name} - download failed]"

                    # Collect surrounding context
                    context_text = self._collect_context_for_image(page_content, full_match, context_radius)

                    # Process with LLM (will use cache if available)
                    description = self._process_image_with_llm(image_data, image_name, context_text, prompt)
                    return f"[Image {image_name} Description: {description}]"

                except Exception as e:
                    logger.error(f"Error processing URL image {image_url}: {str(e)}")
                    return f"[Image: {image_url} - Error: {str(e)}]"

            # Process base64 embedded images
            def process_base64_image(match):
                """Process base64 embedded image references and get contextual descriptions"""
                media_type = match.group(1)
                base64_data = match.group(2)
                full_match = match.group(0)  # The complete image reference

                logger.info(f"Processing base64 embedded image of type: {media_type}")

                try:
                    # Generate a name for the image based on media type
                    image_format = media_type.split('/')[-1]
                    image_name = f"embedded-image.{image_format}"

                    # Decode base64 data
                    try:
                        image_data = base64.b64decode(base64_data)
                    except Exception as e:
                        logger.error(f"Failed to decode base64 image data: {str(e)}")
                        return f"[Image: embedded {media_type} - decode failed]"

                    # Collect surrounding context
                    context_text = self._collect_context_for_image(page_content, full_match, context_radius)

                    # Process with LLM (will use cache if available)
                    description = self._process_image_with_llm(image_data, image_name, context_text, prompt)
                    return f"[Image {image_name} Description: {description}]"

                except Exception as e:
                    logger.error(f"Error processing base64 image: {str(e)}")
                    return f"[Image: embedded {media_type} - Error: {str(e)}]"

            # Replace each type of image reference with its description
            processed_content = page_content

            # 1. Process attachment-based images
            processed_content = re.sub(attachment_image_pattern, process_attachment_image, processed_content)

            # 2. Process URL-based images
            processed_content = re.sub(url_image_pattern, process_url_image, processed_content)

            # 3. Process base64 embedded images
            processed_content = re.sub(base64_image_pattern, process_base64_image, processed_content)

            # Convert HTML to markdown for easier readability
            try:
                augmented_markdown = markdownify(processed_content, heading_style="ATX")
                return f"Page '{page_title}' (ID: {page_id}) with image descriptions:\n\n{augmented_markdown}"
            except Exception as e:
                logger.warning(f"Failed to convert to markdown: {str(e)}. Returning HTML content.")
                # If markdownify fails, return the processed HTML
                return f"Page '{page_title}' (ID: {page_id}) with image descriptions:\n\n{processed_content}"

        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Error processing page with images: {stacktrace}")
            return f"Error processing page with images: {str(e)}"
    
    def get_page_attachments(self, page_id: str, max_content_length: int = 10000, custom_prompt: str = None, allowed_extensions: Optional[List[str]] = None, name_pattern: Optional[str] = None):
        """
        Retrieve all attachments for a Confluence page, including core metadata (with creator, created, updated), comments,
        file content, and LLM-based analysis for supported types.
        Returns a list of dicts, each with keys: metadata, comments, content, llm_analysis.
        """
        try:
            attachments = self.client.get_attachments_from_content(page_id)
            if not attachments or not attachments.get('results'):
                return f"No attachments found for page ID {page_id}."

            # Get attachment history for created/updated info
            history_map = {}
            for attachment in attachments['results']:
                try:
                    hist = self.client.history(attachment['id'])
                    history_map[attachment['id']] = hist
                except Exception as e:
                    logger.warning(f"Failed to fetch history for attachment {attachment.get('title', '')}: {str(e)}")
                    history_map[attachment['id']] = None

            import re
            results = []
            for attachment in attachments['results']:
                title = attachment.get('title', '')
                file_ext = title.lower().split('.')[-1] if '.' in title else ''

                # Filter by allowed_extensions
                if allowed_extensions and file_ext not in allowed_extensions:
                    continue
                # Filter by name_pattern
                if name_pattern and not re.match(name_pattern, title):
                    continue

                media_type = attachment.get('metadata', {}).get('mediaType', '')
                # Core metadata extraction with history
                hist = history_map.get(attachment['id']) or {}
                created_by = hist.get('createdBy', {}).get('displayName', '') if hist else attachment.get('creator', {}).get('displayName', '')
                created_date = hist.get('createdDate', '') if hist else attachment.get('created', '')
                last_updated = hist.get('lastUpdated', {}).get('when', '') if hist else ''
                metadata = {
                    'name': title,
                    'size': attachment.get('extensions', {}).get('fileSize', None),
                    'creator': created_by,
                    'created': created_date,
                    'updated': last_updated,
                    'media_type': media_type,
                    'labels': [label['name'] for label in attachment.get('metadata', {}).get('labels', {}).get('results', [])],
                    'download_url': self.base_url.rstrip('/') + attachment['_links']['download'] if attachment.get('_links', {}).get('download') else None
                }

                # Fetch comments for the attachment
                comments = []
                try:
                    comments_response = self.client.get_comments_for_attachment(attachment['id'])
                    if comments_response and 'results' in comments_response:
                        for comment in comments_response['results']:
                            comments.append({
                                'id': comment.get('id'),
                                'author': comment.get('creator', {}).get('displayName', ''),
                                'created': comment.get('created', ''),
                                'body': comment.get('body', {}).get('storage', {}).get('value', '')
                            })
                except Exception as e:
                    logger.warning(f"Failed to fetch comments for attachment {title}: {str(e)}")

                content = None
                llm_analysis = None
                download_url = self.base_url.rstrip('/') + attachment['_links']['download']

                # --- Begin: Raw content for xml, json, markdown, txt ---
                is_text_type = (
                    media_type in [
                        'application/xml', 'text/xml',
                        'application/json', 'text/json',
                        'text/markdown', 'text/x-markdown',
                        'text/plain', 'text/csv',
                        'text/html', 'image/svg+xml',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel.sheet.macroEnabled.12',
                        'application/csv', 'application/x-csv',
                        'text/x-csv',
                        'application/doc',  'application/docx',
                        'application/xls', 'application/xlsx',
                        'application/svg', 'application/html',
                        'application/octet-stream'
                    ]
                    or file_ext in [
                        'xml', 'json', 'md', 'markdown', 'txt',
                        'csv', 'xls', 'xlsx', 'svg', 'html', 'htm', 'doc', 'docx'
                    ]
                )
                if is_text_type:
                    try:
                        resp = self.client.request(method="GET", path=download_url[len(self.base_url):], advanced_mode=True)
                        if resp.status_code == 200:
                            # Try utf-8, fallback to latin1
                            try:
                                content = resp.content.decode('utf-8')
                            except UnicodeDecodeError:
                                content = resp.content.decode('latin1')
                        else:
                            content = f"[Failed to download: HTTP {resp.status_code}]"
                    except Exception as e:
                        content = f"[Error downloading content: {str(e)}]"

                    # For some types, try to extract text if possible
                    if file_ext in ['doc', 'docx']:
                        try:
                            import io
                            if file_ext == 'docx':
                                try:
                                    from docx import Document as DocxDocument
                                    docx_file = io.BytesIO(resp.content)
                                    doc = DocxDocument(docx_file)
                                    paragraphs = [p.text for p in doc.paragraphs]
                                    content = '\n'.join(paragraphs)
                                except Exception as e:
                                    content = f"[Error extracting docx: {str(e)}]"
                            elif file_ext == 'doc':
                                try:
                                    import textract
                                    content = textract.process(None, extension='doc', input_data=resp.content).decode('utf-8')
                                except Exception as e:
                                    content = f"[Error extracting doc: {str(e)}]"
                        except ImportError:
                            content = "[python-docx or textract not installed for doc/docx extraction]"
                    elif file_ext in ['csv']:
                        try:
                            import io
                            import csv
                            csv_file = io.StringIO(content)
                            reader = csv.reader(csv_file)
                            content = '\n'.join([', '.join(row) for row in reader])
                        except Exception as e:
                            content = f"[Error extracting csv: {str(e)}]"
                    elif file_ext in ['xls', 'xlsx']:
                        try:
                            import io
                            import pandas as pd
                            excel_file = io.BytesIO(resp.content)
                            df = pd.read_excel(excel_file, sheet_name=None)
                            content = ''
                            for sheet, data in df.items():
                                content += f"\n--- Sheet: {sheet} ---\n"
                                content += data.to_csv(index=False)
                        except Exception as e:
                            content = f"[Error extracting xls/xlsx: {str(e)}]"
                    elif file_ext in ['svg'] or media_type == 'image/svg+xml':
                        # SVG is XML, so just return as text
                        pass
                    elif file_ext in ['html', 'htm'] or media_type in ['text/html', 'application/html']:
                        try:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(content, 'html.parser')
                            content = soup.get_text(separator=' ', strip=True)
                        except Exception as e:
                            content = f"[Error extracting html: {str(e)}]"

                    # Truncate content if longer than max_content_length
                    if content and isinstance(content, str) and len(content) > max_content_length:
                        content = content[:max_content_length] + f"\n...[truncated, showing first {max_content_length} characters]"

                    # No LLM analysis for these types
                    results.append({
                        'metadata': metadata,
                        'comments': comments,
                        'content': content,
                        'llm_analysis': llm_analysis
                    })
                    continue
                # --- End: Raw content for xml, json, markdown, txt ---

                # Download content for supported types
                if media_type.startswith('image/') or media_type == 'application/pdf' or media_type.startswith('application/vnd.jgraph.mxfile'):
                    if media_type == 'application/pdf':
                        try:
                            from pdf2image import convert_from_bytes
                        except ImportError:
                            logger.warning("pdf2image is not installed. Please install it to process PDF attachments.")
                            llm_analysis = '[pdf2image not installed]'
                            image_data = None
                        else:
                            image_data = self._download_image(download_url)
                            if image_data:
                                try:
                                    pdf_images = convert_from_bytes(image_data)
                                    llm_analysis = []
                                    for idx, img in enumerate(pdf_images):
                                        from io import BytesIO
                                        img_buffer = BytesIO()
                                        img.save(img_buffer, format='PNG')
                                        img_buffer.seek(0)
                                        page_context = f"Attachment: {title} (type: {media_type}, page {idx+1})"
                                        page_analysis = self._process_image_with_llm(img_buffer.getvalue(), f"{title} (page {idx+1})", page_context, custom_prompt)
                                        llm_analysis.append(page_analysis)
                                    llm_analysis = '\n'.join(llm_analysis)
                                except Exception as e:
                                    logger.error(f"Failed to process PDF pages: {str(e)}")
                                    llm_analysis = f"[Error processing PDF: {str(e)}]"
                            else:
                                content = None
                                llm_analysis = None
                    elif media_type.startswith('application/vnd.jgraph.mxfile'):
                        # Handle drawio (mxfile): base64 decode & decompress, then run LLM
                        image_data = self._download_image(download_url)
                        if image_data:
                            try:
                                import xml.etree.ElementTree as ET
                                import base64
                                import zlib
                                xml_str = image_data.decode("utf-8")
                                root = ET.fromstring(xml_str)
                                diagram_node = root.find("diagram")
                                if diagram_node is not None and diagram_node.text:
                                    diagram_base64 = diagram_node.text
                                else:
                                    diagram_base64 = None

                                compressed = base64.b64decode(diagram_base64)
                                xml_bytes = zlib.decompress(compressed, -15)
                                xml_string = xml_bytes.decode('utf-8')

                                # Use LLM to analyze the diagram XML string as text
                                context_text = f"Attachment: {title} (type: {media_type})\nDrawio XML Content: {xml_string[:2000]}"  # Limit context for LLM
                                llm_analysis = self._process_image_with_llm(b"", title, context_text, custom_prompt)  # Pass empty image, just analyze text
                            except Exception as e:
                                logger.error(f"Failed to convert drawio to image: {str(e)}")
                                llm_analysis = f"[Error processing drawio: {str(e)}]"
                        else:
                            content = None
                            llm_analysis = None
                    else:
                        image_data = self._download_image(download_url)
                        if image_data:
                            context_text = f"Attachment: {title} (type: {media_type})"
                            llm_analysis = self._process_image_with_llm(image_data, title, context_text, custom_prompt)

                if llm_analysis and isinstance(llm_analysis, str) and len(llm_analysis) > max_content_length:
                    llm_analysis = llm_analysis[:max_content_length] + f"\n...[truncated, showing first {max_content_length} characters]"

                results.append({
                    'metadata': metadata,
                    'comments': comments,
                    'content': content,
                    'llm_analysis': llm_analysis
                })
            return results
        except Exception as e:
            logger.error(f"Error retrieving attachments for page {page_id}: {str(e)}")
            return f"Error retrieving attachments: {str(e)}"

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            "content_format": (Literal['view', 'storage', 'export_view', 'editor', 'anonymous'],
                            Field(description="The format of the content to be retrieved.", default='view')),
            "page_ids": (Optional[List[str]], Field(description="List of page IDs to retrieve.", default=None)),
            "label": (Optional[str], Field(description="Label to filter pages.", default=None)),
            "cql": (Optional[str], Field(description="CQL query to filter pages.", default=None)),
            "limit": (Optional[int], Field(description="Limit the number of results.", default=10)),
            "max_pages": (Optional[int], Field(description="Maximum number of pages to retrieve.", default=1000)),
            "include_restricted_content": (Optional[bool], Field(description="Include restricted content.", default=False)),
            "include_archived_content": (Optional[bool], Field(description="Include archived content.", default=False)),
            "include_attachments": (Optional[bool], Field(description="Include attachments.", default=False)),
            'include_extensions': (Optional[List[str]], Field(
                description="List of file extensions to include when processing attachments: i.e. ['*.png', '*.jpg']. "
                            "If empty, all files will be processed (except skip_extensions).",
                default=[])),
            'skip_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing attachments: i.e. ['*.png', '*.jpg']",
                default=[])),
            "include_comments": (Optional[bool], Field(description="Include comments.", default=False)),
            "include_labels": (Optional[bool], Field(description="Include labels.", default=False)),
            "ocr_languages": (Optional[str], Field(description="OCR languages for processing attachments.", default='eng')),
            "keep_markdown_format": (Optional[bool], Field(description="Keep the markdown format.", default=True)),
            "keep_newlines": (Optional[bool], Field(description="Keep newlines in the content.", default=True)),
            "bins_with_llm": (Optional[bool], Field(description="Use LLM for processing binary files.", default=False)),
        }

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "create_page",
                "ref": self.create_page,
                "description": self.create_page.__doc__,
                "args_schema": createPage,
            },
            {
                "name": "create_pages",
                "ref": self.create_pages,
                "description": self.create_pages.__doc__,
                "args_schema": createPages,
            },
            {
                "name": "delete_page",
                "ref": self.delete_page,
                "description": self.delete_page.__doc__,
                "args_schema": deletePage,
            },
            {
                "name": "update_page_by_id",
                "ref": self.update_page_by_id,
                "description": self.update_page_by_id.__doc__,
                "args_schema": updatePageById,
            },
            {
                "name": "update_page_by_title",
                "ref": self.update_page_by_title,
                "description": self.update_page_by_title.__doc__,
                "args_schema": updatePageByTitle,
            },
            {
                "name": "update_pages",
                "ref": self.update_pages,
                "description": self.update_pages.__doc__,
                "args_schema": updatePages,
            },
            {
                "name": "update_labels",
                "ref": self.update_labels,
                "description": self.update_labels.__doc__,
                "args_schema": updateLabels,
            },
            {
                "name": "get_page_tree",
                "ref": self.get_page_tree,
                "description": self.get_page_tree.__doc__,
                "args_schema": getPageTree,
            },
            # {
            #     "name": "page_exists",
            #     "ref": self.page_exists,
            #     "description": self.page_exists.__doc__,
            #     "args_schema": pageExists,
            # },
            {
                "name": "get_pages_with_label",
                "ref": self.get_pages_with_label,
                "description": self.get_pages_with_label.__doc__,
                "args_schema": getPagesWithLabel,
            },
            {
                "name": "list_pages_with_label",
                "ref": self.list_pages_with_label,
                "description": self.list_pages_with_label.__doc__,
                "args_schema": getPagesWithLabel,
            },
            {
                "name": "read_page_by_id",
                "ref": self.read_page_by_id,
                "description": self.read_page_by_id.__doc__,
                "args_schema": pageId,
            },
            {
                "name": "search_pages",
                "ref": self.search_pages,
                "description": self.search_pages.__doc__,
                "args_schema": searchPages,
            },
            {
                "name": "search_by_title",
                "ref": self.search_by_title,
                "description": self.search_by_title.__doc__,
                "args_schema": searchPages,
            },
            {
                "name": "site_search",
                "ref": self.site_search,
                "description": self.site_search.__doc__,
                "args_schema": siteSearch,
            },
            {
                "name": "get_page_with_image_descriptions",
                "ref": self.get_page_with_image_descriptions,
                "description": self.get_page_with_image_descriptions.__doc__,
                "args_schema": GetPageWithImageDescriptions,
            },
            {
                "name": "execute_generic_confluence",
                "description": self.execute_generic_confluence.__doc__,
                "args_schema": сonfluenceInput,
                "ref": self.execute_generic_confluence,
            },
            {
                "name": "get_page_id_by_title",
                "ref": self.get_page_id_by_title,
                "description": self.get_page_id_by_title.__doc__,
                "args_schema": getPageIdByTitleInput,
            },
            {
                "name": "get_page_attachments",
                "ref": self.get_page_attachments,
                "description": self.get_page_attachments.__doc__,
                "args_schema": GetPageAttachmentsInput,
            }
        ]