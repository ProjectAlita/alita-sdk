import hashlib
import logging
import re
import requests
from typing import Generator, Literal, Optional

from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsServiceError
from azure.devops.v7_0.core import CoreClient
from azure.devops.v7_0.wiki import WikiClient, WikiPageCreateOrUpdateParameters, WikiCreateParametersV2, \
    WikiPageMoveParameters
from azure.devops.v7_0.wiki.models import GitVersionDescriptor
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from msrest.authentication import BasicAuthentication
from pydantic import create_model, PrivateAttr, SecretStr, BaseModel
from pydantic import model_validator
from pydantic.fields import Field

import alita_sdk.tools.ado.work_item
from ..repos import ReposApiWrapper
from ...non_code_indexer_toolkit import NonCodeIndexerToolkit
from ...utils.available_tools_decorator import extend_with_parent_available_tools
from ...utils.content_parser import parse_file_content
from ....runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

GetWikiInput = create_model(
    "GetWikiInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name"))
)

GetPageByPathInput = create_model(
    "GetPageByPathInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_name=(str, Field(description="Wiki page path")),
    image_description_prompt=(Optional[str],
                              Field(description="Prompt which is used for image description", default=None))
)

GetPageByIdInput = create_model(
    "GetPageByIdInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_id=(int, Field(description="Wiki page ID")),
    image_description_prompt=(Optional[str],
                              Field(description="Prompt which is used for image description", default=None))
)


class GetPageInput(BaseModel):
    """Input schema for get_wiki_page tool with validation."""
    wiki_identified: str = Field(description="Wiki ID or wiki name")
    page_path: Optional[str] = Field(default=None, description="Wiki page path (e.g., '/MB_Heading/MB_2')")
    page_id: Optional[int] = Field(default=None, description="Wiki page ID")
    include_content: Optional[bool] = Field(default=False, description="Whether to include page content in the response. If True, content will be processed for image descriptions.")
    image_description_prompt: Optional[str] = Field(default=None, description="Prompt which is used for image description when include_content is True")

    @model_validator(mode='before')
    @classmethod
    def validate_inputs(cls, values):
        """Validator to ensure at least one of page_path or page_id is provided."""
        page_path = values.get('page_path')
        page_id = values.get('page_id')
        if not page_path and not page_id:
            raise ValueError("At least one of 'page_path' or 'page_id' must be provided")
        return values


ModifyPageInput = create_model(
    "ModifyPageInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_name=(str, Field(description="Wiki page name")),
    page_content=(str, Field(description="Wiki page content")),
    version_identifier=(str, Field(description="Version string identifier (name of tag/branch, SHA1 of commit). Usually for wiki the branch is 'wikiMaster'")),
    version_type=(Optional[str], Field(description="Version type (branch, tag, or commit). Determines how Id is interpreted", default="branch")),
    expanded=(Optional[bool], Field(description="Whether to return the full page object or just its simplified version.", default=False))
)

RenamePageInput = create_model(
    "RenamePageInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    old_page_name=(str, Field(description="Old Wiki page name to be renamed", examples= ["/TestPageName"])),
    new_page_name=(str, Field(description="New Wiki page name", examples= ["/RenamedName"])),
    version_identifier=(str, Field(description="Version string identifier (name of tag/branch, SHA1 of commit)")),
    version_type=(Optional[str], Field(description="Version type (branch, tag, or commit). Determines how Id is interpreted", default="branch"))
)


def _format_wiki_page_response(wiki_page_response, expanded: bool = False, include_content: bool = False):
    """Format wiki page response.

    Args:
        wiki_page_response: The WikiPageResponse object from Azure DevOps API
        expanded: If True, returns comprehensive page metadata. If False, returns simplified format.
        include_content: If True and expanded=True, includes the page content in the response.

    Returns:
        Dictionary with eTag and page information. Format depends on expanded parameter.
    """
    try:
        if expanded:
            # Comprehensive metadata format
            page = wiki_page_response.page
            result = {
                'eTag': wiki_page_response.eTag,
                'page': {
                    'id': page.id if page else None,
                    'path': page.path if page else None,
                    'git_item_path': page.git_item_path if page and hasattr(page, 'git_item_path') else None,
                    'remote_url': page.remote_url if page and hasattr(page, 'remote_url') else None,
                    'url': page.url if page else None,
                    'order': page.order if page and hasattr(page, 'order') else None,
                    'is_parent_page': page.is_parent_page if page and hasattr(page, 'is_parent_page') else None,
                    'is_non_conformant': page.is_non_conformant if page and hasattr(page, 'is_non_conformant') else None,
                    'sub_pages': page.sub_pages if page and hasattr(page, 'sub_pages') else [],
                }
            }
            # Include content if requested
            if include_content and page and hasattr(page, 'content'):
                result['page']['content'] = page.content
            return result
        else:
            # Simplified format for backward compatibility
            return {
                "eTag": wiki_page_response.eTag,
                "id": wiki_page_response.page.id,
                "page": wiki_page_response.page.url
            }
    except Exception as e:
        logger.error(f"Unable to format wiki page response: {wiki_page_response}, error: {str(e)}")
        return wiki_page_response


class AzureDevOpsApiWrapper(NonCodeIndexerToolkit):
    # TODO use ado_configuration instead of organization_url, project and token
    organization_url: str
    project: str
    token: SecretStr
    _client: Optional[WikiClient] = PrivateAttr()  # Private attribute for the wiki client
    _core_client: Optional[CoreClient] = PrivateAttr()  # Private attribute for the CoreClient client

    class Config:
        arbitrary_types_allowed = True  # Allow arbitrary types (e.g., WorkItemTrackingClient)

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """Validate and set up the Azure DevOps client."""
        try:
            # Set up connection to Azure DevOps using Personal Access Token (PAT)
            credentials = BasicAuthentication('', values['token'])
            connection = Connection(base_url=values['organization_url'], creds=credentials)

            # Retrieve the work item tracking client and assign it to the private _client attribute
            cls._client = connection.clients.get_wiki_client()
            cls._core_client = connection.clients.get_core_client()

        except Exception as e:
            error_msg = str(e).lower()
            if "expired" in error_msg or "token" in error_msg and ("invalid" in error_msg or "unauthorized" in error_msg):
                raise ValueError(
                    "Azure DevOps connection failed: Your access token has expired or is invalid. "
                    "Please refresh your token in the toolkit configuration."
                )
            elif "401" in error_msg or "unauthorized" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Authentication failed. "
                    "Please check your credentials in the toolkit configuration."
                )
            elif "404" in error_msg or "not found" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Organization or project not found. "
                    "Please verify your organization URL and project name."
                )
            elif "timeout" in error_msg or "timed out" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Connection timed out. "
                    "Please check your network connection and try again."
                )
            else:
                raise ValueError(f"Azure DevOps connection failed: {e}")

        return super().validate_toolkit(values)

    def get_wiki(self, wiki_identified: str):
        """Extract ADO wiki information."""
        try:
            return self._client.get_wiki(project=self.project, wiki_identifier=wiki_identified)
        except Exception as e:
            logger.error(f"Error during the attempt to extract wiki: {str(e)}")
            return ToolException(f"Error during the attempt to extract wiki: {str(e)}")

    def get_wiki_page_by_path(self, wiki_identified: str, page_name: str, image_description_prompt=None):
        """Extract ADO wiki page content."""
        try:
            return self._process_images(self._client.get_page(project=self.project, wiki_identifier=wiki_identified, path=page_name,
                                         include_content=True).page.content,
                                        image_description_prompt=image_description_prompt)
        except Exception as e:
            logger.error(f"Error during the attempt to extract wiki page: {str(e)}")
            return ToolException(f"Error during the attempt to extract wiki page: {str(e)}")

    def get_wiki_page_by_id(self, wiki_identified: str, page_id: int, image_description_prompt=None):
        """Extract ADO wiki page content."""
        try:
            return self._process_images(self._client.get_page_by_id(project=self.project, wiki_identifier=wiki_identified, id=page_id,
                                                include_content=True).page.content,
                                        image_description_prompt=image_description_prompt)
        except Exception as e:
            logger.error(f"Error during the attempt to extract wiki page: {str(e)}")
            return ToolException(f"Error during the attempt to extract wiki page: {str(e)}")

    def get_wiki_page(self, wiki_identified: str, page_path: Optional[str] = None, page_id: Optional[int] = None,
                      include_content: bool = False, image_description_prompt: Optional[str] = None):
        """Get wiki page metadata and optionally content.

        Retrieves comprehensive metadata for a wiki page including eTag, id, path, git_item_path,
        remote_url, url, sub_pages, order, and other properties. Optionally includes page content.
        Supports lookup by either page_id (takes precedence) or page_path.

        Args:
            wiki_identified: Wiki ID or wiki name
            page_path: Wiki page path (e.g., '/MB_Heading/MB_2'). Optional if page_id is provided.
            page_id: Wiki page ID. Optional if page_path is provided. Takes precedence over page_path.
            include_content: Whether to include page content in response. Defaults to False (metadata only).
            image_description_prompt: Optional prompt for image description when include_content is True.

        Returns:
            Dictionary containing eTag and comprehensive page metadata including id, path, git_item_path,
            remote_url, url, sub_pages, order, is_parent_page, is_non_conformant, and optionally content.

        Raises:
            ToolException: If page/wiki not found, authentication fails, or other errors occur.
        """
        try:
            # Validate that at least one identifier is provided
            if not page_path and not page_id:
                raise ToolException("At least one of 'page_path' or 'page_id' must be provided")

            # Fetch page using page_id (priority) or page_path
            if page_id:
                logger.info(f"Fetching wiki page by ID: {page_id} from wiki: {wiki_identified}")
                wiki_page_response = self._client.get_page_by_id(
                    project=self.project,
                    wiki_identifier=wiki_identified,
                    id=page_id,
                    include_content=include_content
                )
            else:
                logger.info(f"Fetching wiki page by path: {page_path} from wiki: {wiki_identified}")
                wiki_page_response = self._client.get_page(
                    project=self.project,
                    wiki_identifier=wiki_identified,
                    path=page_path,
                    include_content=include_content
                )

            # Format response with comprehensive metadata
            result = _format_wiki_page_response(
                wiki_page_response,
                expanded=True,
                include_content=include_content
            )

            # Process images in content if requested
            if include_content and result.get('page', {}).get('content'):
                processed_content = self._process_images(
                    result['page']['content'],
                    image_description_prompt=image_description_prompt
                )
                result['page']['content'] = processed_content

            return result

        except AzureDevOpsServiceError as e:
            error_msg = str(e).lower()

            # Page not found errors
            if "404" in error_msg or "not found" in error_msg or "does not exist" in error_msg:
                identifier = f"ID {page_id}" if page_id else f"path '{page_path}'"
                logger.error(f"Page {identifier} not found in wiki '{wiki_identified}': {str(e)}")
                return ToolException(
                    f"Page {identifier} not found in wiki '{wiki_identified}'. "
                    f"Please verify the page exists and the identifier is correct."
                )

            # Path validation errors
            elif "path" in error_msg and ("correct" in error_msg or "invalid" in error_msg):
                logger.error(f"Invalid page path '{page_path}' in wiki '{wiki_identified}': {str(e)}")
                return ToolException(
                    f"Invalid page path '{page_path}'. Please ensure the path format is correct (e.g., '/PageName')."
                )

            # Wiki not found errors
            elif "wiki" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
                logger.error(f"Wiki '{wiki_identified}' not found: {str(e)}")
                return ToolException(
                    f"Wiki '{wiki_identified}' not found. Please verify the wiki identifier is correct."
                )

            # Authentication/authorization errors
            elif "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
                logger.error(f"Authentication failed for wiki '{wiki_identified}': {str(e)}")
                return ToolException(
                    f"Authentication failed. Please check your access token is valid and has permission to access wiki '{wiki_identified}'."
                )

            elif "403" in error_msg or "forbidden" in error_msg or "permission" in error_msg:
                logger.error(f"Permission denied for wiki '{wiki_identified}': {str(e)}")
                return ToolException(
                    f"Permission denied. You do not have access to wiki '{wiki_identified}' or page {page_id if page_id else page_path}."
                )

            # Generic Azure DevOps service errors
            else:
                logger.error(f"Azure DevOps service error while fetching page: {str(e)}")
                return ToolException(f"Error accessing wiki page: {str(e)}")

        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            return ToolException(f"Validation error: {str(e)}")

        except Exception as e:
            error_msg = str(e).lower()

            # Timeout errors
            if "timeout" in error_msg or "timed out" in error_msg:
                logger.error(f"Connection timeout while fetching page: {str(e)}")
                return ToolException(
                    f"Connection timeout. Please check your network connection and try again."
                )

            # Generic errors
            logger.error(f"Unexpected error during wiki page retrieval: {str(e)}")
            return ToolException(f"Unexpected error during wiki page retrieval: {str(e)}")

    def _process_images(self, page_content: str, image_description_prompt=None):

        image_pattern = r"!\[(.*?)\]\((.*?)\)"
        matches = re.findall(image_pattern, page_content)

        for image_name, image_url in matches:
            if image_url.startswith("/.attachments/"):
                try:
                    description = self.process_attachment(attachment_url=image_url,
                                                          attachment_name=image_name,
                                                          image_description_prompt=image_description_prompt)
                except Exception as e:
                    logger.error(f"Error parsing attachment: {str(e)}")
                    description = f"Error parsing attachment: {image_url}"
            else:
                try:
                    response = requests.get(image_url)
                    response.raise_for_status()
                    file_content = response.content
                    description = parse_file_content(
                        file_content=file_content,
                        file_name="image.png",
                        llm=self.llm,
                        prompt=image_description_prompt
                    )
                except Exception as e:
                    logger.error(f"Error fetching external image: {str(e)}")
                    description = f"Error fetching external image: image_url"

            new_image_markdown = f"![{image_name}]({description})"
            page_content = page_content.replace(f"![{image_name}]({image_url})", new_image_markdown)
        return page_content

    def process_attachment(self, attachment_url, attachment_name, image_description_prompt):
        wiki_master_branch = "wikiMaster"
        repos_wrapper = ReposApiWrapper(organization_url=self.organization_url,
                                        project=self.project,
                                        token=self.token.get_secret_value(),
                                        repository_id="Test_agent.wiki",
                                        base_branch=wiki_master_branch,
                                        active_branch=wiki_master_branch)
        attachment_content = repos_wrapper.download_file(path=attachment_url)
        return parse_file_content(
            file_content=attachment_content,
            file_name=attachment_name,
            llm=self.llm,
            prompt=image_description_prompt
        )

    def delete_page_by_path(self, wiki_identified: str, page_name: str):
        """Extract ADO wiki page content."""
        try:
            self._client.delete_page(project=self.project, wiki_identifier=wiki_identified, path=page_name)
            return f"Page '{page_name}' in wiki '{wiki_identified}' has been deleted"
        except Exception as e:
            logger.error(f"Unable to delete wiki page: {str(e)}")
            return ToolException(f"Unable to delete wiki page: {str(e)}")

    def delete_page_by_id(self, wiki_identified: str, page_id: str):
        """Extract ADO wiki page content."""
        try:
            self._client.delete_page_by_id(project=self.project, wiki_identifier=wiki_identified, id=page_id)
            return f"Page with id '{page_id}' in wiki '{wiki_identified}' has been deleted"
        except Exception as e:
            logger.error(f"Unable to delete wiki page: {str(e)}")
            return ToolException(f"Unable to delete wiki page: {str(e)}")

    def rename_wiki_page(self, wiki_identified: str, old_page_name: str, new_page_name: str, version_identifier: str,
                         version_type: str = "branch"):
        """Rename page

        Args:
         wiki_identified (str): The identifier for the wiki.
         old_page_name (str): The current name of the page to be renamed (e.g. '/old_page_name').
         new_page_name (str): The new name for the page (e.g. '/new_page_name').
         version_identifier (str): The identifier for the version (e.g., branch or commit). Defaults to None.
         version_type (str, optional): The type of version identifier. Defaults to "branch".
     """

        try:
            try:
                return self._client.create_page_move(
                    project=self.project,
                    wiki_identifier=wiki_identified,
                    comment=f"Page rename from '{old_page_name}' to '{new_page_name}'",
                    page_move_parameters=WikiPageMoveParameters(new_path=new_page_name, path=old_page_name),
                    version_descriptor=GitVersionDescriptor(version=version_identifier, version_type=version_type)
                )
            except AzureDevOpsServiceError as e:
                if "The version '{0}' either is invalid or does not exist." in str(e):
                    # Retry the request without version_descriptor
                    return self._client.create_page_move(
                        project=self.project,
                        wiki_identifier=wiki_identified,
                        comment=f"Page rename from '{old_page_name}' to '{new_page_name}'",
                        page_move_parameters=WikiPageMoveParameters(new_path=new_page_name, path=old_page_name),
                    )
                else:
                    raise
        except Exception as e:
            logger.error(f"Unable to rename wiki page: {str(e)}")
            return ToolException(f"Unable to rename wiki page: {str(e)}")

    def modify_wiki_page(self, wiki_identified: str, page_name: str, page_content: str, version_identifier: str, version_type: str = "branch", expanded: Optional[bool] = False):
        """Create or Update ADO wiki page content."""
        try:
            all_wikis = [wiki.name for wiki in self._client.get_all_wikis(project=self.project)]
            if wiki_identified not in all_wikis:
                logger.info(f"wiki name '{wiki_identified}' doesn't exist. New wiki will be created.")
                try:
                    project_id = None
                    projects = self._core_client.get_projects()

                    for project in projects:
                        if project.name == self.project:
                            project_id = project.id
                            break
                    if project_id:
                        self._client.create_wiki(project=self.project, wiki_create_params=WikiCreateParametersV2(name=wiki_identified, project_id=project_id))
                    else:
                        return "Project ID has not been found."
                except Exception as create_wiki_e:
                    return ToolException(f"Unable to create new wiki due to error: {create_wiki_e}")
            try:
                page = self._client.get_page(project=self.project, wiki_identifier=wiki_identified, path=page_name)
                version = page.eTag
            except Exception as get_page_e:
                if "Ensure that the path of the page is correct and the page exists" in str(get_page_e):
                    logger.info("Path is not found. New page will be created")
                    version = None
                else:
                    return ToolException(f"Unable to extract page by path {page_name}: {str(get_page_e)}")

            try:
                return _format_wiki_page_response(self._client.create_or_update_page(
                    project=self.project,
                    wiki_identifier=wiki_identified,
                    path=page_name,
                    parameters=WikiPageCreateOrUpdateParameters(content=page_content),
                    version=version,
                    version_descriptor=GitVersionDescriptor(version=version_identifier, version_type=version_type)
                ), expanded=expanded)
            except AzureDevOpsServiceError as e:
                if "The version '{0}' either is invalid or does not exist." in str(e):
                    # Retry the request without version_descriptor
                    return _format_wiki_page_response(wiki_page_response=self._client.create_or_update_page(
                        project=self.project,
                        wiki_identifier=wiki_identified,
                        path=page_name,
                        parameters=WikiPageCreateOrUpdateParameters(content=page_content),
                        version=version
                    ), expanded=expanded)
                else:
                    raise
        except Exception as e:
            logger.error(f"Unable to modify wiki page: {str(e)}")
            return ToolException(f"Unable to modify wiki page: {str(e)}")

    def _base_loader(self, wiki_identifier: str, chunking_tool: str = None, title_contains: Optional[str] = None, **kwargs) -> Generator[Document, None, None]:
        pages = self._client.get_pages_batch(pages_batch_request={}, project=self.project, wiki_identifier=wiki_identifier)
        #
        for page in pages:
            content = self._client.get_page_by_id(project=self.project, wiki_identifier=wiki_identifier, id=page.id, include_content=True).page.content
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            title = page.path.rsplit("/", 1)[-1]
            if not title_contains or (title_contains and title_contains.lower() in title.lower()):
                if chunking_tool:
                    yield Document(page_content='', metadata={
                        'id': str(page.id),
                        'path': page.path,
                        'title': title,
                        'updated_on': content_hash,
                        IndexerKeywords.CONTENT_IN_BYTES.value: content.encode("utf-8")
                    })
                else:
                    yield Document(page_content=content, metadata={
                        'id': str(page.id),
                        'path': page.path,
                        'title': title,
                        'updated_on': content_hash
                    })

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            'chunking_tool': (Literal['markdown', ''], Field(description="Name of chunking tool", default='markdown')),
            "wiki_identifier": (str, Field(description="Wiki identifier to index, e.g., 'ABCProject.wiki'")),
            'title_contains': (Optional[str], Field(default=None, description="Optional filter to include only pages with titles containing exact this string")),
        }

    @extend_with_parent_available_tools
    def get_available_tools(self):
        """Return a list of available tools."""
        return [
            {
                "name": "get_wiki",
                "description": self.get_wiki.__doc__,
                "args_schema": GetWikiInput,
                "ref": self.get_wiki,
            },
            {
                "name": "get_wiki_page",
                "description": self.get_wiki_page.__doc__,
                "args_schema": GetPageInput,
                "ref": self.get_wiki_page,
            },
            {
                "name": "get_wiki_page_by_path",
                "description": self.get_wiki_page_by_path.__doc__,
                "args_schema": GetPageByPathInput,
                "ref": self.get_wiki_page_by_path,
            },
            {
                "name": "get_wiki_page_by_id",
                "description": self.get_wiki_page_by_id.__doc__,
                "args_schema": GetPageByIdInput,
                "ref": self.get_wiki_page_by_id,
            },
            {
                "name": "delete_page_by_path",
                "description": self.delete_page_by_path.__doc__,
                "args_schema": GetPageByPathInput,
                "ref": self.delete_page_by_path,
            },
            {
                "name": "delete_page_by_id",
                "description": self.delete_page_by_id.__doc__,
                "args_schema": GetPageByIdInput,
                "ref": self.delete_page_by_id,
            },
            {
                "name": "modify_wiki_page",
                "description": self.modify_wiki_page.__doc__,
                "args_schema": ModifyPageInput,
                "ref": self.modify_wiki_page,
            },
            {
                "name": "rename_wiki_page",
                "description": self.rename_wiki_page.__doc__,
                "args_schema": RenamePageInput,
                "ref": self.rename_wiki_page,
            }
        ]