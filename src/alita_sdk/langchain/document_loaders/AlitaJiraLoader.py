from typing import Optional, Union, List, Iterator

from atlassian import Jira
from atlassian.errors import ApiError
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

DEFAULT_FIELDS = 'status,summary,reporter'


class AlitaJiraLoader(BaseLoader):

    def __init__(self, url: str,
                 api_key: Optional[str] = None,
                 token: Optional[str] = None,
                 username: Optional[str] = None,
                 cloud: bool = True,
                 jql: Optional[str] = None,
                 project: Optional[str] = None,
                 epic_id: Optional[str] = None,
                 fields_to_extract: Optional[str] = None,
                 fields_to_index: Optional[str] = None,
                 include_attachments: bool = False,
                 max_total_issues: Optional[int] = 1000):
        self.base_url = url
        self.api_key = api_key
        self.token = token
        self.username = username
        self.cloud = cloud
        self.jql = jql
        self.project = project
        self.epic_id = epic_id
        self.fields_to_extract = fields_to_extract
        self.fields_to_index = fields_to_index
        self.include_attachments = include_attachments
        self.max_total_issues = max_total_issues

        errors = AlitaJiraLoader.validate_init_args(url, api_key, username, token)
        if errors:
            raise ValueError(f"Error(s) while validating input: {errors}")
        try:
            from atlassian import Confluence
        except ImportError:
            raise ImportError(
                "`atlassian` package not found, please run "
                "`pip install atlassian-python-api`"
            )

        if token:
            self.jira = Jira(
                url=url, token=token, cloud=cloud
            )
        else:
            self.jira = Jira(
                url=url, username=username, password=api_key, cloud=cloud
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
            fields += f',{self.fields_to_extract}'
        else:
            fields += ',description,comment'  # Fetch only necessary fields by default

        jql_query = ''
        if self.project:
            jql_query = f'project={self.project}'
        elif self.epic_id:
            jql_query = f'parentEpic={self.epic_id}'
        elif self.jql:
            jql_query = self.jql

        if not jql_query:
            raise ValueError("Must provide `jql`, `project`, or `epic_id` to fetch issues.")

        limit = self.max_total_issues if self.max_total_issues is not None else None
        issue_generator = self.__jql_get_tickets(jql_query, fields=fields, limit=limit)
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
                yield self.__process_issue(issue)


    def __process_issue(self, issue: dict) -> Document:
        content = f"{issue['fields']['summary']}\n"
        description = issue['fields'].get('description', '')
        if description:
            content += f"{description}\n"
        if 'comment' in issue['fields'] and issue['fields']['comment']['comments']:
            for comment in issue['fields']['comment']['comments']:
                content += f"{comment['body']}\n"

        if self.fields_to_index:
            for field in self.fields_to_index.split(','):
                if field in issue['fields']:
                    content += f"{issue['fields'][field]}\n"

        metadata = {
            "issue_key": issue["key"],
            "source": f"{self.base_url}/browse/{issue['key']}",
            "author": issue["fields"].get("reporter", {}).get("emailAddress"),
            "status": issue["fields"].get("status", {}).get("name"),
        }
        return Document(page_content=content, metadata=metadata)

    def load(self) -> List[Document]:
        """Load jira issues documents."""
        return list(self.lazy_load())
