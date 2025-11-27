import base64
import json
import logging
import re
from traceback import format_exc
from typing import Any, Optional

import requests
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

**Multi-select fields**: For fields that allow multiple values (e.g., Team, Assigned To etc.), you can provide:
- Single value: "Team": "Epam"
- Multiple values: "Team": ["Epam", "EJ"]

**Clearing/Unsetting fields**: To clear a field value (unassign, set to empty/blank):
- Use `null` in JSON: "Priority": null
- Works for multi-select fields, user assignments, etc. (Note: single-select dropdowns have API limitations)
- Example: {{"QTest Id": "4626964", "Assigned To": null, "Review status": null}}

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
    "Team": ["Epam", "EJ"],
    "Steps": [
        {{ "Test Step Number": 1, "Test Step Description": "Navigate to url", "Test Step Expected Result": "Page content is loaded"}},
        {{ "Test Step Number": 2, "Test Step Description": "Click 'Login'", "Test Step Expected Result": "Form is expanded"}},
    ]
}}

### OUTPUT
Json object
"""

# DQL Syntax Documentation - reusable across all DQL-based search tools
DQL_SYNTAX_DOCS = """
CRITICAL: USE SINGLE QUOTES ONLY - DQL does not support double quotes!
- ✓ CORRECT: Description ~ 'Forgot Password'
- ✗ WRONG: Description ~ "Forgot Password"

LIMITATION - CANNOT SEARCH BY LINKED OBJECTS:
- ✗ Searching by linked requirements, test cases, defects is NOT supported
- Use dedicated find_*_by_*_id tools for relationship queries

SEARCHABLE FIELDS:
- Direct fields: Id, Name, Description, Status, Type, Priority, etc.
- Custom fields: Use exact field name from project configuration
- Date fields: MUST use ISO DateTime format (e.g., '2024-01-01T00:00:00.000Z')

ENTITY-SPECIFIC NOTES:
- test-logs: Only support 'Execution Start Date' and 'Execution End Date' queries
- builds/test-cycles: Also support 'Created Date' and 'Last Modified Date'
- defects: Can use 'Affected Release/Build' and 'Fixed Release/Build'

SYNTAX RULES:
1. ALL string values MUST use single quotes (never double quotes)
2. Field names with spaces MUST be in single quotes: 'Created Date' > '2024-01-01T00:00:00.000Z'
3. Use ~ for 'contains', !~ for 'not contains': Description ~ 'login'
4. Use 'is not empty' for non-empty check: Name is 'not empty'
5. Operators: =, !=, <, >, <=, >=, in, ~, !~

EXAMPLES:
- Id = 'TC-123' or Id = 'RQ-15' or Id = 'DF-100' (depending on entity type)
- Description ~ 'Forgot Password'
- Status = 'New' and Priority = 'High'
- Name ~ 'login'
- 'Created Date' > '2024-01-01T00:00:00.000Z'
- 'Execution Start Date' > '2024-01-01T00:00:00.000Z' (for test-logs)
"""

# Supported object types for DQL search (based on QTest Search API documentation)
# Note: Prefixes are configurable per-project but these are standard defaults
# Modules (MD) are NOT searchable via DQL - use get_modules tool instead
# Test-logs have NO prefix - they are internal records accessed via test runs

# Entity types with ID prefixes (can be looked up by ID like TC-123)
QTEST_OBJECT_TYPES = {
    # Core test management entities
    'test-cases': {'prefix': 'TC', 'name': 'Test Case', 'description': 'Test case definitions with steps'},
    'test-runs': {'prefix': 'TR', 'name': 'Test Run', 'description': 'Execution instances of test cases'},
    'defects': {'prefix': 'DF', 'name': 'Defect', 'description': 'Bugs/issues found during testing'},
    'requirements': {'prefix': 'RQ', 'name': 'Requirement', 'description': 'Requirements to be tested'},
    
    # Test organization entities
    'test-suites': {'prefix': 'TS', 'name': 'Test Suite', 'description': 'Collections of test runs'},
    'test-cycles': {'prefix': 'CL', 'name': 'Test Cycle', 'description': 'Test execution cycles'},
    
    # Release management entities
    'releases': {'prefix': 'RL', 'name': 'Release', 'description': 'Software releases'},
    'builds': {'prefix': 'BL', 'name': 'Build', 'description': 'Builds within releases'},
}

# Entity types searchable via DQL but without ID prefixes
# These can be searched by specific fields only, not by ID
QTEST_SEARCHABLE_ONLY_TYPES = {
    'test-logs': {
        'name': 'Test Log', 
        'description': "Execution logs. Only date queries supported (Execution Start Date, Execution End Date). For specific log details, use test run's 'Latest Test Log' field."
    },
}

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
    requirement_external_id=(str, Field(description="Qtest requirement external id which represent jira issue id linked to Qtest as a requirement e.g. SITEPOD-4038")),
    json_list_of_test_case_ids=(str, Field(description="""List of the test case ids to be linked to particular requirement. 
                                              Create a list of the test case ids in the following format '["TC-123", "TC-234", "TC-456"]' which represents json array as a string.
                                              It should be capable to be extracted directly by python json.loads method."""))
)

QtestLinkTestCaseToQtestRequirement = create_model(
    "QtestLinkTestCaseToQtestRequirement",
    requirement_id=(str, Field(description="QTest internal requirement ID in format RQ-123")),
    json_list_of_test_case_ids=(str, Field(description="""List of the test case ids to be linked to particular requirement. 
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

FindTestCasesByRequirementId = create_model(
    "FindTestCasesByRequirementId",
    requirement_id=(str, Field(description="QTest requirement ID in format RQ-123. This will find all test cases linked to this requirement.")),
    include_details=(Optional[bool], Field(description="If true, returns full test case details. If false (default), returns Id, QTest Id, Name, and Description fields.", default=False)),
)

FindRequirementsByTestCaseId = create_model(
    "FindRequirementsByTestCaseId",
    test_case_id=(str, Field(description="Test case ID in format TC-123. This will find all requirements linked to this test case.")),
)

FindTestRunsByTestCaseId = create_model(
    "FindTestRunsByTestCaseId",
    test_case_id=(str, Field(description="Test case ID in format TC-123. This will find all test runs associated with this test case.")),
)

FindDefectsByTestRunId = create_model(
    "FindDefectsByTestRunId",
    test_run_id=(str, Field(description="Test run ID in format TR-123. This will find all defects associated with this test run.")),
)

# Generic search model for any entity type
GenericDqlSearch = create_model(
    "GenericDqlSearch",
    object_type=(str, Field(description="Entity type to search: 'test-cases', 'test-runs', 'defects', 'requirements', 'test-suites', 'test-cycles', 'test-logs', 'releases', or 'builds'. Note: test-logs only support date queries; modules are NOT searchable - use get_modules tool.")),
    dql=(str, Field(description="QTest Data Query Language (DQL) query string")),
)

# Generic find by ID model - only for entities with ID prefixes (NOT test-logs)
FindEntityById = create_model(
    "FindEntityById",
    entity_id=(str, Field(description="Entity ID with prefix: TC-123 (test case), RQ-15 (requirement), DF-100 (defect), TR-39 (test run), TS-5 (test suite), CL-3 (test cycle), RL-1 (release), or BL-2 (build). Note: test-logs and modules do NOT have ID prefixes.")),
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
    _modules_cache: Optional[list] = PrivateAttr(default=None)
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

            # Skip empty string values (don't update these fields)
            if field_value == '':
                continue

            # Handle None value - this means "clear/unset this field"
            if field_value is None:
                # Validate field exists before attempting to clear
                if field_name not in field_definitions:
                    validation_errors.append(
                        f"❌ Unknown field '{field_name}' - not defined in project configuration"
                    )
                    continue

                field_def = field_definitions[field_name]
                field_id = field_def['field_id']
                is_multiple = field_def.get('multiple', False)
                has_allowed_values = bool(field_def.get('values'))  # True = dropdown, False = text

                if not has_allowed_values:
                    # TEXT FIELD: can clear with empty string
                    props_dict[field_name] = {
                        'field_id': field_id,
                        'field_name': field_name,
                        'field_value': '',
                        'field_value_name': ''
                    }
                elif is_multiple:
                    # MULTI-SELECT: can clear using empty array "[]"
                    props_dict[field_name] = {
                        'field_id': field_id,
                        'field_name': field_name,
                        'field_value': "[]",
                        'field_value_name': None
                    }
                else:
                    # SINGLE-SELECT: QTest API limitation - cannot clear to empty
                    # Note: Users CAN clear these fields from UI, but API doesn't expose this capability
                    validation_errors.append(
                        f"⚠️ Cannot clear single-select field '{field_name}' - this is a QTest API limitation "
                        f"(clearing is possible from UI but not exposed via API). "
                        f"Please select an alternative value instead. "
                        f"Available values: {', '.join(field_def.get('values', {}).keys()) or 'none'}"
                    )
                continue
            
            # Validate field exists in project - STRICT validation
            if field_name not in field_definitions:
                validation_errors.append(
                    f"❌ Unknown field '{field_name}' - not defined in project configuration"
                )
                continue  # Skip to next field, keep collecting errors
            
            field_def = field_definitions[field_name]
            field_id = field_def['field_id']
            data_type = field_def.get('data_type')
            is_multiple = field_def.get('multiple', False)
            
            # Normalize field_value to list for consistent processing
            # Multi-select fields can receive: "value", ["value1", "value2"], or ["value1"]
            # Single-select fields: "value" only
            if is_multiple:
                # Convert to list if not already
                values_to_process = field_value if isinstance(field_value, list) else [field_value]
            else:
                # Single-select: keep as single value
                values_to_process = [field_value]
            
            # Validate value(s) for dropdown fields (only if field has allowed values)
            if field_def['values']:
                # Field has allowed values (dropdown/combobox/user fields) - validate strictly
                value_ids = []
                value_names = []
                
                for single_value in values_to_process:
                    if single_value not in field_def['values']:
                        available = ", ".join(sorted(field_def['values'].keys()))
                        validation_errors.append(
                            f"❌ Invalid value '{single_value}' for field '{field_name}'. "
                            f"Allowed values: {available}"
                        )
                        continue  # Skip this value, but continue validating others
                    
                    # Valid value - add to lists
                    value_ids.append(field_def['values'][single_value])
                    value_names.append(single_value)
                
                # If all values were invalid, skip this field
                if not value_ids:
                    continue
                
                # Format based on field type and value count
                if is_multiple and len(value_ids) == 1:
                    # Single value in multi-select field: bracketed string "[419950]"
                    # This includes single user assignment: "[626983]"
                    field_value_id = f"[{value_ids[0]}]"
                    field_value_name = f"[{value_names[0]}]" if data_type == 5 else value_names[0]
                elif is_multiple:
                    # Multiple values in multi-select: bracketed string with comma-separated IDs
                    ids_str = ",".join(str(vid) for vid in value_ids)
                    field_value_id = f"[{ids_str}]"
                    field_value_name = ", ".join(value_names)
                else:
                    # Regular single-select dropdown: plain ID
                    field_value_id = value_ids[0]
                    field_value_name = value_names[0]
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
            
            # Handle core fields: Name, Description, Precondition
            # These are set if explicitly provided in the input
            # None or empty string means "clear this field" (except Name which is required)
            if 'Name' in test_case:
                # Name is required - use 'Untitled' as fallback if null/empty
                name_value = test_case['Name']
                body.name = name_value if name_value else 'Untitled'
            
            if 'Precondition' in test_case:
                # Allow clearing with None or empty string
                body.precondition = test_case['Precondition'] if test_case['Precondition'] is not None else ''
            
            if 'Description' in test_case:
                # Allow clearing with None or empty string
                body.description = test_case['Description'] if test_case['Description'] is not None else ''
            
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

    def __get_field_definitions_from_properties_api(self) -> dict:
        """
        Fallback method: Get field definitions using /properties and /properties-info APIs.
        
        These APIs don't require Field Management permission and are available to all users.
        Requires 2 API calls + 1 search to get a test case ID.
        
        Returns:
            dict: Same structure as __get_project_field_definitions()
        """
        logger.info(
            "Using properties API fallback (no Field Management permission). "
            "This requires getting a template test case first."
        )
        
        # Step 1: Get any test case ID to query properties
        search_instance = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(
            object_type='test-cases',
            fields=['*'],
            query=''  # Empty query returns all test cases
        )
        
        try:
            # Search for any test case - just need one
            response = search_instance.search_artifact(
                self.qtest_project_id,
                body,
                page_size=1,
                page=1
            )
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Failed to find test case for properties API: {stacktrace}")
            raise ValueError(
                f"Cannot find any test case to query field definitions. "
                f"Please create at least one test case in project {self.qtest_project_id}"
            ) from e
        
        if not response or not response.get('items') or len(response['items']) == 0:
            raise ValueError(
                f"No test cases found in project {self.qtest_project_id}. "
                f"Please create at least one test case to retrieve field definitions."
            )
        
        test_case_id = response['items'][0]['id']
        logger.info(f"Using test case ID {test_case_id} to retrieve field definitions")
        
        # Step 2: Call /properties API
        headers = {
            "Authorization": f"Bearer {self.qtest_api_token.get_secret_value()}"
        }
        
        properties_url = f"{self.base_url}/api/v3/projects/{self.qtest_project_id}/test-cases/{test_case_id}/properties"
        properties_info_url = f"{self.base_url}/api/v3/projects/{self.qtest_project_id}/test-cases/{test_case_id}/properties-info"
        
        try:
            # Get properties with current values and field metadata
            props_response = requests.get(
                properties_url,
                headers=headers,
                params={'calledBy': 'testcase_properties'}
            )
            props_response.raise_for_status()
            properties_data = props_response.json()
            
            # Get properties-info with data types and allowed values
            info_response = requests.get(properties_info_url, headers=headers)
            info_response.raise_for_status()
            info_data = info_response.json()
            
        except requests.exceptions.RequestException as e:
            stacktrace = format_exc()
            logger.error(f"Failed to call properties API: {stacktrace}")
            raise ValueError(
                f"Unable to retrieve field definitions using properties API. "
                f"Error: {stacktrace}"
            ) from e
        
        # Step 3: Build field mapping by merging both responses
        field_mapping = {}
        
        # Create lookup by field ID from properties-info
        metadata_by_id = {item['id']: item for item in info_data['metadata']}
        
        # Data type mapping to determine 'multiple' flag
        MULTI_SELECT_TYPES = {
            'UserListDataType',
            'MultiSelectionDataType',
            'CheckListDataType'
        }
        
        USER_FIELD_TYPES = {'UserListDataType'}
        
        # System fields to exclude (same as in property mapping)
        excluded_fields = {'Shared', 'Projects Shared to'}
        
        for prop in properties_data:
            field_name = prop.get('name')
            field_id = prop.get('id')
            
            if not field_name or field_name in excluded_fields:
                continue
            
            # Get metadata for this field
            metadata = metadata_by_id.get(field_id, {})
            data_type_str = metadata.get('data_type')
            
            # Determine data_type number (5 for user fields, None for others)
            data_type = 5 if data_type_str in USER_FIELD_TYPES else None
            
            # Determine if multi-select
            is_multiple = data_type_str in MULTI_SELECT_TYPES
            
            field_mapping[field_name] = {
                'field_id': field_id,
                'required': prop.get('required', False),
                'data_type': data_type,
                'multiple': is_multiple,
                'values': {}
            }
            
            # Map allowed values from metadata
            allowed_values = metadata.get('allowed_values', [])
            for allowed_val in allowed_values:
                value_text = allowed_val.get('value_text')
                value_id = allowed_val.get('id')
                if value_text and value_id:
                    field_mapping[field_name]['values'][value_text] = value_id
        
        logger.info(
            f"Retrieved {len(field_mapping)} field definitions using properties API. "
            f"This method works for all users without Field Management permission."
        )
        
        return field_mapping

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
            # Check if permission denied (403) - use fallback
            if e.status == 403:
                logger.warning(
                    "get_fields permission denied (Field Management permission required). "
                    "Using properties API fallback..."
                )
                return self.__get_field_definitions_from_properties_api()
            
            # Other API errors
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
                'data_type': getattr(field, 'data_type', None),  # 5 = user field
                'multiple': getattr(field, 'multiple', False),  # True = multi-select, needs array format
                'values': {}
            }
            
            # Map allowed values if field has them (dropdown/combobox/user fields)
            # Only include active values (is_active=True)
            if hasattr(field, 'allowed_values') and field.allowed_values:
                for allowed_value in field.allowed_values:
                    # Skip inactive values (deleted/deprecated options)
                    if hasattr(allowed_value, 'is_active') and not allowed_value.is_active:
                        continue
                    
                    # AllowedValueResource has 'label' for the display name and 'value' for the ID
                    # Note: 'value' is the field_value, not 'id'
                    # For user fields (data_type=5), label is user name and value is user ID
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
            has_values = bool(field_info.get('values'))
            is_multiple = field_info.get('multiple', False)
            
            # Determine field type label
            if not has_values:
                type_label = "Text"
            elif is_multiple:
                type_label = "Multi-select"
            else:
                type_label = "Single-select"
            
            output.append(f"\n{field_name} ({type_label}{required_marker}):")
            
            if has_values:
                for value_name, value_id in sorted(field_info['values'].items()):
                    output.append(f"  - {value_name}")
            else:
                output.append("  Free text input. Set to null to clear.")
        
        output.append("\n\n--- Field Type Guide ---")
        output.append("\nText fields: Use null to clear, provide string value to set.")
        output.append("\nSingle-select: Provide exact value name from the list above. Cannot be cleared via API.")
        output.append("\nMulti-select: Provide value as array [\"val1\", \"val2\"]. Use null to clear.")
        return '\n'.join(output)

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
        """Get parsed modules list with caching for the session."""
        if self._modules_cache is not None:
            return self._modules_cache
        
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

        self._modules_cache = result
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

    def __format_property_value(self, prop: dict) -> Any:
        """Format property value for display, detecting field type from response structure.
        
        Detection rules based on API response patterns:
        - Text field: field_value_name is empty/None
        - Multi-select: field_value_name starts with '[' and ends with ']'
        - Single-select: field_value_name is plain text (no brackets)
        
        Args:
            prop: Property dict from API response with field_value and field_value_name
            
        Returns:
            Formatted value: list for multi-select, string for others
        """
        field_value = prop.get('field_value') or ''
        field_value_name = prop.get('field_value_name')
        
        # Text field: no field_value_name, use field_value directly
        if not field_value_name:
            return field_value
        
        # Multi-select: field_value_name is bracketed like '[value1, value2]'
        if isinstance(field_value_name, str) and field_value_name.startswith('[') and field_value_name.endswith(']'):
            inner = field_value_name[1:-1].strip()  # Remove brackets
            if inner:
                return [v.strip() for v in inner.split(',')]
            return []  # Empty multi-select
        
        # Single-select: plain text value
        return field_value_name

    def __parse_data(self, response_to_parse: dict, parsed_data: list, extract_images: bool=False, prompt: str=None):
        import html
        
        # PERMISSION-FREE: Parse properties directly from API response
        # No get_fields call needed - works for all users
        
        for item in response_to_parse['items']:
            # Start with core fields (always present)
            parsed_data_row = {
                'Id': item['pid'],
                'Name': item['name'],
                'Description': html.unescape(strip_tags(item['description'])),
                'Precondition': html.unescape(strip_tags(item['precondition'])),
                QTEST_ID: item['id'],
                'Steps': list(map(lambda step: {
                    'Test Step Number': step[0] + 1,
                    'Test Step Description': self._process_image(step[1]['description'], extract_images, prompt),
                    'Test Step Expected Result':  self._process_image(step[1]['expected'], extract_images, prompt)
                }, enumerate(item['test_steps']))),
            }
            
            # Add custom fields directly from API response properties
            for prop in item['properties']:
                field_name = prop.get('field_name')
                if not field_name:
                    continue
                
                # Format value based on field type (multi-select as array, etc.)
                parsed_data_row[field_name] = self.__format_property_value(prop)
            
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

    def __find_qtest_internal_id(self, object_type: str, entity_id: str) -> int:
        """Generic search for an entity's internal QTest ID using its external ID (e.g., TR-xxx, DF-xxx, RQ-xxx).
        
        This is the unified method for looking up internal IDs. Use this instead of 
        the entity-specific methods (__find_qtest_requirement_id_by_id, etc.).
        
        Args:
            object_type: QTest object type ('test-runs', 'defects', 'requirements', etc.)
            entity_id: Entity ID in format TR-123, DF-456, etc.
            
        Returns:
            int: Internal QTest ID for the entity
            
        Raises:
            ValueError: If entity is not found
        """
        dql = f"Id = '{entity_id}'"
        search_instance: SearchApi = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(object_type=object_type, fields=['*'], query=dql)
        
        try:
            response = search_instance.search_artifact(self.qtest_project_id, body)
            if response['total'] == 0:
                raise ValueError(
                    f"{object_type.capitalize()} '{entity_id}' not found in project {self.qtest_project_id}. "
                    f"Please verify the {entity_id} ID exists."
                )
            return response['items'][0]['id']
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Exception when searching for '{object_type}': '{entity_id}': \n {stacktrace}")
            raise ToolException(
                f"Unable to search for {object_type} '{entity_id}' in project {self.qtest_project_id}. "
                f"Exception: \n{stacktrace}"
            ) from e

    def __find_qtest_requirement_id_by_id(self, requirement_id: str) -> int:
        """Search for requirement's internal QTest ID using requirement ID (RQ-xxx format).
        
        Args:
            requirement_id: Requirement ID in format RQ-123
            
        Returns:
            int: Internal QTest ID for the requirement
            
        Raises:
            ValueError: If requirement is not found
        """
        return self.__find_qtest_internal_id('requirements', requirement_id)

    def __find_qtest_defect_id_by_id(self, defect_id: str) -> int:
        """Search for defect's internal QTest ID using defect ID (DF-xxx format).
        
        Args:
            defect_id: Defect ID in format DF-123
            
        Returns:
            int: Internal QTest ID for the defect
            
        Raises:
            ValueError: If defect is not found
        """
        return self.__find_qtest_internal_id('defects', defect_id)

    def __search_entity_by_id(self, object_type: str, entity_id: str) -> dict:
        """Generic search for any entity by its ID (RQ-xxx, DF-xxx, etc.).
        
        Uses the unified __parse_entity_item method for consistent parsing.
        
        Args:
            object_type: QTest object type ('requirements', 'defects', etc.)
            entity_id: Entity ID in format prefix-number (RQ-123, DF-456)
            
        Returns:
            dict: Entity data with all parsed fields, or None if not found
        """
        dql = f"Id = '{entity_id}'"
        search_instance: SearchApi = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(object_type=object_type, fields=['*'], query=dql)
        
        try:
            response = search_instance.search_artifact(self.qtest_project_id, body)
            if response['total'] == 0:
                return None  # Not found, but don't raise - caller handles this
            
            # Use the unified parser
            return self.__parse_entity_item(object_type, response['items'][0])
            
        except ApiException as e:
            logger.warning(f"Could not fetch details for {entity_id}: {e}")
            return None

    def __get_entity_pid_by_internal_id(self, object_type: str, internal_id: int) -> str:
        """Reverse lookup: get entity PID (TC-xxx, TR-xxx, etc.) from internal QTest ID.
        
        Args:
            object_type: QTest object type ('test-cases', 'test-runs', 'defects', 'requirements')
            internal_id: Internal QTest ID (numeric)
            
        Returns:
            str: Entity PID in format prefix-number (TC-123, TR-456, etc.) or None if not found
        """
        search_instance = swagger_client.SearchApi(self._client)
        # Note: 'id' needs quotes for DQL when searching by internal ID
        body = swagger_client.ArtifactSearchParams(
            object_type=object_type, 
            fields=['id', 'pid'], 
            query=f"'id' = '{internal_id}'"
        )
        
        try:
            response = search_instance.search_artifact(self.qtest_project_id, body)
            if response['total'] > 0:
                return response['items'][0].get('pid')
            return None
        except ApiException as e:
            logger.warning(f"Could not get PID for {object_type} internal ID {internal_id}: {e}")
            return None

    def __find_qtest_test_run_id_by_id(self, test_run_id: str) -> int:
        """Search for test run's internal QTest ID using test run ID (TR-xxx format).
        
        Args:
            test_run_id: Test run ID in format TR-123
            
        Returns:
            int: Internal QTest ID for the test run
            
        Raises:
            ValueError: If test run is not found
        """
        return self.__find_qtest_internal_id('test-runs', test_run_id)

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

    def _get_jira_requirement_id(self, jira_issue_id: str) -> int:
        """Search for requirement id using the linked jira_issue_id.
        
        Args:
            jira_issue_id: External Jira issue ID (e.g., PLAN-128)
            
        Returns:
            int: Internal QTest ID for the Jira requirement
            
        Raises:
            ValueError: If Jira requirement is not found in QTest
        """
        is_present, response = self.__is_jira_requirement_present(jira_issue_id)
        if not is_present:
            raise ValueError(
                f"Jira requirement '{jira_issue_id}' not found in QTest project {self.qtest_project_id}. "
                f"Please ensure the Jira issue is linked to QTest as a requirement."
            )
        return response['items'][0]['id']


    def link_tests_to_jira_requirement(self, requirement_external_id: str, json_list_of_test_case_ids: str) -> str:
        """Link test cases to external Jira requirement.
        
        Args:
            requirement_external_id: Jira issue ID (e.g., PLAN-128)
            json_list_of_test_case_ids: JSON array string of test case IDs (e.g., '["TC-123", "TC-234"]')
            
        Returns:
            Success message with linked test case IDs
        """
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        source_type = "requirements"
        linked_type = "test-cases"
        test_case_ids = json.loads(json_list_of_test_case_ids)
        qtest_test_case_ids = [self.__find_qtest_id_by_test_id(tc_id) for tc_id in test_case_ids]
        requirement_id = self._get_jira_requirement_id(requirement_external_id)

        try:
            response = link_object_api_instance.link_artifacts(
                self.qtest_project_id, 
                object_id=requirement_id,
                type=linked_type,
                object_type=source_type, 
                body=qtest_test_case_ids
            )
            linked_test_cases = [link.pid for link in response[0].objects]
            return (
                f"Successfully linked {len(linked_test_cases)} test case(s) to Jira requirement '{requirement_external_id}' "
                f"in project {self.qtest_project_id}.\n"
                f"Linked test cases: {', '.join(linked_test_cases)}"
            )
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error linking to Jira requirement: {stacktrace}")
            raise ToolException(
                f"Unable to link test cases to Jira requirement '{requirement_external_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def link_tests_to_qtest_requirement(self, requirement_id: str, json_list_of_test_case_ids: str) -> str:
        """Link test cases to internal QTest requirement.
        
        Args:
            requirement_id: QTest requirement ID in format RQ-123
            json_list_of_test_case_ids: JSON array string of test case IDs (e.g., '["TC-123", "TC-234"]')
            
        Returns:
            Success message with linked test case IDs
            
        Raises:
            ValueError: If requirement or test cases are not found
            ToolException: If linking fails
        """
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        source_type = "requirements"
        linked_type = "test-cases"
        
        # Parse and convert test case IDs
        test_case_ids = json.loads(json_list_of_test_case_ids)
        qtest_test_case_ids = [self.__find_qtest_id_by_test_id(tc_id) for tc_id in test_case_ids]
        
        # Get internal QTest ID for the requirement
        qtest_requirement_id = self.__find_qtest_requirement_id_by_id(requirement_id)

        try:
            response = link_object_api_instance.link_artifacts(
                self.qtest_project_id,
                object_id=qtest_requirement_id,
                type=linked_type,
                object_type=source_type,
                body=qtest_test_case_ids
            )
            linked_test_cases = [link.pid for link in response[0].objects]
            return (
                f"Successfully linked {len(linked_test_cases)} test case(s) to QTest requirement '{requirement_id}' "
                f"in project {self.qtest_project_id}.\n"
                f"Linked test cases: {', '.join(linked_test_cases)}"
            )
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error linking to QTest requirement: {stacktrace}")
            raise ToolException(
                f"Unable to link test cases to QTest requirement '{requirement_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def find_test_cases_by_requirement_id(self, requirement_id: str, include_details: bool = False) -> dict:
        """Find all test cases linked to a QTest requirement.
        
        This method uses the ObjectLinkApi.find() to discover test cases that are 
        linked to a specific requirement. This is the correct way to find linked 
        test cases - DQL queries cannot search test cases by linked requirement.
        
        Args:
            requirement_id: QTest requirement ID in format RQ-123
            include_details: If True, fetches full test case details. If False, returns summary with Id, Name, Description.
            
        Returns:
            dict with requirement_id, total count, and test_cases list
            
        Raises:
            ValueError: If requirement is not found
            ToolException: If API call fails
        """
        # Get internal QTest ID for the requirement
        qtest_requirement_id = self.__find_qtest_requirement_id_by_id(requirement_id)
        
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        
        try:
            # Use ObjectLinkApi.find() to get linked artifacts
            # type='requirements' means we're searching from requirements
            # ids=[qtest_requirement_id] specifies which requirement(s) to check
            response = link_object_api_instance.find(
                self.qtest_project_id,
                type='requirements',
                ids=[qtest_requirement_id]
            )
            
            # Parse the response to extract linked test cases
            # Response structure: [{id: req_internal_id, pid: 'RQ-15', objects: [{id: tc_internal_id, pid: 'TC-123'}, ...]}]
            linked_test_cases = []
            if response and len(response) > 0:
                for container in response:
                    # Convert to dict if it's an object
                    container_data = container.to_dict() if hasattr(container, 'to_dict') else container
                    objects = container_data.get('objects', []) if isinstance(container_data, dict) else []
                    
                    for obj in objects:
                        obj_data = obj.to_dict() if hasattr(obj, 'to_dict') else obj
                        if isinstance(obj_data, dict):
                            pid = obj_data.get('pid', '')
                            internal_id = obj_data.get('id')
                            if pid and pid.startswith('TC-'):
                                linked_test_cases.append({
                                    'Id': pid,
                                    QTEST_ID: internal_id
                                })
            
            if not linked_test_cases:
                return {
                    'requirement_id': requirement_id,
                    'total': 0,
                    'test_cases': [],
                    'message': f"No test cases are linked to requirement '{requirement_id}'"
                }
            
            # Build result based on detail level
            test_cases_result = []
            
            if not include_details:
                # Short view: fetch Name, Description via DQL for each test case
                for tc in linked_test_cases:
                    try:
                        parsed_data = self.__perform_search_by_dql(f"Id = '{tc['Id']}'")
                        if parsed_data:
                            tc_data = parsed_data[0]
                            test_cases_result.append({
                                'Id': tc['Id'],
                                QTEST_ID: tc[QTEST_ID],
                                'Name': tc_data.get('Name'),
                                'Description': tc_data.get('Description', '')
                            })
                    except Exception as e:
                        logger.warning(f"Could not fetch details for {tc['Id']}: {e}")
                        test_cases_result.append({
                            'Id': tc['Id'],
                            QTEST_ID: tc[QTEST_ID],
                            'Name': 'Unable to fetch',
                            'Description': ''
                        })
            else:
                # Full details: fetch complete test case data
                for tc in linked_test_cases:
                    try:
                        parsed_data = self.__perform_search_by_dql(f"Id = '{tc['Id']}'")
                        if parsed_data:
                            test_cases_result.append(parsed_data[0])
                    except Exception as e:
                        logger.warning(f"Could not fetch details for {tc['Id']}: {e}")
                        test_cases_result.append({
                            'Id': tc['Id'],
                            QTEST_ID: tc[QTEST_ID],
                            'error': f'Unable to fetch details: {str(e)}'
                        })
            
            return {
                'requirement_id': requirement_id,
                'total': len(test_cases_result),
                'test_cases': test_cases_result
            }
            
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error finding test cases by requirement: {stacktrace}")
            raise ToolException(
                f"Unable to find test cases linked to requirement '{requirement_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def find_requirements_by_test_case_id(self, test_case_id: str) -> dict:
        """Find all requirements linked to a test case.
        
        This method uses the ObjectLinkApi.find() to discover requirements that are 
        linked to a specific test case (reverse lookup).
        
        Args:
            test_case_id: Test case ID in format TC-123
            
        Returns:
            dict with test_case_id, total count, and requirements list
            
        Raises:
            ValueError: If test case is not found
            ToolException: If API call fails
        """
        # Get internal QTest ID for the test case
        qtest_test_case_id = self.__find_qtest_id_by_test_id(test_case_id)
        
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        
        try:
            # Use ObjectLinkApi.find() to get linked artifacts
            # type='test-cases' means we're searching from test cases
            response = link_object_api_instance.find(
                self.qtest_project_id,
                type='test-cases',
                ids=[qtest_test_case_id]
            )
            
            # Parse the response to extract linked requirement IDs
            linked_requirement_ids = []
            if response and len(response) > 0:
                for container in response:
                    container_data = container.to_dict() if hasattr(container, 'to_dict') else container
                    objects = container_data.get('objects', []) if isinstance(container_data, dict) else []
                    
                    for obj in objects:
                        obj_data = obj.to_dict() if hasattr(obj, 'to_dict') else obj
                        if isinstance(obj_data, dict):
                            pid = obj_data.get('pid', '')
                            # Requirements have RQ- prefix
                            if pid and pid.startswith('RQ-'):
                                linked_requirement_ids.append(pid)
            
            if not linked_requirement_ids:
                return {
                    'test_case_id': test_case_id,
                    'total': 0,
                    'requirements': [],
                    'message': f"No requirements are linked to test case '{test_case_id}'"
                }
            
            # Fetch actual requirement details via DQL search
            requirements_result = []
            for req_id in linked_requirement_ids:
                req_data = self.__search_entity_by_id('requirements', req_id)
                if req_data:
                    requirements_result.append(req_data)
                else:
                    # Fallback if search fails
                    requirements_result.append({
                        'Id': req_id,
                        'QTest Id': None,
                        'Name': 'Unable to fetch',
                        'Description': ''
                    })
            
            return {
                'test_case_id': test_case_id,
                'total': len(requirements_result),
                'requirements': requirements_result
            }
            
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error finding requirements by test case: {stacktrace}")
            raise ToolException(
                f"Unable to find requirements linked to test case '{test_case_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def find_test_runs_by_test_case_id(self, test_case_id: str) -> dict:
        """Find all test runs associated with a test case.
        
        A test run represents an execution instance of a test case. Each test run 
        tracks execution details, status, and any defects found during that run.
        
        IMPORTANT: In QTest's data model, defects are linked to test runs, not directly 
        to test cases. To find defects related to a test case:
        1. Use this tool to find test runs for the test case
        2. Use find_defects_by_test_run_id for each test run to get related defects
        
        Each test run in the result includes 'Test Case Id' showing which test case 
        it executes, and 'Latest Test Log' with execution status and log ID.
        
        Args:
            test_case_id: Test case ID in format TC-123
            
        Returns:
            dict with test_case_id, total count, and test_runs list with full details
            
        Raises:
            ValueError: If test case is not found
            ToolException: If API call fails
        """
        # Get internal QTest ID for the test case
        qtest_test_case_id = self.__find_qtest_id_by_test_id(test_case_id)
        
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        
        try:
            # Use ObjectLinkApi.find() to get linked artifacts
            response = link_object_api_instance.find(
                self.qtest_project_id,
                type='test-cases',
                ids=[qtest_test_case_id]
            )
            
            # Parse the response to extract linked test run IDs
            linked_test_run_ids = []
            if response and len(response) > 0:
                for container in response:
                    container_data = container.to_dict() if hasattr(container, 'to_dict') else container
                    objects = container_data.get('objects', []) if isinstance(container_data, dict) else []
                    
                    for obj in objects:
                        obj_data = obj.to_dict() if hasattr(obj, 'to_dict') else obj
                        if isinstance(obj_data, dict):
                            pid = obj_data.get('pid', '')
                            # Test runs have TR- prefix
                            if pid and pid.startswith('TR-'):
                                linked_test_run_ids.append(pid)
            
            if not linked_test_run_ids:
                return {
                    'test_case_id': test_case_id,
                    'total': 0,
                    'test_runs': [],
                    'message': f"No test runs are associated with test case '{test_case_id}'"
                }
            
            # Fetch actual test run details via DQL search
            test_runs_result = []
            for tr_id in linked_test_run_ids:
                tr_data = self.__search_entity_by_id('test-runs', tr_id)
                if tr_data:
                    test_runs_result.append(tr_data)
                else:
                    # Fallback if search fails
                    test_runs_result.append({
                        'Id': tr_id,
                        'QTest Id': None,
                        'Name': 'Unable to fetch',
                        'Description': ''
                    })
            
            return {
                'test_case_id': test_case_id,
                'total': len(test_runs_result),
                'test_runs': test_runs_result,
                'hint': 'To find defects, use find_defects_by_test_run_id for each test run.'
            }
            
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error finding test runs by test case: {stacktrace}")
            raise ToolException(
                f"Unable to find test runs associated with test case '{test_case_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def find_defects_by_test_run_id(self, test_run_id: str) -> dict:
        """Find all defects associated with a test run.
        
        In QTest, defects are linked to test runs (not directly to test cases).
        A test run executes a specific test case, so defects found here are 
        related to that test case through the test run execution context.
        
        Use this tool after find_test_runs_by_test_case_id to discover defects.
        The result includes source context (test run and test case IDs) for traceability.
        
        Args:
            test_run_id: Test run ID in format TR-123
            
        Returns:
            dict with test_run_id, source_test_case_id, total count, and defects list with full details
            
        Raises:
            ValueError: If test run is not found
            ToolException: If API call fails
        """
        # First, get test run details to get the source test case context
        test_run_data = self.__search_entity_by_id('test-runs', test_run_id)
        source_test_case_id = None
        if test_run_data:
            # testCaseId is the internal ID, we need the PID (TC-xxx format)
            internal_tc_id = test_run_data.get('Test Case Id')
            if internal_tc_id:
                source_test_case_id = self.__get_entity_pid_by_internal_id('test-cases', internal_tc_id)
        else:
            raise ValueError(f"Test run '{test_run_id}' not found")
        
        # Get internal QTest ID for the test run from test_run_data (avoids duplicate API call)
        qtest_test_run_id = test_run_data.get('QTest Id')
        if not qtest_test_run_id:
            raise ValueError(f"QTest Id not found in test run data for '{test_run_id}'")
        
        link_object_api_instance = swagger_client.ObjectLinkApi(self._client)
        
        try:
            # Use ObjectLinkApi.find() to get linked artifacts
            response = link_object_api_instance.find(
                self.qtest_project_id,
                type='test-runs',
                ids=[qtest_test_run_id]
            )
            
            # Parse the response to extract linked defect IDs
            linked_defect_ids = []
            if response and len(response) > 0:
                for container in response:
                    container_data = container.to_dict() if hasattr(container, 'to_dict') else container
                    objects = container_data.get('objects', []) if isinstance(container_data, dict) else []
                    
                    for obj in objects:
                        obj_data = obj.to_dict() if hasattr(obj, 'to_dict') else obj
                        if isinstance(obj_data, dict):
                            pid = obj_data.get('pid', '')
                            # Defects have DF- prefix
                            if pid and pid.startswith('DF-'):
                                linked_defect_ids.append(pid)
            
            if not linked_defect_ids:
                result = {
                    'test_run_id': test_run_id,
                    'total': 0,
                    'defects': [],
                    'message': f"No defects are associated with test run '{test_run_id}'"
                }
                if source_test_case_id:
                    result['source_test_case_id'] = source_test_case_id
                return result
            
            # Fetch actual defect details via DQL search
            defects_result = []
            for defect_id in linked_defect_ids:
                defect_data = self.__search_entity_by_id('defects', defect_id)
                if defect_data:
                    defects_result.append(defect_data)
                else:
                    # Fallback if search fails
                    defects_result.append({
                        'Id': defect_id,
                        'QTest Id': None,
                        'Name': 'Unable to fetch',
                        'Description': ''
                    })
            
            result = {
                'test_run_id': test_run_id,
                'total': len(defects_result),
                'defects': defects_result
            }
            if source_test_case_id:
                result['source_test_case_id'] = source_test_case_id
            return result
            
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error finding defects by test run: {stacktrace}")
            raise ToolException(
                f"Unable to find defects associated with test run '{test_run_id}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def search_by_dql(self, dql: str, extract_images:bool=False, prompt: str=None):
        """Search for the test cases in qTest using Data Query Language """
        parsed_data = self.__perform_search_by_dql(dql, extract_images, prompt)
        return "Found " + str(
            len(parsed_data)) + f" Qtest test cases:\n" + str(parsed_data[:self.no_of_tests_shown_in_dql_search])

    def search_entities_by_dql(self, object_type: str, dql: str) -> dict:
        """Generic DQL search for any entity type (test-cases, requirements, defects, test-runs, etc.).
        
        This is the unified search method that works for all QTest searchable entity types.
        Each entity type has its own properties structure, but this method parses
        them consistently using the generic entity parser.
        
        Args:
            object_type: Entity type to search (see QTEST_OBJECT_TYPES and QTEST_SEARCHABLE_ONLY_TYPES)
            dql: QTest Data Query Language query string
            
        Returns:
            dict with object_type, total count, and items list with full entity details
        """
        # Check if object_type is valid (either has prefix or is searchable-only)
        all_searchable = {**QTEST_OBJECT_TYPES, **QTEST_SEARCHABLE_ONLY_TYPES}
        if object_type not in all_searchable:
            raise ValueError(
                f"Invalid object_type '{object_type}'. "
                f"Must be one of: {', '.join(all_searchable.keys())}"
            )
        
        entity_info = all_searchable[object_type]
        search_instance = swagger_client.SearchApi(self._client)
        body = swagger_client.ArtifactSearchParams(
            object_type=object_type,
            fields=['*'],
            query=dql
        )
        
        try:
            response = search_instance.search_artifact(self.qtest_project_id, body)
            
            # Parse all items using the generic parser
            items = []
            for item in response.get('items', []):
                parsed = self.__parse_entity_item(object_type, item)
                items.append(parsed)
            
            return {
                'object_type': object_type,
                'entity_name': entity_info['name'],
                'total': response.get('total', 0),
                'returned': len(items),
                'items': items[:self.no_of_tests_shown_in_dql_search]
            }
            
        except ApiException as e:
            stacktrace = format_exc()
            logger.error(f"Error searching {object_type} by DQL: {stacktrace}")
            raise ToolException(
                f"Unable to search {entity_info['name']}s with DQL '{dql}' "
                f"in project {self.qtest_project_id}. Exception: \n{stacktrace}"
            ) from e

    def find_entity_by_id(self, entity_id: str) -> dict:
        """Find any QTest entity by its ID (TC-xxx, RQ-xxx, DF-xxx, TR-xxx).
        
        This is a universal lookup tool that works for any entity type.
        The entity type is automatically determined from the ID prefix.
        
        Args:
            entity_id: Entity ID with prefix (TC-123, RQ-15, DF-100, TR-39, etc.)
            
        Returns:
            dict with full entity details including all properties
        """
        # Determine object type from prefix - dynamically built from registry
        prefix = entity_id.split('-')[0].upper() if '-' in entity_id else ''
        
        # Build reverse mapping: prefix -> object_type from QTEST_OBJECT_TYPES
        prefix_to_type = {
            info['prefix']: obj_type 
            for obj_type, info in QTEST_OBJECT_TYPES.items()
        }
        
        if prefix not in prefix_to_type:
            valid_prefixes = ', '.join(sorted(prefix_to_type.keys()))
            raise ValueError(
                f"Invalid entity ID format '{entity_id}'. "
                f"Expected prefix to be one of: {valid_prefixes}"
            )
        
        object_type = prefix_to_type[prefix]
        result = self.__search_entity_by_id(object_type, entity_id)
        
        if result is None:
            entity_name = QTEST_OBJECT_TYPES[object_type]['name']
            raise ValueError(
                f"{entity_name} '{entity_id}' not found in project {self.qtest_project_id}"
            )
        
        return result

    def __parse_entity_item(self, object_type: str, item: dict) -> dict:
        """Generic parser for any entity type from DQL search response.
        
        This parses the raw API response item into a clean dictionary,
        handling the differences between entity types (some have name at top level,
        some have it in properties as Summary, etc.)
        
        Args:
            object_type: QTest object type
            item: Raw item from search response
            
        Returns:
            dict with parsed entity data
        """
        import html
        
        result = {
            'Id': item.get('pid'),
            'QTest Id': item.get('id'),
        }
        
        # Add top-level fields if present
        if item.get('name'):
            result['Name'] = item.get('name')
        if item.get('description'):
            result['Description'] = html.unescape(strip_tags(item.get('description', '') or ''))
        if item.get('web_url'):
            result['Web URL'] = item.get('web_url')
        
        # Test-case specific fields
        if object_type == 'test-cases':
            if item.get('precondition'):
                result['Precondition'] = html.unescape(strip_tags(item.get('precondition', '') or ''))
            if item.get('test_steps'):
                result['Steps'] = [
                    {
                        'Test Step Number': idx + 1,
                        'Test Step Description': html.unescape(strip_tags(step.get('description', '') or '')),
                        'Test Step Expected Result': html.unescape(strip_tags(step.get('expected', '') or ''))
                    }
                    for idx, step in enumerate(item.get('test_steps', []))
                ]
        
        # Test-run specific fields
        if object_type == 'test-runs':
            if item.get('testCaseId'):
                result['Test Case Id'] = item.get('testCaseId')
            if item.get('automation'):
                result['Automation'] = item.get('automation')
            if item.get('latest_test_log'):
                log = item.get('latest_test_log')
                result['Latest Test Log'] = {
                    'Log Id': log.get('id'),
                    'Status': log.get('status'),
                    'Execution Start': log.get('exe_start_date'),
                    'Execution End': log.get('exe_end_date')
                }
            if item.get('test_case_version'):
                result['Test Case Version'] = item.get('test_case_version')
        
        # Parse all properties - works for all entity types
        for prop in item.get('properties', []):
            field_name = prop.get('field_name')
            if not field_name:
                continue
            
            # Format value based on field type (multi-select as array, etc.)
            field_value = self.__format_property_value(prop)
            
            # Strip HTML from text fields (strings only, not arrays)
            if isinstance(field_value, str) and ('<' in field_value or '&' in field_value):
                field_value = html.unescape(strip_tags(field_value))
            
            result[field_name] = field_value
        
        return result

    def create_test_cases(self, test_case_content: str, folder_to_place_test_cases_to: str) -> dict:
        """ Create the test case based on the incoming content. The input should be in json format. """
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
                "description": """Search test cases in qTest using Data Query Language (DQL).

CRITICAL: USE SINGLE QUOTES ONLY - DQL does not support double quotes!
- ✓ CORRECT: Description ~ 'Forgot Password'
- ✗ WRONG: Description ~ "Forgot Password"

LIMITATION - CANNOT SEARCH BY LINKED OBJECTS:
- ✗ 'Requirement Id' = 'RQ-15' will fail - use 'find_test_cases_by_requirement_id' tool instead
- ✗ Linked defects or other relationship queries are not supported

SEARCHABLE FIELDS:
- Direct fields: Id, Name, Description, Status, Type, Priority, Automation, etc.
- Module: Use 'Module in' syntax
- Custom fields: Use exact field name from project configuration
- Date fields: MUST use ISO DateTime format (e.g., '2024-01-01T00:00:00.000Z')

SYNTAX RULES:
1. ALL string values MUST use single quotes (never double quotes)
2. Field names with spaces MUST be in single quotes: 'Created Date' > '2024-01-01T00:00:00.000Z'
3. Use ~ for 'contains', !~ for 'not contains': Description ~ 'login'
4. Use 'is not empty' for non-empty check: Name is 'not empty'
5. Operators: =, !=, <, >, <=, >=, in, ~, !~

EXAMPLES:
- Id = 'TC-123'
- Description ~ 'Forgot Password'
- Status = 'New' and Priority = 'High'
- Module in 'MD-78 Master Test Suite'
- Name ~ 'login'
- 'Created Date' > '2024-01-01T00:00:00.000Z'
""",
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
                "name": "link_tests_to_jira_requirement",
                "mode": "link_tests_to_jira_requirement",
                "description": "Link test cases to external Jira requirement. Provide Jira issue ID (e.g., PLAN-128) and list of test case IDs in format '[\"TC-123\", \"TC-234\"]'",
                "args_schema": QtestLinkTestCaseToJiraRequirement,
                "ref": self.link_tests_to_jira_requirement,
            },
            {
                "name": "link_tests_to_qtest_requirement",
                "mode": "link_tests_to_qtest_requirement",
                "description": "Link test cases to internal QTest requirement. Provide QTest requirement ID (e.g., RQ-15) and list of test case IDs in format '[\"TC-123\", \"TC-234\"]'",
                "args_schema": QtestLinkTestCaseToQtestRequirement,
                "ref": self.link_tests_to_qtest_requirement,
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
            },
            {
                "name": "find_test_cases_by_requirement_id",
                "mode": "find_test_cases_by_requirement_id",
                "description": """Find all test cases linked to a QTest requirement.

Use this tool to find test cases associated with a specific requirement.
DQL search cannot query by linked requirement - use this tool instead.

Parameters:
- requirement_id: QTest requirement ID in format RQ-123
- include_details: If true, returns full test case data. If false (default), returns Id, QTest Id, Name, and Description.

Examples:
- Find test cases for RQ-15: requirement_id='RQ-15'
- Get full details: requirement_id='RQ-15', include_details=true
""",
                "args_schema": FindTestCasesByRequirementId,
                "ref": self.find_test_cases_by_requirement_id,
            },
            {
                "name": "find_requirements_by_test_case_id",
                "mode": "find_requirements_by_test_case_id",
                "description": """Find all requirements linked to a test case (direct link: test-case 'covers' requirements).

Use this tool to discover which requirements a specific test case covers.

Parameters:
- test_case_id: Test case ID in format TC-123

Returns: List of linked requirements with Id, QTest Id, Name, and Description.

Examples:
- Find requirements for TC-123: test_case_id='TC-123'
""",
                "args_schema": FindRequirementsByTestCaseId,
                "ref": self.find_requirements_by_test_case_id,
            },
            {
                "name": "find_test_runs_by_test_case_id",
                "mode": "find_test_runs_by_test_case_id",
                "description": """Find all test runs associated with a test case.

IMPORTANT: In QTest, defects are NOT directly linked to test cases. 
Defects are linked to TEST RUNS. To find defects related to a test case:
1. First use this tool to find test runs for the test case
2. Then use find_defects_by_test_run_id for each test run

Parameters:
- test_case_id: Test case ID in format TC-123

Returns: List of test runs with Id, QTest Id, Name, and Description.
Also includes a hint about finding defects via test runs.

Examples:
- Find test runs for TC-123: test_case_id='TC-123'
""",
                "args_schema": FindTestRunsByTestCaseId,
                "ref": self.find_test_runs_by_test_case_id,
            },
            {
                "name": "find_defects_by_test_run_id",
                "mode": "find_defects_by_test_run_id",
                "description": """Find all defects associated with a test run.

In QTest data model, defects are linked to test runs (not directly to test cases).
A defect found here means it was reported during execution of this specific test run.

To find defects related to a test case:
1. First use find_test_runs_by_test_case_id to get test runs
2. Then use this tool for each test run

Parameters:
- test_run_id: Test run ID in format TR-123

Returns: List of defects with Id, QTest Id, Name, and Description.

Examples:
- Find defects for TR-39: test_run_id='TR-39'
""",
                "args_schema": FindDefectsByTestRunId,
                "ref": self.find_defects_by_test_run_id,
            },
            {
                "name": "search_entities_by_dql",
                "mode": "search_entities_by_dql",
                "description": f"""Search any QTest entity type using Data Query Language (DQL).

This is a unified search tool for all searchable QTest entity types.

SUPPORTED ENTITY TYPES (object_type parameter):
- 'test-cases' (TC-xxx): Test case definitions with steps
- 'test-runs' (TR-xxx): Execution instances of test cases  
- 'defects' (DF-xxx): Bugs/issues found during testing
- 'requirements' (RQ-xxx): Requirements to be tested
- 'test-suites' (TS-xxx): Collections of test runs
- 'test-cycles' (CL-xxx): Test execution cycles
- 'test-logs': Execution logs (date queries ONLY - see notes)
- 'releases' (RL-xxx): Software releases
- 'builds' (BL-xxx): Builds within releases

NOTES: 
- Modules (MD-xxx) are NOT searchable via DQL. Use 'get_modules' tool instead.
- Test-logs: Only date queries work (Execution Start Date, Execution End Date).
  For specific test log details, use find_test_runs_by_test_case_id - 
  the test run includes 'Latest Test Log' with status and execution times.

{DQL_SYNTAX_DOCS}

EXAMPLES BY ENTITY TYPE:
- Test cases: object_type='test-cases', dql="Name ~ 'login'"
- Requirements: object_type='requirements', dql="Status = 'Baselined'"
- Defects: object_type='defects', dql="Priority = 'High'"
- Test runs: object_type='test-runs', dql="Status = 'Failed'"
- Test logs: object_type='test-logs', dql="'Execution Start Date' > '2024-01-01T00:00:00.000Z'" (date queries only)
- Releases: object_type='releases', dql="Name ~ '2024'"
""",
                "args_schema": GenericDqlSearch,
                "ref": self.search_entities_by_dql,
            },
            {
                "name": "find_entity_by_id",
                "mode": "find_entity_by_id",
                "description": """Find any QTest entity by its ID.

This universal lookup tool works for entity types that have ID prefixes. 
The entity type is automatically determined from the ID prefix.

SUPPORTED ID FORMATS:
- TC-123: Test Case
- TR-39: Test Run  
- DF-100: Defect
- RQ-15: Requirement
- TS-5: Test Suite
- CL-3: Test Cycle
- RL-1: Release
- BL-2: Build

NOT SUPPORTED (no ID prefix):
- Test Logs: Get details from test run's 'Latest Test Log' field (contains Log Id, Status, Execution Start/End Date)
- Modules: Use 'get_modules' tool instead

Parameters:
- entity_id: Entity ID with prefix (e.g., TC-123, RQ-15, DF-100, TR-39)

Returns: Full entity details including all properties.

Examples:
- Find test case: entity_id='TC-123'
- Find requirement: entity_id='RQ-15'
- Find defect: entity_id='DF-100'
- Find test run: entity_id='TR-39'
""",
                "args_schema": FindEntityById,
                "ref": self.find_entity_by_id,
            }
        ]