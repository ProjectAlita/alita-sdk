import logging
from typing import Optional, Any, List

import requests
from langchain_core.tools import ToolException
from pydantic import create_model, PrivateAttr, SecretStr
from pydantic import model_validator
from pydantic.fields import Field
from python_graphql_client import GraphqlClient

from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

_get_tests_query = """query GetTests($jql: String!, $limit:Int!, $start: Int)
{
    getTests(jql: $jql, limit: $limit, start: $start) {
        total
        start
        limit
        results {
            issueId
            jira(fields: ["key"])
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


def _parse_tests(test_results) -> List[Any]:
    """Handles tests in order to minimize tests' output"""

    for test_item in test_results:
        # remove preconditions if it is absent
        if test_item['preconditions']['total'] == 0:
            del test_item['preconditions']
    return test_results


class XrayApiWrapper(BaseToolApiWrapper):
    _default_base_url: str = 'https://xray.cloud.getxray.app'
    base_url: str = ""
    client_id: str = None,
    client_secret: SecretStr = None,
    limit: Optional[int] = 100,
    _client: Optional[GraphqlClient] = PrivateAttr()

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
