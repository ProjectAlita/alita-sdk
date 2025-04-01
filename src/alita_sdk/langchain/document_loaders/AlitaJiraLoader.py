import os
import tempfile
from typing import Optional, Union, List, Iterator

import requests
from atlassian import Jira
from atlassian.errors import ApiError
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from .constants import loaders_map

DEFAULT_FIELDS = ['status','summary','reporter','description']


class AlitaJiraLoader(BaseLoader):

    def __init__(self, **kwargs):
        self.base_url = kwargs.get("url")
        if not self.base_url:
            raise ValueError("URL parameter 'url' is required")
        self.api_key = kwargs.get('api_key', None)
        self.token = kwargs.get('token', None)
        self.llm = kwargs.get('llm', None)
        self.username = kwargs.get('username', None)
        self.cloud = kwargs.get('cloud', True)
        self.jql = kwargs.get('jql', None)
        self.project = kwargs.get('project', None)
        self.epic_id = kwargs.get('epic_id', None)
        self.fields_to_extract = kwargs.get('fields_to_extract', None)
        self.fields_to_index = kwargs.get('fields_to_index', None)
        self.include_attachments = kwargs.get('include_attachments', False)
        self.max_total_issues = kwargs.get('max_total_issues', 1000)
        self.skip_attachment_extensions = kwargs.get('skip_attachment_extensions', None)

        errors = AlitaJiraLoader.validate_init_args(self.base_url, self.api_key, self.username, self.token)
        if errors:
            raise ValueError(f"Error(s) while validating input: {errors}")
        try:
            from atlassian import Confluence
        except ImportError:
            raise ImportError(
                "`atlassian` package not found, please run "
                "`pip install atlassian-python-api`"
            )

        if self.token:
            self.jira = Jira(
                url=self.base_url, token=self.token, cloud=self.cloud
            )
        else:
            self.jira = Jira(
                url=self.base_url, username=self.username, password=self.api_key, cloud=self.cloud
            )

    @staticmethod
    def validate_init_args(
            url: Optional[str] = None,
            api_key: Optional[str] = None,
            username: Optional[str] = None,
            token: Optional[str] = None,
    ) -> Union[List, None]:
        """Validates proper combinations of init arguments"""

        errors = []
        if url is None:
            errors.append("Must provide `base_url`")

        if (api_key and not username) or (username and not api_key):
            errors.append(
                "If one of `api_key` or `username` is provided, "
                "the other must be as well."
            )

        non_null_creds = list(
            x is not None
            for x in ((api_key or username), token)
        )
        if sum(non_null_creds) > 1:
            all_names = ("(api_key, username)", "token")
            provided = tuple(n for x, n in zip(non_null_creds, all_names) if x)
            errors.append(
                f"Cannot provide a value for more than one of: {all_names}. Received "
                f"values for: {provided}"
            )

        return errors or None

    def __get_issues(self):
        fields = DEFAULT_FIELDS
        if self.fields_to_extract:
            fields += self.fields_to_extract

        if self.include_attachments:
            fields += ['attachment']

        jql_query = ''
        if self.project:
            jql_query = f'project={self.project}'
        elif self.epic_id:
            if self.cloud:
                jql_query = f'parentEpic={self.epic_id}'
            else:
                jql_query = f'"Parent Link"={self.epic_id}'
        elif self.jql:
            jql_query = self.jql

        if not jql_query:
            raise ValueError("Must provide `jql`, `project`, or `epic_id` to fetch issues.")

        final_fields = ','.join({field.lower() for field in fields})

        limit = self.max_total_issues if self.max_total_issues is not None else None
        issue_generator = self.__jql_get_tickets(jql_query, fields=final_fields, limit=limit)
        return issue_generator

    def __jql_get_tickets(
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
        url = self.jira.resource_url("search")

        while True:
            params["startAt"] = int(start)
            try:
                response = self.jira.get(url, params=params)
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

    def lazy_load(self) -> Iterator[Document]:
        """Lazy load jira issues as documents."""
        issue_generator = self.__get_issues()
        for issues_batch in issue_generator:
            for issue in issues_batch:
                issue_doc = self.__process_issue(issue)
                if issue_doc:
                    yield self.__process_issue(issue)

    def __process_issue(self, issue: dict) -> Document | None:
        content = f"{issue['fields']['summary']}\n"
        description = issue['fields'].get('description', '')
        if description:
            content += f"{description}\n"
        else:
            return None
        if 'comment' in issue['fields'] and issue['fields']['comment']['comments']:
            for comment in issue['fields']['comment']['comments']:
                content += f"{comment['body']}\n"

        if self.fields_to_index:
            for field in self.fields_to_index:
                if field in issue['fields'] and issue['fields'][field]:
                    content += f"{issue['fields'][field]}\n"

        if self.include_attachments and issue['fields'].get('attachment', {}):
            content += self._process_attachments_for_issue(issue)

        metadata = {
            "issue_key": issue["key"],
            "source": f"{self.base_url}/browse/{issue['key']}",
            "author": issue["fields"].get("reporter", {}).get("emailAddress"),
            "status": issue["fields"].get("status", {}).get("name"),
        }
        return Document(page_content=content, metadata=metadata)

    def _process_attachments_for_issue(self, issue: dict) -> str:
        """Processes attachments for a given Jira issue."""
        attachments = issue['fields'].get('attachment', [])
        if not attachments:
            return ""

        processed_content = ""
        skip_extensions = set(self.skip_attachment_extensions.split(',')) if self.skip_attachment_extensions else set()

        for attachment in attachments:
            attachment_content = self._process_single_attachment(attachment, skip_extensions)
            # attachment_content = self._process_single_attachment(attachment)
            if attachment_content:
                processed_content += attachment_content

        return processed_content

    def _process_single_attachment(self, attachment: dict, skip_extensions: set) -> str:
        # def _process_single_attachment(self, attachment: dict) -> str:
        """Processes a single attachment."""
        filename = attachment['filename']
        attachment_url = attachment['content']
        _, extension = os.path.splitext(filename)
        extension = extension.lower()

        if extension in skip_extensions:
            return ""

        if extension not in loaders_map:
            return ""  # Skip unsupported file types

        attachment_file = self._download_attachment(filename, attachment_url)
        if not attachment_file:
            return ""

        content = self._load_attachment_content(attachment_file, extension)
        os.remove(attachment_file)  # Clean up temporary file
        return content

    def _download_attachment(self, filename: str, attachment_url: str) -> Optional[str]:
        """Downloads attachment content to a temporary file."""
        temp_dir = os.path.join(tempfile.TemporaryDirectory().name)
        attachment_file = os.path.abspath(os.path.join(temp_dir, filename))
        os.makedirs(temp_dir, exist_ok=True)
        try:
            response = self.jira._session.get(attachment_url, stream=True)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            with open(attachment_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                    f.write(chunk)
            return attachment_file
        except ApiError as e:
            error_message = f"Jira API error: {str(e)}"
            raise ValueError(f"Failed to fetch attachment from Jira: {error_message}")
        except requests.exceptions.RequestException as e:  # Catch network errors
            error_message = f"Network error: {str(e)}"
            raise ValueError(f"Failed to download attachment: {error_message}")

    def _load_attachment_content(self, attachment_file: str, extension: str) -> str:
        """Loads content from an attachment file using appropriate loader."""
        try:
            loader_config = loaders_map.get(extension)
            if not loader_config:  # Should not happen as we check extension earlier, but for safety
                return ""
            loader_cls = loader_config['class']
            loader_kwargs = loader_config['kwargs']
            # Conditionally pass llm to multimodal loaders
            if loader_config['is_multimodal_processing'] and self.llm:
                loader_kwargs['llm'] = self.llm
            loader = loader_cls(attachment_file, **loader_kwargs)
            documents = loader.load()

            page_contents = [doc.page_content for doc in documents]
            return "\n".join(page_contents)
        except Exception as e:
            error_message = f"Error loading attachment: {str(e)}"
            print(f"Warning: {error_message} for file {attachment_file}")
            return ""

    def load(self) -> List[Document]:
        """Load jira issues documents."""
        return list(self.lazy_load())
