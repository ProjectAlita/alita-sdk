import json
import logging
from traceback import format_exc
from typing import Any

import swagger_client
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, model_validator, create_model, SecretStr
from sklearn.feature_extraction.text import strip_tags
from swagger_client import TestCaseApi, SearchApi, PropertyResource
from swagger_client.rest import ApiException

from ..elitea_base import BaseToolApiWrapper

QTEST_ID = "QTest Id"

TEST_CASES_IN_JSON_FORMAT = f"""
Provide test case in json format strictly following CRITERIA:

If there is no provided test case, try to extract data to fill json from history, otherwise generate some relevant data.
If generated data was used, put appropriate note to the test case description field.

### CRITERIA
1. The structure should be as in EXAMPLE.
2. Case and spaces for field names should be exactly the same as in NOTES.
3. Extra fields are allowed.
4. "{QTEST_ID}" is required to update, change or replace values in test case.
5. Do not provide "Id" and "{QTEST_ID}" to create test case.
6  "Steps" is a list of test step objects with fields "Test Step Number", "Test Step Description", "Test Step Expected Result".

### NOTES
Id: Unique identifier (e.g., TC-123).
QTest id: Unique identifier (e.g., 4626964).
Name: Brief title.
Description: Short purpose.
Type: 'Manual' or 'Automation - UTAF'. Leave blank if unknown.
Status: Default 'New'.
Priority: Leave blank.
Test Type: Default 'Functional'.
Precondition: List prerequisites in one cell, formatted as: <Step1> <Step2> Leave blank if none..

### EXAMPLE
{{
    "Id": "TC-12780",
    "{QTEST_ID}": "4626964",
    "Name": "Brief title.",
    "Description": "Short purpose.",
    "Type": "Manual",
    "Status": "New",
    "Priority": "",
    "Test Type": "Functional",
    "Precondition": "<ONLY provided by user precondition>",
    "Steps": [
        {{ "Test Step Number": 1, "Test Step Description": "Navigate to url", "Test Step Expected Result": "Page content is loaded"}},
        {{ "Test Step Number": 2, "Test Step Description": "Click 'Login'", "Test Step Expected Result": "Form is expanded"}},
    ]
}}

### OUTPUT
Json object
"""

logger = logging.getLogger(__name__)

QtestDataQuerySearch = create_model(
    "QtestDataQuerySearch",
    dql=(str, Field(description="Qtest Data Query Language (DQL) query string")))

QtestCreateTestCase = create_model(
    "QtestCreateTestCase",
    test_case_content=(str, Field(
        description=TEST_CASES_IN_JSON_FORMAT)),
    folder_to_place_test_cases_to=(
        str, Field(description="Folder to place test cases to. Default is empty value", default="")),
)

QtestLinkTestCaseToJiraRequirement = create_model(
    "QtestLinkTestCaseToJiraRequirement",
    requirement_external_id=(str, Field("Qtest requirement external id which represent jira issue id linked to Qtest as a requirement e.g. SITEPOD-4038")),
    json_list_of_test_case_ids=(str, Field("""List of the test case ids to be linked to particular requirement. 
                                              Create a list of the test case ids in the following format '["TC-123", "TC-234", "TC-456"]' which represents json array as a string.
                                              It should be capable to be extracted directly by python json.loads method."""))
)

UpdateTestCase = create_model(
    "UpdateTestCase",
    test_id=(str, Field(description="Test ID e.g. TC-1234")),
    test_case_content=(str, Field(
        description=TEST_CASES_IN_JSON_FORMAT))
)

FindTestCaseById = create_model(
    "FindTestCaseById",
    test_id=(str, Field(description="Test case ID e.g. TC-1234")),
)

DeleteTestCase = create_model(
    "DeleteTestCase",
    qtest_id=(int, Field(description="Qtest id e.g. 3253490123")),
)

class QtestApiWrapper(BaseToolApiWrapper):
    base_url: str
    qtest_project_id: int
    qtest_api_token: SecretStr
    no_of_items_per_page: int = 100
    page: int = 1
    no_of_tests_shown_in_dql_search: int = 10
    _client: Any = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def project_id_alias(cls, values):
        if 'project_id' in values:
            values['qtest_project_id'] = values.pop('project_id')
        return values

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            import swagger_client  # noqa: F401
        except ImportError:
            raise ImportError(
                "`swagger_client` package not found, please run "
                "`pip install git+https://github.com/Roman-Mitusov/qtest-api.git`"
            )

        url = values['base_url']
        api_token = values.get('qtest_api_token')
        if api_token:
            configuration = swagger_client.Configuration()
            configuration.host = url
            configuration.api_key['Authorization'] = api_token
            configuration.api_key_prefix['Authorization'] = 'Bearer'
            cls._client = swagger_client.ApiClient(configuration)
        return values

    def __instantiate_test_api_instance(self) -> TestCaseApi:
        # Instantiate the TestCaseApi instance according to the qtest api documentation and swagger client
        return swagger_client.TestCaseApi(self._client)

    def __build_body_for_create_test_case(self, test_cases_data: list[dict],
                                          folder_to_place_test_cases_to: str = '') -> list:
        initial_project_properties = self.__get_properties_form_project()
        modules = self._parse_modules()
        parent_id = ''.join(str(module['module_id']) for module in modules if
                            folder_to_place_test_cases_to and module['full_module_name'] == folder_to_place_test_cases_to)
        props = []
        for prop in initial_project_properties:
            if prop.get('field_name', '') == 'Shared' or prop.get('field_name', '') == 'Projects Shared to':
                continue
            props.append(PropertyResource(field_id=prop['field_id'], field_name=prop['field_name'],
                                          field_value_name=prop.get('field_value_name', None),
                                          field_value=prop['field_value']))
        bodies = []
        for test_case in test_cases_data:
            body = swagger_client.TestCaseWithCustomFieldResource(properties=props)
            body.name = test_case.get('Name')
            body.precondition = test_case.get('Precondition')
            body.description = test_case.get('Description')
            if parent_id:
                body.parent_id = parent_id
            test_steps_resources = []
            for step in test_case.get('Steps'):
                test_steps_resources.append(
                    swagger_client.TestStepResource(description=step.get('Test Step Description'),
                                                    expected=step.get('Test Step Expected Result')))
            body.test_steps = test_steps_resources
            bodies.append(body)
        return bodies

    def __get_all_modules_for_project(self):
        module_api = swagger_client.ModuleApi(self._client)
        expand = 'descendants'
        try:
            modules = module_api.get_sub_modules_of(self.qtest_project_id, expand=expand)
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling ModuleApi->get_sub_modules_of:\n {stacktrace}")
            raise ValueError(
                f"""Unable to get all the modules information from following qTest project - {self.qtest_project_id}.
                                Exception: \n {stacktrace}""")
        return modules

    def _parse_modules(self) -> list[dict]:
        modules = self.__get_all_modules_for_project()
        result = []

        def parse_module(mod):
            module_id = mod.id
            full_module_name = f"{mod.pid} {mod.name}"
            result.append({
                'module_id': module_id,
                'module_name': mod.name,
                'full_module_name': full_module_name,
            })

            # Recursively parse children if they exist
            if mod.children:
                for child in mod.children:
                    parse_module(child)

        for module in modules:
            parse_module(module)

        return result

    def __execute_single_create_test_case_request(self, test_case_api_instance: TestCaseApi, body,
                                                  test_case_content: str) -> dict:
        try:
            response = test_case_api_instance.create_test_case(self.qtest_project_id, body)
            test_case_id = response.pid
            url = response.web_url
            test_name = response.name
            return {'test_case_id': test_case_id, 'test_case_name': test_name, 'url': url}
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling TestCaseApi->create_test_case:\n {stacktrace}")
            raise ToolException(
                f"Unable to create test case in project - {self.qtest_project_id} with the following content:\n{test_case_content}.\n\n Stacktrace was {stacktrace}") from e

    def __parse_data(self, response_to_parse: dict, parsed_data: list):
        import html
        for item in response_to_parse['items']:
            parsed_data_row = {
                'Id': item['pid'],
                'Description': html.unescape(strip_tags(item['description'])),
                'Precondition': html.unescape(strip_tags(item['precondition'])),
                'Name': item['name'],
                QTEST_ID: item['id'],
                'Steps': list(map(lambda step: {
                    'Test Step Number': step[0] + 1,
                    'Test Step Description': step[1]['description'],
                    'Test Step Expected Result': step[1]['expected']
                }, enumerate(item['test_steps']))),
                'Status': ''.join([properties['field_value_name'] for properties in item['properties']
                                   if properties['field_name'] == 'Status']),
                'Automation': ''.join([properties['field_value_name'] for properties in item['properties']
                                       if properties['field_name'] == 'Automation']),
                'Type': ''.join([properties['field_value_name'] for properties in item['properties']
                                 if properties['field_name'] == 'Type']),
                'Priority': ''.join([properties['field_value_name'] for properties in item['properties']
                                     if properties['field_name'] == 'Priority']),
            }
            parsed_data.append(parsed_data_row)

    def __perform_search_by_dql(self, dql: str) -> list:
        search_instance: SearchApi = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(object_type='test-cases', fields=['*'],
                                                   query=dql)
        append_test_steps = 'true'
        include_external_properties = 'true'
        parsed_data = []
        try:
            api_response = search_instance.search_artifact(self.qtest_project_id, body, append_test_steps=append_test_steps,
                                                           include_external_properties=include_external_properties,
                                                           page_size=self.no_of_items_per_page, page=self.page)
            self.__parse_data(api_response, parsed_data)

            if api_response['links']:
                while api_response['links'][0]['rel'] == 'next':
                    next_page = self.page + 1
                    api_response = search_instance.search_artifact(self.qtest_project_id, body,
                                                                   append_test_steps=append_test_steps,
                                                                   include_external_properties=include_external_properties,
                                                                   page_size=self.no_of_items_per_page, page=next_page)
                    self.__parse_data(api_response, parsed_data)
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling SearchApi->search_artifact: \n {stacktrace}")
            raise ToolException(
                f"""Unable to get the test cases by dql: {dql} from following qTest project - {self.qtest_project_id}.
                    Exception: \n{stacktrace}""")
        return parsed_data

    def __find_qtest_id_by_test_id(self, test_id: str) -> int:
        """ Search for a qtest id using the test id. Test id should be in format TC-123. """
        dql = f"Id = '{test_id}'"
        parsed_data = self.__perform_search_by_dql(dql)
        return parsed_data[0]['QTest Id']

    def __get_properties_form_project(self) -> list[dict] | None:
        test_api_instance = self.__instantiate_test_api_instance()
        expand_props = 'true'
        try:
            response = test_api_instance.get_test_cases(self.qtest_project_id, 1, 1, expand_props=expand_props)
            return response[0]['properties']
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling TestCaseApi->get_test_cases: \n {stacktrace}")
            raise e

    def __is_jira_requirement_present(self, jira_issue_id: str) -> (bool, dict):
        """ Define if particular Jira requirement is present in qtest or not """
        dql = f"'External Id' = '{jira_issue_id}'"
        search_instance: SearchApi = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(object_type='requirements', fields=['*'],
                                                   query=dql)
        try:
            response = search_instance.search_artifact(self.qtest_project_id, body)
            if response['total'] == 0:
                return False, response
            return True, response
        except Exception as e:
            from traceback import format_exc
            logger.error(f"Error: {format_exc()}")
            raise e

    def _get_jira_requirement_id(self, jira_issue_id: str) -> int | None:
        """ Search for requirement id using the linked jira_issue_id. """
        is_present, response = self.__is_jira_requirement_present(jira_issue_id)
        if not is_present:
            return None
        return response['items'][0]['id']


    def link_tests_to_jira_requirement(self, requirement_external_id: str, json_list_of_test_case_ids: str) -> str:
        """ Link the list of the test cases represented as string like this '["TC-123", "TC-234"]' to the Jira requirement represented as external id e.g. PLAN-128 which is the Jira Issue Id"""
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        source_type = "requirements"
        linked_type = "test-cases"
        list = [self.__find_qtest_id_by_test_id(test_case_id) for test_case_id in json.loads(json_list_of_test_case_ids)]
        requirement_id = self._get_jira_requirement_id(requirement_external_id)

        try:
            response = link_object_api_instance.link_artifacts(self.qtest_project_id, object_id=requirement_id,
                                                               type=linked_type,
                                                               object_type=source_type, body=list)
            return f"The test cases with the following id's - {[link.pid for link in response[0].objects]} have been linked in following project {self.qtest_project_id} under following requirement {requirement_external_id}"
        except Exception as e:
            from traceback import format_exc
            logger.error(f"Error: {format_exc()}")
            raise e

    def search_by_dql(self, dql: str):
        """Search for the test cases in qTest using Data Query Language """
        parsed_data = self.__perform_search_by_dql(dql)
        return "Found " + str(
            len(parsed_data)) + f" Qtest test cases:\n" + str(parsed_data[:self.no_of_tests_shown_in_dql_search])

    def create_test_cases(self, test_case_content: str, folder_to_place_test_cases_to: str) -> dict:
        """ Create the tes case base on the incoming content. The input should be in json format. """
        test_cases_api_instance: TestCaseApi = self.__instantiate_test_api_instance()
        input_obj = json.loads(test_case_content)
        test_cases = input_obj if isinstance(input_obj, list) else [input_obj]
        bodies = self.__build_body_for_create_test_case(test_cases, folder_to_place_test_cases_to)
        result = {'qtest_folder': folder_to_place_test_cases_to, 'test_cases': []}

        if len(bodies) == 1:
            test_result = self.__execute_single_create_test_case_request(test_cases_api_instance, bodies[0],
                                                                         test_case_content)
            result['test_cases'].append(test_result)
            return result
        else:
            for body in bodies:
                test_result = self.__execute_single_create_test_case_request(test_cases_api_instance, body,
                                                                             test_case_content)
                result['test_cases'].append(test_result)
            return result

    def update_test_case(self, test_id: str, test_case_content: str) -> str:
        """ Update the test case base on the incoming content. The input should be in json format. Also test id should be passed in following format TC-786. """
        input_obj = json.loads(test_case_content)
        test_case = input_obj[0] if isinstance(input_obj, list) else input_obj

        qtest_id = test_case.get(QTEST_ID)
        if qtest_id is None or qtest_id == '':
            actual_test_case = self.__perform_search_by_dql(f"Id = '{test_id}'")[0]
            test_case = actual_test_case | test_case
            qtest_id = test_case[QTEST_ID]

        test_cases_api_instance: TestCaseApi = self.__instantiate_test_api_instance()
        bodies = self.__build_body_for_create_test_case([test_case])
        try:
            response = test_cases_api_instance.update_test_case(self.qtest_project_id, qtest_id, bodies[0])
            return f"""Successfully updated test case in project with id - {self.qtest_project_id}.
            Updated test case id - {response.pid}.
            Test id of updated test case - {test_id}.
            Updated with content:\n{test_case}"""
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling TestCaseApi->update_test_case: \n {stacktrace}")
            raise ToolException(
                f"""Unable to update test case in project with id - {self.qtest_project_id} and test id - {test_id}.\n Exception: \n {stacktrace}""") from e

    def find_test_case_by_id(self, test_id: str) -> str:
        """ Find the test case by its id. Id should be in format TC-123. """
        dql: str = f"Id = '{test_id}'"
        return f"{self.search_by_dql(dql=dql)}"

    def delete_test_case(self, qtest_id: int) -> str:
        """ Delete the test case by its id. Id should be in format 3534653120. """
        test_cases_api_instance: TestCaseApi = self.__instantiate_test_api_instance()
        try:
            test_cases_api_instance.delete_test_case(self.qtest_project_id, qtest_id)
            return f"Successfully deleted test case in project with id - {self.qtest_project_id} and qtest id - {qtest_id}."
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling TestCaseApi->delete_test_case: \n {stacktrace}")
            raise ToolException(
                f"""Unable to delete test case in project with id - {self.qtest_project_id} and qtest_id - {qtest_id}. \n Exception: \n {stacktrace}""") from e

    def get_available_tools(self):
        return [
            {
                "name": "search_by_dql",
                "mode": "search_by_dql",
                "description": 'Search the test cases in qTest using Data Query Language. The input of the tool will be in following format - Module in \'MD-78 Master Test Suite\' and Type = \'Automation - UTAF\'. If keyword or value to check against has 2 words in it it should be surrounded with single quotes',
                "args_schema": QtestDataQuerySearch,
                "ref": self.search_by_dql,
            },
            {
                "name": "create_test_cases",
                "mode": "create_test_cases",
                "description": "Create a test case in qTest.",
                "args_schema": QtestCreateTestCase,
                "ref": self.create_test_cases,
            },
            {
                "name": "update_test_case",
                "mode": "update_test_case",
                "description": "Update, change or replace data in the test case.",
                "args_schema": UpdateTestCase,
                "ref": self.update_test_case,
            },
            {
                "name": "find_test_case_by_id",
                "mode": "find_test_case_by_id",
                "description": f"Find the test case and its fields (e.g., '{QTEST_ID}') by test case id. Id should be in format TC-123",
                "args_schema": FindTestCaseById,
                "ref": self.find_test_case_by_id,
            },
            {
                "name": "delete_test_case",
                "mode": "delete_test_case",
                "description": "Delete test case by its qtest id. Id should be in format 3534653120.",
                "args_schema": DeleteTestCase,
                "ref": self.delete_test_case,
            },
            {
                "name": "link_tests_to_requirement",
                "mode": "link_tests_to_requirement",
                "description": """Link tests to Jira requirements. The input is jira issue id and th list of test ids in format '["TC-123", "TC-234", "TC-345"]'""",
                "args_schema": QtestLinkTestCaseToJiraRequirement,
                "ref": self.link_tests_to_jira_requirement,
            }
        ]