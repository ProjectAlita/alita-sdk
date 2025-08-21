import json
import logging
from typing import Optional, Generator, Literal
from pydantic import model_validator, create_model, Field, SecretStr, PrivateAttr

from .client import ZephyrEssentialAPI
from ..elitea_base import extend_with_vector_tools, BaseVectorStoreToolApiWrapper
from langchain_core.documents import Document
from langchain_core.tools import ToolException

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools


class ZephyrEssentialApiWrapper(NonCodeIndexerToolkit):
    token: SecretStr
    _client: ZephyrEssentialAPI = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        base_url = values.get("base_url", "https://prod-api.zephyr4jiracloud.com/v2")
        token = values.get("token", None)
        if not token:
            raise ValueError("token is required.")
        cls._client = ZephyrEssentialAPI(
            base_url=base_url,
            token=token
        )
        return super().validate_toolkit(values)

    def list_test_cases(self, project_key: Optional[str] = None, folder_id: Optional[str] = None, max_results: int = None, start_at: int = None):
        """List test cases with optional filters."""
        return self._client.list_test_cases(project_key=project_key, folder_id=folder_id, max_results=max_results, start_at=start_at)['values']

    def create_test_case(self, json: str):
        """Create a new test case."""
        test_case_data = self._parse_json(json)
        return self._client.create_test_case(test_case_data)

    def get_test_case(self, test_case_key: str):
        """Retrieve details of a specific test case."""
        return self._client.get_test_case(test_case_key)

    def update_test_case(self, test_case_key: str, json: str):
        """Update an existing test case."""
        test_case_data = self._parse_json(json)
        return self._client.update_test_case(test_case_key, test_case_data)

    def get_test_case_links(self, test_case_key: str):
        """Retrieve links associated with a test case."""
        return self._client.get_test_case_links(test_case_key)

    def create_test_case_issue_link(self, test_case_key: str, json: str):
        """Create an issue link for a test case."""
        issue_link_data = self._parse_json(json)
        return self._client.create_test_case_issue_link(test_case_key, issue_link_data)

    def create_test_case_web_link(self, test_case_key: str, json: str):
        """Create a web link for a test case."""
        web_link_data = self._parse_json(json)
        return self._client.create_test_case_web_link(test_case_key, web_link_data)

    def list_test_case_versions(self, test_case_key: str, max_results: int = None, start_at: int = None):
        """List versions of a test case."""
        return self._client.list_test_case_versions(test_case_key, max_results=max_results, start_at=start_at)

    def get_test_case_version(self, test_case_key: str, version: int):
        """Retrieve a specific version of a test case."""
        return self._client.get_test_case_version(test_case_key, version)

    def get_test_case_test_script(self, test_case_key: str):
        """Retrieve the test script of a test case."""
        try:
            return self._client.get_test_case_test_script(test_case_key)
        except Exception as e:
            return ToolException(f"Failed while receiving test steps: {e}")

    def create_test_case_test_script(self, test_case_key: str, json: str):
        """Create a test script for a test case."""
        test_script_data = self._parse_json(json)
        return self._client.create_test_case_test_script(test_case_key, test_script_data)

    def get_test_case_test_steps(self, test_case_key: str, max_results: int = None, start_at: int = None):
        """List test steps of a test case."""
        try:
            return self._client.get_test_case_test_steps(test_case_key, max_results=max_results, start_at=start_at)["values"]
        except Exception as e:
            return ToolException(f"Failed while receiving test steps: {e}")

    def create_test_case_test_steps(self, test_case_key: str, json: str):
        """Create test steps for a test case."""
        test_steps_data = self._parse_json(json)
        return self._client.create_test_case_test_steps(test_case_key, test_steps_data)

    def list_test_cycles(self, project_key: Optional[str] = None, folder_id: Optional[str] = None, jira_project_version_id: Optional[str] = None, max_results: int = None, start_at: int = None):
        """List test cycles with optional filters."""
        return self._client.list_test_cycles(project_key=project_key, folder_id=folder_id, jira_project_version_id=jira_project_version_id, max_results=max_results, start_at=start_at)

    def create_test_cycle(self, json: str):
        """Create a new test cycle."""
        test_cycle_data = self._parse_json(json)
        return self._client.create_test_cycle(test_cycle_data)

    def get_test_cycle(self, test_cycle_id_or_key: str):
        """Retrieve details of a specific test cycle."""
        return self._client.get_test_cycle(test_cycle_id_or_key)

    def update_test_cycle(self, test_cycle_id_or_key: str, json: str):
        """Update an existing test cycle."""
        test_cycle_data = self._parse_json(json)
        return self._client.update_test_cycle(test_cycle_id_or_key, test_cycle_data)

    def get_test_cycle_links(self, test_cycle_id_or_key: str):
        """Retrieve links associated with a test cycle."""
        return self._client.get_test_cycle_links(test_cycle_id_or_key)

    def create_test_cycle_issue_link(self, test_cycle_id_or_key: str, json: str):
        """Create an issue link for a test cycle."""
        issue_link_data = self._parse_json(json)
        return self._client.create_test_cycle_issue_link(test_cycle_id_or_key, issue_link_data)

    def create_test_cycle_web_link(self, test_cycle_id_or_key: str, json: str):
        """Create a web link for a test cycle."""
        web_link_data = self._parse_json(json)
        return self._client.create_test_cycle_web_link(test_cycle_id_or_key, web_link_data)

    def list_test_executions(self, project_key: Optional[str] = None, test_cycle: Optional[str] = None, test_case: Optional[str] = None, max_results: int = None, start_at: int = None):
        """List test executions with optional filters."""
        return self._client.list_test_executions(project_key=project_key, test_cycle=test_cycle, test_case=test_case, max_results=max_results, start_at=start_at)

    def create_test_execution(self, json: str):
        """Create a new test execution."""
        test_execution_data = self._parse_json(json)
        return self._client.create_test_execution(test_execution_data)

    def get_test_execution(self, test_execution_id_or_key: str):
        """Retrieve details of a specific test execution."""
        return self._client.get_test_execution(test_execution_id_or_key)

    def update_test_execution(self, test_execution_id_or_key: str, json: str):
        """Update an existing test execution."""
        test_execution_data = self._parse_json(json)
        return self._client.update_test_execution(test_execution_id_or_key, test_execution_data)

    def get_test_execution_test_steps(self, test_execution_id_or_key: str, max_results: int = None, start_at: int = None):
        """List test steps of a test execution."""
        return self._client.get_test_execution_test_steps(test_execution_id_or_key, max_results=max_results, start_at=start_at)

    def update_test_execution_test_steps(self, test_execution_id_or_key: str, json: str):
        """Update test steps of a test execution."""
        test_steps_data = self._parse_json(json)
        return self._client.update_test_execution_test_steps(test_execution_id_or_key, test_steps_data)

    def sync_test_execution_script(self, test_execution_id_or_key: str):
        """Sync the test execution script."""
        return self._client.sync_test_execution_script(test_execution_id_or_key)

    def list_test_execution_links(self, test_execution_id_or_key: str):
        """List links associated with a test execution."""
        return self._client.list_test_execution_links(test_execution_id_or_key)

    def create_test_execution_issue_link(self, test_execution_id_or_key: str, json: str):
        """Create an issue link for a test execution."""
        issue_link_data = self._parse_json(json)
        return self._client.create_test_execution_issue_link(test_execution_id_or_key, issue_link_data)

    def list_projects(self, max_results: int = None, start_at: int = None):
        """List all projects."""
        return self._client.list_projects(max_results=max_results, start_at=start_at)

    def get_project(self, project_id_or_key: str):
        """Retrieve details of a specific project."""
        return self._client.get_project(project_id_or_key)

    def list_folders(self, project_key: Optional[str] = None, folder_type: Optional[str] = None, max_results: int = None, start_at: int = None):
        """List folders with optional filters."""
        return self._client.list_folders(project_key=project_key, folder_type=folder_type, max_results=max_results, start_at=start_at)

    def create_folder(self, json: str):
        """Create a new folder."""
        folder_data = self._parse_json(json)
        return self._client.create_folder(folder_data)

    def get_folder(self, folder_id: str):
        """Retrieve details of a specific folder."""
        return self._client.get_folder(folder_id)

    def delete_link(self, link_id: str):
        """Delete a specific link."""
        return self._client.delete_link(link_id)

    def get_issue_link_test_cases(self, issue_key: str):
        """Retrieve test cases linked to an issue."""
        return self._client.get_issue_link_test_cases(issue_key)

    def get_issue_link_test_cycles(self, issue_key: str):
        """Retrieve test cycles linked to an issue."""
        return self._client.get_issue_link_test_cycles(issue_key)

    def get_issue_link_test_plans(self, issue_key: str):
        """Retrieve test plans linked to an issue."""
        return self._client.get_issue_link_test_plans(issue_key)

    def get_issue_link_test_executions(self, issue_key: str):
        """Retrieve test executions linked to an issue."""
        return self._client.get_issue_link_test_executions(issue_key)

    def create_custom_executions(self, project_key: str, files: str, auto_create_test_cases: bool = False):
        """Create custom executions."""
        return self._client.create_custom_executions(project_key, files, auto_create_test_cases)

    def create_cucumber_executions(self, project_key: str, files: str, auto_create_test_cases: bool = False):
        """Create cucumber executions."""
        return self._client.create_cucumber_executions(project_key, files, auto_create_test_cases)

    def create_junit_executions(self, project_key: str, files: str, auto_create_test_cases: bool = False):
        """Create JUnit executions."""
        return self._client.create_junit_executions(project_key, files, auto_create_test_cases)

    def retrieve_bdd_test_cases(self, project_key: str):
        """Retrieve BDD test cases."""
        return self._client.retrieve_bdd_test_cases(project_key)

    def healthcheck(self):
        """Perform a health check on the API."""
        return self._client.healthcheck()

    def _parse_json(self, json_str: str):
        """Helper method to parse JSON strings."""
        import json
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {str(e)}")

    def _index_tool_params(self):
        return {
            'chunking_tool':(Literal[None, 'json'],
                           Field(description="Name of chunking tool", default='json'))
        }

    def _base_loader(self, **kwargs) -> Generator[Document, None, None]:
        try:
            test_cases = self.list_test_cases()
        except Exception as e:
            raise ToolException(f"Unable to extract test cases: {e}")

        for case in test_cases:
            metadata = {
                k: v for k, v in case.items()
                if isinstance(v, (str, int, float, bool, list, dict))
            }
            metadata['type'] = "TEST_CASE"

            yield Document(page_content="", metadata=metadata)

    def _extend_data(self, documents: Generator[Document, None, None]) -> Generator[Document, None, None]:
        for document in documents:
            try:
                if document.metadata['type'] and document.metadata['type'] == "TEST_CASE":
                    additional_content = self._process_test_case(document.metadata['key'])
                    document.page_content = json.dumps(additional_content)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON from document: {e}")
            yield document

    def _process_test_case(self, key):
        steps = self.get_test_case_test_steps(key)
        script = self.get_test_case_test_script(key)
        additional_content = {
            "steps": "" if isinstance(steps, ToolException) else steps,
            "script": "" if isinstance(script, ToolException) else script,
        }
        return additional_content

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "list_test_cases",
                "description": self.list_test_cases.__doc__,
                "args_schema": ListTestCases,
                "ref": self.list_test_cases,
            },
            {
                "name": "create_test_case",
                "description": self.create_test_case.__doc__,
                "args_schema": CreateTestCase,
                "ref": self.create_test_case,
            },
            {
                "name": "get_test_case",
                "description": self.get_test_case.__doc__,
                "args_schema": GetTestCase,
                "ref": self.get_test_case,
            },
            {
                "name": "update_test_case",
                "description": self.update_test_case.__doc__,
                "args_schema": UpdateTestCase,
                "ref": self.update_test_case,
            },
            {
                "name": "get_test_case_links",
                "description": self.get_test_case_links.__doc__,
                "args_schema": GetTestCaseLinks,
                "ref": self.get_test_case_links,
            },
            {
                "name": "create_test_case_issue_link",
                "description": self.create_test_case_issue_link.__doc__,
                "args_schema": CreateTestCaseIssueLink,
                "ref": self.create_test_case_issue_link,
            },
            {
                "name": "create_test_case_web_link",
                "description": self.create_test_case_web_link.__doc__,
                "args_schema": CreateTestCaseWebLink,
                "ref": self.create_test_case_web_link,
            },
            {
                "name": "list_test_case_versions",
                "description": self.list_test_case_versions.__doc__,
                "args_schema": ListTestCaseVersions,
                "ref": self.list_test_case_versions,
            },
            {
                "name": "get_test_case_version",
                "description": self.get_test_case_version.__doc__,
                "args_schema": GetTestCaseVersion,
                "ref": self.get_test_case_version,
            },
            {
                "name": "get_test_case_test_script",
                "description": self.get_test_case_test_script.__doc__,
                "args_schema": GetTestCaseTestScript,
                "ref": self.get_test_case_test_script,
            },
            {
                "name": "create_test_case_test_script",
                "description": self.create_test_case_test_script.__doc__,
                "args_schema": CreateTestCaseTestScript,
                "ref": self.create_test_case_test_script,
            },
            {
                "name": "get_test_case_test_steps",
                "description": self.get_test_case_test_steps.__doc__,
                "args_schema": GetTestCaseTestSteps,
                "ref": self.get_test_case_test_steps,
            },
            {
                "name": "create_test_case_test_steps",
                "description": self.create_test_case_test_steps.__doc__,
                "args_schema": CreateTestCaseTestSteps,
                "ref": self.create_test_case_test_steps,
            },
            {
                "name": "list_test_cycles",
                "description": self.list_test_cycles.__doc__,
                "args_schema": ListTestCycles,
                "ref": self.list_test_cycles,
            },
            {
                "name": "create_test_cycle",
                "description": self.create_test_cycle.__doc__,
                "args_schema": CreateTestCycle,
                "ref": self.create_test_cycle,
            },
            {
                "name": "get_test_cycle",
                "description": self.get_test_cycle.__doc__,
                "args_schema": GetTestCycle,
                "ref": self.get_test_cycle,
            },
            {
                "name": "update_test_cycle",
                "description": self.update_test_cycle.__doc__,
                "args_schema": UpdateTestCycle,
                "ref": self.update_test_cycle,
            },
            {
                "name": "get_test_cycle_links",
                "description": self.get_test_cycle_links.__doc__,
                "args_schema": GetTestCycleLinks,
                "ref": self.get_test_cycle_links,
            },
            {
                "name": "create_test_cycle_issue_link",
                "description": self.create_test_cycle_issue_link.__doc__,
                "args_schema": CreateTestCycleIssueLink,
                "ref": self.create_test_cycle_issue_link,
            },
            {
                "name": "create_test_cycle_web_link",
                "description": self.create_test_cycle_web_link.__doc__,
                "args_schema": CreateTestCycleWebLink,
                "ref": self.create_test_cycle_web_link,
            },
            {
                "name": "list_test_executions",
                "description": self.list_test_executions.__doc__,
                "args_schema": ListTestExecutions,
                "ref": self.list_test_executions,
            },
            {
                "name": "create_test_execution",
                "description": self.create_test_execution.__doc__,
                "args_schema": CreateTestExecution,
                "ref": self.create_test_execution,
            },
            {
                "name": "get_test_execution",
                "description": self.get_test_execution.__doc__,
                "args_schema": GetTestExecution,
                "ref": self.get_test_execution,
            },
            {
                "name": "update_test_execution",
                "description": self.update_test_execution.__doc__,
                "args_schema": UpdateTestExecution,
                "ref": self.update_test_execution,
            },
            {
                "name": "get_test_execution_test_steps",
                "description": self.get_test_execution_test_steps.__doc__,
                "args_schema": GetTestExecutionTestSteps,
                "ref": self.get_test_execution_test_steps,
            },
            {
                "name": "update_test_execution_test_steps",
                "description": self.update_test_execution_test_steps.__doc__,
                "args_schema": UpdateTestExecutionTestSteps,
                "ref": self.update_test_execution_test_steps,
            },
            {
                "name": "sync_test_execution_script",
                "description": self.sync_test_execution_script.__doc__,
                "args_schema": SyncTestExecutionScript,
                "ref": self.sync_test_execution_script,
            },
            {
                "name": "list_test_execution_links",
                "description": self.list_test_execution_links.__doc__,
                "args_schema": ListTestExecutionLinks,
                "ref": self.list_test_execution_links,
            },
            {
                "name": "create_test_execution_issue_link",
                "description": self.create_test_execution_issue_link.__doc__,
                "args_schema": CreateTestExecutionIssueLink,
                "ref": self.create_test_execution_issue_link,
            },
            {
                "name": "list_projects",
                "description": self.list_projects.__doc__,
                "args_schema": ListProjects,
                "ref": self.list_projects,
            },
            {
                "name": "get_project",
                "description": self.get_project.__doc__,
                "args_schema": GetProject,
                "ref": self.get_project,
            },
            {
                "name": "list_folders",
                "description": self.list_folders.__doc__,
                "args_schema": ListFolders,
                "ref": self.list_folders,
            },
            {
                "name": "create_folder",
                "description": self.create_folder.__doc__,
                "args_schema": CreateFolder,
                "ref": self.create_folder,
            },
            {
                "name": "get_folder",
                "description": self.get_folder.__doc__,
                "args_schema": GetFolder,
                "ref": self.get_folder,
            },
            {
                "name": "delete_link",
                "description": self.delete_link.__doc__,
                "args_schema": DeleteLink,
                "ref": self.delete_link,
            },
            {
                "name": "get_issue_link_test_cases",
                "description": self.get_issue_link_test_cases.__doc__,
                "args_schema": GetIssueLinkTestCases,
                "ref": self.get_issue_link_test_cases,
            },
            {
                "name": "get_issue_link_test_cycles",
                "description": self.get_issue_link_test_cycles.__doc__,
                "args_schema": GetIssueLinkTestCycles,
                "ref": self.get_issue_link_test_cycles,
            },
            {
                "name": "get_issue_link_test_plans",
                "description": self.get_issue_link_test_plans.__doc__,
                "args_schema": GetIssueLinkTestPlans,
                "ref": self.get_issue_link_test_plans,
            },
            {
                "name": "get_issue_link_test_executions",
                "description": self.get_issue_link_test_executions.__doc__,
                "args_schema": GetIssueLinkTestExecutions,
                "ref": self.get_issue_link_test_executions,
            },
            {
                "name": "create_custom_executions",
                "description": self.create_custom_executions.__doc__,
                "args_schema": CreateCustomExecutions,
                "ref": self.create_custom_executions,
            },
            {
                "name": "create_cucumber_executions",
                "description": self.create_cucumber_executions.__doc__,
                "args_schema": CreateCucumberExecutions,
                "ref": self.create_cucumber_executions,
            },
            {
                "name": "create_junit_executions",
                "description": self.create_junit_executions.__doc__,
                "args_schema": CreateJUnitExecutions,
                "ref": self.create_junit_executions,
            },
            {
                "name": "retrieve_bdd_test_cases",
                "description": self.retrieve_bdd_test_cases.__doc__,
                "args_schema": RetrieveBDDTestCases,
                "ref": self.retrieve_bdd_test_cases,
            },
            {
                "name": "healthcheck",
                "description": self.healthcheck.__doc__,
                "args_schema": create_model("NoInput"),
                "ref": self.healthcheck,
            }
        ]

ListTestCases = create_model(
    "ListTestCases",
    project_key=(Optional[str], Field(default=None, description="Project key to filter test cases.")),
    folder_id=(Optional[str], Field(default=None, description="Folder ID to filter test cases.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

CreateTestCase = create_model(
    "CreateTestCase",
    json=(str, Field(description=("""
        JSON body to create a test case. Example:
        {
          "name": "Test Case Name",
          "description": "Test Case Description",
          "projectKey": "PROJECT_KEY",
          "folderId": "FOLDER_ID"
        }
        """
    )))
)

GetTestCase = create_model(
    "GetTestCase",
    test_case_key=(str, Field(description="Key of the test case to retrieve."))
)

UpdateTestCase = create_model(
    "UpdateTestCase",
    test_case_key=(str, Field(description="Key of the test case to update.")),
    json=(str, Field(description=("""
        JSON body to update a test case. Example:
        {
          "name": "Updated Test Case Name",
          "description": "Updated Test Case Description"
        }
        """
    )))
)

GetTestCaseLinks = create_model(
    "GetTestCaseLinks",
    test_case_key=(str, Field(description="Key of the test case to retrieve links for."))
)

CreateTestCaseIssueLink = create_model(
    "CreateTestCaseIssueLink",
    test_case_key=(str, Field(description="Key of the test case to link an issue to.")),
    json=(str, Field(description=("""
        JSON body to create an issue link. Example:
        {
          "issueKey": "ISSUE_KEY",
          "description": "Link Description"
        }
        """
    )))
)

CreateTestCaseWebLink = create_model(
    "CreateTestCaseWebLink",
    test_case_key=(str, Field(description="Key of the test case to link a web link to.")),
    json=(str, Field(description=("""
        JSON body to create a web link. Example:
        {
          "url": "https://example.com",
          "description": "Web Link Description"
        }"
        """
    )))
)

ListTestCaseVersions = create_model(
    "ListTestCaseVersions",
    test_case_key=(str, Field(description="Key of the test case to list versions for.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

GetTestCaseVersion = create_model(
    "GetTestCaseVersion",
    test_case_key=(str, Field(description="Key of the test case to retrieve a specific version for.")),
    version=(int, Field(description="Version number to retrieve."))
)

GetTestCaseTestScript = create_model(
    "GetTestCaseTestScript",
    test_case_key=(str, Field(description="Key of the test case to retrieve the test script for."))
)

CreateTestCaseTestScript = create_model(
    "CreateTestCaseTestScript",
    test_case_key=(str, Field(description="Key of the test case to create a test script for.")),
    json=(str, Field(description=("""
        JSON body to create a test script. Example:
        {
          "script": "Test Script Content"
        }
        """
    )))
)

GetTestCaseTestSteps = create_model(
    "GetTestCaseTestSteps",
    test_case_key=(str, Field(description="Key of the test case to retrieve test steps for.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

CreateTestCaseTestSteps = create_model(
    "CreateTestCaseTestSteps",
    test_case_key=(str, Field(description="Key of the test case to create test steps for.")),
    json=(str, Field(description=("""
        JSON body to create test steps. Example:
        [
          {
            "step": "Step 1",
            "data": "Test Data",
            "result": "Expected Result"
          }
        ]
        """
    )))
)

ListTestCycles = create_model(
    "ListTestCycles",
    project_key=(Optional[str], Field(default=None, description="Project key to filter test cycles.")),
    folder_id=(Optional[str], Field(default=None, description="Folder ID to filter test cycles.")),
    jira_project_version_id=(Optional[str], Field(default=None, description="JIRA project version ID to filter test cycles.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

CreateTestCycle = create_model(
    "CreateTestCycle",
    json=(str, Field(description=("""
        JSON body to create a test cycle. Example:
        {
          "name": "Test Cycle Name",
          "description": "Test Cycle Description",
          "projectKey": "PROJECT_KEY"
        }
        """
    )))
)

GetTestCycle = create_model(
    "GetTestCycle",
    test_cycle_id_or_key=(str, Field(description="ID or key of the test cycle to retrieve."))
)

UpdateTestCycle = create_model(
    "UpdateTestCycle",
    test_cycle_id_or_key=(str, Field(description="ID or key of the test cycle to update.")),
    json=(str, Field(description=("""
        JSON body to update a test cycle. Example:
        {
          "name": "Updated Test Cycle Name",
          "description": "Updated Test Cycle Description"
        }
        """
    )))
)

GetTestCycleLinks = create_model(
    "GetTestCycleLinks",
    test_cycle_id_or_key=(str, Field(description="ID or key of the test cycle to retrieve links for."))
)

CreateTestCycleIssueLink = create_model(
    "CreateTestCycleIssueLink",
    test_cycle_id_or_key=(str, Field(description="ID or key of the test cycle to link an issue to.")),
    json=(str, Field(description=("""
        JSON body to create an issue link. Example:
        {
          "issueKey": "ISSUE_KEY",
          "description": "Link Description"
        }
        """
    )))
)

CreateTestCycleWebLink = create_model(
    "CreateTestCycleWebLink",
    test_cycle_id_or_key=(str, Field(description="ID or key of the test cycle to link a web link to.")),
    json=(str, Field(description=("""
        JSON body to create a web link. Example:
        {
          "url": "https://example.com",
          "description": "Web Link Description"
        }
        """
    )))
)

ListTestExecutions = create_model(
    "ListTestExecutions",
    project_key=(Optional[str], Field(default=None, description="Project key to filter test executions.")),
    test_cycle=(Optional[str], Field(default=None, description="Test cycle to filter test executions.")),
    test_case=(Optional[str], Field(default=None, description="Test case to filter test executions.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

CreateTestExecution = create_model(
    "CreateTestExecution",
    json=(str, Field(description=("""
        JSON body to create a test execution. Example:
        {
          "testCaseKey": "TEST_CASE_KEY",
          "testCycleKey": "TEST_CYCLE_KEY",
          "status": "PASS"
        }
        """
    )))
)

GetTestExecution = create_model(
    "GetTestExecution",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to retrieve."))
)

UpdateTestExecution = create_model(
    "UpdateTestExecution",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to update.")),
    json=(str, Field(description=("""
        JSON body to update a test execution. Example:
        {
          "status": "FAIL",
          "comment": "Updated comment"
        }
        """
    )))
)

GetTestExecutionTestSteps = create_model(
    "GetTestExecutionTestSteps",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to retrieve test steps for.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

UpdateTestExecutionTestSteps = create_model(
    "UpdateTestExecutionTestSteps",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to update test steps for.")),
    json=(str, Field(description=("""
        "JSON body to update test steps. Example:
        ["
          {"
            "step": "Step 1",
            "status": "PASS"
          }
        ]
        """
    )))
)

SyncTestExecutionScript = create_model(
    "SyncTestExecutionScript",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to sync the script for."))
)

ListTestExecutionLinks = create_model(
    "ListTestExecutionLinks",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to retrieve links for."))
)

CreateTestExecutionIssueLink = create_model(
    "CreateTestExecutionIssueLink",
    test_execution_id_or_key=(str, Field(description="ID or key of the test execution to link an issue to.")),
    json=(str, Field(description=("""
        JSON body to create an issue link. Example:
        {
          "issueKey": "ISSUE_KEY",
          "description": "Link Description"
        }
        """
    )))
)

ListProjects = create_model(
    "ListProjects",
    max_results=(int, Field(default=None, description="Maximum number of results to return.")),
    start_at=(int, Field(default=None, description="Starting index of the results."))
)

GetProject = create_model(
    "GetProject",
    project_id_or_key=(str, Field(description="ID or key of the project to retrieve."))
)

ListFolders = create_model(
    "ListFolders",
    project_key=(Optional[str], Field(default=None, description="Project key to filter folders.")),
    folder_type=(Optional[str], Field(default=None, description="Folder type to filter folders.")),
    max_results=(Optional[int], Field(default=None, description="Maximum number of results to return.")),
    start_at=(Optional[int], Field(default=None, description="Starting index of the results."))
)

CreateFolder = create_model(
    "CreateFolder",
    json=(str, Field(description=("""
        JSON body to create a folder. Example:
        {
          "name": "Folder Name",
          "description": "Folder Description",
          "projectKey": "PROJECT_KEY"
        }
        """
    )))
)

GetFolder = create_model(
    "GetFolder",
    folder_id=(str, Field(description="ID of the folder to retrieve."))
)

DeleteLink = create_model(
    "DeleteLink",
    link_id=(str, Field(description="ID of the link to delete."))
)

GetIssueLinkTestCases = create_model(
    "GetIssueLinkTestCases",
    issue_key=(str, Field(description="Key of the issue to retrieve linked test cases for."))
)

GetIssueLinkTestCycles = create_model(
    "GetIssueLinkTestCycles",
    issue_key=(str, Field(description="Key of the issue to retrieve linked test cycles for."))
)

GetIssueLinkTestPlans = create_model(
    "GetIssueLinkTestPlans",
    issue_key=(str, Field(description="Key of the issue to retrieve linked test plans for."))
)

GetIssueLinkTestExecutions = create_model(
    "GetIssueLinkTestExecutions",
    issue_key=(str, Field(description="Key of the issue to retrieve linked test executions for."))
)

CreateCustomExecutions = create_model(
    "CreateCustomExecutions",
    project_key=(str, Field(description="Project key for the custom executions.")),
    files=(str, Field(description="Path to the file for custom executions.")),
    auto_create_test_cases=(Optional[bool], Field(default=False, description="Whether to auto-create test cases."))
)

CreateCucumberExecutions = create_model(
    "CreateCucumberExecutions",
    project_key=(str, Field(description="Project key for the cucumber executions.")),
    files=(str, Field(description="Path to the file for cucumber executions.")),
    auto_create_test_cases=(Optional[bool], Field(default=False, description="Whether to auto-create test cases."))
)

CreateJUnitExecutions = create_model(
    "CreateJUnitExecutions",
    project_key=(str, Field(description="Project key for the JUnit executions.")),
    files=(str, Field(description="Path to the file for JUnit executions.")),
    auto_create_test_cases=(Optional[bool], Field(default=False, description="Whether to auto-create test cases."))
)

RetrieveBDDTestCases = create_model(
    "RetrieveBDDTestCases",
    project_key=(str, Field(description="Project key to retrieve BDD test cases for."))
)