import json
import logging
import re
from typing import Any, Optional, List, Dict, Tuple, Union, Generator, Literal

from pydantic import model_validator, BaseModel, SecretStr
from langchain_core.tools import ToolException
from pydantic import create_model, PrivateAttr
from pydantic.fields import Field

from langchain_core.documents import Document

from ..non_code_indexer_toolkit import NonCodeIndexerToolkit
from ..utils.available_tools_decorator import extend_with_parent_available_tools

try:
    from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
except ImportError:
    from alita_sdk.langchain.interfaces.llm_processor import get_embeddings

logger = logging.getLogger(__name__)

_additional_fields_description=("JSON containing additional optional fields such as: "
                     "'objective' (description of the objective), "
                     "'precondition' (any conditions that need to be met), "
                     "'estimatedTime' (estimated duration in milliseconds), "
                     "'componentId' (ID of a component from Jira), "
                     "'priorityName' (the priority name), "
                     "'statusName' (the status name), "
                     "'folderId' (ID of a folder to place the entity within), "
                     "'ownerId' (Atlassian Account ID of the Jira user), "
                     "'labels' (array of labels associated to this entity), "
                     "'customFields' (object containing custom fields such as build number, release date, etc.)."
                     "Dates should be in the format 'yyyy-MM-dd', and multi-line text fields should denote a new line with the <br> syntax.")

_test_steps_description=("JSON representing the list of test steps. Each step should be an object containing either 'inline' or 'testCase'. "
                     "They should only include one of these fields at a time. Example: "
                     "[{'inline': {'description': 'Attempt to login to the application', 'testData': 'Username = SmartBear Password = weLoveAtlassian', "
                     "'expectedResult': 'Login succeeds, web-app redirects to the dashboard view', 'customFields': {'Build Number': 20, "
                     "'Release Date': '2020-01-01', 'Pre-Condition(s)': 'User should have logged in. <br> User should have navigated to the administration panel.', "
                     "'Implemented': false, 'Category': ['Performance', 'Regression'], 'Tester': 'fa2e582e-5e15-521e-92e3-47e6ca2e7256'}, 'reflectRef': 'Not available yet'}, "
                     "'testCase': {'self': 'string', 'testCaseKey': 'PROJ-T123', 'parameters': [{'name': 'username', 'type': 'DEFAULT_VALUE', 'value': 'admin'}]}}]")

ZephyrGetTestCases = create_model(
    "ZephyrGetTestCases",
    project_key=(str, Field(description="Jira project key filter")),
    folder_id=(Optional[str], Field(description="Folder ID filter", default=None)),
    maxResults=(Optional[int], Field(
        description="A hint as to the maximum number of results to return in each call. Must be an integer >= 1.", 
        default=10)),
    startAt=(Optional[int], Field(
        description="Zero-indexed starting position. Should be a multiple of maxResults.",
        default=0))
)

ZephyrGetTestCase = create_model(
    "ZephyrGetTestCase",
    test_case_key=(str, Field(description="Test case key")),
)

ZephyrCreateTestCase = create_model(
    "TestCaseInput",
    project_key=(str, Field(description="Jira project key.")),
    test_case_name=(str, Field(description="Name of the test case.")),
    additional_fields=(str, Field(description=_additional_fields_description, default="{}")),
    steps=(Optional[str], Field(description=_test_steps_description, default=None))
)

ZephyrCreateTestCases = create_model(
    "TestCasesInput",
    create_test_cases_data=(str, Field(description=(
    "Json with list of test cases to create in format: [{project_key: str, test_case_name:str, additional_fields: {obj}, steps:[{obj}, ...] }, ...]"
    "where:"
    "'project_key' (required) - Jira project key."
    "'test_case_name' (required)  - Name of the test case."
    f"'additional_fields' (required)  - {_additional_fields_description}, Could be empty if no additional fields needed: '{{}}'"
    f"'steps' (optional) - {_test_steps_description}"
    ))))

ZephyrTestStepsInputModel = create_model(
    "ZephyrTestStepsInputModel",
    test_case_key=(str, Field(
        description="The key of the test case. Test case keys are of the format [A-Z]+-T[0-9]+")),
    tc_mode=(str, Field(
        description=("Valid values: 'APPEND', 'OVERWRITE'. "
                     "'OVERWRITE' deletes and recreates the test steps and associated custom field values using the provided input. "
                     "Attachments for existing steps are kept, but those for missing steps are deleted permanently. "
                     "'APPEND' only adds extra steps to your test steps."))),
    items=(str, Field(description=_test_steps_description))
)

ZephyrGetFolders = create_model(
    "ZephyrGetFolders",
    maxResults=(Optional[int], Field(
        description=("A hint as to the maximum number of results to return in each call. "
                     "Must be an integer >= 1. Default is 10. Note that the server may impose a lower limit."),
        default=10)),
    startAt=(Optional[int], Field(
        description=("Zero-indexed starting position. Should be a multiple of maxResults. "
                     "Must be an integer >= 0. Default is 0."),
        default=0)),
    projectKey=(Optional[str], Field(
        description="Jira project key filter. Must match the pattern [A-Z][A-Z_0-9]+.",
        default=None)),
    folderType=(Optional[str], Field(
        description=("Folder type filter. Valid values are 'TEST_CASE', 'TEST_PLAN', or 'TEST_CYCLE'."),
        default=None))
)

ZephyrUpdateTestCase = create_model(
    "ZephyrUpdateTestCase",
    test_case_key=(str, Field(description="The key of the test case")),
    test_case_id=(int, Field(description="Integer id of the test")),
    name=(str, Field(description="Test case name")),
    project_id=(int, Field(description="Project id")),
    priority_id=(int, Field(description="Priority id")),
    status_id=(int, Field(description="Status id")),
    additional_fields=(str, Field(
        description="JSON string containing any additional fields that need to be updated",
        default="{}")
    )
)

ZephyrGetLinks = create_model(
    "ZephyrGetLinks",
    test_case_key=(str, Field(description="The key of the test case"))
)

ZephyrCreateIssueLinks = create_model(
    "ZephyrCreateIssueLinks",
    test_case_key=(str, Field(description="The key of the test case")),
    issue_id=(int, Field(description="The ID of the Jira issue to link"))
)

ZephyrCreateWebLinks = create_model(
    "ZephyrCreateWebLinks",
    test_case_key=(str, Field(description="The key of the test case")),
    url=(str, Field(description="The URL to link")),
    additional_fields=(str, Field(
        description="JSON string containing any additional fields for the web link",
        default="{}")
    )
)

ZephyrGetVersions = create_model(
    "ZephyrGetVersions",
    test_case_key=(str, Field(description="The key of the test case")),
    maxResults=(Optional[int], Field(
        description="A hint as to the maximum number of results to return in each call", 
        default=10)),
    startAt=(Optional[int], Field(
        description="Zero-indexed starting position. Should be a multiple of maxResults.",
        default=0))
)

ZephyrGetVersion = create_model(
    "ZephyrGetVersion",
    test_case_key=(str, Field(description="The key of the test case")),
    version=(str, Field(description="The version number"))
)

ZephyrGetTestScript = create_model(
    "ZephyrGetTestScript",
    test_case_key=(str, Field(description="The key of the test case"))
)

ZephyrCreateTestScript = create_model(
    "ZephyrCreateTestScript",
    test_case_key=(str, Field(description="The key of the test case")),
    script_type=(str, Field(description="The type of the script")),
    text=(str, Field(description="The text content of the script"))
)

ZephyrSearchTestCases = create_model(
    "ZephyrSearchTestCases",
    project_key=(str, Field(description="Jira project key filter")),
    search_term=(Optional[str], Field(description="Optional search term to filter test cases", default=None)),
    max_results=(Optional[int], Field(description="Maximum number of results to query from the API", default=1000)),
    start_at=(Optional[int], Field(description="Zero-indexed starting position", default=0)),
    order_by=(Optional[str], Field(description="Field to order results by", default="name")),
    order_direction=(Optional[str], Field(description="Order direction", default="ASC")),
    archived=(Optional[bool], Field(description="Include archived test cases", default=False)),
    fields=(Optional[List[str]], Field(description="Fields to include in the response (default: key, name). Regular fields include key, name, id, labels, folder, etc. Custom fields can be included in the following ways:Individual custom fields via customFields.field_name format, All custom fields via customFields in the fields list", default=["key", "name"])),
    limit_results=(Optional[int], Field(description="Maximum number of filtered results to return", default=10)),
    folder_id=(Optional[str], Field(description="Filter test cases by folder ID", default=None)),
    folder_name=(Optional[str], Field(description="Filter test cases by folder name (full or partial)", default=None)),
    exact_folder_match=(Optional[bool], Field(description="Whether to match the folder name exactly or allow partial matches", default=False)),
    folder_path=(Optional[str], Field(description="Filter test cases by folder path (e.g., 'Root/Parent/Child')", default=None)),
    include_subfolders=(Optional[bool], Field(description="Include test cases from subfolders of matching folders", default=True)),
    labels=(Optional[List[str]], Field(description="Filter test cases by labels", default=None)),
    custom_fields=(Optional[str], Field(
        description="JSON string containing custom field filters (e.g., {\"Country\": \"All\", \"Is Automated\": \"Yes\"}).",
        default=None)),
    steps_search=(Optional[str], Field(
        description="Search term to find in test case steps (description, expected result, or test data)",
        default=None)),
    include_steps=(Optional[bool], Field(
        description="Whether to include test steps in the response",
        default=False))
)

ZephyrGetTestsRecursive = create_model(
    "ZephyrGetTestsRecursive",
    project_key=(Optional[str], Field(description="Jira project key filter", default=None)),
    folder_id=(Optional[str], Field(description="Parent folder ID to start the recursive search from", default=None)),
    maxResults=(Optional[int], Field(
        description="A hint as to the maximum number of results to return in each call. Must be an integer >= 1.", 
        default=100)),
    startAt=(Optional[int], Field(
        description="Zero-indexed starting position. Should be a multiple of maxResults.",
        default=0))
)

ZephyrGetTestsByFolderName = create_model(
    "ZephyrGetTestsByFolderName",
    project_key=(str, Field(description="Jira project key filter")),
    folder_name=(str, Field(description="Full or partial folder name to search for")),
    exact_match=(Optional[bool], Field(
        description="Whether to match the folder name exactly or allow partial matches",
        default=False)),
    include_subfolders=(Optional[bool], Field(
        description="Whether to include test cases from subfolders",
        default=True)),
    maxResults=(Optional[int], Field(
        description="A hint as to the maximum number of results to return in each call. Must be an integer >= 1.",
        default=100)),
    startAt=(Optional[int], Field(
        description="Zero-indexed starting position. Should be a multiple of maxResults.",
        default=0))
)

ZephyrGetTestsByFolderPath = create_model(
    "ZephyrGetTestsByFolderPath",
    project_key=(str, Field(description="Jira project key filter")),
    folder_path=(str, Field(description="Full folder path (e.g., 'Root/Parent/Child')")),
    include_subfolders=(Optional[bool], Field(
        description="Whether to include test cases from subfolders",
        default=True)),
    maxResults=(Optional[int], Field(
        description="A hint as to the maximum number of results to return in each call. Must be an integer >= 1.",
        default=100)),
    startAt=(Optional[int], Field(
        description="Zero-indexed starting position. Should be a multiple of maxResults.",
        default=0))
)


ZephyrUpdateTestSteps = create_model(
    "ZephyrUpdateTestSteps",
    test_case_key=(str, Field(description="The key of the test case")),
    steps_updates=(str, Field(description="JSON string representing the test steps to update. Format: [{\"index\": 0, \"description\": \"Updated step description\", \"testData\": \"Updated test data\", \"expectedResult\": \"Updated expected result\"}]"))
)


class ZephyrScaleApiWrapper(NonCodeIndexerToolkit):
    # url for a Zephyr server
    base_url: Optional[str] = ""
    # auth with Jira token (cloud & server)
    token: Optional[SecretStr] = ""
    # auth with username and password
    username: Optional[str] = ""
    password: Optional[SecretStr] = ""
    # auth with a session cookie dict
    cookies: Optional[str] = ""

    # max results to show
    max_results: Optional[int] = 100

    _is_cloud: bool = False
    _api: Any = PrivateAttr()

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        try:
            from zephyr import ZephyrScale
        except ImportError:
            raise ImportError(
                "`zephyr scale package` package not found, please run "
                "`pip install zephyr-python-api`"
            )

        # Verify authentication
        if not (values.get('token') or (values.get('username') and values.get('password')) or values.get('cookies')):
            raise ToolException(
                f"Define correct authentication flow: 1) token, 2) credential (username + password), 3) cookies")

        # auth = {"token": values['token']}
        # if values['username'] and values['password']:
        #     auth = {"username": values['username'], "password": values['password']}
        # elif 'cookies' in values and values['cookies']:
        #     auth = {"cookies": values['cookies']}
        #
        # if 'base_url' in values and values['base_url']:
        #     cls._api = ZephyrScale.server_api(base_url=values['base_url'], **auth).api
        # else:
        # Cloud version is enabled for now
        cls._api = ZephyrScale(token=values['token']).api
        return super().validate_toolkit(values)

    def get_tests(self, project_key: str = None, folder_id: str = None, maxResults: Optional[int] = 10, startAt: Optional[int] = 0):
        """Retrieves all test cases. Query parameters can be used to filter the results.
        
        Args:
            project_key: Jira project key filter
            folder_id: Folder ID filter
            custom_fields: JSON string containing custom field filters (e.g., {"Country": "All", "Is Automated": "Yes"})
            maxResults: A hint as to the maximum number of results to return in each call
            startAt: Zero-indexed starting position. Should be a multiple of maxResults
        """

        kwargs = {}
        if project_key:
            kwargs["projectKey"] = project_key
        if folder_id:
            kwargs["folderId"] = folder_id
        if maxResults:
            kwargs["maxResults"] = maxResults
        if startAt:
            kwargs["startAt"] = startAt
            
        test_cases = self._api.test_cases.get_test_cases(**kwargs)
        # Convert each test case to a string and join them with new line
        test_cases_str = str(self._parse_tests(test_cases))
        return f"Extracted tests: {test_cases_str}"

    def get_test(self, test_case_key: str):
        """Returns a test case for the given key
        
        Args:
            test_case_key: The key of the test case
        """

        try:
            test_case = self._api.test_cases.get_test_case(test_case_key)
        except Exception as e:
            return ToolException(f"Unable to extract test case with key: {test_case_key}:\n{str(e)}")
        return f"Extracted tests: {str(test_case)}"

    def get_test_steps(self, test_case_key: str, **kwargs):
        """Returns the test steps for the given test case. Provides a paged response.
        
        Args:
            test_case_key: The key of the test case
            **kwargs: Additional parameters like maxResults and startAt
        """

        try:
            test_case_steps = self._api.test_cases.get_test_steps(test_case_key, **kwargs)
            steps_list = [str(step) for step in test_case_steps]
            if kwargs['return_list']:
                return steps_list
            all_steps_concatenated = '\n'.join(steps_list)
        except Exception as e:
            return ToolException(f"Unable to extract test case steps from test case with key: {test_case_key}:\n{str(e)}")
        return f"Extracted test steps: {all_steps_concatenated}"

    def create_test_case(self, project_key: str, test_case_name: str, additional_fields: Union[str, dict], steps: Union[str, list] = None) -> str | ToolException:
        """Creates a test case. Fields priorityName and statusName will be set to default values if not informed.
        Args:
            project_key: Jira project key
            test_case_name: Test case name
            additional_fields: JSON string containing additional optional fields
            steps: JSON string representing the list of test steps
        
        NOTE: Please note that if the user specifies a folder name, it is necessary to execute the get_folders() function first to find the correct mapping
        """
        if isinstance(additional_fields, str):
            additional_fields = json.loads(additional_fields) if additional_fields else {}
        try:
            create_test_case_response = self._api.test_cases.create_test_case(
                project_key=project_key,
                name=test_case_name,
                **additional_fields
            )
            result = f"Test case with name `{test_case_name}` was created: {str(create_test_case_response)}"
            if steps:
                add_steps_response = self.add_test_steps(create_test_case_response['test_case_key'], 'APPEND', steps)
                result += f"\n{str(add_steps_response)}"
            return result
        except Exception as e:
            return ToolException(f"Unable to create test case with name: {test_case_name}:\n{str(e)}")

    def create_test_cases(self, create_test_cases_data: str) -> list[str | ToolException]:
        """Creates a bunch of test cases"""
        test_cases = json.loads(create_test_cases_data)
        return [self.create_test_case(test_case['project_key'], test_case['test_case_name'], test_case['additional_fields'], test_case['steps']) for test_case in test_cases]

    def add_test_steps(self, test_case_key: str, tc_mode: str, items: Union[str, list]) -> str | ToolException:
        """Assigns a series of test steps to a test case.
        
        Args:
            test_case_key: The key of the test case
            tc_mode: Valid values: 'APPEND', 'OVERWRITE'
            items: JSON string representing the list of test steps
        """

        try:
            if isinstance(items, str):
                items = json.loads(items)
            add_steps_response = self._api.test_cases.post_test_steps(
                test_case_key,
                tc_mode,
                items
            )
            return f"Steps for test case `{test_case_key}` were added/updated: {str(add_steps_response)}"
        except Exception as e:
            return ToolException(f"Unable to add/update steps for test case with key: {test_case_key}:\n{str(e)}")

    def get_folders(self,
            maxResults: Optional[int] = 10,
            startAt: Optional[int] = 0,
            projectKey: Optional[str] = None,
            folderType: Optional[str] = None,
            return_as_list: bool = False
    ):
        """Retrieves all folders. Query parameters can be used to filter the results: maxResults, startAt, projectKey, folderType"""

        folders_str = []
        for folder in self._api.folders.get_folders(maxResults=maxResults, startAt=startAt,
                                                    projectKey=projectKey, folderType=folderType):
            folders_str.append(folder)
        return folders_str if return_as_list else f"Extracted folders: {folders_str}"

    def update_test_case(self, test_case_key: str, test_case_id: int, name: str, project_id: int, priority_id: int, status_id: int, **kwargs) -> str:
        """Updates an existing test case.
        
        Args:
            test_case_key: The key of the test case
            test_case_id: Integer id of the test
            name: Test case name
            project_id: Project id
            priority_id: Priority id
            status_id: Status id
            **kwargs: Additional parameters to update
        """
        
        try:
            json_data = {
                "id": test_case_id,
                "key": test_case_key,
                "name": name,
                "project": {"id": project_id},
                "priority": {"id": priority_id},
                "status": {"id": status_id}
            }
            
            if kwargs:
                json_data.update(kwargs)
                
            update_response = self._api.test_cases.update_test_case(
                test_case_key,
                test_case_id,
                name,
                project_id,
                priority_id,
                status_id,
                **kwargs
            )
            return f"Test case `{test_case_key}` was updated: {str(update_response)}"
        except Exception as e:
            return ToolException(f"Unable to update test case with key: {test_case_key}:\n{str(e)}")
            
    def get_links(self, test_case_key: str, **kwargs) -> str:
        """Returns links for a test case with specified key
        
        Args:
            test_case_key: The key of the test case
        """
        
        try:
            links = self._api.test_cases.get_links(test_case_key)
            if kwargs['return_only_links']:
                return links
            return f"Links for test case `{test_case_key}`: {str(links)}"
        except Exception as e:
            return ToolException(f"Unable to get links for test case with key: {test_case_key}:\n{str(e)}")
            
    def create_issue_links(self, test_case_key: str, issue_id: int) -> str:
        """Creates a link between a test case and a Jira issue
        
        Args:
            test_case_key: The key of the test case
            issue_id: The ID of the Jira issue to link
        NOTE: The issue ID should be a valid Jira issue ID. If JIRA issue key is provided instead, it's requrid to get issue id first either by asking user or by using JIRA tooking (if avialable).
        """
        
        try:
            link_response = self._api.test_cases.create_issue_links(test_case_key, issue_id)
            return f"Issue link created for test case `{test_case_key}` with issue ID `{issue_id}`: {str(link_response)}"
        except Exception as e:
            return ToolException(f"Unable to create issue link for test case with key: {test_case_key}:\n{str(e)}")
    
    def create_web_links(self, test_case_key: str, url: str, additional_fields: str) -> str:
        """Creates a link between a test case and a generic URL
        
        Args:
            test_case_key: The key of the test case
            url: The URL to link
            additional_fields: JSON string containing any additional fields for the web link
        """
        
        try:
            additional_params = json.loads(additional_fields) if additional_fields else {}
            web_link_response = self._api.test_cases.create_web_links(test_case_key, url, **additional_params)
            return f"Web link created for test case `{test_case_key}` with URL `{url}`: {str(web_link_response)}"
        except Exception as e:
            return ToolException(f"Unable to create web link for test case with key: {test_case_key}:\n{str(e)}")

    def _get_last_version(self, test_case_key: str, step:int = 10):
        max_iterations = 50
        count = 0
        start_at = 0
        last_version = None

        while count < max_iterations:
            count+=1
            last_versions = self.get_versions(test_case_key=test_case_key, maxResults=step, startAt=start_at, return_as_list=True)
            last_versions_count = len(last_versions)

            if last_versions_count == 0:
                break

            last_version = last_versions[-1]
            start_at+=last_versions_count

        if last_version:
            match = re.search(r'/versions/(\d+)', last_version["self"])
            version_number = match.group(1)
            return self.get_version(test_case_key=test_case_key, version=version_number, return_as_object=True)
        return None


    def get_versions(self, test_case_key: str, maxResults: Optional[int] = 10, startAt: Optional[int] = 0, return_as_list: bool = False) -> str|list:
        """Returns all test case versions for a test case with specified key. Response is ordered by most recent first.
        
        Args:
            test_case_key: The key of the test case
            maxResults: A hint as to the maximum number of results to return in each call
            startAt: Zero-indexed starting position. Should be a multiple of maxResults
        """
        
        try:
            versions = self._api.test_cases.get_versions(test_case_key, maxResults=maxResults, startAt=startAt)
            if return_as_list:
                return [version for version in versions]
            versions_list = [str(version) for version in versions]
            all_versions = '\n'.join(versions_list)
            return f"Versions for test case `{test_case_key}`: {all_versions}"
        except Exception as e:
            return ToolException(f"Unable to get versions for test case with key: {test_case_key}:\n{str(e)}")
    
    def get_version(self, test_case_key: str, version: str, return_as_object: bool = False) -> str|dict:
        """Retrieves a specific version of a test case"""
        
        try:
            version_data = self._api.test_cases.get_version(test_case_key, version)
            return version_data if return_as_object else f"Version {version} of test case `{test_case_key}`: {str(version_data)}"
        except Exception as e:
            return ToolException(f"Unable to get version {version} for test case with key: {test_case_key}:\n{str(e)}")
    
    def get_test_script(self, test_case_key: str, return_only_script:bool = False) -> str:
        """Returns the test script for the given test case"""
        
        try:
            test_script = self._api.test_cases.get_test_script(test_case_key)
            if return_only_script:
                return test_script
            return f"Test script for test case `{test_case_key}`: {str(test_script)}"
        except Exception as e:
            return ToolException(f"Unable to get test script for test case with key: {test_case_key}:\n{str(e)}")
    
    def create_test_script(self, test_case_key: str, script_type: str, text: str) -> str:
        """Creates or updates the test script for a test case"""
        
        try:
            script_response = self._api.test_cases.create_test_script(test_case_key, script_type, text)
            return f"Test script created/updated for test case `{test_case_key}`: {str(script_response)}"
        except Exception as e:
            return ToolException(f"Unable to create/update test script for test case with key: {test_case_key}:\n{str(e)}")
            
    # Helper methods for folder operations
    def _get_folders(self, project_key: str, folder_type: str = "TEST_CASE", max_results: int = 100) -> List[Dict]:
        """Get all folders in a project
        
        Args:
            project_key: Jira project key
            folder_type: Type of folder (default: TEST_CASE)
            max_results: Maximum number of folders to retrieve
            
        Returns:
            List of folder objects
        
        Raises:
            ToolException: If there's an error getting folders
        """
        all_folders = []
        try:
            for folder in self._api.folders.get_folders(
                maxResults=max_results, 
                projectKey=project_key, 
                folderType=folder_type
            ):
                all_folders.append(folder)
            return all_folders
        except Exception as e:
            raise ToolException(f"Error getting folders: {str(e)}")
    
    def _build_folder_hierarchy(self, all_folders: List[Dict]) -> Dict:
        """Build a folder hierarchy from a list of folders
        
        Args:
            all_folders: List of folder objects
            
        Returns:
            Dictionary representing the folder hierarchy
        """
        folder_hierarchy = {}
        for folder in all_folders:
            folder_id = folder.get('id')
            parent_id = folder.get('parentId')
            
            if folder_id not in folder_hierarchy:
                folder_hierarchy[folder_id] = {
                    'folder': folder,
                    'children': []
                }
            else:
                folder_hierarchy[folder_id]['folder'] = folder
                
            if parent_id:
                if parent_id not in folder_hierarchy:
                    folder_hierarchy[parent_id] = {
                        'folder': None,
                        'children': [folder_id]
                    }
                else:
                    folder_hierarchy[parent_id]['children'].append(folder_id)
        
        return folder_hierarchy
    
    def _find_folders_by_name(self, all_folders: List[Dict], folder_name: str, exact_match: bool = False) -> List[str]:
        """Find folders matching a name
        
        Args:
            all_folders: List of folder objects
            folder_name: Name to search for
            exact_match: Whether to match the name exactly
            
        Returns:
            List of folder IDs matching the name
        """
        matching_folder_ids = []
        for folder in all_folders:
            folder_name_val = folder.get('name', '')
            if exact_match:
                if folder_name_val == folder_name:
                    matching_folder_ids.append(folder.get('id'))
            else:
                if folder_name.lower() in folder_name_val.lower():
                    matching_folder_ids.append(folder.get('id'))
        
        return matching_folder_ids
    
    def _get_folder_paths(self, folder_hierarchy: Dict) -> Tuple[Dict, List[str]]:
        """Build full paths for each folder
        
        Args:
            folder_hierarchy: Dictionary representing the folder hierarchy
            
        Returns:
            Tuple of (folder_paths, root_folders)
                folder_paths: Dictionary mapping folder IDs to their full paths
                root_folders: List of root folder IDs
        """
        folder_paths = {}
        root_folders = []
        
        # Identify root folders
        for folder_id, data in folder_hierarchy.items():
            folder = data.get('folder')
            if folder and not folder.get('parentId'):
                root_folders.append(folder_id)
        
        # Function to build full paths for each folder
        def build_folder_paths(folder_id, current_path=""):
            if folder_id not in folder_hierarchy or not folder_hierarchy[folder_id]['folder']:
                return
                
            folder_name = folder_hierarchy[folder_id]['folder'].get('name', '')
            if current_path:
                full_path = f"{current_path}/{folder_name}"
            else:
                full_path = folder_name
                
            folder_paths[folder_id] = full_path
            
            # Process children
            for child_id in folder_hierarchy[folder_id]['children']:
                build_folder_paths(child_id, full_path)
        
        # Build paths starting from root folders
        for root_id in root_folders:
            build_folder_paths(root_id)
        
        return folder_paths, root_folders
    
    def _find_folder_by_path(self, folder_paths: Dict, folder_path: str) -> Optional[str]:
        """Find a folder by its path
        
        Args:
            folder_paths: Dictionary mapping folder IDs to their full paths
            folder_path: Path to search for
            
        Returns:
            Folder ID or None if not found
        """
        for folder_id, path in folder_paths.items():
            if path == folder_path:
                return folder_id
        return None
    
    def _collect_subfolders(self, folder_hierarchy: Dict, parent_folder_ids: List[str], include_parents: bool = True) -> List[str]:
        """Collect all subfolders of the given parent folders
        
        Args:
            folder_hierarchy: Dictionary representing the folder hierarchy
            parent_folder_ids: List of parent folder IDs
            include_parents: Whether to include the parent folders in the result
            
        Returns:
            List of all subfolder IDs (and parent IDs if include_parents is True)
        """
        result_folder_ids = parent_folder_ids.copy() if include_parents else []
        # collected_folders = set(result_folder_ids)
        
        # Function to recursively collect subfolders
        def collect_subfolders_recursive(parent_folder_id):
            if int(parent_folder_id) not in folder_hierarchy.keys():
                return              
            
            for child_id in folder_hierarchy[int(parent_folder_id)].get('children', []):
                result_folder_ids.append(child_id)
                collect_subfolders_recursive(child_id)
        
        # Start recursive collection for each parent folder
        for folder_id in parent_folder_ids:
            collect_subfolders_recursive(folder_id)
        
        return list(set(result_folder_ids))  # Remove duplicates
    
    def _get_test_cases_from_folders(self, project_key: str, folder_ids: List[str], 
                                     max_results: int = 100, start_at: int = 0, 
                                     params: Dict = None) -> List[Dict]:
        """Get test cases from multiple folders
        
        Args:
            project_key: Jira project key
            folder_ids: List of folder IDs
            max_results: Maximum number of results per folder
            start_at: Starting position
            params: Additional parameters for the API call
            
        Returns:
            List of test case objects
        """
        all_test_cases = []
        base_params = params.copy() if params else {}
        base_params.update({
            "projectKey": project_key,
            "maxResults": max_results,
            "startAt": start_at
        })
        
        for folder_id in folder_ids:
            folder_params = base_params.copy()
            folder_params["folderId"] = folder_id
            try:
                test_cases = self._api.test_cases.get_test_cases(**folder_params)
                all_test_cases.extend(test_cases)
            except Exception as e:
                logger.warning(f"Error getting test cases from folder {folder_id}: {str(e)}")
        
        return all_test_cases
    
    def _process_custom_fields_param(self, custom_fields: str) -> Dict:
        """Process custom fields parameter from JSON string
        
        Args:
            custom_fields: JSON string containing custom fields
            
        Returns:
            Dictionary of parameters to add to the API call
            
        Raises:
            ToolException: If the JSON is invalid
        """
        params = {}
        if not custom_fields:
            return params
            
        try:
            custom_fields_dict = json.loads(custom_fields)
            for field_name, field_value in custom_fields_dict.items():
                # Format according to Zephyr Scale API: customField_{fieldName}
                field_key = f"customField_{field_name.replace(' ', '_')}"
                params[field_key] = field_value
            return params
        except json.JSONDecodeError as e:
            raise ToolException(f"Invalid JSON format for custom_fields: {str(e)}")
    
    def _filter_test_cases(self, test_cases: List[Dict], search_term: str = None, 
                          labels: List[str] = None, custom_fields_dict: Dict = None) -> List[Dict]:
        """Filter test cases based on criteria
        
        Args:
            test_cases: List of test case objects
            search_term: Term to search for in name and key
            labels: List of labels to filter by
            custom_fields_dict: Custom fields to filter by
            
        Returns:
            Filtered list of test case objects
        """
        filtered_cases = []
        
        for tc in test_cases:
            # Apply search term filter if provided
            search_match = True
            if search_term:
                search_match = (search_term.lower() in str(tc.values()).lower())
            
            # Apply labels filter if provided
            labels_match = True
            if labels and len(labels) > 0:
                tc_labels = tc.get('labels', [])
                # Check if at least one of the specified labels exists in the test case
                labels_match = any(label in tc_labels for label in labels)
            
            # Apply custom fields filter if provided
            custom_fields_match = True
            if custom_fields_dict:
                for field_name, expected_value in custom_fields_dict.items():
                    # Check if the test case has the custom field and the expected value
                    if "customFields" in tc and field_name in tc.get("customFields", {}):
                        actual_value = tc["customFields"][field_name]
                        print(f"Checking custom field '{field_name}': expected={expected_value}, actual={actual_value}, isinstance(expected_value, list)={isinstance(expected_value, list)}, isinstance(actual_value, list)={isinstance(actual_value, list)}, any(ev in actual_value for ev in expected_value)={any(ev in actual_value for ev in expected_value)}")
                        # Handle different types of custom field values (single value, list, etc.)
                        # if isinstance(actual_value, list) and isinstance(expected_value, list):
                        #     # For list values, check if they match exactly
                        #     if set(actual_value) != set(expected_value):
                        #         custom_fields_match = False
                        #         break
                        if isinstance(actual_value, list) and isinstance(expected_value, list):
                            # For list values, check if they contain the expected value
                            if not any(ev in actual_value for ev in expected_value):
                                custom_fields_match = False
                                break
                        elif isinstance(actual_value, list) and not isinstance(expected_value, list):
                            # For list values, check if expected value is in the list
                            if expected_value not in actual_value:
                                custom_fields_match = False
                                break
                        else:
                            # For single values, check for exact match
                            if actual_value != expected_value:
                                custom_fields_match = False
                                break
                    else:
                        # If the test case doesn't have the custom field, it doesn't match
                        custom_fields_match = False
                        break
            
            # Add test case if it matches all filters
            if search_match and labels_match and custom_fields_match:
                filtered_cases.append(tc)
                
        return filtered_cases
    
    def _filter_test_steps(self, test_cases: List[Dict], steps_search: str, include_steps: bool = False) -> Tuple[List[Dict], Dict]:
        """Filter test cases based on their steps
        
        Args:
            test_cases: List of test case objects
            steps_search: Term to search for in steps
            include_steps: Whether to include matching steps in the results
            
        Returns:
            Tuple of (filtered_cases, steps_search_results)
                filtered_cases: List of test cases with matching steps
                steps_search_results: Dictionary mapping test case keys to their matching steps
        """
        filtered_cases = []
        steps_search_results = {}
        
        # Collect test case keys
        test_case_keys = [tc.get('key') for tc in test_cases]
        
        # For each test case, check if any steps match the search term
        for tc_key in test_case_keys:
            try:
                # Get steps for this test case
                steps = self._api.test_cases.get_test_steps(tc_key)
                
                # Check if any step matches the search term
                matching_steps = []
                for step in steps:
                    description = step.get('inline', {}).get('description', '')
                    test_data = step.get('inline', {}).get('testData', '')
                    expected_result = step.get('inline', {}).get('expectedResult', '')
                    
                    # Check if search term appears in any step field
                    if ((description and steps_search.lower() in description.lower()) or
                        (test_data and steps_search.lower() in test_data.lower()) or
                        (expected_result and steps_search.lower() in expected_result.lower())):
                        # If we need to include steps in the response, save the matching step
                        if include_steps:
                            matching_steps.append(step)
                        else:
                            # Just mark as matching, no need to save the step details
                            matching_steps = True
                            break
                
                # If any steps matched, add to our results
                if matching_steps:
                    steps_search_results[tc_key] = matching_steps
            except Exception as e:
                logger.warning(f"Error getting steps for test case {tc_key}: {str(e)}")
        
        # Filter test cases based on step search results
        for tc in test_cases:
            tc_key = tc.get('key')
            if tc_key in steps_search_results:
                # If including steps, add them to the test case
                if include_steps:
                    tc['steps'] = steps_search_results[tc_key]
                filtered_cases.append(tc)
        
        return filtered_cases, steps_search_results
    
    def _format_test_case_results(self, test_cases: List[Dict], fields: List[str], 
                                 search_criteria: Dict = None) -> Tuple[List[Dict], str]:
        """Format test case results
        
        Args:
            test_cases: List of test case objects
            fields: Fields to include in the response
            search_criteria: Dictionary of search criteria for the response message
            
        Returns:
            Tuple of (formatted_cases, message)
                formatted_cases: List of formatted test case objects
                message: Response message
        """
        # Keep only the requested fields for each test case
        result_cases = []
        for tc in test_cases:
            result_case = {}
            for field in fields:
                if field in tc:
                    result_case[field] = tc[field]
                # Check if the field is a custom field request
                elif field.startswith("customFields."):
                    custom_field_name = field.split(".", 1)[1]
                    if "customFields" in tc and custom_field_name in tc["customFields"]:
                        # Create customFields object if it doesn't exist yet
                        if "customFields" not in result_case:
                            result_case["customFields"] = {}
                        # Add the custom field to the result
                        result_case["customFields"][custom_field_name] = tc["customFields"][custom_field_name]
                # If requesting all customFields
                elif field == "customFields" and "customFields" in tc:
                    result_case["customFields"] = tc["customFields"]
            
            result_cases.append(result_case)
        
        # Build a helpful response message
        message = f"Found {len(result_cases)} test cases"
        if search_criteria:
            response_details = []
            for key, value in search_criteria.items():
                if value:
                    response_details.append(f"{key} '{value}'")
            
            search_details = " and ".join(response_details)
            if search_details:
                message += f" matching {search_details}"
        
        return result_cases, message

    def search_test_cases(self, project_key: str, search_term: Optional[str] = None,
                         max_results: Optional[int] = 1000, start_at: Optional[int] = 0,
                         order_by: Optional[str] = "name", order_direction: Optional[str] = "ASC", 
                         archived: Optional[bool] = False, fields: Optional[List[str]] = ["key", "name"],
                         limit_results: Optional[int] = None, folder_id: Optional[str] = None,
                         folder_name: Optional[str] = None, exact_folder_match: Optional[bool] = False,
                         folder_path: Optional[str] = None, include_subfolders: Optional[bool] = True,
                         labels: Optional[List[str]] = None, custom_fields: Optional[str] = None,
                         steps_search: Optional[str] = None, include_steps: Optional[bool] = False,
                         return_raw: bool = False) -> Union[str, List[dict]]:
        """Searches for test cases using custom search API.
        
        Args:
            project_id: Jira project key (e.g., "SIT", "PROJ")
            search_term: Optional search term to filter test cases
            max_results: Maximum number of results to query from the API
            start_at: Zero-indexed starting position
            order_by: Field to order results by
            order_direction: Order direction (ASC or DESC)
            archived: Include archived test cases
            fields: Fields to include in the response (default: key, name)
            limit_results: Maximum number of filtered results to return
            folder_id: Filter test cases by folder ID
            folder_name: Filter test cases by folder name (full or partial)
            exact_folder_match: Whether to match the folder name exactly or allow partial matches
            folder_path: Filter test cases by folder path (e.g., 'Root/Parent/Child')
            include_subfolders: Include test cases from subfolders of matching folders
            labels: Filter test cases by labels
            custom_fields: JSON string containing custom field filters (e.g., {"Country": "All", "Is Automated": "Yes"})
            steps_search: Search term to find in test case steps (description, expected result, or test data)
            include_steps: Whether to include test steps in the response
        """
        try:
            # First, handle folder name and folder path search
            target_folder_ids = []
            
            # If we have folder_name or folder_path, we need to get folders and build the folder hierarchy
            if folder_name or folder_path:
                # Get all folders in the project
                all_folders = self._get_folders(project_key, "TEST_CASE", 1000)
                
                # Build folder hierarchy
                folder_hierarchy = self._build_folder_hierarchy(all_folders)
                
                # Handle folder name search
                if folder_name:
                    matching_ids = self._find_folders_by_name(all_folders, folder_name, exact_folder_match)
                    target_folder_ids.extend(matching_ids)
                
                # Handle folder path search
                if folder_path:
                    folder_paths, _ = self._get_folder_paths(folder_hierarchy)
                    target_folder_id = self._find_folder_by_path(folder_paths, folder_path)
                    if target_folder_id:
                        target_folder_ids.append(target_folder_id)
                
                # If include_subfolders is True, add all subfolders of matching folders
                if include_subfolders and target_folder_ids:
                    target_folder_ids = self._collect_subfolders(folder_hierarchy, target_folder_ids)
                
                # If we have target folder IDs but no folder_id is specified, use the first one
                if target_folder_ids and not folder_id:
                    folder_id = target_folder_ids[0]
            
            # Prepare parameters for the API call
            params = {
                "projectKey": project_key,
                "maxResults": max_results,
                "startAt": start_at
            }
            
            # Add folder_id if provided or found through folder name/path search
            if folder_id:
                params["folderId"] = folder_id
            
            # Process custom fields if provided
            custom_fields_params = {}
            custom_fields_dict = None
            if custom_fields:
                try:
                    custom_fields_dict = json.loads(custom_fields)
                    custom_fields_params = self._process_custom_fields_param(custom_fields)
                    # params.update(custom_fields_params)
                except Exception as e:
                    return ToolException(f"Error processing custom fields: {str(e)}")
            
            # Get test cases from the API
            all_test_cases = []
            
            # If we have multiple target folder IDs, get test cases from each folder
            if target_folder_ids and include_subfolders:
                all_test_cases = self._get_test_cases_from_folders(
                    project_key, target_folder_ids, max_results, start_at, params
                )
            else:
                # Just use the standard params (which might include a single folder_id)
                all_test_cases = self._api.test_cases.get_test_cases(**params)
            
            # Apply filtering based on search term, labels, and custom fields
            filtered_cases = self._filter_test_cases(
                all_test_cases, search_term, labels, custom_fields_dict
            )
            
            # If steps_search is provided, filter by test steps
            if steps_search:
                filtered_cases, steps_search_results = self._filter_test_steps(
                    filtered_cases, steps_search, include_steps
                )
            #ToDo later: if steps_search_results is not empty, need to be added to output (maybe).
            
            # Sort the results if needed
            if order_by and filtered_cases:
                reverse = order_direction.upper() == "DESC"
                filtered_cases.sort(key=lambda x: x.get(order_by, ''), reverse=reverse)
            
            # Limit the number of results if specified
            if limit_results is not None and limit_results < len(filtered_cases):
                filtered_cases = filtered_cases[:limit_results]
            
            # Format the results
            search_criteria = {
                "folder name": folder_name,
                "folder path": folder_path,
                "folder ID": folder_id,
                "search term": search_term,
                "labels": labels,
                "custom fields": custom_fields,
                "steps containing": steps_search
            }

            if return_raw:
                return filtered_cases
            return self._finalize_test_case_results(filtered_cases, fields, search_criteria)

        except Exception as e:
            return ToolException(f"Error searching test cases: {str(e)}")

    def _finalize_test_case_results(self, filtered_cases: List[dict], fields: List[str], search_criteria: dict) -> str:
        result_cases, message = self._format_test_case_results(filtered_cases, fields, search_criteria)
        return f"{message}: {json.dumps(result_cases, indent=2)}"

    def _search_test_cases_by_jql(self, project_key: str, jql: str):
        try:
            parsed = self._parse_jql(jql)

            return self.search_test_cases(
                project_key=project_key,
                search_term=parsed.get("text"),
                order_by=parsed.get("orderBy", "name"),
                order_direction=parsed.get("orderDirection", "ASC"),
                limit_results=parsed.get("limit"),
                folder_name=parsed.get("folder"),
                folder_path=parsed.get("folderPath"),
                exact_folder_match=parsed.get("exactFolderMatch", False),
                include_subfolders=parsed.get("includeSubfolders", True),
                labels=parsed.get("label"),
                custom_fields=parsed.get("customFields"),
                steps_search=parsed.get("steps"),
                include_steps=True,
                return_raw=True
            )
        except Exception as e:
            return ToolException(f"Error searching test cases by JQL: {str(e)}")

    def _parse_jql(self, jql: str) -> dict:
        import re
        result = {}

        # Match string equality: field = "value"
        for match in re.findall(r'(\w+)\s*=\s*"([^"]*)"', jql):
            result[match[0]] = match[1]

        # Match text search: field ~ "value"
        for match in re.findall(r'(\w+)\s*~\s*"([^"]*)"', jql):
            result[match[0]] = match[1]

        # Match list: field in ("a", "b", ...)
        for match in re.findall(r'(\w+)\s*in\s*\(\s*([^)]+?)\s*\)', jql):
            values = [v.strip().strip('"') for v in match[1].split(",")]
            result[match[0]] = values

        # Match number/bool: field = 123 or field = true/false
        for match in re.findall(r'(\w+)\s*=\s*([^\s"()]+)', jql):
            key, raw_val = match
            if key in result:
                continue
            if raw_val.lower() == "true":
                result[key] = True
            elif raw_val.lower() == "false":
                result[key] = False
            elif raw_val.isdigit():
                result[key] = int(raw_val)
            else:
                try:
                    result[key] = float(raw_val)
                except ValueError:
                    result[key] = raw_val

        return result

    def _index_tool_params(self, **kwargs) -> dict[str, tuple[type, Field]]:
        """
        Returns a list of fields for index_data args schema.
        """
        return {
            "project_key": (str, Field(description="Jira project key filter")),
            "jql":(str, Field(description="""JQL-like query for searching test cases.
            Supported fields:
            - folder: exact folder name (e.g., folder = "Login Tests")
            - folderPath: full folder path (e.g., folderPath = "Root/Subfolder")
            - label: one or more labels (e.g., label in ("Smoke", "Critical"))
            - text: full-text search in name/description (e.g., text ~ "login")
            - customFields: JSON string with key-value pairs to filter by custom fields
            - steps: search within test steps (e.g., steps ~ "click submit")
            - orderBy: sort field (e.g., orderBy = "name")
            - orderDirection: ASC or DESC (e.g., orderDirection = "DESC")
            - limit: maximum number of results (e.g., limit = 100)
            - includeSubfolders: whether to include subfolders (e.g., includeSubfolders = false)
            - exactFolderMatch: match folder name exactly (e.g., exactFolderMatch = true)
        
            Example:
                'folder = "Authentication" AND label in ("Smoke", "Critical") AND text ~ "login" AND orderBy = "name" AND orderDirection = "ASC"'
            """)),
            'chunking_tool': (Literal['json'], Field(description="Name of chunking tool", default='json'))
        }

    def _base_loader(self, project_key: str, jql: str, **kwargs) -> Generator[Document, None, None]:
        for test_case_doc in self._get_test_cases_docs(project_key, jql):
            yield test_case_doc
        for folder_doc in self._get_folders_docs(project_key):
            yield folder_doc

    def _get_all_folders(self, project_key: str, folder_type:str, step: int = 10):
        max_iterations = 50
        count = 0
        all_folders = []
        start_at = 0
        while count < max_iterations:
            count+=1
            new_folders = self.get_folders(projectKey=project_key, folderType=folder_type, maxResults=step, startAt=start_at, return_as_list=True)

            if new_folders and len(new_folders) > 0:
                all_folders.extend(new_folders)
                start_at+=step
            else:
                break
        return all_folders

    def _get_folders_docs(self, project_key: str) -> Generator[Document, None, None]:
        folder_types = ['TEST_CASE', 'TEST_PLAN', 'TEST_CYCLE']
        folders = []
        for folder_type in folder_types:
            try:
                folders.extend(self._get_all_folders(project_key, folder_type=folder_type, step=100))
            except Exception as e:
                raise ToolException(f"Unable to extract folders for folder type '{folder_type}': {e}")
        page_content = {}
        for folder in folders:
            page_content['name'] = folder['name']
            metadata = {}
            for key, value in folder.items():
                if value is not None:
                    metadata[key] = value
            metadata['type'] = "FOLDER"
            yield Document(page_content="", metadata=metadata)

    def _get_test_cases_docs(self, project_key: str, jql: str) -> Generator[Document, None, None]:
        try:
            test_cases = self._search_test_cases_by_jql(project_key, jql)
        except Exception as e:
            raise ToolException(f"Unable to extract test cases: {e}")

        for case in test_cases:
            last_version = self._get_last_version(case['key'], step=100)
            metadata = {
                k: v for k, v in case.items()
                if isinstance(v, (str, int, float, bool, list, dict))
            }
            if last_version and isinstance(last_version, dict) and 'createdOn' in last_version:
                metadata['updated_on'] = last_version['createdOn']
            else:
                metadata['updated_on'] = case['createdOn']
            metadata['type'] = "TEST_CASE"

            yield Document(page_content="", metadata=metadata)

    def _extend_data(self, documents: Generator[Document, None, None]) -> Generator[Document, None, None]:
        for document in documents:
            try:
                if 'type' in document.metadata and document.metadata['type'] == "TEST_CASE":
                    additional_content = self._process_test_case(document.metadata['key'])
                    for steps_type, content in additional_content.items():
                        if content:
                            document.page_content = json.dumps(content)
                            document.metadata["steps_type"] = steps_type
            except Exception as e:
                logging.error(f"Failed to process document: {e}")
            yield document

    def _process_test_case(self, key):
        steps = self.get_test_steps(key, return_list=True)
        if steps and not isinstance(steps, ToolException):
            return {"steps": steps}
        script = self.get_test_script(key, return_only_script=True)
        if script and not isinstance(script, ToolException):
            return {"script": script}
        return {"empty": ""}

    def get_tests_recursive(self, project_key: str = None, folder_id: str = None, maxResults: Optional[int] = 100, startAt: Optional[int] = 0):
        """Retrieves all test cases recursively from a folder and all its subfolders.
        
        Args:
            project_key: Jira project key filter
            folder_id: Parent folder ID to start the recursive search from
            maxResults: A hint as to the maximum number of results to return in each call
            startAt: Zero-indexed starting position. Should be a multiple of maxResults
            
        Returns:
            A string with all test cases found in the folder and its subfolders
        """
        try:
            # Store all test cases
            all_test_cases = []
            
            # Prepare base parameters for API calls
            base_params = {
                "maxResults": maxResults,
                "startAt": startAt
            }
            if project_key:
                base_params["projectKey"] = project_key
            
            # First, get test cases from the specified folder if a folder_id was provided
            if folder_id:
                folder_params = base_params.copy()
                folder_params["folderId"] = folder_id
                try:
                    test_cases = self._api.test_cases.get_test_cases(**folder_params)
                    all_test_cases.extend(test_cases)
                except Exception as e:
                    logger.warning(f"Error getting test cases from folder {folder_id}: {str(e)}")
            
            # Get all folders in the project
            all_folders = self._get_folders(project_key, "TEST_CASE", 1000)
            
            # Build folder hierarchy
            folder_hierarchy = self._build_folder_hierarchy(all_folders)
            # If a folder_id was specified, collect all its subfolders
            if folder_id:
                # Get all subfolders of the specified folder
                subfolder_ids = self._collect_subfolders(folder_hierarchy, [folder_id], include_parents=False)
                # Get test cases from all subfolders
                if subfolder_ids:
                    subfolder_test_cases = self._get_test_cases_from_folders(
                        project_key, subfolder_ids, maxResults, startAt, base_params
                    )
                    all_test_cases.extend(subfolder_test_cases)
            
            # Convert the test cases to a string
            parsed_tests = self._parse_tests(all_test_cases)
            return f"Extracted {len(all_test_cases)} tests recursively: {str(parsed_tests)}"
            
        except Exception as e:
            return ToolException(f"Error retrieving test cases recursively: {str(e)}")

    @staticmethod
    def _parse_tests(tests) -> list:
        """Parses test cases information"""
        parsed_tests = []
        for test in tests:
            test_item = []
            # Adding extracted information to the list
            test_item.append(f"Test ID: {test.get('id')}")
            test_item.append(f"Key: {test.get('key')}")
            test_item.append(f"Name: {test.get('name')}")

            # For project ID
            project = test.get('project')
            if project is not None:
                test_item.append(f"Project ID: {project.get('id')}")
            else:
                test_item.append("Project ID: None")

            test_item.append(f"Precondition: {test.get('precondition')}")

            # For priority ID
            priority = test.get('priority')
            if priority is not None:
                test_item.append(f"Priority ID: {priority.get('id')}")
            else:
                test_item.append("Priority ID: None")

            # For status ID
            status = test.get('status')
            if status is not None:
                test_item.append(f"Status ID: {status.get('id')}")
            else:
                test_item.append("Status ID: None")

            # For owner account ID
            owner = test.get('owner')
            if owner is not None:
                test_item.append(f"Owner Account ID: {owner.get('accountId')}")
            else:
                test_item.append("Owner Account ID: None")
            parsed_tests.append(test_item)
        return parsed_tests
    
    def get_tests_by_folder_name(self, project_key: str, folder_name: str, exact_match: Optional[bool] = False, 
                             include_subfolders: Optional[bool] = True, maxResults: Optional[int] = 100, 
                             startAt: Optional[int] = 0):
        """Retrieves all test cases from folders matching the specified name.
        
        Args:
            project_key: Jira project key filter
            folder_name: Full or partial folder name to search for
            exact_match: Whether to match the folder name exactly or allow partial matches
            include_subfolders: Whether to include test cases from subfolders of matching folders
            maxResults: A hint as to the maximum number of results to return in each call
            startAt: Zero-indexed starting position. Should be a multiple of maxResults
            
        Returns:
            A string with all test cases found in matching folders
        """
        try:
            # Get all folders in the project
            all_folders = self._get_folders(project_key, "TEST_CASE", 1000)
            
            # Find folders matching the name
            matching_folder_ids = self._find_folders_by_name(all_folders, folder_name, exact_match)
            
            if not matching_folder_ids:
                return f"No folders found matching name: {folder_name}"
            
            # If include_subfolders is True, add all subfolders
            if include_subfolders:
                folder_hierarchy = self._build_folder_hierarchy(all_folders)
                matching_folder_ids = self._collect_subfolders(folder_hierarchy, matching_folder_ids)
                print (f"Collecting subfolders for {len(matching_folder_ids)} matching folders: {matching_folder_ids}")
            # Get test cases from all matching folders
            all_test_cases = self._get_test_cases_from_folders(
                project_key, matching_folder_ids, maxResults, startAt
            )
            
            # Convert the test cases to a string
            parsed_tests = self._parse_tests(all_test_cases)
            return f"Extracted {len(all_test_cases)} tests from {len(matching_folder_ids)} folders matching '{folder_name}': {str(parsed_tests)}"
            
        except Exception as e:
            return ToolException(f"Error getting tests by folder name: {str(e)}")

    def get_tests_by_folder_path(self, project_key: str, folder_path: str, include_subfolders: Optional[bool] = True,
                                maxResults: Optional[int] = 100, startAt: Optional[int] = 0):
        """Retrieves all test cases from a folder specified by its path.
        
        Args:
            project_key: Jira project key filter
            folder_path: Full folder path (e.g., 'Root/Parent/Child')
            include_subfolders: Whether to include test cases from subfolders
            maxResults: A hint as to the maximum number of results to return in each call
            startAt: Zero-indexed starting position. Should be a multiple of maxResults
            
        Returns:
            A string with all test cases found in the specified folder path
        """
        try:
            # Get all folders in the project
            all_folders = self._get_folders(project_key, "TEST_CASE", 1000)
            
            # Build folder hierarchy
            folder_hierarchy = self._build_folder_hierarchy(all_folders)
            
            # Get folder paths
            folder_paths, _ = self._get_folder_paths(folder_hierarchy)
            
            # Find the folder matching the exact path
            target_folder_id = self._find_folder_by_path(folder_paths, folder_path)
            
            if not target_folder_id:
                return f"No folder found with path: {folder_path}"
            
            # Get test cases from the target folder
            folder_ids = [target_folder_id]
            
            # If including subfolders, add all subfolders
            if include_subfolders:
                folder_ids = self._collect_subfolders(folder_hierarchy, folder_ids)
            
            # Get test cases from all matching folders
            all_test_cases = self._get_test_cases_from_folders(
                project_key, folder_ids, maxResults, startAt
            )
            
            # Convert the test cases to a string
            parsed_tests = self._parse_tests(all_test_cases)
            return f"Extracted {len(all_test_cases)} tests from folder path '{folder_path}': {str(parsed_tests)}"
            
        except Exception as e:
            return ToolException(f"Error getting tests by folder path: {str(e)}")

    def update_test_steps(self, test_case_key: str, steps_updates: str) -> str:
        """Updates specific test steps in a test case.
        
        Args:
            test_case_key: The key of the test case
            steps_updates: JSON string representing the test steps to update. Format:
                [{
                    "index": 0,  # Zero-based index of the step to update
                    "description": "Updated step description",  # Optional
                    "testData": "Updated test data",  # Optional
                    "expectedResult": "Updated expected result"  # Optional
                }]
                
        Returns:
            A confirmation message with the update result
        """
        try:
            # Get current test steps
            current_steps = self._api.test_cases.get_test_steps(test_case_key)
            if not current_steps:
                return ToolException(f"No test steps found for test case: {test_case_key}")
            
            # Parse updates from JSON string
            try:
                updates = json.loads(steps_updates)
                if not isinstance(updates, list):
                    return ToolException("Steps updates must be a JSON array")
            except json.JSONDecodeError as e:
                return ToolException(f"Invalid JSON format for steps_updates: {str(e)}")
            
            # Apply updates to the steps
            for update in updates:
                if 'index' not in update:
                    return ToolException("Each update must contain an 'index' field")
                
                index = update.get('index')
                if not isinstance(index, int) or index < 0 or index >= len(current_steps):
                    return ToolException(f"Step index {index} is out of range. Valid range: 0-{len(current_steps)-1}")
                
                # Get the current step
                step = current_steps[index]
                
                # Only update the inline field if it exists
                if 'inline' not in step:
                    return ToolException(f"Step at index {index} does not have an inline field")
                
                # Update the fields that are provided
                if 'description' in update:
                    step['inline']['description'] = update['description']
                if 'testData' in update:
                    step['inline']['testData'] = update['testData']
                if 'expectedResult' in update:
                    step['inline']['expectedResult'] = update['expectedResult']
            
            # Update all steps back to the test case
            update_response = self._api.test_cases.post_test_steps(
                test_case_key,
                'OVERWRITE',  # Use OVERWRITE mode to replace all steps
                current_steps
            )
            
            return f"Test steps updated for test case `{test_case_key}`: {len(updates)} step(s) modified"
        except Exception as e:
            return ToolException(f"Error updating test steps for test case {test_case_key}: {str(e)}")

    @extend_with_parent_available_tools
    def get_available_tools(self):
        return [
            {
                "name": "get_tests",
                "description": self.get_tests.__doc__,
                "args_schema": ZephyrGetTestCases,
                "ref": self.get_tests,
            },
            {
                "name": "get_test",
                "description": self.get_test.__doc__,
                "args_schema": ZephyrGetTestCase,
                "ref": self.get_test,
            },
            {
                "name": "get_test_steps",
                "description": self.get_test_steps.__doc__,
                "args_schema": ZephyrGetTestCase,
                "ref": self.get_test_steps,
            },
            {
                "name": "create_test_case",
                "description": self.create_test_case.__doc__,
                "args_schema": ZephyrCreateTestCase,
                "ref": self.create_test_case,
            },
            {
                "name": "create_test_cases",
                "description": self.create_test_cases.__doc__,
                "args_schema": ZephyrCreateTestCases,
                "ref": self.create_test_cases,
            },
            {
                "name": "add_test_steps",
                "description": self.add_test_steps.__doc__,
                "args_schema": ZephyrTestStepsInputModel,
                "ref": self.add_test_steps,
            },
            {
                "name": "update_test_steps",
                "description": self.update_test_steps.__doc__,
                "args_schema": ZephyrUpdateTestSteps,
                "ref": self.update_test_steps,
            },
            {
                "name": "get_folders",
                "description": self.get_folders.__doc__,
                "args_schema": ZephyrGetFolders,
                "ref": self.get_folders,
            },
            {
                "name": "update_test_case",
                "description": self.update_test_case.__doc__,
                "args_schema": ZephyrUpdateTestCase,
                "ref": self.update_test_case,
            },
            {
                "name": "get_links",
                "description": self.get_links.__doc__,
                "args_schema": ZephyrGetLinks,
                "ref": self.get_links,
            },
            {
                "name": "create_issue_links",
                "description": self.create_issue_links.__doc__,
                "args_schema": ZephyrCreateIssueLinks,
                "ref": self.create_issue_links,
            },
            {
                "name": "create_web_links",
                "description": self.create_web_links.__doc__,
                "args_schema": ZephyrCreateWebLinks,
                "ref": self.create_web_links,
            },
            {
                "name": "get_versions",
                "description": self.get_versions.__doc__,
                "args_schema": ZephyrGetVersions,
                "ref": self.get_versions,
            },
            {
                "name": "get_version",
                "description": self.get_version.__doc__,
                "args_schema": ZephyrGetVersion,
                "ref": self.get_version,
            },
            {
                "name": "get_test_script",
                "description": self.get_test_script.__doc__,
                "args_schema": ZephyrGetTestScript,
                "ref": self.get_test_script,
            },
            {
                "name": "create_test_script",
                "description": self.create_test_script.__doc__,
                "args_schema": ZephyrCreateTestScript,
                "ref": self.create_test_script,
            },
            {
                "name": "search_test_cases",
                "description": self.search_test_cases.__doc__,
                "args_schema": ZephyrSearchTestCases,
                "ref": self.search_test_cases,
            },
            {
                "name": "get_tests_recursive",
                "description": self.get_tests_recursive.__doc__,
                "args_schema": ZephyrGetTestsRecursive,
                "ref": self.get_tests_recursive,
            },
            {
                "name": "get_tests_by_folder_name",
                "description": self.get_tests_by_folder_name.__doc__,
                "args_schema": ZephyrGetTestsByFolderName,
                "ref": self.get_tests_by_folder_name,
            },
            {
                "name": "get_tests_by_folder_path",
                "description": self.get_tests_by_folder_path.__doc__,
                "args_schema": ZephyrGetTestsByFolderPath,
                "ref": self.get_tests_by_folder_path,
            }
        ]