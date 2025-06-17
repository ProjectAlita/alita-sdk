import itertools
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, Any, List, Set, Iterator

from atlassian.errors import ApiError
from langchain_community.document_loaders import ConfluenceLoader
from langchain_community.document_loaders.confluence import ContentFormat
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import model_validator, BaseModel, SecretStr
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_text_splitters import MarkdownHeaderTextSplitter
from pydantic import create_model
from pydantic.fields import Field, PrivateAttr
from atlassian import Jira

from logging import getLogger

from ..llm.llm_utils import get_model, summarize

logger = getLogger(__name__)

PrepareDataSchema = create_model(
    "PrepareDataSchema",
    jira_issue_key=(str, Field(
        description="The issue key of the Jira issue, which will be used to pull data from, e.g. 'TEST-123'.")),
)

SearchDataSchema = create_model(
    "SearchDataSchema",
    jira_issue_key=(str, Field(
        description="The issue key of the Jira issue, which will be used to pull data from, e.g. 'TEST-123'.")),
    query=(
        str,
        Field(description="The query to search in the data created from jira ticket. Usually it will be an AC")),
)


class AdvancedJiraMiningWrapper(BaseModel):
    """
    AdvancedJiraMiningWrapper is a class designed to interface with Jira and Confluence APIs,
    providing advanced mining capabilities for extracting and summarizing data.

    Attributes:
        jira_base_url (str): The base URL for the Jira instance.
        confluence_base_url (str): The base URL for the Confluence instance.
        llm_settings (dict): Settings for the language model used for summarization.
        model_type (str): The type of language model to be used.
        summarization_prompt (Optional[str]): The prompt to be used for summarization. Default is None.
        gaps_analysis_prompt (Optional[str]): The prompt to be used for gaps analysis. Default is None.
        jira_api_key (Optional[str]): The API key for accessing Jira. Default is None.
        jira_username (Optional[str]): The username for accessing Jira. Default is None.
        jira_token (Optional[str]): The token for accessing Jira. Default is None.
        is_jira_cloud (Optional[bool]): Indicates if the Jira instance is a cloud instance. Default is True.
        verify_ssl (Optional[bool]): Indicates if SSL verification should be performed. Default is True.

    Example:
        .. code-block:: python

            from alita_sdk.tools.advanced_jira_mining.data_mining_wrapper import AdvancedJiraMiningWrapper

            wrapper = AdvancedJiraMiningWrapper(
                jira_base_url="https://your-jira-instance.atlassian.net",
                confluence_base_url="https://your-confluence-instance.atlassian.net",
                llm_settings={"temperature": 0.7, "max_tokens": 150},
                model_type="Alita",
                summarization_prompt="Summarize the following Jira issues:",
                gaps_analysis_prompt="Analyze the gaps in the provided information:",
                jira_api_key="your_api_key",
                jira_username="your_username",
                jira_token="your_token",
                is_jira_cloud=True,
                verify_ssl=True
            )
    """

    jira_base_url: str
    """The base URL for the Jira instance."""

    confluence_base_url: str
    """The base URL for the Confluence instance."""

    model_type: str
    """The type of language model to be used."""

    summarization_prompt: Optional[str] = None
    """The prompt to be used for summarization. Default is None."""

    gaps_analysis_prompt: Optional[str] = None
    """The prompt to be used for gaps analysis. Default is None."""

    jira_api_key: Optional[SecretStr] = None
    """The API key for accessing Jira. Default is None."""

    jira_username: Optional[str] = None
    """The username for accessing Jira. Default is None."""

    jira_token: Optional[SecretStr] = None
    """The token for accessing Jira. Default is None."""

    is_jira_cloud: Optional[bool] = True
    """Indicates if the Jira instance is a cloud instance. Default is True."""

    verify_ssl: Optional[bool] = True
    """Indicates if SSL verification should be performed. Default is True."""

    _client: Optional[Jira] = PrivateAttr()
    _llm: Optional[Any] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        """
        Validates and initializes the toolkit for interacting with Jira and the language model.

        This function is a root validator for a Pydantic model. It ensures that the necessary
        packages are installed, validates the provided configuration values, and initializes
        the Jira client and language model.

        Parameters:
            cls (Type): The class being validated.
            values (Dict[str, Any]): The values to validate and initialize.

        Returns:
            Dict[str, Any]: The validated and initialized values.

        Raises:
            ImportError: If the `atlassian` package is not installed.
        """
        try:
            from atlassian import Jira  # noqa: F401
        except ImportError:
            raise ImportError(
                "`atlassian` package not found, please run "
                "`pip install atlassian-python-api`"
            )
        url = values['jira_base_url']
        model_type = values['model_type']
        api_key = values.get('jira_api_key')
        username = values.get('jira_username')
        token = values.get('jira_token')
        is_cloud = values.get('is_jira_cloud')
        if token:
            cls._client = Jira(url=url, token=token, cloud=is_cloud, verify_ssl=values['verify_ssl'])
        else:
            cls._client = Jira(url=url, username=username, password=api_key, cloud=is_cloud,
                               verify_ssl=values['verify_ssl'])
        cls._llm = values['llm']
        return values

    def __zip_directory(self, folder_path, output_path):
        """
        Compresses the contents of a directory into a ZIP file.

        This function compresses the contents of the specified directory, including all
        subdirectories and files, into a ZIP file. The directory structure is preserved
        within the ZIP file.

        Parameters:
            folder_path (str): The path to the directory to be compressed.
            output_path (str): The path where the output ZIP file will be saved.

        Returns:
            None
        """
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    # Create a relative path for files to keep the directory structure
                    relative_path = os.path.relpath(os.path.join(root, file), os.path.join(folder_path, '..'))
                    zipf.write(os.path.join(root, file), relative_path)

    def __fetch_jira_confluence_page_ids(self, jira_issue_key: str) -> List[str]:
        """
        Fetches Confluence page IDs linked to a Jira issue.

        This function retrieves the remote links associated with a given Jira issue key,
        filters the links to find those that point to Confluence pages, and extracts the
        Confluence page IDs from the URLs.

        Parameters:
            jira_issue_key (str): The key of the Jira issue for which to fetch Confluence page IDs, for example, TEST-12

        Returns:
            List[str]: A list of Confluence page IDs extracted from the remote links.
        """
        remote_links = self._client.get_issue_remote_links(jira_issue_key)
        confluence_remote_links = [link['object']['url'] for link in remote_links if
                                   (link['application'].get('type') is not None and
                                    link['application']['type'] == 'com.atlassian.confluence')]

        return re.findall(r'\d{4,12}', '\n'.join(confluence_remote_links), re.DOTALL)

    def __get_issues_by_jql_query(
            self,
            jql,
            fields="*all",
            start=0,
            limit=None,
            expand=None,
            validate_query=None,
    ) -> Iterator[List[dict]]:
        params = {}
        if limit is not None:
            params["maxResults"] = int(limit)
        if fields is not None:
            if isinstance(fields, (list, tuple, set)):
                fields = ",".join(fields)
            params["fields"] = fields
        if jql is not None:
            params["jql"] = jql
        if expand is not None:
            params["expand"] = expand
        if validate_query is not None:
            params["validateQuery"] = validate_query
        url = self._client.resource_url("search")

        while True:
            params["startAt"] = int(start)
            try:
                response = self._client.get(url, params=params)
                if not response:
                    break
            except ApiError as e:
                error_message = f"Jira API error: {str(e)}"
                raise ValueError(f"Failed to fetch issues from Jira: {error_message}")

            issues = response["issues"]
            yield issues
            if limit is not None and len(response["issues"]) + start >= limit:
                break
            if not response["issues"]:
                break
            start += len(issues)

    def __fetch_all_linked_jira_issue_keys(self, jira_issue_key: str) -> Set[str]:
        """
        Fetches all linked Jira issue keys that are not of type Bug, Task, or Sub-task.

        This function retrieves the issue links associated with a given Jira issue key,
        filters the links to exclude issues of type Bug, Task, or Sub-task, and returns
        a set of the remaining linked issue keys.

        Parameters:
            jira_issue_key (str): The key of the Jira issue for which to fetch linked issue keys.

        Returns:
            Set[str]: A set of linked Jira issue keys that are not of type Bug, Task, or Sub-task.
        """
        linked_issues_keys = set()
        jira_issue_type = self._client.issue(jira_issue_key, fields='issuetype')
        if jira_issue_type['fields']['issuetype']['name'] == 'Epic':
            related_issues = self.__get_issues_by_jql_query(f'parentEpic = {jira_issue_key}', fields='description')
            for issues_chunk in related_issues:
                linked_issues_keys.update({item['key'] for item in issues_chunk})
            return linked_issues_keys
        else:
            jira_issue = self._client.issue(jira_issue_key, fields='issuelinks')
            linked_links = [link for link in jira_issue['fields']['issuelinks']]
            for link in linked_links:
                if link.get('outwardIssue') is not None:
                    # Include in result set ONLY those issues, which are not of type Bug, Task, or Sub-task
                    if not (link['outwardIssue']['fields']['issuetype']['name'] in ['Bug', 'Task', 'Sub-task']):
                        linked_issues_keys.add(link['outwardIssue']['key'])
                else:
                    # Include in result set ONLY those issues, which are not of type Bug, Task, or Sub-task
                    if not (link['inwardIssue']['fields']['issuetype']['name'] in ['Bug', 'Task', 'Sub-task']):
                        linked_issues_keys.add(link['inwardIssue']['key'])
        return linked_issues_keys

    def __bulk_fetch_specific_fields_from_jira_issue_key(self, jira_issue_keys: List[str], fields="*all") -> List[dict]:
        """
        Fetches specific fields from multiple Jira issues in bulk.

        This function retrieves specific fields from multiple Jira issues using their issue keys.
        The fields to be retrieved can be specified, with the default being all fields.

        Parameters:
            jira_issue_keys (List[str]): A list of Jira issue keys for which to fetch specific fields.
            fields (str): The fields to be retrieved from the Jira issues. Default is "*all".

        Returns:
            List[dict]: A list of Jira issues with the specified fields.
        """
        issues = []
        jql = "key in ({})".format(", ".join(set(jira_issue_keys)))
        issues_generator = self.__get_issues_by_jql_query(jql=jql, fields=fields)
        for issues_chunk in issues_generator:
            issues.extend(issues_chunk)
        return issues

    def __get_all_jira_issue_keys_from_issue_description(self, jira_issue_key: str) -> List[str]:
        """
        Extracts all Jira issue keys from the description of a given Jira issue.

        This function retrieves the description of a specified Jira issue and extracts all
        Jira issue keys mentioned in the description. The extracted issue keys are returned
        as a list of unique values.

        Parameters:
            jira_issue_key (str): The key of the Jira issue from which to extract issue keys.

        Returns:
            List[str]: A list of unique Jira issue keys extracted from the issue description.
        """
        jira_issue = self._client.issue(jira_issue_key, 'description')
        description = jira_issue['fields']['description']
        return list(set(re.findall(r'[A-Z]{1,5}-\d{1,5}', description, re.DOTALL)))

    def __get_all_jira_issue_keys_from_issue_ac(self, jira_issue_key: str) -> List[str]:
        """
        Extracts all Jira issue keys from the acceptance criteria (AC) field of a given Jira issue.

        This function retrieves the acceptance criteria (AC) field of a specified Jira issue
        and extracts all Jira issue keys mentioned in the AC. The extracted issue keys are
        returned as a list of unique values.
        NOTE: The AC field is a custom field, and it can be different for different Jira instances.

        Parameters:
            jira_issue_key (str): The key of the Jira issue from which to extract issue keys.

        Returns:
            List[str]: A list of unique Jira issue keys extracted from the AC field.
        """
        jira_issue = self._client.issue(jira_issue_key, 'customfield_10300')
        if jira_issue['fields']['customfield_10300'] is None:
            return set()
        ac = jira_issue['fields']['customfield_10300']
        return list(set(re.findall(r'[A-Z]{1,5}-\d{1,5}', ac, re.DOTALL)))

    def __get_all_jira_issue_keys_from_description_and_ac(self, jira_issue_key: str) -> List[str]:
        """
        Extracts all Jira issue keys from both the description and acceptance criteria (AC) fields of a given Jira issue.

        This function retrieves the issue keys mentioned in both the description and acceptance criteria (AC) fields
        of a specified Jira issue. The extracted issue keys are combined and returned as a list of unique values.

        Parameters:
            jira_issue_key (str): The key of the Jira issue from which to extract issue keys.

        Returns:
            List[str]: A list of unique Jira issue keys extracted from both the description and AC fields.
        """
        desc_keys = self.__get_all_jira_issue_keys_from_issue_description(jira_issue_key)
        ac_keys = self.__get_all_jira_issue_keys_from_issue_ac(jira_issue_key)
        return list(set(itertools.chain(desc_keys, ac_keys)))

    def __get_all_linked_and_in_text_jira_keys(self, jira_issue_key: str) -> List[str]:
        """
        Extracts all linked Jira issue keys and issue keys mentioned in the description and acceptance criteria (AC) fields of a given Jira issue.

        This function retrieves the issue keys that are linked to a specified Jira issue and the issue keys mentioned
        in both the description and acceptance criteria (AC) fields. The extracted issue keys are combined and returned
        as a list of unique values.

        Parameters:
            jira_issue_key (str): The key of the Jira issue from which to extract linked and in-text issue keys.

        Returns:
            List[str]: A list of unique Jira issue keys extracted from both the linked issues and the description and AC fields.
        """
        linked_issues = self.__fetch_all_linked_jira_issue_keys(jira_issue_key)
        linked_issues.add(jira_issue_key)
        in_text_issues = self.__get_all_jira_issue_keys_from_description_and_ac(jira_issue_key)
        return list(set(itertools.chain(linked_issues, in_text_issues)))

    def __attach_file_to_jira_issue(self, jira_issue_key: str, file_name: str):
        """
        Attach a file to a specified JIRA issue.

        This private method uses the JIRA client to add an attachment to a JIRA issue identified by its key.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue to which the file will be attached.
            file_name (str): The path to the file that will be attached to the JIRA issue.

        Raises:
            JIRAError: If there is an error while attaching the file to the JIRA issue.

        Examples:
            .. code-block:: python

                self.__attach_file_to_jira_issue('PROJ-123', '/path/to/file.txt')

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        self._client.add_attachment(jira_issue_key, filename=file_name)

    def __get_confluence_documents_by_jira_ticket(self, jira_issue_id: str) -> List[Document]:
        """
        Retrieve Confluence documents associated with a given JIRA issue.

        This private method fetches the Confluence page IDs linked to a specified JIRA issue and then loads the corresponding Confluence documents.

        Args:
            jira_issue_id (str): The unique identifier (ID) of the JIRA issue for which the Confluence documents are to be retrieved.

        Returns:
            List[Document]: A list of Document objects representing the Confluence pages associated with the given JIRA issue. If no pages are found, an empty list is returned.

        Raises:
            JIRAError: If there is an error while fetching the Confluence page IDs from the JIRA issue.
            ConfluenceError: If there is an error while loading the Confluence documents.

        Example:
             .. code-block:: python

                documents = self.__get_confluence_documents_by_jira_ticket('PROJ-123')
                for doc in documents:
                    print(doc.page_content)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        page_ids = self.__fetch_jira_confluence_page_ids(jira_issue_id)
        if len(page_ids) == 0:
            return []
        confluence_loader = ConfluenceLoader(
            page_ids=page_ids,
            url=self.confluence_base_url,
            api_key=self.jira_api_key,
            username=self.jira_username,
            limit=len(page_ids),
            max_pages=len(page_ids),
            keep_markdown_format=True,
            content_format=ContentFormat.VIEW
        )
        return confluence_loader.load()

    def __split_the_confluence_documents(self, confluence_documents: List[Document]) -> List[Document]:
        """
        Split Confluence documents into smaller sections based on markdown headers.

        This private method takes a list of Confluence documents and splits each document into smaller sections using specified markdown headers.
        The metadata of each section is preserved and augmented with a unique split identifier.

        Args:
            confluence_documents (List[Document]): A list of Confluence document objects to be split.

        Returns:
            List[Document]: A list of document sections, each split based on the specified markdown headers. If the input list is empty, an empty list is returned.

        Example:
            .. code-block:: python

                confluence_docs = [doc1, doc2]
                split_docs = self.__split_the_confluence_documents(confluence_docs)
                for split_doc in split_docs:
                    print(split_doc.page_content)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        if len(confluence_documents) == 0:
            return []
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
        ]

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
        splitted_by_headers_docs = []
        for doc in confluence_documents:
            meta = doc.metadata
            docs_by_headers = markdown_splitter.split_text(doc.page_content)
            for i, split in enumerate(docs_by_headers):
                meta['split_id'] = i
                split.metadata = meta | split.metadata
                splitted_by_headers_docs.append(split)
        return splitted_by_headers_docs

    def __clean_text_lines(self, text: str):
        """
        Clean and process lines of text by removing non-breaking spaces and stripping whitespace.

        This private method takes a string of text, splits it into lines, replaces non-breaking spaces with regular spaces, and strips leading and trailing whitespace from each line.
        Empty lines are removed from the output.

        Args:
            text (str): The input string of text to be cleaned and processed.

        Returns:
            generator: A generator that yields cleaned lines of text.

        Example:
            .. code-block:: python

                text = "This is a line with\xa0non-breaking spaces.\n\nThis is another line."
                cleaned_lines = self.__clean_text_lines(text)
                for line in cleaned_lines:
                    print(line)
                Output:
                This is a line with non-breaking spaces.
                This is another line.

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        # Clean non-breaking spaces (nbsp)
        return (line.replace('\xa0', ' ').strip() for line in text.splitlines() if line.strip())

    def __clean_text_from_color_identifiers(self, text: str) -> str:
        """
        Remove color identifiers from a given text.

        This private method removes color identifiers in the format `{color:#xxxxxx}` and `{color}` from the input text.
        These identifiers are often used in markup languages to specify text color.

        Args:
            text (str): The input string of text from which color identifiers will be removed.

        Returns:
            str: The cleaned text with color identifiers removed.

        Example:
            .. code-block:: python

                text = "This is a {color:#ff0000}red{color} text."
                cleaned_text = self.__clean_text_from_color_identifiers(text)
                print(cleaned_text)
                Output: This is a red text.

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        clean_color_start = re.sub(r'\{color:#[a-z0-9]{1,6}}', '', text)
        return re.sub(r'\{color}', '', clean_color_start)

    def __process_issue_from_bulk_response(self, issue_from_bulk_response: dict) -> str:
        """
        Process a JIRA issue from a bulk response and optionally summarize its description.

        This private method processes the description of a JIRA issue obtained from a bulk response.
        It cleans the description by removing color identifiers and stripping whitespace from each line.
        If a summarization prompt is provided, it summarizes the cleaned description using a language model.

        Args:
            issue_from_bulk_response (dict): A dictionary representing a JIRA issue from a bulk response. The dictionary is expected to contain a 'fields' key with a 'description' field.

        Returns:
            str: The cleaned and optionally summarized description of the JIRA issue.

        Example:
            .. code-block:: python

            issue = {
                'fields': {
                    'description': 'This is a {color:#ff0000}red{color} text.\nAnother line.'
                }
            }
            processed_description = self.__process_issue_from_bulk_response(issue)
            print(processed_description)
            Output:
            This is a red text.
            Another line.

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        description = self.__clean_text_from_color_identifiers(
            '\n'.join(self.__clean_text_lines(issue_from_bulk_response['fields']['description'])))
        if self.summarization_prompt:
            return summarize(llm=self._llm, data_to_summarize=description, summarization_key='description',
                             summarization_prompt=self.summarization_prompt)
        else:
            return description

    def __get_jira_descriptions_to_dict(self, jira_issue_key: str) -> Tuple[dict, list[str]]:
        """
        Retrieve and process descriptions of JIRA issues related to a given JIRA issue key.

        This private method fetches descriptions for a specified JIRA issue and all related issues.
        It processes each description to clean and optionally summarize it, and stores the results in a dictionary.
        The method uses a thread pool to parallelize the processing of multiple issues.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue for which related issue descriptions are to be fetched and processed.

        Returns:
            Tuple[dict, list[str]]: A tuple containing:
                - A dictionary where keys are JIRA issue keys and values are the processed descriptions.
                - A list of all JIRA issue keys related to the specified JIRA issue.

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                descriptions_dict, related_keys = self.__get_jira_descriptions_to_dict(jira_issue_key)
                print(descriptions_dict)
                print(related_keys)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        # Cache to store fetched Jira data
        jira_data_cache = {}
        # Get all the jJira issue keys related to jira issue passed in method argument
        jira_keys = self.__get_all_linked_and_in_text_jira_keys(jira_issue_key)
        # Find all the descriptions for all the related jira issues + issue passed in argument itself
        found_issues = self.__bulk_fetch_specific_fields_from_jira_issue_key(jira_keys, fields='description')

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_issue = {
                executor.submit(self.__process_issue_from_bulk_response, issue): issue for issue in
                found_issues}
            for future in as_completed(future_to_issue):
                jira_issue = future_to_issue[future]
                try:
                    jira_data_cache[jira_issue['key']] = future.result()
                except Exception as e:
                    logger.error(f"Error fetching data for Jira issue {jira_issue}: {e}")
        return jira_data_cache, jira_keys

    def __create_ac_documents_content(self, jira_issue_key: str) -> List[Document]:
        """
        Create a list of Document objects containing the descriptions of related JIRA issues.

        This private method retrieves descriptions for a specified JIRA issue and all related issues, processes the descriptions, and creates Document objects for each description.
        Each Document object includes the JIRA issue key and the processed description.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue for which related issue descriptions are to be fetched and processed.

        Returns:
            List[Document]: A list of Document objects, each containing the processed description of a related JIRA issue.

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                documents = self.__create_ac_documents_content(jira_issue_key)
                for doc in documents:
                    print(doc.page_content)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        related_description_content = []  # List of related descriptions

        # Cache to store fetched JIRA descriptions
        jira_data_cache, keys = self.__get_jira_descriptions_to_dict(jira_issue_key)

        # Process scenarios and ACs
        for key in keys:
            if key in jira_data_cache:
                res_desc = jira_data_cache[key]
                related_description_content.append(Document(
                    page_content=f"Related links content for jira key - {key}:Ticket Description:\n{res_desc}",
                    metadata={'source': key}))
        return related_description_content

    def __get_attachment_id(self, jira_issue_key: str, file_name: str) -> str | None:
        """
        Retrieve the attachment ID for a specific file attached to a JIRA issue.

        This private method fetches the list of attachment IDs from a specified JIRA issue and filters the list to find the attachment ID for a given file name.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue from which to retrieve attachment IDs.
            file_name (str): The name of the file for which to find the attachment ID.

        Returns:
            str | None: The attachment ID of the specified file if found, otherwise None.

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                file_name = 'example.txt'
                attachment_id = self.__get_attachment_id(jira_issue_key, file_name)
                print(attachment_id)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        attachment_ids = self._client.get_attachments_ids_from_issue(jira_issue_key)
        filtered_ids = list(filter(lambda attachment: attachment['filename'] == file_name, attachment_ids))
        logger.info(f"Filtered attachment ids len: {len(filtered_ids)} and value: {filtered_ids}")
        if len(filtered_ids) > 0:
            return filtered_ids[0]['attachment_id']
        else:
            return None

    def __download_attachment_by_id(self, jira_issue_key: str, file_name: str, persistent_path: str = '.'):
        """
        Download and extract a file attachment from a JIRA issue by its ID.

        This private method retrieves the attachment ID for a specified file from a JIRA issue, downloads the attachment, and extracts its contents if it is a ZIP file.
        The extracted contents are saved to a specified directory.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue from which to download the attachment.
            file_name (str): The name of the file to be downloaded and extracted.
            persistent_path (str, optional): The directory where the extracted contents will be saved. Defaults to the current directory ('.').

        Returns:
            None

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                file_name = 'example.zip'
                self.__download_attachment_by_id(jira_issue_key, file_name, persistent_path='/path/to/save')

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        attachment_json = self._client.get_attachment(self.__get_attachment_id(jira_issue_key, file_name))
        url_to_download = attachment_json['content']

        # Download the content
        content_to_download = self._client._session.get(url_to_download).content

        # Save the downloaded content to a file
        with open(os.path.join('.', file_name), 'wb') as f:
            f.write(content_to_download)

        # Open the ZIP file and extract its contents
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            zip_ref.extractall(persistent_path)

        # Remove the downloaded ZIP file
        os.remove(file_name)

    def __prepare_vectorstore(self, jira_issue_key: str, obtain_vectorstore: bool = False) -> Tuple[str, Chroma | None]:
        """
        Prepare the vector store for a JIRA issue, optionally creating and returning a Chroma vector store.

        This private method prepares the directory path for storing vector embeddings related to a specified JIRA issue.
        If requested, it also initializes and returns a Chroma vector store with embeddings.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue for which the vector store is to be prepared.
            obtain_vectorstore (bool, optional): Flag indicating whether to create and return a Chroma vector store. Defaults to False.

        Returns:
            Tuple[str, Chroma | None]: A tuple containing:
                - The absolute path to the directory for storing vector embeddings.
                - A Chroma vector store object if `obtain_vectorstore` is True, otherwise None.

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                persistent_path, vectorstore = self.__prepare_vectorstore(jira_issue_key, obtain_vectorstore=True)
                print(persistent_path)
                print(vectorstore)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        persistent_path = os.path.abspath(os.path.join('.', f'jira_ticket_embeddings_{jira_issue_key}'))
        if obtain_vectorstore:
            embedding_function = HuggingFaceEmbeddings(encode_kwargs={'normalize_embeddings': True})
            vectorstore = Chroma(
                collection_name="jira_ticket_data",
                embedding_function=embedding_function,
                persist_directory=persistent_path
            )
            return persistent_path, vectorstore
        return persistent_path, None

    def __perform_similarity_search(self, jira_issue_key: str, query: str) -> List[str]:
        """
        Perform a similarity search on the vector store for a given JIRA issue and query.

        This private method prepares the vector store for a specified JIRA issue, performs a similarity search using the provided query, and returns the content of the retrieved documents.

        Args:
            jira_issue_key (str): The unique identifier (key) of the JIRA issue for which the similarity search is to be performed.
            query (str): The query string to be used for the similarity search.

        Returns:
            List[str]: A list of strings, each containing the content of a retrieved document.

        Example:
            .. code-block:: python

                jira_issue_key = 'PROJ-123'
                query = 'How to fix login issue'
                results = self.__perform_similarity_search(jira_issue_key, query)
                for result in results:
                    print(result)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        _, vectorstore = self.__prepare_vectorstore(jira_issue_key, obtain_vectorstore=True)
        output = []
        retrieved_docs = vectorstore.search(query, 'mmr', k=20, fetch_k=50)

        for doc in retrieved_docs:
            output.append(f'\n\n{doc.page_content}')

        return output

    def prepare_data(self, jira_issue_key: str) -> str:
        """ Prepare the embeddings for the specific jira issue key. They will include both Jira and Confluence info. """
        path, _ = self.__prepare_vectorstore(jira_issue_key)
        zip_file_name = f'jira_ticket_embeddings_{jira_issue_key}.zip'
        if self.__get_attachment_id(jira_issue_key, zip_file_name) is not None:
            self.__download_attachment_by_id(jira_issue_key, zip_file_name)
            return f"The vectorstore content have been obtained from Jira ticket - {jira_issue_key}. You can use it from the path - {path}"
        elif not os.path.exists(path):
            initial_confluence_docs = self.__get_confluence_documents_by_jira_ticket(jira_issue_key)
            result_confluence_docs = self.__split_the_confluence_documents(initial_confluence_docs)
            related_description_list = self.__create_ac_documents_content(jira_issue_key)
            _, vectorstore = self.__prepare_vectorstore(jira_issue_key, obtain_vectorstore=True)
            if result_confluence_docs:
                vectorstore.add_documents(result_confluence_docs)
            vectorstore.add_documents(related_description_list)
            vectorstore.persist()
            self.__zip_directory(path, zip_file_name)
            self.__attach_file_to_jira_issue(jira_issue_key, zip_file_name)
            os.remove(zip_file_name)
            return f'Successfully created embeddings for the jira ticket with following id - {jira_issue_key}'
        else:
            pass

    def search_data(self, jira_issue_key: str, query: str) -> str:
        """
        Search the specific jira ticket data using already provided by user jira ticket id and given query.
        Usually query will be a simple acceptance criterion (AC) from the same ticket
        """
        result = self.__perform_similarity_search(jira_issue_key, query)
        return ''.join(result)

    def __build_search_results(self, results: List[Document]) -> dict[str, List[str]]:
        """
        Build a dictionary of search results from a list of Document objects.

        This private method processes a list of Document objects and extracts their content to build a dictionary.
        The dictionary contains a single key, 'documents', which maps to a list of strings representing the content of each Document.

        Args:
            results (List[Document]): A list of Document objects from which to extract the content.

        Returns:
            dict[str, List[str]]: A dictionary with a single key 'documents', where the value is a list of strings containing the content of each Document.

        Example:
            .. code-block:: python

                results = [Document(page_content="Content 1"), Document(page_content="Content 2")]
                search_results = self.__build_search_results(results)
                print(search_results)
                Output: {'documents': ['Content 1', 'Content 2']}

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        return {'documents': [doc.page_content for doc in results]}

    def __build_prompt(self, input_dict: dict) -> List[BaseMessage]:
        """
        Build a list of formatted prompt messages for a chat-based model using the provided input dictionary.

        This private method takes an input dictionary containing context and question information, formats the documents from the context, and constructs a list of prompt messages using a chat prompt template.
        The formatted messages are then returned as a list of BaseMessage objects.

        Args:
            input_dict (dict): A dictionary containing the context and question for building the prompt. The dictionary should have the following structure:
                - 'context': A dictionary with a key 'documents' mapping to a list of document strings.
                - 'question': A string representing the question or query to be included in the prompt.

        Returns:
            List[BaseMessage]: A list of formatted prompt messages as BaseMessage objects.

        Example:
            .. code-block:: python

                input_dict = {
                    'context': {'documents': ['Document 1 content', 'Document 2 content']},
                    'question': 'What are the gaps in the analysis?'
                }
                prompt_messages = self.__build_prompt(input_dict)
                for message in prompt_messages:
                    print(message.content)

        Note:
            This method is intended for internal use within the class and should not be called directly from outside the class.
        """
        formatted_docs = '\n'.join(input_dict['context']['documents'])
        prompt = ChatPromptTemplate.from_messages([
            ('user', self.gaps_analysis_prompt),
        ]).format_messages(documents=formatted_docs, ac=input_dict['question'])
        return prompt

    def gaps_analysis(self, jira_issue_key: str, query: str) -> str:
        """
        Perform a gaps analysis using the JIRA issue key already provided by the user and the given query.
        The query is typically an acceptance criterion (AC) from the same ticket.
        If a gaps analysis prompt is provided, it will be used to generate the analysis.
        """
        _, vectorstore = self.__prepare_vectorstore(jira_issue_key, obtain_vectorstore=True)
        retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={'k': 25, 'fetch_k': 50})
        if self.gaps_analysis_prompt:
            # Create the LLM chain with the provided in settings gaps_analysis_prompt
            chain = (
                    RunnableParallel({
                        'context': retriever | RunnableLambda(self.__build_search_results),
                        'question': RunnablePassthrough()
                    })
                    | RunnableLambda(self.__build_prompt)
                    | self._llm
                    | StrOutputParser()
            )
            return chain.invoke(query)
        else:
            return "No gap analysis prompt has been provided. Please provide the gap analysis prompt in toolkit configuration. You should provide it under gaps_analysis_prompt value as a string."

    def get_available_tools(self):
        return [
            {
                "name": "prepare_data",
                "description": self.prepare_data.__doc__,
                "args_schema": PrepareDataSchema,
                "ref": self.prepare_data,
            },
            {
                "name": "search_data",
                "description": self.search_data.__doc__,
                "args_schema": SearchDataSchema,
                "ref": self.search_data,
            },
            {
                "name": "gaps_analysis",
                "description": self.gaps_analysis.__doc__,
                "args_schema": SearchDataSchema,
                "ref": self.gaps_analysis,
            }

        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
