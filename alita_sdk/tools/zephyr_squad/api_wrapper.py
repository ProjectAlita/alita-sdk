from typing import List, Literal

from pydantic import model_validator, create_model, Field, SecretStr, BaseModel, PrivateAttr

from .zephyr_squad_cloud_client import ZephyrSquadCloud
from ..elitea_base import BaseToolApiWrapper


class ZephyrSquadApiWrapper(BaseToolApiWrapper):
    account_id: str
    access_key: str
    secret_key: SecretStr
    _client: ZephyrSquadCloud = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        account_id = values.get("account_id", None)
        access_key = values.get("access_key", None)
        secret_key = values.get("secret_key", None)
        if not account_id:
            raise ValueError("account_id is required.")
        if not access_key:
            raise ValueError("access_key is required.")
        if not secret_key:
            raise ValueError("secret_key is required.")
        cls._client = ZephyrSquadCloud(
            account_id=account_id,
            access_key=access_key,
            secret_key=secret_key
        )
        return values

    def get_test_step(self, issue_id, step_id, project_id):
        """Retrieve details for a specific test step in a Jira test case."""
        return self._client.get_test_step(issue_id, step_id, project_id)

    def update_test_step(self, issue_id, step_id, project_id, json):
        """Update the content or a specific test step in a Jira test case."""
        return self._client.update_test_step(issue_id, step_id, project_id, json)

    def delete_test_step(self, issue_id, step_id, project_id):
        """Remove a specific test step from a Jira test case."""
        return self._client.delete_test_step(issue_id, step_id, project_id)

    def create_new_test_step(self, issue_id, project_id, json):
        """Add a new test step to a Jira test case."""
        return self._client.create_new_test_step(issue_id, project_id, json)

    def get_all_test_steps(self, issue_id, project_id):
        """List all test steps associated with a Jira test case."""
        return self._client.get_all_test_steps(issue_id, project_id)

    def get_all_test_step_statuses(self):
        """Retrieve all possible statuses for test steps in Jira."""
        return self._client.get_all_test_step_statuses()

    def get_bdd_content(self, issue_id):
        """Retrieve BDD (Gherkin) content of an issue (feature or scenario)."""
        return self._client.get_bdd_content(issue_id)

    def update_bdd_content(self, issue_id, new_content):
        """Replace BDD (Gherkin) content of an issue (feature or scenario)."""
        return self._client.update_bdd_content(issue_id, new_content)

    def delete_bdd_content(self, issue_id):
        """Remove BDD (Gherkin) content of an issue (feature or scenario)."""
        return self._client.delete_bdd_content(issue_id)

    def create_new_cycle(self, json):
        """Creates a Cycle from a JSON representation. If no VersionId is passed in the request, it will be defaulted to an unscheduled version"""
        return self._client.create_new_cycle(json)

    def create_folder(self, json):
        """Creates a Folder from a JSON representation. Folder names within a cycle needs to be unique."""
        return self._client.create_folder(json)

    def add_test_to_cycle(self, cycle_id, json):
        """Adds Tests(s) to a Cycle."""
        return self._client.add_test_to_cycle(cycle_id, json)

    def add_test_to_folder(self, folder_id, json):
        """Adds Tests(s) to a Folder."""
        return self._client.add_test_to_folder(folder_id, json)

    def create_execution(self, json):
        """Creates an execution from a JSON representation."""
        return self._client.create_execution(json)

    def get_execution(self, execution_id, issue_id, project_id):
        """Retrieves Execution and ExecutionStatus by ExecutionId"""
        return self._client.get_execution(execution_id, issue_id, project_id)

    def get_available_tools(self):
        return [
            {
                "name": "get_test_step",
                "description": self.get_test_step.__doc__,
                "args_schema": ProjectIssueStep,
                "ref": self.get_test_step,
            },
            {
                "name": "update_test_step",
                "description": self.update_test_step.__doc__,
                "args_schema": UpdateTestStep,
                "ref": self.update_test_step,
            },
            {
                "name": "delete_test_step",
                "description": self.delete_test_step.__doc__,
                "args_schema": ProjectIssueStep,
                "ref": self.delete_test_step,
            },
            {
                "name": "create_new_test_step",
                "description": self.create_new_test_step.__doc__,
                "args_schema": CreateNewTestStep,
                "ref": self.create_new_test_step,
            },
            {
                "name": "get_all_test_steps",
                "description": self.get_all_test_steps.__doc__,
                "args_schema": ProjectIssue,
                "ref": self.get_all_test_steps,
            },
            {
                "name": "get_all_test_step_statuses",
                "description": self.get_all_test_step_statuses.__doc__,
                "args_schema": create_model("NoInput"),
                "ref": self.get_all_test_step_statuses,
            },
            {
                "name": "get_bdd_content",
                "description": self.get_bdd_content.__doc__,
                "args_schema": Issue,
                "ref": self.get_bdd_content,
            },
            {
                "name": "update_bdd_content",
                "description": self.update_bdd_content.__doc__,
                "args_schema": UpdateBddContent,
                "ref": self.update_bdd_content,
            },
            {
                "name": "delete_bdd_content",
                "description": self.delete_bdd_content.__doc__,
                "args_schema": Issue,
                "ref": self.delete_bdd_content,
            },
            {
                "name": "create_new_cycle",
                "description": self.create_new_cycle.__doc__,
                "args_schema": CycleJson,
                "ref": self.create_new_cycle,
            },
            {
                "name": "create_folder",
                "description": self.create_folder.__doc__,
                "args_schema": FolderJson,
                "ref": self.create_folder,
            },
            {
                "name": "add_test_to_cycle",
                "description": self.add_test_to_cycle.__doc__,
                "args_schema": TestToCycle,
                "ref": self.add_test_to_cycle,
            },
            {
                "name": "add_test_to_folder",
                "description": self.add_test_to_folder.__doc__,
                "args_schema": TestToFolder,
                "ref": self.add_test_to_folder,
            },
            {
                "name": "create_execution",
                "description": self.create_execution.__doc__,
                "args_schema": ExecutionJson,
                "ref": self.create_execution,
            },
            {
                "name": "get_execution",
                "description": self.get_execution.__doc__,
                "args_schema": GetExecution,
                "ref": self.get_execution,
            }
        ]


Issue = create_model(
    "Issue",
    issue_id=(int, Field(description="Jira ticket id of test case."))
)

ProjectIssue = create_model(
    "ProjectIssue",
    project_id=(int, Field(description="Jira project id to which test case belongs.")),
    __base__=Issue
)

ProjectIssueStep = create_model(
    "ProjectIssueStep",
    step_id=(str, Field(description="Test step id to operate.")),
    __base__=ProjectIssue
)

UpdateTestStep = create_model(
    "UpdateTestStep",
    json=(str, Field(description=(
            "JSON body to update a Zephyr test step. Fields:\n"
            "- id (string, required): Unique identifier for the test step. Example: \"0001481146115453-3a0480a3ffffc384-0001\"\n"
            "- step (string, required): Description of the test step. Example: \"Sample Test Step\"\n"
            "- data (string, optional): Test data used in this step. Example: \"Sample Test Data\"\n"
            "- result (string, optional): Expected result after executing the step. Example: \"Expected Test Result\"\n"
            "- customFieldValues (array[object], optional): List of custom field values for the test step. Each object contains:\n"
            "    - customFieldId (string, required): ID of the custom field. Example: \"3ce1c679-7c43-4d37-89f6-757603379e31\"\n"
            "    - value (object, required): Value for the custom field. Example: {\"value\": \"08/21/2018\"}\n"
            "*IMPORTANT*: Use double quotes for all field names and string values."))),
    __base__=ProjectIssueStep
)

CreateNewTestStep = create_model(
    "CreateNewTestStep",
    json=(str, Field(description=(
            "JSON body to create a Zephyr test step. Fields:\n"
            "- step (string, required): Description of the test step. Example: \"Sample Test Step\"\n"
            "- data (string, optional): Test data used in this step. Example: \"Sample Test Data\"\n"
            "- result (string, optional): Expected result after executing the step. Example: \"Expected Test Result\"\n"
            "*IMPORTANT*: Use double quotes for all field names and string values."))),
    __base__=ProjectIssue
)

UpdateBddContent = create_model(
    "UpdateTestStep",
    new_content=(str, Field(description=(
            "String containing a Gherkin scenario or a feature background.\n"
            "New lines must be encoded as \\n or \\r\\n, and other characters that have special meaning in JSON strings must be escaped accordingly"))),
    __base__=Issue
)

CycleJson = create_model(
    "CycleJson",
    json=(str, Field(description=(
            "JSON body to create a Zephyr test cycle. Fields:\n"
            "- name (string, required): Test cycle name. Example: \"Test Cycle\"\n"
            "- build (string, optional): Build name. Example: \"build 1.0\"\n"
            "- environment (string, optional): Environment name. Example: \"Bug Fix\"\n"
            "- description (string, optional): Cycle description. Example: \"This contains the zephyr tests for a version\"\n"
            "- startDate (long, optional): Start date as a Unix timestamp. Example: 1485278607\n"
            "- endDate (long, optional): End date as a Unix timestamp. Example: 1485302400\n"
            "- projectId (integer, required): Project ID. Example: 10100\n"
            "- versionId (integer, required): Version ID. Example: 10000\n"
            "*IMPORTANT*: Use double quotes for all field names and string values.")))
)

FolderJson = create_model(
    "FolderJson",
    json=(str, Field(description=(
            "JSON body to create a Zephyr folder. Fields:\n"
            "- name (string, required): Folder name. Example: \"Folder 01\"\n"
            "- description (string, optional): Folder description. Example: \"Create New Folder\"\n"
            "- cycleId (string, required): Cycle ID. Example: \"0001513838430954-242ac112-0001\"\n"
            "- projectId (integer, required): Project ID. Example: 10100\n"
            "- versionId (integer, required): Version ID. Example: 10000\n"
            "*IMPORTANT*: Use double quotes for all field names and string values.")))
)

ExecutionJson = create_model(
    "ExecutionJson",
    json=(str, Field(description=(
            "JSON body for Zephyr operation. Fields:\n"
            "- status (object, optional): Status object. Example: {\"id\": 1}\n"
            "- id (string, optional): Unique identifier. Example: \"0001456664462103-5aoee13a3fob-0001\"\n"
            "- projectId (integer, required): Project ID. Example: 10000\n"
            "- issueId (integer, required): Issue ID. Example: 10000\n"
            "- cycleId (string, optional): Cycle ID. Example: \"0001456664262308-5a6ee13a3f6b-0001\"\n"
            "- versionId (integer, required): Version ID. Example: -1\n"
            "- assigneeType (string, optional): \"currentUser\" or \"assignee\". Example: \"assignee\"\n"
            "- assignee (string, optional): Assignee name if assigneeType is \"assignee\". Example: \"jiraUserKey\"\n"
            "*IMPORTANT*: Use double quotes for all field names and string values.")))
)

TestToCycle = create_model(
    "TestToCycle",
    step_id=(str, Field(description="Test step id to operate.")),
    json=(str, Field(description=(
            "JSON body for Zephyr operation. Fields:\n"
            "- issues (array[string], required if method=1): List of Jira issue keys. Example: [\"TEST-1\"]\n"
            "- jql (string, required if method=2): JQL query string. Example: \"project = DEMO AND type = Test AND reporter = admin\"\n"
            "- versionId (integer, required): Version ID. Example: -1\n"
            "- projectId (integer, required): Project ID. Example: 10000\n"
            "- fromVersionId (integer, required if method=3): Source Version ID. Example: -1\n"
            "- fromCycleId (string, required if method=3): Source Cycle ID. Example: \"-0001484006184518-242ac112-0001\"\n"
            "- statuses (string, optional, used when method=3): Statuses. Example: \"-1\"\n"
            "- priorities (string, optional, used when method=3): Priorities (comma-separated). Example: \"1,4\"\n"
            "- labels (string, optional, used when method=3): Labels (comma-separated). Example: \"-High,dock\"\n"
            "- method (string, required): Operation method. Example: \"1\"\n"
            "*IMPORTANT*: Use double quotes for all field names and string values.")))
)

TestToFolder = create_model(
    "TestToFolder",
    step_id=(str, Field(description="folderId of Execution.")),
    json=(str, Field(description=(
            "JSON body to update a Zephyr test step. Fields:\n"
            "- issues (array[string], required): List of Jira issue keys. Example: [\"FSC-2\", \"FSC-3\"]\n"
            "- assigneeType (string, required): Type of assignee. Example: \"currentUser\"\n"
            "- method (integer, required): Method identifier. Example: 1\n"
            "- versionId (integer, required): Version ID. Example: 12829\n"
            "- projectId (integer, required): Project ID. Example: 10930\n"
            "- cycleId (string, required): Cycle ID. Example: \"0001513838430954-242ac112-0001\"\n"
            "*IMPORTANT*: Use double quotes for all field names and string values.")))
)

GetExecution = create_model(
    "GetExecution",
    execution_id=(str, Field(description="executionId of Execution.")),
    issue_id=(int, Field(description="issueId of Execution.")),
    project_id=(int, Field(description="projectId of Execution."))
)
