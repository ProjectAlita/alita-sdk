import json
import logging
from typing import Optional

from azure.devops.connection import Connection
from azure.devops.v7_0.test_plan.models import TestPlanCreateParams, TestSuiteCreateParams, \
    SuiteTestCaseCreateUpdateParameters
from azure.devops.v7_0.test_plan.test_plan_client import TestPlanClient
from langchain_core.tools import ToolException
from msrest.authentication import BasicAuthentication
from pydantic import create_model, PrivateAttr, model_validator, SecretStr
from pydantic.fields import FieldInfo as Field

from ...elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

# Input models for Test Plan operations
TestPlanCreateModel = create_model(
    "TestPlanCreateModel",
    test_plan_create_params=(str, Field(description="JSON of the test plan create parameters")),
    project=(str, Field(description="Project ID or project name"))
)

TestPlanDeleteModel = create_model(
    "TestPlanDeleteModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan to be deleted"))
)

TestPlanGetModel = create_model(
    "TestPlanGetModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(Optional[int], Field(description="ID of the test plan to get", default=None))
)

TestSuiteCreateModel = create_model(
    "TestSuiteCreateModel",
    test_suite_create_params=(str, Field(description="""JSON of the test suite create parameters.
    test_suite_create_params model:
    {
        'default_configurations': '[TestConfigurationReference]',
        'default_testers': '[IdentityRef]',
        'inherit_default_configurations': 'bool',
        'name': 'str',
        'parent_suite': '[TestSuiteReference]',
        'query_string':'str',
        'requirement_id':'int',
        'suite_type': 'object'
    }
    default_configurations model:
    {
        'id':'int',
        'name':'str'
    }
    default_testers model:
    {
        '_links':'dict',
        'descriptor':'str',
        'display_name':'str',
        'url':'str',
        'directory_alias':'str',
        'id':'str',
        'image_url':'str',
        'inactive':'bool',
        'is_aad_identity':'bool',
        'is_container':'bool',
        'is_deleted_in_origin':'bool',
        'profile_url':'str',
        'unique_name':'str'
    }
    parent_suite model:
    {
        'id':'int',
        'name':'str'
    }
    """)),
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan that contains the suites"))
)

TestSuiteDeleteModel = create_model(
    "TestSuiteDeleteModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan that contains the suite")),
    suite_id=(int, Field(description="ID of the test suite to delete"))
)

TestSuiteGetModel = create_model(
    "TestSuiteGetModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan that contains the suites")),
    suite_id=(Optional[int], Field(description="ID of the suite to get", default=None))
)

TestCaseAddModel = create_model(
    "TestCaseAddModel",
    suite_test_case_create_update_parameters=(str, Field(description='JSON array of the suite test case create update parameters. Example: \"[{"work_item":{"id":"23"}}]\"')),
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan to which test cases are to be added")),
    suite_id=(int, Field(description="ID of the test suite to which test cases are to be added"))
)

TestCaseGetModel = create_model(
    "TestCaseGetModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan for which test cases are requested")),
    suite_id=(int, Field(description="ID of the test suite for which test cases are requested")),
    test_case_id=(str, Field(description="Test Case Id to be fetched"))
)

TestCasesGetModel = create_model(
    "TestCasesGetModel",
    project=(str, Field(description="Project ID or project name")),
    plan_id=(int, Field(description="ID of the test plan for which test cases are requested")),
    suite_id=(int, Field(description="ID of the test suite for which test cases are requested"))
)

class TestPlanApiWrapper(BaseToolApiWrapper):
    __test__ = False
    organization_url: str
    token: SecretStr
    limit: Optional[int] = 5
    _client: Optional[TestPlanClient] = PrivateAttr()

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    def validate_toolkit(cls, values):
        try:
            credentials = BasicAuthentication('', values['token'])
            connection = Connection(base_url=values['organization_url'], creds=credentials)
            cls._client = connection.clients.get_test_plan_client()
        except Exception as e:
            raise ImportError(f"Failed to connect to Azure DevOps: {e}")
        return values

    def create_test_plan(self, test_plan_create_params: str, project: str):
        """Create a test plan in Azure DevOps."""
        try:
            params = json.loads(test_plan_create_params)
            test_plan_create_params_obj = TestPlanCreateParams(**params)
            test_plan = self._client.create_test_plan(test_plan_create_params_obj, project)
            return f"Test plan {test_plan.id} created successfully."
        except Exception as e:
            logger.error(f"Error creating test plan: {e}")
            return ToolException(f"Error creating test plan: {e}")

    def delete_test_plan(self, project: str, plan_id: int):
        """Delete a test plan in Azure DevOps."""
        try:
            self._client.delete_test_plan(project, plan_id)
            return f"Test plan {plan_id} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting test plan: {e}")
            return ToolException(f"Error deleting test plan: {e}")

    def get_test_plan(self, project: str, plan_id: Optional[int] = None):
        """Get a test plan or list of test plans in Azure DevOps."""
        try:
            if plan_id:
                test_plan = self._client.get_test_plan_by_id(project, plan_id)
                return test_plan.as_dict()
            else:
                test_plans = self._client.get_test_plans(project)
                return [plan.as_dict() for plan in test_plans]
        except Exception as e:
            logger.error(f"Error getting test plan(s): {e}")
            return ToolException(f"Error getting test plan(s): {e}")

    def create_test_suite(self, test_suite_create_params: str, project: str, plan_id: int):
        """Create a test suite in Azure DevOps."""
        try:
            params = json.loads(test_suite_create_params)
            test_suite_create_params_obj = TestSuiteCreateParams(**params)
            test_suite = self._client.create_test_suite(test_suite_create_params_obj, project, plan_id)
            return f"Test suite {test_suite.id} created successfully."
        except Exception as e:
            logger.error(f"Error creating test suite: {e}")
            return ToolException(f"Error creating test suite: {e}")

    def delete_test_suite(self, project: str, plan_id: int, suite_id: int):
        """Delete a test suite in Azure DevOps."""
        try:
            self._client.delete_test_suite(project, plan_id, suite_id)
            return f"Test suite {suite_id} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting test suite: {e}")
            return ToolException(f"Error deleting test suite: {e}")

    def get_test_suite(self, project: str, plan_id: int, suite_id: Optional[int] = None):
        """Get a test suite or list of test suites in Azure DevOps."""
        try:
            if suite_id:
                test_suite = self._client.get_test_suite_by_id(project, plan_id, suite_id)
                return test_suite.as_dict()
            else:
                test_suites = self._client.get_test_suites_for_plan(project, plan_id)
                return [suite.as_dict() for suite in test_suites]
        except Exception as e:
            logger.error(f"Error getting test suite(s): {e}")
            return ToolException(f"Error getting test suite(s): {e}")

    def add_test_case(self, suite_test_case_create_update_parameters: str, project: str, plan_id: int, suite_id: int):
        """Add a test case to a suite in Azure DevOps."""
        try:
            params = json.loads(suite_test_case_create_update_parameters)
            suite_test_case_create_update_params_obj = [SuiteTestCaseCreateUpdateParameters(**param) for param in params]
            test_cases = self._client.add_test_cases_to_suite(suite_test_case_create_update_params_obj, project, plan_id, suite_id)
            return [test_case.as_dict() for test_case in test_cases]
        except Exception as e:
            logger.error(f"Error adding test case: {e}")
            return ToolException(f"Error adding test case: {e}")

    def get_test_case(self, project: str, plan_id: int, suite_id: int, test_case_id: str):
        """Get a test case from a suite in Azure DevOps."""
        try:
            test_cases = self._client.get_test_case(project, plan_id, suite_id, test_case_id)
            if test_cases:  # This checks if the list is not empty
                test_case = test_cases[0]
                return test_case.as_dict()
            else:
                return f"No test cases found per given criteria: project {project}, plan {plan_id}, suite {suite_id}, test case id {test_case_id}"
        except Exception as e:
            logger.error(f"Error getting test case: {e}")
            return ToolException(f"Error getting test case: {e}")

    def get_test_cases(self, project: str, plan_id: int, suite_id: int):
        """Get test cases from a suite in Azure DevOps."""
        try:
            test_cases = self._client.get_test_case_list(project, plan_id, suite_id)
            return [test_case.as_dict() for test_case in test_cases]
        except Exception as e:
            logger.error(f"Error getting test cases: {e}")
            return ToolException(f"Error getting test cases: {e}")

    def get_available_tools(self):
        """Return a list of available tools."""
        return [
            {
                "name": "create_test_plan",
                "description": self.create_test_plan.__doc__,
                "args_schema": TestPlanCreateModel,
                "ref": self.create_test_plan,
            },
            {
                "name": "delete_test_plan",
                "description": self.delete_test_plan.__doc__,
                "args_schema": TestPlanDeleteModel,
                "ref": self.delete_test_plan,
            },
            {
                "name": "get_test_plan",
                "description": self.get_test_plan.__doc__,
                "args_schema": TestPlanGetModel,
                "ref": self.get_test_plan,
            },
            {
                "name": "create_test_suite",
                "description": self.create_test_suite.__doc__,
                "args_schema": TestSuiteCreateModel,
                "ref": self.create_test_suite,
            },
            {
                "name": "delete_test_suite",
                "description": self.delete_test_suite.__doc__,
                "args_schema": TestSuiteDeleteModel,
                "ref": self.delete_test_suite,
            },
            {
                "name": "get_test_suite",
                "description": self.get_test_suite.__doc__,
                "args_schema": TestSuiteGetModel,
                "ref": self.get_test_suite,
            },
            {
                "name": "add_test_case",
                "description": self.add_test_case.__doc__,
                "args_schema": TestCaseAddModel,
                "ref": self.add_test_case,
            },
            {
                "name": "get_test_case",
                "description": self.get_test_case.__doc__,
                "args_schema": TestCaseGetModel,
                "ref": self.get_test_case,
            },
            {
                "name": "get_test_cases",
                "description": self.get_test_cases.__doc__,
                "args_schema": TestCasesGetModel,
                "ref": self.get_test_cases,
            }
        ]