import json
import logging
import hashlib
from typing import Any, Dict, Generator, List, Optional, Literal

import requests
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import PrivateAttr, SecretStr, create_model, model_validator, Field
from python_graphql_client import GraphqlClient

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools
from ...runtime.utils.utils import IndexerKeywords

try:
    from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
except ImportError:
    from alita_sdk.langchain.interfaces.llm_processor import get_embeddings

logger = logging.getLogger(__name__)

_get_tests_query = """query GetTests($jql: String!, $limit:Int!, $start: Int)
{
    getTests(jql: $jql, limit: $limit, start: $start) {
        total
        start
        limit
        results {
            issueId
            jira(fields: ["key", "summary", "description", "created", "updated", "assignee.displayName", "reporter.displayName"])
            projectId
            testType {
                name
                kind
            }
            steps {
                id
                data
                action
                result
                attachments {
                    id
                    filename
                    downloadLink
                }
            }
            preconditions(limit: $limit) {
                total
                start
                limit
                results {
                    issueId
                    jira(fields: ["key"])
                    projectId
                }
            }
            unstructured
            gherkin
        }
    }
}
"""

_graphql_mutation_description="""Xray GraphQL mutation to create new test:
     Mutation createTest {
# Mutation used to create a new Test.
#
# Arguments
# testType: the Test Type of the Test.
# steps: the Step definition of the test.
# unstructured: the unstructured definition of the Test.
# gherkin: the gherkin definition of the Test.
# preconditionIssueIds: the Precondition ids that be associated with the Test.
# folderPath: the Test repository folder for the Test.
# jira: the Jira object that will be used to create the Test.
# Examples:
1. Create a new Test with type Manual:
mutation { createTest( testType: { name: "Manual" }, steps: [ { action: "Create first example step", result: "First step was created" }, { action: "Create second example step with data", data: "Data for the step", result: "Second step was created with data" } ], jira: { fields: { summary:"Exploratory Test", project: {key: "CALC"} } } ) { test { issueId testType { name } steps { action data result } jira(fields: ["key"]) } warnings } }
createTest(testType: UpdateTestTypeInput, steps: [CreateStepInput], unstructured: String, gherkin: String, preconditionIssueIds: [String], folderPath: String, jira: JSON!): CreateTestResult
}
2. Create a new Test with type Generic:
mutation { createTest( testType: { name: "Generic" }, unstructured: "Perform exploratory tests on calculator.", jira: { fields: { summary:"Exploratory Test", project: {key: "CALC"} } } ) { test { issueId testType { name } unstructured jira(fields: ["key"]) } warnings } }
"""

NoInput = create_model(
    "NoInput"
)

XrayGrapql = create_model(
    "XrayGrapql",
    graphql=(str, Field(description="""Custom XRAY GraphQL query for execution"""))
)

XrayGetTests = create_model(
    "XrayGetTests",
    jql=(str, Field(description="the jql that defines the search"))
)

XrayCreateTest = create_model(
    "XrayCreateTest",
    graphql_mutation=(str, Field(description=_graphql_mutation_description))
)

XrayCreateTests = create_model(
    "XrayCreateTests",
    graphql_mutations=(List[str], Field(description="list of GraphQL mutations:\n" + _graphql_mutation_description))
)

def _parse_tests(test_results) -> List[Any]:
    """Handles tests in order to minimize tests' output"""

    for test_item in test_results:
        # remove preconditions if it is absent
        if test_item['preconditions']['total'] == 0:
            del test_item['preconditions']
    return test_results


class XrayApiWrapper(NonCodeIndexerToolkit):
    _default_base_url: str = 'https://xray.cloud.getxray.app'
    base_url: str = ""
    client_id: str = None
    client_secret: SecretStr = None
    limit: Optional[int] = 100
    _client: Optional[GraphqlClient] = PrivateAttr()
    _auth_token: Optional[str] = PrivateAttr(default=None)

    doctype: str = "xray_test"

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            from python_graphql_client import GraphqlClient
        except ImportError:
            raise ImportError(
                "`gqpython_graphql_clientl` package not found, please run "
                "`pip install python_graphql_client`"
            )
        client_id = values['client_id']
        client_secret = values['client_secret']
        # Authenticate to get the token
        values['base_url'] = values.get('base_url', '') or cls._default_base_url.default
        auth_url = f"{values['base_url']}/api/v1/authenticate"
        auth_data = {
            "client_id": client_id,
            "client_secret": client_secret
        }
        try:
            auth_response = requests.post(auth_url, json=auth_data)
            auth_response.raise_for_status()
            token = auth_response.json()
            values['_auth_token'] = token

            values['_client_endpoint'] = f"{values['base_url']}/api/v2/graphql"
            values['_client_headers'] = {'Authorization': f'Bearer {token}'}
            
        except Exception as e:
            if "invalid or doesn't have the required permissions" in str(e):
                masked_secret = '*' * (len(client_secret) - 4) + client_secret[-4:] if client_secret is not None else "UNDEFINED"
                return ToolException(f"Please, check you credentials ({values['client_id']} / {masked_secret}). Unable")
            else:
                return ToolException(f"Authentication failed: {str(e)}")
        return super().validate_toolkit(values)

    def __init__(self, **data):
        super().__init__(**data)
        
        from python_graphql_client import GraphqlClient
        
        if not hasattr(self, '_auth_token') or self._auth_token is None:
            if hasattr(self, 'client_id') and hasattr(self, 'client_secret'):
                try:
                    auth_url = f"{self.base_url}/api/v1/authenticate"
                    auth_data = {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret.get_secret_value() if hasattr(self.client_secret, 'get_secret_value') else str(self.client_secret)
                    }
                    auth_response = requests.post(auth_url, json=auth_data, timeout=30)
                    auth_response.raise_for_status()
                    self._auth_token = auth_response.json()
                except Exception as e:
                    raise ToolException(f"Failed to authenticate in __init__: {str(e)}")
            else:
                raise ToolException("No client_id or client_secret available for authentication")
        
        # Initialize the GraphQL client
        if self._auth_token and hasattr(self, 'base_url'):
            endpoint = f"{self.base_url}/api/v2/graphql"
            headers = {'Authorization': f'Bearer {self._auth_token}'}
            self._client = GraphqlClient(endpoint=endpoint, headers=headers)
        else:
            raise ToolException(f"GraphQL client could not be initialized - missing auth_token: {self._auth_token is not None}, base_url: {hasattr(self, 'base_url')}")
        
        if '_graphql_endpoint' in data:
            self._graphql_endpoint = data['_graphql_endpoint']

    def _ensure_auth_token(self) -> str:
        """
        Ensure we have a valid auth token, refreshing if necessary.
        
        Returns:
            str: The authentication token
            
        Raises:
            ToolException: If authentication fails
        """
        if self._auth_token is None:
            logger.warning("Auth token is None, attempting to re-authenticate")
            try:
                auth_url = f"{self.base_url}/api/v1/authenticate"
                auth_data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret.get_secret_value() if hasattr(self.client_secret, 'get_secret_value') else str(self.client_secret)
                }
                auth_response = requests.post(auth_url, json=auth_data, timeout=30)
                auth_response.raise_for_status()
                self._auth_token = auth_response.json()
                logger.info("Successfully re-authenticated and obtained new token")
            except Exception as e:
                raise ToolException(f"Failed to authenticate: {str(e)}")
        
        return self._auth_token

    def get_tests(self, jql: str):
        """get all tests"""

        start_at = 0
        all_tests = []
        logger.info(f"jql to get tests: {jql}")
        while True:
            # get tests
            try:
                get_tests_response = self._client.execute(query=_get_tests_query,
                                                          variables={"jql": jql, "start": start_at,
                                                                     "limit": self.limit})['data']["getTests"]
            except Exception as e:
                return ToolException(f"Unable to get tests due to error:\n{str(e)}")
            # filter tests results
            tests = _parse_tests(get_tests_response["results"])
            total = get_tests_response['total']
            all_tests.extend(tests)

            # Check if more results are available
            if len(all_tests) == total:
                break

            start_at += self.limit
        return f"Extracted tests ({len(all_tests)}):\n{all_tests}"

    def create_test(self, graphql_mutation: str) -> str:
        """Create new test in XRAY per defined XRAY graphql mutation"""

        logger.info(f"graphql_mutation to create new test: {graphql_mutation}")
        try:
            create_test_response = self._client.execute(query=graphql_mutation)
        except Exception as e:
            return ToolException(f"Unable to create new test due to error:\n{str(e)}")
        return f"Created test case:\n{create_test_response}"

    def create_tests(self, graphql_mutations: list[str]) -> list[str]:
        """Create new tests in XRAY per defined XRAY graphql mutations"""
        return [self.create_test(mutation) for mutation in graphql_mutations]

    def execute_graphql(self, graphql: str) -> str:
        """Executes custom graphql query or mutation"""

        logger.info(f"The following graphql will be executed: {graphql}")
        try:
            return f"Result of graphql execution:\n{self._client.execute(query=graphql)}"
        except Exception as e:
            return ToolException(f"Unable to execute custom graphql due to error:\n{str(e)}")

    def _base_loader(
            self, jql: Optional[str] = None, graphql: Optional[str] = None, include_attachments: Optional[bool] = False,
            skip_attachment_extensions: Optional[List[str]] = None, **kwargs: Any
    ) -> Generator[Document, None, None]:
        """
        Index Xray test cases into vector store using JQL query or custom GraphQL.

        Args:
            jql: JQL query for searching test cases
            graphql: Custom GraphQL query for advanced data extraction
            include_attachments: Whether to include attachment content in indexing
        Examples:
            # Using JQL
            jql = 'project = "CALC" AND testType = "Manual" AND labels in ("Smoke", "Critical")'

            # Using GraphQL
            graphql = 'query { getTests(jql: "project = \\"CALC\\"") { results { issueId jira(fields: ["key"]) steps { action result } } } }'
        """

        self._skipped_attachment_extensions = skip_attachment_extensions if skip_attachment_extensions else []
        self._include_attachments = include_attachments

        if not jql and not graphql:
            raise ToolException("Either 'jql' or 'graphql' parameter must be provided.")

        if jql and graphql:
            raise ToolException("Please provide either 'jql' or 'graphql', not both.")

        try:
            if jql:
                tests_data = self._get_tests_direct(jql)

            elif graphql:
                graphql_data = self._execute_graphql_direct(graphql)

                if "data" in graphql_data:
                    if "getTests" in graphql_data["data"]:
                        tests_data = graphql_data["data"]["getTests"].get("results", [])
                    else:
                        tests_data = []
                        for key, value in graphql_data["data"].items():
                            if isinstance(value, list):
                                tests_data = value
                                break
                            elif isinstance(value, dict) and "results" in value:
                                tests_data = value["results"]
                                break
                else:
                    tests_data = graphql_data if isinstance(graphql_data, list) else []

                if not tests_data:
                    raise ToolException("No test data found in GraphQL response")

            for test in tests_data:
                page_content = ""
                content_structure = {}
                test_type_name = test.get("testType", {}).get("name", "").lower()

                attachment_ids = []
                if include_attachments and "steps" in test:
                    for step in test["steps"]:
                        if "attachments" in step and step["attachments"]:
                            for attachment in step["attachments"]:
                                if attachment and "id" in attachment:
                                    attachment_ids.append(str(attachment["id"]))

                if test_type_name == "manual" and "steps" in test and test["steps"]:
                    steps_content = []
                    for step in test["steps"]:
                        step_obj = {}
                        if step.get("action"):
                            step_obj["action"] = step["action"]
                        if step.get("data"):
                            step_obj["data"] = step["data"]
                        if step.get("result"):
                            step_obj["result"] = step["result"]
                        if step_obj:
                            steps_content.append(step_obj)
                    
                    content_structure = {"steps": steps_content}
                    if attachment_ids:
                        content_structure["attachment_ids"] = sorted(attachment_ids)

                elif test_type_name == "cucumber" and test.get("gherkin"):
                    content_structure = {"gherkin": test["gherkin"]}
                    if attachment_ids:
                        content_structure["attachment_ids"] = sorted(attachment_ids)

                elif test.get("unstructured"):
                    content_structure = {"unstructured": test["unstructured"]}
                    if attachment_ids:
                        content_structure["attachment_ids"] = sorted(attachment_ids)

                metadata = {"doctype": self.doctype}

                if "jira" in test and test["jira"]:
                    jira_data = test["jira"]
                    metadata["key"] = jira_data.get("key", "")
                    metadata["summary"] = jira_data.get("summary", "")

                    if "created" in jira_data:
                        metadata["created_on"] = jira_data["created"]

                    if jira_data.get("description"):
                        content_structure["description"] = jira_data.get("description")

                    page_content = json.dumps(content_structure if content_structure.items() else "", indent=2)

                    content_hash = hashlib.sha256(page_content.encode('utf-8')).hexdigest()[:16]
                    metadata["updated_on"] = content_hash

                    if "assignee" in jira_data and jira_data["assignee"]:
                        metadata["assignee"] = str(jira_data["assignee"])

                    if "reporter" in jira_data and jira_data["reporter"]:
                        metadata["reporter"] = str(jira_data["reporter"])

                if "issueId" in test:
                    metadata["issueId"] = str(test["issueId"])
                    metadata["id"] = str(test["issueId"])
                if "projectId" in test:
                    metadata["projectId"] = str(test["projectId"])
                if "testType" in test and test["testType"]:
                    metadata["testType"] = test["testType"].get("name", "")
                    metadata["testKind"] = test["testType"].get("kind", "")

                if include_attachments and "steps" in test:
                    attachments_data = []
                    for step in test["steps"]:
                        if "attachments" in step and step["attachments"]:
                            for attachment in step["attachments"]:
                                if attachment and "id" in attachment and "filename" in attachment:
                                    attachment['step_id'] = step['id']
                                    attachments_data.append(attachment)
                    if attachments_data:
                        metadata["_attachments_data"] = attachments_data

                metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = page_content.encode('utf-8')
                yield Document(page_content='', metadata=metadata)
                
        except Exception as e:
            logger.error(f"Error processing test data: {e}")
            raise ToolException(f"Error processing test data: {e}")

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        """
        Process an existing base document to extract relevant metadata for full document preparation.
        Used for late processing of documents after we ensure that the document has to be indexed to avoid
        time-consuming operations for documents which might be useless.

        Args:
            document (Document): The base document to process.

        Returns:
            Generator[Document, None, None]: A generator yielding processed Document objects with metadata.
        """
        try:
            attachments_data = document.metadata.get("_attachments_data", [])
                
            issue_id = document.metadata.get("id")
            
            for attachment in attachments_data:
                filename = attachment.get('filename', '')
                if filename:
                    ext = f".{filename.split('.')[-1].lower()}"
                else:
                    ext = ""

                if hasattr(self, '_skipped_attachment_extensions') and ext in self._skipped_attachment_extensions:
                    logger.info(f"Skipping attachment {filename} due to extension filter: {ext}")
                    continue
                
                attachment_id = f"attach_{attachment['id']}"
                document.metadata.setdefault(
                    IndexerKeywords.DEPENDENT_DOCS.value, []
                ).append(attachment_id)

                try:
                    attachment_metadata = {
                        'id': str(attachment_id),
                        'issue_key': document.metadata.get('key', ''),
                        'issueId': str(issue_id),
                        'projectId': document.metadata.get('projectId', ''),
                        'source': f"xray_test_{issue_id}",
                        'filename': filename,
                        'download_link': attachment.get('downloadLink', ''),
                        'entity_type': 'test_case_attachment',
                        'step_id': attachment.get('step_id', ''),
                        'key': document.metadata.get('key', ''),
                        IndexerKeywords.PARENT.value: document.metadata.get('id', str(issue_id)),
                        'type': 'attachment',
                        'doctype': self.doctype,
                    }
                    yield from self._process_attachment(attachment, attachment_metadata)
                except Exception as e:
                    logger.error(f"Failed to process attachment {filename}: {str(e)}")
                    continue
            
            if "_attachments_data" in document.metadata:
                del document.metadata["_attachments_data"]
            
        except Exception as e:
            logger.error(f"Error processing document for attachments: {e}")

    def _process_attachment(self, attachment: Dict[str, Any], attachment_metadata) -> Generator[Document, None, None]:
        """
        Processes an attachment to extract its content.

        Args:
            attachment (Dict[str, Any]): The attachment data containing id, filename, and downloadLink.

        Returns:
            str: String description/content of the attachment.
        """
        try:
            download_link = attachment.get('downloadLink')
            filename = attachment.get('filename', '')

            try:
                auth_token = self._ensure_auth_token()
                headers = {'Authorization': f'Bearer {auth_token}'}
                response = requests.get(download_link, headers=headers, timeout=30)
                response.raise_for_status()

                yield from self._load_attachment(content=response.content,
                                                 file_name=filename,
                                                 attachment_metadata=attachment_metadata)

            except requests.RequestException as req_e:
                logger.error(f"Unable to download attachment {filename} with existing token: {req_e}")
                
                # If the token fails (401 Unauthorized), try to re-authenticate and retry
                if "401" in str(req_e) or "Unauthorized" in str(req_e):
                    try:
                        logger.info(f"Re-authenticating for attachment download: {filename}")
                        # Re-authenticate to get a fresh token
                        auth_url = f"{self.base_url}/api/v1/authenticate"
                        auth_data = {
                            "client_id": self.client_id,
                            "client_secret": self.client_secret.get_secret_value() if hasattr(self.client_secret, 'get_secret_value') else str(self.client_secret)
                        }
                        auth_response = requests.post(auth_url, json=auth_data, timeout=30)
                        auth_response.raise_for_status()
                        fresh_token = auth_response.json()
                        
                        fresh_headers = {'Authorization': f'Bearer {fresh_token}'}
                        response = requests.get(download_link, headers=fresh_headers, timeout=60)
                        response.raise_for_status()

                        yield from self._load_attachment(content=response.content,
                                                         file_name=filename,
                                                         attachment_metadata=attachment_metadata)
                            
                    except Exception as reauth_e:
                        logger.error(f"Re-authentication and retry failed for {filename}: {reauth_e}")
                else:
                    try:
                        auth_token = self._ensure_auth_token()
                        fallback_headers = {
                            'Authorization': f'Bearer {auth_token}',
                            'User-Agent': 'Mozilla/5.0 (compatible; XrayAPI/1.0; Python)',
                            'Accept': '*/*'
                        }
                        response = requests.get(download_link, headers=fallback_headers, timeout=60)
                        response.raise_for_status()

                        yield from self._load_attachment(content=response.content,
                                                         file_name=filename,
                                                         attachment_metadata=attachment_metadata)
                            
                    except Exception as fallback_e:
                        logger.error(f"Fallback download also failed for {filename}: {fallback_e}")
                    
            except Exception as parse_e:
                logger.error(f"Unable to parse attachment {filename}: {parse_e}")
                
        except Exception as e:
            logger.error(f"Error processing attachment: {e}")

    def _load_attachment(self, content, file_name, attachment_metadata) -> Generator[Document, None, None]:
        attachment_metadata[IndexerKeywords.CONTENT_IN_BYTES.value] = content
        attachment_metadata[IndexerKeywords.CONTENT_FILE_NAME.value] = file_name
        yield Document(page_content='', metadata=attachment_metadata)

    def _index_tool_params(self, **kwargs) -> dict[str, tuple[type, Field]]:
        return {
            'chunking_tool': (Literal['json', ''],
                              Field(description="Name of chunking tool for base document", default='json')),
            'jql': (Optional[str], Field(description="""JQL query for searching test cases in Xray.

            Standard JQL query syntax for filtering Xray test cases. Examples:
            - project = "CALC" AND testType = "Manual"
            - project = "CALC" AND labels in ("Smoke", "Regression")
            - project = "CALC" AND summary ~ "login"
            - project = "CALC" AND testType = "Manual" AND labels = "Critical"

            Supported fields:
            - project: project key filter (e.g., project = "CALC")
            - testType: filter by test type (e.g., testType = "Manual")
            - labels: filter by labels (e.g., labels = "Smoke" or labels in ("Smoke", "Regression"))
            - summary: search in test summary (e.g., summary ~ "login")
            - description: search in test description
            - status: filter by test status
            - priority: filter by test priority

            Example:
                'project = "CALC" AND testType = "Manual" AND labels in ("Smoke", "Critical")'
            """, default=None)),
            'graphql': (Optional[str], Field(description="""Custom GraphQL query for advanced data extraction.

            Use this for custom GraphQL queries that return test data. The query should return test objects
            with relevant fields like issueId, jira, testType, steps, etc.

            Example:
                'query { getTests(jql: "project = \\"CALC\\"") { results { issueId jira(fields: ["key"]) testType { name } steps { action result } } } }'
            """, default=None)),
            'include_attachments': (Optional[bool],
                                    Field(description="Whether to include attachment content in indexing",
                                          default=False)),
            'skip_attachment_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing attachments (e.g., ['.exe', '.zip', '.bin'])",
                default=None)),
        }

    def _get_tests_direct(self, jql: str) -> List[Dict]:
        """Direct method to get test data without string formatting"""
        start_at = 0
        all_tests = []
        logger.info(f"[indexing] jql to get tests: {jql}")
        
        while True:
            try:
                get_tests_response = self._client.execute(query=_get_tests_query,
                                                          variables={"jql": jql, "start": start_at,
                                                                     "limit": self.limit})['data']["getTests"]
            except Exception as e:
                raise ToolException(f"Unable to get tests due to error: {str(e)}")
            
            tests = _parse_tests(get_tests_response["results"])
            total = get_tests_response['total']
            all_tests.extend(tests)

            if len(all_tests) == total:
                break

            start_at += self.limit
        
        return all_tests

    def _execute_graphql_direct(self, graphql: str) -> Any:
        """Direct method to execute GraphQL and return parsed data"""
        logger.info(f"[indexing] executing GraphQL query: {graphql}")
        try:
            return self._client.execute(query=graphql)
        except Exception as e:
            raise ToolException(f"Unable to execute GraphQL due to error: {str(e)}")

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "get_tests",
                "description": self.get_tests.__doc__,
                "args_schema": XrayGetTests,
                "ref": self.get_tests,
            },
            {
                "name": "create_test",
                "description": self.create_test.__doc__,
                "args_schema": XrayCreateTest,
                "ref": self.create_test,
            },
            {
                "name": "create_tests",
                "description": self.create_tests.__doc__,
                "args_schema": XrayCreateTests,
                "ref": self.create_tests,
            },
            {
                "name": "execute_graphql",
                "description": self.execute_graphql.__doc__,
                "args_schema": XrayGrapql,
                "ref": self.execute_graphql,
            }
        ]