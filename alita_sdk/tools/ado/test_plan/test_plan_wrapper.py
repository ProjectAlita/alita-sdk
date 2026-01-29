import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Generator, Literal, Optional, List, Dict

from azure.devops.connection import Connection
from azure.devops.v7_0.test_plan.models import TestPlanCreateParams, TestSuiteCreateParams, \
    SuiteTestCaseCreateUpdateParameters
from azure.devops.v7_0.test_plan.test_plan_client import TestPlanClient
from langchain_core.documents import Document
from langchain_core.tools import ToolException
from msrest.authentication import BasicAuthentication
from pydantic import create_model, PrivateAttr, model_validator, SecretStr
from pydantic.fields import FieldInfo as Field

from ..work_item import AzureDevOpsApiWrapper
from ...non_code_indexer_toolkit import NonCodeIndexerToolkit
from ...utils.available_tools_decorator import extend_with_parent_available_tools
from ....runtime.utils.utils import IndexerKeywords

logger = logging.getLogger(__name__)

# Input models for Test Plan operations
TestPlanCreateModel = create_model(
    "TestPlanCreateModel",
    test_plan_create_params=(str, Field(description="JSON of the test plan create parameters"))
)

TestPlanDeleteModel = create_model(
    "TestPlanDeleteModel",
    plan_id=(int, Field(description="ID of the test plan to be deleted"))
)

TestPlanGetModel = create_model(
    "TestPlanGetModel",
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
    plan_id=(int, Field(description="ID of the test plan that contains the suites"))
)

TestSuiteDeleteModel = create_model(
    "TestSuiteDeleteModel",
    plan_id=(int, Field(description="ID of the test plan that contains the suite")),
    suite_id=(int, Field(description="ID of the test suite to delete"))
)

TestSuiteGetModel = create_model(
    "TestSuiteGetModel",
    plan_id=(int, Field(description="ID of the test plan that contains the suites")),
    suite_id=(Optional[int], Field(description="ID of the suite to get", default=None))
)

TestCaseAddModel = create_model(
    "TestCaseAddModel",
    suite_test_case_create_update_parameters=(str, Field(description='JSON array of the suite test case create update parameters. Example: \"[{"work_item":{"id":"23"}}]\"')),
    plan_id=(int, Field(description="ID of the test plan to which test cases are to be added")),
    suite_id=(int, Field(description="ID of the test suite to which test cases are to be added"))
)

test_steps_description = """Json or XML array string with test steps. 
    Json example: [{"stepNumber": 1, "action": "Some action", "expectedResult": "Some expectation"},...]
    XML example: 
    <Steps>
    <Step>
      <StepNumber>1</StepNumber>
      <Action>Some action</Action>
      <ExpectedResult>Some expectation</ExpectedResult>
    </Step>
    ...
    </Steps>
    """

TestCasesCreateModel = create_model(
    "TestCasesCreateModel",
    create_test_cases_parameters=(str, Field(description=f"""Json array where each object is separate test case to be created.
    Input format:
    [
        {'{'}
            plan_id: str
            suite_id: str
            title: str
            description: str
            test_steps: str
            test_steps_format: str
            additional_fields: str (optional)
        {'}'}
        ...
    ]
    Where:
    plan_id - ID of the test plan to which test cases are to be added;
    suite_id - ID of the test suite to which test cases are to be added
    title - Test case title;
    description - Test case description;
    test_steps - {test_steps_description}
    test_steps_format - Format of provided test steps. Possible values: json, xml
    additional_fields - (Optional) JSON string of additional custom fields as key-value pairs. Example: '{{"SDLC": "Development", "Priority": "High"}}'
    """))
)

TestCaseCreateModel = create_model(
    "TestCaseCreateModel",
    plan_id=(int, Field(description="ID of the test plan to which test cases are to be added")),
    suite_id=(int, Field(description="ID of the test suite to which test cases are to be added")),
    title=(str, Field(description="Test case title")),
    description=(str, Field(description="Test case description")),
    test_steps=(str, Field(description=test_steps_description)),
    test_steps_format=(Optional[str], Field(description="Format of provided test steps. Possible values: json, xml", default='json')),
    additional_fields=(Optional[str], Field(description="JSON string of additional custom fields as key-value pairs. Example: '{\"SDLC\": \"Development\", \"Priority\": \"High\"}'. Use get_all_test_case_fields_for_project to discover required fields.", default=None))
)

TestCaseGetModel = create_model(
    "TestCaseGetModel",
    plan_id=(int, Field(description="ID of the test plan for which test cases are requested")),
    suite_id=(int, Field(description="ID of the test suite for which test cases are requested")),
    test_case_id=(str, Field(description="Test Case Id to be fetched")),
    fields=(Optional[List[str]], Field(description="List of specific work item field names to return. If not provided, all fields are returned. Example: ['System.Title', 'System.State', 'Custom.SDLC']", default=None))
)

TestCasesGetModel = create_model(
    "TestCasesGetModel",
    plan_id=(int, Field(description="ID of the test plan for which test cases are requested")),
    suite_id=(int, Field(description="ID of the test suite for which test cases are requested")),
    fields=(Optional[List[str]], Field(description="List of specific work item field names to return. If not provided, all fields are returned. Example: ['System.Title', 'System.State', 'Custom.SDLC']", default=None))
)

GetAllTestCaseFieldsModel = create_model(
    "GetAllTestCaseFieldsModel",
    force_refresh=(Optional[bool], Field(description="If True, reload field definitions from Azure DevOps API. Use this if project configuration has changed.", default=False))
)

class TestPlanApiWrapper(NonCodeIndexerToolkit):
    # TODO use ado_configuration instead of organization_url, project and token
    __test__ = False
    organization_url: str
    project: str
    token: SecretStr
    limit: Optional[int] = 5
    _client: Optional[TestPlanClient] = PrivateAttr()
    _work_item_wrapper: Optional[AzureDevOpsApiWrapper] = PrivateAttr()

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    def validate_toolkit(cls, values):
        try:
            credentials = BasicAuthentication('', values['token'])
            connection = Connection(base_url=values['organization_url'], creds=credentials)
            cls._client = connection.clients.get_test_plan_client()

            # Initialize work item wrapper at class level
            cls._work_item_wrapper = AzureDevOpsApiWrapper(
                organization_url=values['organization_url'],
                token=values['token'],
                project=values['project'],
                llm=values.get('llm', None)
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "expired" in error_msg or "token" in error_msg and ("invalid" in error_msg or "unauthorized" in error_msg):
                raise ValueError(
                    "Azure DevOps connection failed: Your access token has expired or is invalid. "
                    "Please refresh your token in the toolkit configuration."
                )
            elif "401" in error_msg or "unauthorized" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Authentication failed. "
                    "Please check your credentials in the toolkit configuration."
                )
            elif "404" in error_msg or "not found" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Organization or project not found. "
                    "Please verify your organization URL and project name."
                )
            elif "timeout" in error_msg or "timed out" in error_msg:
                raise ValueError(
                    "Azure DevOps connection failed: Connection timed out. "
                    "Please check your network connection and try again."
                )
            else:
                raise ValueError(f"Azure DevOps connection failed: {e}")
        return super().validate_toolkit(values)

    def get_all_test_case_fields_for_project(self, force_refresh: bool = False) -> str:
        """
        Get formatted information about available Test Case fields and their metadata.
        This method helps discover which fields are required for Test Case creation.
        Delegates to the work_item wrapper's get_work_item_type_fields method.

        Args:
            force_refresh: If True, reload field definitions from Azure DevOps instead of using cache.
                          Use this if project configuration has changed (new fields added, etc.).

        Returns:
            Formatted string with field names, types, and requirements
        """
        # Use the class-level work_item wrapper instance
        return self._work_item_wrapper.get_work_item_type_fields(work_item_type="Test Case", force_refresh=force_refresh)

    def create_test_plan(self, test_plan_create_params: str):
        """Create a test plan in Azure DevOps."""
        try:
            params = json.loads(test_plan_create_params)
            test_plan_create_params_obj = TestPlanCreateParams(**params)
            test_plan = self._client.create_test_plan(test_plan_create_params_obj, self.project)
            return f"Test plan {test_plan.id} created successfully."
        except Exception as e:
            logger.error(f"Error creating test plan: {e}")
            return ToolException(f"Error creating test plan: {e}")

    def delete_test_plan(self, plan_id: int):
        """Delete a test plan in Azure DevOps."""
        try:
            self._client.delete_test_plan(self.project, plan_id)
            return f"Test plan {plan_id} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting test plan: {e}")
            return ToolException(f"Error deleting test plan: {e}")

    def get_test_plan(self, plan_id: Optional[int] = None):
        """Get a test plan or list of test plans in Azure DevOps."""
        try:
            if plan_id:
                test_plan = self._client.get_test_plan_by_id(self.project, plan_id)
                return test_plan.as_dict()
            else:
                test_plans = self._client.get_test_plans(self.project)
                return [plan.as_dict() for plan in test_plans]
        except Exception as e:
            logger.error(f"Error getting test plan(s): {e}")
            return ToolException(f"Error getting test plan(s): {e}")

    def create_test_suite(self, test_suite_create_params: str, plan_id: int):
        """Create a test suite in Azure DevOps."""
        try:
            params = json.loads(test_suite_create_params)
            test_suite_create_params_obj = TestSuiteCreateParams(**params)
            test_suite = self._client.create_test_suite(test_suite_create_params_obj, self.project, plan_id)
            return f"Test suite {test_suite.id} created successfully."
        except Exception as e:
            logger.error(f"Error creating test suite: {e}")
            return ToolException(f"Error creating test suite: {e}")

    def delete_test_suite(self, plan_id: int, suite_id: int):
        """Delete a test suite in Azure DevOps."""
        try:
            self._client.delete_test_suite(self.project, plan_id, suite_id)
            return f"Test suite {suite_id} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting test suite: {e}")
            return ToolException(f"Error deleting test suite: {e}")

    def get_test_suite(self, plan_id: int, suite_id: Optional[int] = None):
        """Get a test suite or list of test suites in Azure DevOps."""
        try:
            if suite_id:
                test_suite = self._client.get_test_suite_by_id(self.project, plan_id, suite_id)
                return test_suite.as_dict()
            else:
                test_suites = self._client.get_test_suites_for_plan(self.project, plan_id)
                return [suite.as_dict() for suite in test_suites]
        except Exception as e:
            logger.error(f"Error getting test suite(s): {e}")
            return ToolException(f"Error getting test suite(s): {e}")

    def add_test_case(self, suite_test_case_create_update_parameters, plan_id: int, suite_id: int):
        """Add a test case to a suite in Azure DevOps."""
        try:
            if isinstance(suite_test_case_create_update_parameters, str):
                suite_test_case_create_update_parameters = json.loads(suite_test_case_create_update_parameters)
            suite_test_case_create_update_params_obj = [SuiteTestCaseCreateUpdateParameters(**param) for param in
                                                        suite_test_case_create_update_parameters]
            test_cases = self._client.add_test_cases_to_suite(suite_test_case_create_update_params_obj, self.project,
                                                              plan_id, suite_id)
            return [test_case.as_dict() for test_case in test_cases]
        except Exception as e:
            logger.error(f"Error adding test case: {e}")
            return ToolException(f"Error adding test case: {e}")

    def create_test_cases(self, create_test_cases_parameters):
        """Creates new test cases in specified suite in Azure DevOps."""
        test_cases = json.loads(create_test_cases_parameters)
        return [self.create_test_case(
            plan_id=test_case['plan_id'],
            suite_id=test_case['suite_id'],
            title=test_case['title'],
            description=test_case['description'],
            test_steps=test_case['test_steps'],
            test_steps_format=test_case['test_steps_format'],
            additional_fields=test_case.get('additional_fields', None)) for test_case in test_cases]

    def create_test_case(self, plan_id: int, suite_id: int, title: str, description: str, test_steps: str,
                         test_steps_format: str = 'json', additional_fields: Optional[str] = None):
        """Creates a new test case in specified suite in Azure DevOps."""
        if test_steps_format == 'json':
            steps_xml = self.get_test_steps_xml(json.loads(test_steps))
        elif test_steps_format == 'xml':
            steps_xml = self.convert_steps_tag_to_ado_steps(test_steps)
        else:
            return ToolException("Unknown test steps format: " + test_steps_format)

        # Parse additional fields if provided
        additional_fields_dict = None
        if additional_fields:
            try:
                additional_fields_dict = json.loads(additional_fields) if isinstance(additional_fields, str) else additional_fields
            except json.JSONDecodeError as e:
                return ToolException(f"Invalid JSON format for additional_fields: {e}")

        work_item_json = self.build_ado_test_case(title, description, steps_xml, additional_fields_dict)

        # Use the class-level work_item wrapper instance
        create_work_item_result = \
        self._work_item_wrapper.create_work_item(work_item_json=json.dumps(work_item_json), wi_type="Test Case")
        if isinstance(create_work_item_result, ToolException):
            # issue creating work item, return error with helpful context
            error_msg = str(create_work_item_result)
            if "TF401320" in error_msg or "validation" in error_msg.lower():
                # Add helpful suggestion about field discovery
                enhanced_error = (
                    f"{error_msg}\n\n"
                    "💡 To discover all required fields for Test Case work items in your project:\n"
                    "   • Use the get_all_test_case_fields_for_project() tool\n"
                    "   • Provide missing required fields via the additional_fields parameter\n"
                    "   • Example: additional_fields='{\"Custom.SDLC\": \"Development\"}'"
                )
                return ToolException(enhanced_error)
            return create_work_item_result
        created_work_item_id = create_work_item_result['id']
        return self.add_test_case([{"work_item": {"id": created_work_item_id}}], plan_id, suite_id)

    def build_ado_test_case(self, title, description, steps_xml, additional_fields: Optional[Dict] = None):
        """
        Build Test Case work item JSON with standard and custom fields.

        :param title: test title
        :param description: test description
        :param steps_xml: steps xml
        :param additional_fields: optional dictionary of additional custom fields
        :return: JSON with ADO fields
        """
        # Standard required fields for Test Case
        standard_fields = {
            "System.Title": title,
            "System.Description": description,
            "Microsoft.VSTS.TCM.Steps": steps_xml
        }

        # Merge additional fields if provided
        if additional_fields:
            # Ensure additional fields don't override standard fields
            protected_fields = ["System.Title", "System.Description", "Microsoft.VSTS.TCM.Steps"]
            for field_name, field_value in additional_fields.items():
                if field_name in protected_fields:
                    logger.warning(f"Ignoring attempt to override protected field: {field_name}")
                else:
                    standard_fields[field_name] = field_value

        return {
            "fields": standard_fields
        }

    def get_test_steps_xml(self, steps: dict):
        steps_elem = ET.Element("steps")
        for step in steps:
            step_number = step.get("stepNumber", 1)
            action = step.get("action", "")
            expected_result = step.get("expectedResult", "")
            steps_elem.append(self.build_step_element(step_number, action, expected_result))
        return ET.tostring(steps_elem, encoding="unicode")

    def convert_steps_tag_to_ado_steps(self, input_xml: str) -> str:
        """
        Converts input XML from format:
        <Steps><Step><Action>...</Action><ExpectedResult>...</ExpectedResult></Step></Steps>
        to Azure DevOps test case format:
        <steps><step id="1" type="Action">...</step>...</steps>
        """
        input_root = ET.fromstring(input_xml)
        steps_elem = ET.Element("steps")
        for step_node in input_root.findall("Step"):
            step_number = step_node.findtext("StepNumber", default="1")
            action = step_node.findtext("Action", default="")
            expected_result = step_node.findtext("ExpectedResult", default="")
            steps_elem.append(self.build_step_element(step_number, action, expected_result))
        return ET.tostring(steps_elem, encoding="unicode")

    def build_step_element(self, step_number: str, action: str, expected_result: str) -> ET.Element:
        """
            Creates an individual <step> element for Azure DevOps.
            """
        step_elem = ET.Element("step", id=str(step_number), type="Action")
        action_elem = ET.SubElement(step_elem, "parameterizedString", isformatted="true")
        action_elem.text = action or ""
        expected_elem = ET.SubElement(step_elem, "parameterizedString", isformatted="true")
        expected_elem.text = expected_result or ""
        return step_elem

    def get_test_case(self, plan_id: int, suite_id: int, test_case_id: str, fields: Optional[List[str]] = None):
        """Get a test case from a suite in Azure DevOps with all custom fields."""
        try:
            # Get test case reference from test plan client (basic info only)
            test_cases = self._client.get_test_case(self.project, plan_id, suite_id, test_case_id)
            if not test_cases:
                return f"No test cases found per given criteria: project {self.project}, plan {plan_id}, suite {suite_id}, test case id {test_case_id}"

            test_case = test_cases[0]
            test_case_dict = test_case.as_dict()

            # Extract work item ID from the test case reference
            work_item_id = test_case_dict.get('work_item', {}).get('id')

            if work_item_id:
                # Fetch full work item details (including all custom fields) using work item wrapper
                # Note: Azure DevOps API does not allow using expand with fields parameter
                if fields:
                    # When specific fields requested, cannot use expand
                    full_work_item = self._work_item_wrapper.get_work_item(
                        id=work_item_id,
                        fields=fields
                    )
                else:
                    # When all fields requested, can use expand for relations
                    full_work_item = self._work_item_wrapper.get_work_item(
                        id=work_item_id,
                        expand='Relations'
                    )

                # Add full work item details to the response
                if isinstance(full_work_item, dict):
                    test_case_dict['work_item_full_details'] = full_work_item
                else:
                    logger.warning(f"Failed to fetch full work item details for ID {work_item_id}")

            return test_case_dict
        except Exception as e:
            logger.error(f"Error getting test case: {e}")
            return ToolException(f"Error getting test case: {e}")

    def get_test_cases(self, plan_id: int, suite_id: int, fields: Optional[List[str]] = None):
        """Get test cases from a suite in Azure DevOps with all custom fields."""
        try:
            # Get test case references from test plan client (basic info only)
            test_cases = self._client.get_test_case_list(self.project, plan_id, suite_id)
            result = []

            for test_case in test_cases:
                test_case_dict = test_case.as_dict()

                # Extract work item ID from the test case reference
                work_item_id = test_case_dict.get('work_item', {}).get('id')

                if work_item_id:
                    # Fetch full work item details (including all custom fields) using work item wrapper
                    # Note: Azure DevOps API does not allow using expand with fields parameter
                    if fields:
                        # When specific fields requested, cannot use expand
                        full_work_item = self._work_item_wrapper.get_work_item(
                            id=work_item_id,
                            fields=fields
                        )
                    else:
                        # When all fields requested, can use expand for relations
                        full_work_item = self._work_item_wrapper.get_work_item(
                            id=work_item_id,
                            expand='Relations'
                        )

                    # Add full work item details to the response
                    if isinstance(full_work_item, dict):
                        test_case_dict['work_item_full_details'] = full_work_item
                    else:
                        logger.warning(f"Failed to fetch full work item details for ID {work_item_id}")

                result.append(test_case_dict)

            return result
        except Exception as e:
            self._log_tool_event(f"Error getting test cases: {e}", 'get_test_cases')
            logger.error(f"Error getting test cases: {e}")
            return ToolException(f"Error getting test cases: {e}")

    def get_suites_in_plan(self, plan_id: int) -> List[dict]:
        """Get all test suites in a test plan."""
        try:
            test_suites = self._client.get_test_suites_for_plan(self.project, plan_id)
            return [suite.as_dict() for suite in test_suites]
        except Exception as e:
            logger.error(f"Error getting test suites: {e}")
            return ToolException(f"Error getting test suites: {e}")

    def _base_loader(self, plan_id: int, suite_ids: Optional[List[int]] = [], chunking_tool: str = None, **kwargs) -> Generator[Document, None, None]:
        cases = []
        if not suite_ids:
            suites = self.get_suites_in_plan(plan_id)
            suite_ids = [suite['id'] for suite in suites if 'id' in suite]
        for sid in suite_ids:
            cases.extend(self.get_test_cases(plan_id, sid))
        #
        for case in cases:
            field_dicts = case.get('work_item', {}).get('work_item_fields', [])
            data = {k: v for d in field_dicts for k, v in d.items()}
            if chunking_tool:
                steps = data.get('Microsoft.VSTS.TCM.Steps', '')
                # Remove XML declaration if present (like <?xml version="1.0" encoding="utf-16"?>) to avoid encoding issues
                steps_no_decl = re.sub(r'<\?xml[^>]*\?>', '', steps, count=1).lstrip()

                yield Document(
                    page_content='',
                    metadata={
                        'id': case.get('work_item', {}).get('id', ''),
                        'title': case.get('work_item', {}).get('name', ''),
                        'plan_id': case.get('test_plan', {}).get('id', ''),
                        'suite_id': case.get('test_suite', {}).get('id', ''),
                        'description': data.get('System.Description', ''),
                        'updated_on': data.get('System.Rev', ''),
                        # content is in metadata for chunking tool post-processing
                        IndexerKeywords.CONTENT_IN_BYTES.value: steps_no_decl.encode("utf-8")
                    })
            else:
                yield Document(
                    page_content=data.get('Microsoft.VSTS.TCM.Steps', ''),
                    metadata={
                        'id': case.get('work_item', {}).get('id', ''),
                        'title': case.get('work_item', {}).get('name', ''),
                        'plan_id': case.get('test_plan', {}).get('id', ''),
                        'suite_id': case.get('test_suite', {}).get('id', ''),
                        'description': data.get('System.Description', ''),
                        'updated_on': data.get('System.Rev', ''),
                    })

    def _index_tool_params(self):
        """Return the parameters for indexing data."""
        return {
            'chunking_tool': (Literal['xml', ''], Field(description="Name of chunking tool", default='xml')),
            "plan_id": (int, Field(description="ID of the test plan for which test cases are requested")),
            "suite_ids": (Optional[List[int]], Field(description='List of test suite IDs for which test cases are requested '
                                                                 '(can be empty for all suites indexing from the plan). '
                                                                 'Example: [2, 23]', default=[])),
        }

    @extend_with_parent_available_tools
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
                "name": "create_test_case",
                "description": self.create_test_case.__doc__,
                "args_schema": TestCaseCreateModel,
                "ref": self.create_test_case,
            },
            {
                "name": "create_test_cases",
                "description": self.create_test_cases.__doc__,
                "args_schema": TestCasesCreateModel,
                "ref": self.create_test_cases,
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
            },
            {
                "name": "get_all_test_case_fields_for_project",
                "description": self.get_all_test_case_fields_for_project.__doc__,
                "args_schema": GetAllTestCaseFieldsModel,
                "ref": self.get_all_test_case_fields_for_project,
            }
        ]