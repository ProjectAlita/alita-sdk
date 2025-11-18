import base64
import json
import logging
import re
from traceback import format_exc
from typing import Any, Optional

import swagger_client
from langchain_core.tools import ToolException
from pydantic import Field, PrivateAttr, model_validator, create_model, SecretStr
from sklearn.feature_extraction.text import strip_tags
from swagger_client import TestCaseApi, SearchApi, PropertyResource, ModuleApi, ProjectApi, FieldApi
from swagger_client.rest import ApiException

from ..elitea_base import BaseToolApiWrapper
from ..utils.content_parser import parse_file_content

QTEST_ID = "QTest Id"

TEST_CASES_IN_JSON_FORMAT = f"""
Provide test case in json format strictly following CRITERIA:

If there is no provided test case, try to extract data to fill json from history, otherwise generate some relevant data.
If generated data was used, put appropriate note to the test case description field.

### CRITERIA
1. The structure should be as in EXAMPLE.
2. Case and spaces for field names should be exactly the same as in NOTES.
3. Extra fields are allowed and will be mapped to project's custom fields if they exist.
4. "{QTEST_ID}" is required to update, change or replace values in test case.
5. Do not provide "Id" and "{QTEST_ID}" to create test case.
6. "Steps" is a list of test step objects with fields "Test Step Number", "Test Step Description", "Test Step Expected Result".
7. For updates, provide ONLY the fields you want to change. Omitted fields will remain unchanged.

### NOTES
Id: Unique identifier (e.g., TC-123). Read-only.
QTest id: Unique identifier (e.g., 4626964). Required for updates.
Name: Brief title of the test case.
Description: Short description of the test purpose.
Type: Type of test (e.g., 'Manual', 'Automation - UTAF').
Status: Current status (e.g., 'New', 'In Progress', 'Completed').
Priority: Priority level (e.g., 'High', 'Medium', 'Low').
Test Type: Category of test (e.g., 'Functional', 'Regression', 'Smoke').
Precondition: Prerequisites for the test, formatted as: <Step1> <Step2> Leave blank if none.
Steps: Array of test steps with Description and Expected Result.

**For Updates**: Include only the fields you want to modify. The system will validate property values against project configuration.

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
    dql=(str, Field(description="Qtest Data Query Language (DQL) query string")),
    extract_images=(Optional[bool], Field(description="Should images be processed by llm", default=False)),
    prompt=(Optional[str], Field(description="Prompt for image processing", default=None))
)

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
    extract_images=(Optional[bool], Field(description="Should images be processed by llm", default=False)),
    prompt=(Optional[str], Field(description="Prompt for image processing", default=None))
)

DeleteTestCase = create_model(
    "DeleteTestCase",
    qtest_id=(int, Field(description="Qtest id e.g. 3253490123")),
)

GetModules = create_model(
    "GetModules",
    parent_id=(Optional[int],
               Field(description="ID of the parent Module. Leave it blank to retrieve Modules under root",
                                    default=None)),
    search=(Optional[str],
               Field(description="The free-text to search for Modules by names. You can utilize this parameter to search for Modules. Leave it blank to retrieve all Modules under root or the parent Module",
                     default=None)),

)

GetAllTestCasesFieldsForProject = create_model(
    "GetAllTestCasesFieldsForProject",
    force_refresh=(Optional[bool],
                   Field(description="Set to true to reload field definitions from API if project configuration has changed (new fields added, dropdown values modified). Default: false (uses cached data).",
                         default=False)),
)

NoInput = create_model(
    "NoInput"
)

class QtestApiWrapper(BaseToolApiWrapper):
    base_url: str
    qtest_project_id: int
    qtest_api_token: SecretStr
    no_of_items_per_page: int = 100
    page: int = 1
    no_of_tests_shown_in_dql_search: int = 10
    _client: Any = PrivateAttr()
    _field_definitions_cache: Optional[dict] = PrivateAttr(default=None)
    llm: Any

    @model_validator(mode='before')
    @classmethod
    def project_id_alias(cls, values):
        if 'project_id' in values:
            values['qtest_project_id'] = values.pop('project_id')
        return values

    @model_validator(mode='after')
    def validate_toolkit(self):
        try:
            import swagger_client  # noqa: F401
        except ImportError:
            raise ImportError(
                "`swagger_client` package not found, please run "
                "`pip install git+https://github.com/Roman-Mitusov/qtest-api.git`"
            )

        if self.qtest_api_token:
            configuration = swagger_client.Configuration()
            configuration.host = self.base_url
            configuration.api_key['Authorization'] = self.qtest_api_token.get_secret_value()
            configuration.api_key_prefix['Authorization'] = 'Bearer'
            self._client = swagger_client.ApiClient(configuration)
        return self

    def __instantiate_test_api_instance(self) -> TestCaseApi:
        # Instantiate the TestCaseApi instance according to the qtest api documentation and swagger client
        return swagger_client.TestCaseApi(self._client)

    def __instantiate_module_api_instance(self) -> ModuleApi:
        return swagger_client.ModuleApi(self._client)

    def __instantiate_fields_api_instance(self) -> FieldApi:
        return swagger_client.FieldApi(self._client)

    def __get_field_definitions_cached(self) -> dict:
        """Get field definitions with session-level caching.
        
        Field definitions are cached for the lifetime of this wrapper instance.
        If project field configuration changes, call refresh_field_definitions_cache()
        to reload the definitions.
        
        Returns:
            dict: Field definitions mapping
        """
        if self._field_definitions_cache is None:
            self._field_definitions_cache = self.__get_project_field_definitions()
        return self._field_definitions_cache

    def refresh_field_definitions_cache(self) -> dict:
        """Manually refresh the field definitions cache.
        
        Call this method if project field configuration has been updated
        (new fields added, dropdown values changed, etc.) and you need to
        reload the definitions within the same agent session.
        
        Returns:
            dict: Freshly loaded field definitions
        """
        self._field_definitions_cache = None
        return self.__get_field_definitions_cached()

    def __map_properties_to_api_format(self, test_case_data: dict, field_definitions: dict,
                                       base_properties: list = None) -> list:
        """
        Convert user-friendly property names/values to QTest API PropertyResource format.
        
        Args:
            test_case_data: Dict with property names as keys (e.g., {"Status": "New", "Priority": "High"})
            field_definitions: Output from __get_project_field_definitions()
            base_properties: Existing properties from a test case (for updates, optional)
            
        Returns:
            list[PropertyResource]: Properties ready for API submission
            
        Raises:
            ValueError: If any field names are unknown or values are invalid (shows ALL errors)
        """
        # Start with base properties or empty dict
        props_dict = {}
        if base_properties:
            for prop in base_properties:
                field_name = prop.get('field_name')
                if field_name:
                    props_dict[field_name] = {
                        'field_id': prop['field_id'],
                        'field_name': field_name,
                        'field_value': prop['field_value'],
                        'field_value_name': prop.get('field_value_name')
                    }
        
        # Collect ALL validation errors before raising
        validation_errors = []
        
        # Map incoming properties from test_case_data
        for field_name, field_value in test_case_data.items():
            # Skip non-property fields (these are handled separately)
            if field_name in ['Name', 'Description', 'Precondition', 'Steps', 'Id', QTEST_ID]:
                continue
            
            # Skip None or empty string values (don't update these fields)
            if field_value is None or field_value == '':
                continue
            
            # Validate field exists in project - STRICT validation
            if field_name not in field_definitions:
                validation_errors.append(
                    f"❌ Unknown field '{field_name}' - not defined in project configuration"
                )
                continue  # Skip to next field, keep collecting errors
            
            field_def = field_definitions[field_name]
            field_id = field_def['field_id']
            
            # Validate value for dropdown fields (only if field has allowed values)
            if field_def['values']:
                # Field has allowed values (dropdown/combobox) - validate strictly
                if field_value not in field_def['values']:
                    available = ", ".join(sorted(field_def['values'].keys()))
                    validation_errors.append(
                        f"❌ Invalid value '{field_value}' for field '{field_name}'. "
                        f"Allowed values: {available}"
                    )
                    continue  # Skip to next field, keep collecting errors
                field_value_id = field_def['values'][field_value]
                field_value_name = field_value
            else:
                # Text field or field without restricted values - use value directly
                # No validation needed - users can write anything (by design)
                field_value_id = field_value
                field_value_name = field_value if isinstance(field_value, str) else None
            
            # Update or add property (only if no errors for this field)
            props_dict[field_name] = {
                'field_id': field_id,
                'field_name': field_name,
                'field_value': field_value_id,
                'field_value_name': field_value_name
            }
        
        # If ANY validation errors found, raise comprehensive error with all issues
        if validation_errors:
            available_fields = ", ".join(sorted(field_definitions.keys()))
            error_msg = (
                f"Found {len(validation_errors)} validation error(s) in test case properties:\n\n" +
                "\n".join(validation_errors) +
                f"\n\n📋 Available fields for this project: {available_fields}\n\n"
                f"💡 Tip: Use 'get_all_test_cases_fields_for_project' tool to see all fields with their allowed values."
            )
            raise ValueError(error_msg)
        
        # Convert to PropertyResource list, filtering out special fields
        result = []
        for field_name, prop_data in props_dict.items():
            if field_name in ['Shared', 'Projects Shared to']:
                continue
            result.append(PropertyResource(
                field_id=prop_data['field_id'],
                field_name=prop_data['field_name'],
                field_value=prop_data['field_value'],
                field_value_name=prop_data.get('field_value_name')
            ))
        
        return result

    def __build_body_for_create_test_case(self, test_cases_data: list[dict],
                                          folder_to_place_test_cases_to: str = '') -> list:
        # Get field definitions for property mapping (cached for session)
        field_definitions = self.__get_field_definitions_cached()
        
        modules = self._parse_modules()
        parent_id = ''.join(str(module['module_id']) for module in modules if
                            folder_to_place_test_cases_to and module['full_module_name'] == folder_to_place_test_cases_to)
        
        bodies = []
        for test_case in test_cases_data:
            # Map properties from user format to API format
            props = self.__map_properties_to_api_format(test_case, field_definitions)
            
            body = swagger_client.TestCaseWithCustomFieldResource(properties=props)
            
            # Only set fields if they are explicitly provided in the input
            # This prevents overwriting existing values with None during partial updates
            if 'Name' in test_case:
                body.name = test_case['Name']
            if 'Precondition' in test_case:
                body.precondition = test_case['Precondition']
            if 'Description' in test_case:
                body.description = test_case['Description']
            
            if parent_id:
                body.parent_id = parent_id
            
            # Only set test_steps if Steps are provided in the input
            # This prevents overwriting existing steps during partial updates
            if 'Steps' in test_case and test_case['Steps'] is not None:
                test_steps_resources = []
                for step in test_case['Steps']:
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

    def __get_project_field_definitions(self) -> dict:
        """
        Get structured field definitions for test cases in the project.
        
        Returns:
            dict: Mapping of field names to their IDs and allowed values.
                  Example: {
                      'Status': {
                          'field_id': 12345,
                          'required': True,
                          'values': {'New': 1, 'In Progress': 2, 'Completed': 3}
                      },
                      'Priority': {
                          'field_id': 12346,
                          'required': False,
                          'values': {'High': 1, 'Medium': 2, 'Low': 3}
                      }
                  }
        """
        fields_api = self.__instantiate_fields_api_instance()
        qtest_object = 'test-cases'
        
        try:
            fields = fields_api.get_fields(self.qtest_project_id, qtest_object)
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when calling FieldAPI->get_fields:\n {stacktrace}")
            raise ValueError(
                f"Unable to get test case fields for project {self.qtest_project_id}. Exception: \n {stacktrace}")
        
        # Build structured mapping
        field_mapping = {}
        for field in fields:
            field_name = field.label
            field_mapping[field_name] = {
                'field_id': field.id,
                'required': getattr(field, 'required', False),
                'values': {}
            }
            
            # Map allowed values if field has them (dropdown/combobox fields)
            if hasattr(field, 'allowed_values') and field.allowed_values:
                for allowed_value in field.allowed_values:
                    # AllowedValueResource has 'label' for the display name and 'value' for the ID
                    # Note: 'value' is the field_value, not 'id'
                    value_label = allowed_value.label
                    value_id = allowed_value.value
                    field_mapping[field_name]['values'][value_label] = value_id
        
        return field_mapping

    def __format_field_info_for_display(self, field_definitions: dict) -> str:
        """
        Format field definitions in human-readable format for LLM.
        
        Args:
            field_definitions: Output from __get_project_field_definitions()
            
        Returns:
            Formatted string with field information
        """
        output = [f"Available Test Case Fields for Project {self.qtest_project_id}:\n"]
        
        for field_name, field_info in sorted(field_definitions.items()):
            required_marker = " (Required)" if field_info.get('required') else ""
            output.append(f"\n{field_name}{required_marker}:")
            
            if field_info.get('values'):
                for value_name, value_id in sorted(field_info['values'].items()):
                    output.append(f"  - {value_name} (id: {value_id})")
            else:
                output.append("  Type: text")
        
        output.append("\n\nUse these exact value names when creating or updating test cases.")
        return ''.join(output)

    def get_all_test_cases_fields_for_project(self, force_refresh: bool = False) -> str:
        """
        Get formatted information about available test case fields and their values.
        This method is exposed as a tool for LLM to query field information.
        
        Args:
            force_refresh: If True, reload field definitions from API instead of using cache.
                          Use this if project configuration has changed (new fields added,
                          dropdown values modified, etc.).
        
        Returns:
            Formatted string with field names and allowed values
        """
        if force_refresh:
            self.refresh_field_definitions_cache()
        field_defs = self.__get_field_definitions_cached()
        return self.__format_field_info_for_display(field_defs)

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

    def __parse_data(self, response_to_parse: dict, parsed_data: list, extract_images: bool=False, prompt: str=None):
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
                    'Test Step Description': self._process_image(step[1]['description'], extract_images, prompt),
                    'Test Step Expected Result':  self._process_image(step[1]['expected'], extract_images, prompt)
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

    def _process_image(self, content: str, extract: bool=False, prompt: str=None):
        #extract image by regex
        img_regex = r'<img\s+src="data:image\/[^;]+;base64,([^"]+)"\s+[^>]*data-filename="([^"]+)"[^>]*>'

        def replace_image(match):
            base64_content = match.group(1)
            file_name = match.group(2)

            file_content = base64.b64decode(base64_content)

            if extract:
                description = f"<img description=\"{parse_file_content(file_content=file_content, file_name=file_name, prompt=prompt, llm=self.llm)}\">"
            else:
                description = ""

            return description
        #replace image tag by description
        content = re.sub(img_regex, replace_image, content)
        return content

    def __perform_search_by_dql(self, dql: str, extract_images:bool=False, prompt: str=None) -> list:
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
            self.__parse_data(api_response, parsed_data, extract_images, prompt)

            if api_response['links']:
                while api_response['links'][0]['rel'] == 'next':
                    next_page = self.page + 1
                    api_response = search_instance.search_artifact(self.qtest_project_id, body,
                                                                   append_test_steps=append_test_steps,
                                                                   include_external_properties=include_external_properties,
                                                                   page_size=self.no_of_items_per_page, page=next_page)
                    self.__parse_data(api_response, parsed_data, extract_images, prompt)
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

    def __is_jira_requirement_present(self, jira_issue_id: str) -> tuple[bool, dict]:
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

    def search_by_dql(self, dql: str, extract_images:bool=False, prompt: str=None):
        """Search for the test cases in qTest using Data Query Language """
        parsed_data = self.__perform_search_by_dql(dql, extract_images, prompt)
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

    def find_test_case_by_id(self, test_id: str, extract_images=False, prompt=None) -> str:
        """ Find the test case by its id. Id should be in format TC-123. """
        dql: str = f"Id = '{test_id}'"
        return f"{self.search_by_dql(dql=dql, extract_images=extract_images, prompt=prompt)}"

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

    def get_modules(self, parent_id: int = None, search: str = None):
        """
        :param int project_id: ID of the project (required)
        :param int parent_id: ID of the parent Module. Leave it blank to retrieve Modules under root
        :param str search: The free-text to search for Modules by names. You can utilize this parameter to search for Modules. Leave it blank to retrieve all Modules under root or the parent Module
        """
        module_api = self.__instantiate_module_api_instance()
        kwargs = {}
        if parent_id:
            kwargs["parent_id"] = parent_id
        if search:
            kwargs["search"] = search
        return module_api.get_sub_modules_of(project_id=self.qtest_project_id, **kwargs)

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
            },
            {
                "name": "get_modules",
                "mode": "get_modules",
                "description": self.get_modules.__doc__,
                "args_schema": GetModules,
                "ref": self.get_modules,
            },
            {
                "name": "get_all_test_cases_fields_for_project",
                "mode": "get_all_test_cases_fields_for_project",
                "description": "Get information about available test case fields and their valid values for the project. Shows which property values are allowed (e.g., Status: 'New', 'In Progress', 'Completed') based on the project configuration. Use force_refresh=true if project configuration has changed.",
                "args_schema": GetAllTestCasesFieldsForProject,
                "ref": self.get_all_test_cases_fields_for_project,
            }
        ]