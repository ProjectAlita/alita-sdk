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
from pydantic import create_model, PrivateAttr, SecretStr
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

ModifyPageInput = create_model(
    "ModifyPageInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    page_name=(str, Field(description="Wiki page name")),
    page_content=(str, Field(description="Wiki page content")),
    version_identifier=(str, Field(description="Version string identifier (name of tag/branch, SHA1 of commit)")),
    version_type=(Optional[str], Field(description="Version type (branch, tag, or commit). Determines how Id is interpreted", default="branch"))
)

RenamePageInput = create_model(
    "RenamePageInput",
    wiki_identified=(str, Field(description="Wiki ID or wiki name")),
    old_page_name=(str, Field(description="Old Wiki page name to be renamed", examples= ["/TestPageName"])),
    new_page_name=(str, Field(description="New Wiki page name", examples= ["/RenamedName"])),
    version_identifier=(str, Field(description="Version string identifier (name of tag/branch, SHA1 of commit)")),
    version_type=(Optional[str], Field(description="Version type (branch, tag, or commit). Determines how Id is interpreted", default="branch"))
)


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
            return ImportError(f"Failed to connect to Azure DevOps: {e}")

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

    def modify_wiki_page(self, wiki_identified: str, page_name: str, page_content: str, version_identifier: str, version_type: str = "branch"):
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
                return self._client.create_or_update_page(
                    project=self.project,
                    wiki_identifier=wiki_identified,
                    path=page_name,
                    parameters=WikiPageCreateOrUpdateParameters(content=page_content),
                    version=version,
                    version_descriptor=GitVersionDescriptor(version=version_identifier, version_type=version_type)
                )
            except AzureDevOpsServiceError as e:
                if "The version '{0}' either is invalid or does not exist." in str(e):
                    # Retry the request without version_descriptor
                    return self._client.create_or_update_page(
                        project=self.project,
                        wiki_identifier=wiki_identified,
                        path=page_name,
                        parameters=WikiPageCreateOrUpdateParameters(content=page_content),
                        version=version
                    )
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