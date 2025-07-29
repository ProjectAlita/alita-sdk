import logging
from typing import Any, Dict, Generator, List, Optional

import requests
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from pydantic import PrivateAttr, SecretStr, create_model, model_validator, Field
from pydantic.fields import Field
from pydantic.fields import Field
from python_graphql_client import GraphqlClient

from ..elitea_base import (
    BaseIndexParams,
    BaseVectorStoreToolApiWrapper,
    extend_with_vector_tools,
)

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
            jira(fields: ["key", "summary", "created", "updated", "assignee.displayName", "reporter.displayName"])
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
    graphql_mutations=(list[str], Field(description="list of GraphQL mutations:\n" + _graphql_mutation_description))
)

# Schema for indexing Xray data into vector store
XrayIndexData = create_model(
    "XrayIndexData",
    __base__=BaseIndexParams,
    jql=(Optional[str], Field(description="""JQL query for searching test cases in Xray.

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
    graphql=(Optional[str], Field(description="""Custom GraphQL query for advanced data extraction.
    
    Use this for custom GraphQL queries that return test data. The query should return test objects
    with relevant fields like issueId, jira, testType, steps, etc.
    
    Example:
        'query { getTests(jql: "project = \\"CALC\\"") { results { issueId jira(fields: ["key"]) testType { name } steps { action result } } } }'
    """, default=None)),
    progress_step=(Optional[int], Field(description="Progress step for tracking indexing progress", default=None)),
    clean_index=(Optional[bool], Field(default=False, description="Optional flag to enforce clean existing index before indexing new data")),
)


def _parse_tests(test_results) -> List[Any]:
    """Handles tests in order to minimize tests' output"""

    for test_item in test_results:
        # remove preconditions if it is absent
        if test_item['preconditions']['total'] == 0:
            del test_item['preconditions']
    return test_results


class XrayApiWrapper(BaseVectorStoreToolApiWrapper):
    _default_base_url: str = 'https://xray.cloud.getxray.app'
    base_url: str = ""
    client_id: str = None,
    client_secret: SecretStr = None,
    limit: Optional[int] = 100,
    _client: Optional[GraphqlClient] = PrivateAttr()

    # Vector store fields
    llm: Any = None
    connection_string: Optional[SecretStr] = None
    collection_name: Optional[str] = None
    embedding_model: Optional[str] = "HuggingFaceEmbeddings"
    embedding_model_params: Optional[Dict[str, Any]] = {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}
    vectorstore_type: Optional[str] = "PGVector"
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
        values['base_url'] = values.get('base_url', '') or cls._default_base_url
        auth_url = f"{values['base_url']}/api/v1/authenticate"
        auth_data = {
            "client_id": client_id,
            "client_secret": client_secret
        }
        try:
            auth_response = requests.post(auth_url, json=auth_data)
            token = auth_response.json()
            cls._client = GraphqlClient(endpoint=f"{values['base_url']}/api/v2/graphql",
                                        headers={'Authorization': f'Bearer {token}'})
        except Exception as e:
            if "invalid or doesn't have the required permissions" in str(e):
                masked_secret = '*' * (len(client_secret) - 4) + client_secret[-4:] if client_secret is not None else "UNDEFINED"
                return ToolException(f"Please, check you credentials ({values['client_id']} / {masked_secret}). Unable")
        return values

    def __init__(self, **data):
        super().__init__(**data)
        # Set private attributes after initialization if they were passed
        if '_auth_token' in data:
            self._auth_token = data['_auth_token']
        if '_graphql_endpoint' in data:
            self._graphql_endpoint = data['_graphql_endpoint']

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
        self, jql: Optional[str] = None, graphql: Optional[str] = None
    ) -> Generator[Document, None, None]:
        """
        Index Xray test cases into vector store using JQL query or custom GraphQL.

        Args:
            jql: JQL query for searching test cases
            graphql: Custom GraphQL query for advanced data extraction
        Examples:
            # Using JQL
            jql = 'project = "CALC" AND testType = "Manual" AND labels in ("Smoke", "Critical")'

            # Using GraphQL
            graphql = 'query { getTests(jql: "project = \\"CALC\\"") { results { issueId jira(fields: ["key"]) steps { action result } } } }'
        """

        if not jql and not graphql:
            raise ToolException("Either 'jql' or 'graphql' parameter must be provided.")

        if jql and graphql:
            raise ToolException("Please provide either 'jql' or 'graphql', not both.")

        try:
            if jql:
                tests_data = self._get_tests_direct(jql)

            elif graphql:
                # Use direct GraphQL execution
                graphql_data = self._execute_graphql_direct(graphql)

                # Extract tests from GraphQL response (handle different possible structures)
                if "data" in graphql_data:
                    if "getTests" in graphql_data["data"]:
                        tests_data = graphql_data["data"]["getTests"].get("results", [])
                    else:
                        # Try to find any list of test objects in the data
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

            docs: List[Document] = []
            for test in tests_data:
                page_content = ""
                test_type_name = test.get("testType", {}).get("name", "").lower()

                if test_type_name == "manual" and "steps" in test and test["steps"]:
                    import json

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
                    page_content = json.dumps(steps_content, indent=2)

                elif test_type_name == "cucumber" and test.get("gherkin"):
                    page_content = test["gherkin"]

                elif test.get("unstructured"):
                    page_content = test["unstructured"]

                metadata = {"doctype": self.doctype}

                if "jira" in test and test["jira"]:
                    jira_data = test["jira"]
                    metadata["key"] = jira_data.get("key", "")
                    metadata["summary"] = jira_data.get("summary", "")

                    if "created" in jira_data:
                        metadata["created_on"] = jira_data["created"]
                    if "updated" in jira_data:
                        metadata["updated_on"] = jira_data["updated"]

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

                docs.append(Document(page_content=page_content, metadata=metadata))
        except Exception as e:
            logger.error(f"Error processing test data: {e}")
            raise ToolException(f"Error processing test data: {e}")

        return docs
    
    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        yield document

    def index_data(
        self,
        jql: Optional[str] = None,
        graphql: Optional[str] = None,
        collection_suffix: str = "",
        progress_step: Optional[int] = None,
        clean_index: Optional[bool] = False,
    ) -> str:
        """Index Xray test cases into vector store using JQL query or custom GraphQL."""
        if not get_embeddings:
            raise ToolException(
                "get_embeddings function not available. Please check the import."
            )
        docs = self._base_loader(jql=jql, graphql=graphql)
        embedding = get_embeddings(self.embedding_model, self.embedding_model_params)
        vs = self._init_vector_store(collection_suffix, embeddings=embedding)

        return vs.index_documents(
            docs, progress_step=progress_step, clean_index=clean_index
        )
    
    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        for attachment_id in document.metadata.get('attachment_ids', []):
            content_generator = self._client.get_attachment_content(id=attachment_id, download=True)
            content = ''.join(str(item) for item in content_generator)
            yield Document(page_content=content, metadata={'id': attachment_id})

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
            
            # Get raw test data without parsing
            tests = _parse_tests(get_tests_response["results"])
            total = get_tests_response['total']
            all_tests.extend(tests)

            # Check if more results are available
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

    @extend_with_vector_tools
    def get_available_tools(self):
        tools = [
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
            },
            {
                "name": "index_data",
                "description": self.index_data.__doc__,
                "args_schema": XrayIndexData,
                "ref": self.index_data,
            }
        ]

        tools.extend(self._get_vector_search_tools())
        return tools