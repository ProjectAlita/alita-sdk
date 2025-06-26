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
            }
        ]


ProjectIssue = create_model(
    "ProjectIssue",
    issue_id=(int, Field(description="Jira ticket id of test case to which the test step belongs.")),
    project_id=(int, Field(description="Jira project id to which test case belongs."))
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
