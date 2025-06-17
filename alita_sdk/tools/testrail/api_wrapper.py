import json
import logging
from typing import Dict, List, Optional, Union

import pandas as pd
from langchain_core.tools import ToolException
from pydantic import SecretStr, create_model, model_validator
from pydantic.fields import Field, PrivateAttr
from testrail_api import StatusCodeError, TestRailAPI

from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

getCase = create_model("getCase", testcase_id=(str, Field(description="Testcase id")))

getCases = create_model(
    "getCases",
    project_id=(str, Field(description="Project id")),
    output_format=(
        str,
        Field(
            default="json",
            description="Desired output format. Supported values: 'json', 'csv', 'markdown'. Defaults to 'json'.",
        ),
    ),
    keys=(
        Optional[List[str]],
        Field(
            default=["title", "id"],
            description="A list of case field keys to include in the data output. If None, defaults to ['title', 'id'].",
        ),
    ),
)

getCasesByFilter = create_model(
    "getCasesByFilter",
    project_id=(str, Field(description="Project id")),
    json_case_arguments=(
        Union[str, dict],
        Field(
            description="""
        JSON (as a string or dictionary) of the test case arguments used to filter test cases.

        Supported args:
        :key suite_id: int
                The ID of the test suite (optional if the project is operating in
                single suite mode)
            :key created_after: int/datetime
                Only return test cases created after this date (as UNIX timestamp).
            :key created_before: int/datetime
                Only return test cases created before this date (as UNIX timestamp).
            :key created_by: List[int] or comma-separated string
                A comma-separated list of creators (user IDs) to filter by.
            :key filter: str
                Only return cases with matching filter string in the case title
            :key limit: int
                The number of test cases the response should return
                (The response size is 250 by default) (requires TestRail 6.7 or later)
            :key milestone_id: List[int] or comma-separated string
                A comma-separated list of milestone IDs to filter by (not available
                if the milestone field is disabled for the project).
            :key offset: int
                Where to start counting the tests cases from (the offset)
            :key priority_id: List[int] or comma-separated string
                A comma-separated list of priority IDs to filter by.
            :key refs: str
                A single Reference ID (e.g. TR-1, 4291, etc.)
            :key section_id: int
                The ID of a test case section
            :key template_id: List[int] or comma-separated string
                A comma-separated list of template IDs to filter by
            :key type_id: List[int] or comma-separated string
                A comma-separated list of case type IDs to filter by.
            :key updated_after: int/datetime
                Only return test cases updated after this date (as UNIX timestamp).
            :key updated_before: int/datetime
                Only return test cases updated before this date (as UNIX timestamp).
            :key updated_by: List[int] or comma-separated string
                A comma-separated list of user IDs who updated test cases to filter by.
        """
        ),
    ),
    output_format=(
        str,
        Field(
            default="json",
            description="Desired output format. Supported values: 'json', 'csv', 'markdown'. Defaults to 'json'.",
        ),
    ),
    keys=(
        Optional[List[str]],
        Field(
            default=None,
            description="A list of case field keys to include in the data output",
        ),
    ),
)

addCase = create_model(
    "addCase",
    section_id=(str, Field(description="Section id")),
    title=(str, Field(description="Title")),
    case_properties=(
        Optional[dict],
        Field(
            description="""
        Properties of new test case in a key-value format: testcase_field_name=testcase_field_value.
        Possible arguments
            :key template_id: int
                The ID of the template (field layout)
            :key type_id: int
                The ID of the case type
            :key priority_id: int
                The ID of the case priority
            :key estimate: str
                The estimate, e.g. "30s" or "1m 45s"
            :key milestone_id: int
                The ID of the milestone to link to the test case
            :key refs: str
                A comma-separated list of references/requirements

        Custom fields are supported as well and must be submitted with their
        system name, prefixed with 'custom_', e.g.:
        {
            ...
            "template_id": 1,
            "custom_preconds": "These are the preconditions for a test case",
            "custom_steps": "Step-by-step instructions for the test.",
            "custom_expected": "The final expected result."
            ...
        }
        OR
        {
            ...
            "template_id": 2,
            "custom_preconds": "These are the preconditions for a test case",
            "custom_steps_separated": [
                {"content": "Step 1 description", "expected": "Step 1 expected result"},
                {"content": "Step 2 description", "expected": "Step 2 expected result"},
                {"shared_step_id": 5}
            ]
            ...
        }

        The following custom field types are supported:
            Checkbox: bool
                True for checked and false otherwise
            Date: str
                A date in the same format as configured for TestRail and API user
                (e.g. "07/08/2013")
            Dropdown: int
                The ID of a dropdown value as configured in the field configuration
            Integer: int
                A valid integer
            Milestone: int
                The ID of a milestone for the custom field
            Multi-select: list
                An array of IDs as configured in the field configuration
            Steps: list
                An array of objects specifying the steps. Also see the example below.
            String: str
                A valid string with a maximum length of 250 characters
            Text: str
                A string without a maximum length
            URL: str
                A string with matches the syntax of a URL
            User: int
                The ID of a user for the custom field

        **Notes for `steps` and `expected`:**
        - The `steps` field can take one of two forms based on template id:
          1. A **string** for simple test steps, mapped to `custom_steps`.
             - Template ID should be 1 passed as default
             - The `expected` field in this case should also be a **string** and is mapped to `custom_expected`.
          2. A **list of dictionaries** for detailed step-by-step instructions, mapped to `custom_steps_separated`.
             - Template ID should be 2 passed as default
             - Each dictionary requires a `content` key for the step text and an `expected` key for the individual expected outcome.
             - If `shared_step_id` is included, it is preserved for that step.
        - `expected` values must always be strings and are required when `steps` is a single string or may be supplied per step when `steps` is a list.
        """,
            default={},
        ),
    ),
)

updateCase = create_model(
    "updateCase",
    case_id=(str, Field(description="Case ID")),
    case_properties=(
        Optional[dict],
        Field(
            description="""
        Properties of new test case in a key-value format: testcase_field_name=testcase_field_value.
        Possible arguments
            :key title: str
                    The title of the test case
            :key section_id: int
                The ID of the section (requires TestRail 6.5.2 or later)
            :key template_id: int
                The ID of the template (field layout)
            :key type_id: int
                The ID of the case type
            :key priority_id: int
                The ID of the case priority
            :key estimate: str
                The estimate, e.g. "30s" or "1m 45s"
            :key milestone_id: int
                The ID of the milestone to link to the test case
            :key refs: str
                A comma-separated list of references/requirements

        Custom fields are supported as well and must be submitted with their
        system name, prefixed with 'custom_', e.g.:
        {
            ...
            "template_id": 1,
            "custom_preconds": "These are the preconditions for a test case",
            "custom_steps": "Step-by-step instructions for the test.",
            "custom_expected": "The final expected result."
            ...
        }
        OR
        {
            ...
            "template_id": 2,
            "custom_preconds": "These are the preconditions for a test case",
            "custom_steps_separated": [
                {"content": "Step 1 description", "expected": "Step 1 expected result"},
                {"content": "Step 2 description", "expected": "Step 2 expected result"},
                {"shared_step_id": 5}
            ]
            ...
        }

        The following custom field types are supported:
            Checkbox: bool
                True for checked and false otherwise
            Date: str
                A date in the same format as configured for TestRail and API user
                (e.g. "07/08/2013")
            Dropdown: int
                The ID of a dropdown value as configured in the field configuration
            Integer: int
                A valid integer
            Milestone: int
                The ID of a milestone for the custom field
            Multi-select: list
                An array of IDs as configured in the field configuration
            Steps: list
                An array of objects specifying the steps. Also see the example below.
            String: str
                A valid string with a maximum length of 250 characters
            Text: str
                A string without a maximum length
            URL: str
                A string with matches the syntax of a URL
            User: int
                The ID of a user for the custom field

        **Notes for `steps` and `expected`:**
        - The `steps` field can take one of two forms based on template id:
          1. A **string** for simple test steps, mapped to `custom_steps`.
             - Template ID should be 1 passed as default
             - The `expected` field in this case should also be a **string** and is mapped to `custom_expected`.
          2. A **list of dictionaries** for detailed step-by-step instructions, mapped to `custom_steps_separated`.
             - Template ID should be 2 passed as default
             - Each dictionary requires a `content` key for the step text and an `expected` key for the individual expected outcome.
             - If `shared_step_id` is included, it is preserved for that step.
        - `expected` values must always be strings and are required when `steps` is a single string or may be supplied per step when `steps` is a list.
        """,
            default={},
        ),
    ),
)


SUPPORTED_KEYS = {
    "id", "title", "section_id", "template_id", "type_id", "priority_id", "milestone_id",
    "refs", "created_by", "created_on", "updated_by", "updated_on", "estimate",
    "estimate_forecast", "suite_id", "display_order", "is_deleted", "case_assignedto_id",
    "custom_automation_type", "custom_preconds", "custom_steps", "custom_testrail_bdd_scenario",
    "custom_expected", "custom_steps_separated", "custom_mission", "custom_goals"
}


class TestrailAPIWrapper(BaseToolApiWrapper):
    url: str
    password: Optional[SecretStr] = None,
    email: Optional[str] = None,
    _client: Optional[TestRailAPI] = PrivateAttr() # Private attribute for the TestRail client

    @model_validator(mode="before")
    @classmethod
    def validate_toolkit(cls, values):
        try:
            from testrail_api import TestRailAPI
        except ImportError:
            raise ImportError(
                "`testrail_api` package not found, please run "
                "`pip install testrail_api`"
            )

        url = values["url"]
        password = values.get("password")
        email = values.get("email")
        cls._client = TestRailAPI(url, email, password)
        return values

    def add_case(self, section_id: str, title: str, case_properties: Optional[dict]):
        """Adds new test case into Testrail per defined parameters.
        Parameters:
            section_id: str - test case section id.
            title: str - new test case title.
            case_properties: dict[str, str] - properties of new test case, for examples:
                :key template_id: int
                The ID of the template
                :key type_id: int
                The ID of the case type
                :key priority_id: int
                The ID of the case priority
                :key estimate: str
                The estimate, e.g. "30s" or "1m 45s"
                etc.
                Custom fields are supported with prefix 'custom_', e.g.:
                :custom_steps: str
                Steps in String format (requires template_id: 1)
                :custom_steps_separated: dict
                Steps in Dict format (requires template_id: 2)
                :custom_preconds: str
                These are the preconditions for a test case
        """
        try:
            created_case = self._client.cases.add_case(
                section_id=section_id, title=title, **case_properties
            )
        except StatusCodeError as e:
            return ToolException(f"Unable to add new testcase {e}")
        return f"New test case has been created: id - {created_case['id']} at '{created_case['created_on']}')"

    def get_case(self, testcase_id: str):
        """Extracts information about single test case from Testrail"""
        try:
            extracted_case = self._client.cases.get_case(testcase_id)
        except StatusCodeError as e:
            return ToolException(f"Unable to extract testcase {e}")
        return f"Extracted test case:\n{str(extracted_case)}"

    def get_cases(
        self, project_id: str, output_format: str = "json", keys: Optional[List[str]] = None
    ) -> Union[str, ToolException]:
        """
        Extracts a list of test cases in the specified format: `json`, `csv`, or `markdown`.

        Args:
            project_id (str): The project ID to extract test cases from.
            output_format (str): Desired output format. Options are 'json', 'csv', 'markdown'.
                                Default is 'json'.
            keys (List[str]): A list of case field keys to include in the data output.
                              If None, defaults to ['id', 'title'].

        Returns:
            str: A representation of the test cases in the specified format
        """
        if keys is None:
            keys = ["title", "id"]

        invalid_keys = [key for key in keys if key not in SUPPORTED_KEYS]

        try:
            extracted_cases = self._client.cases.get_cases(project_id=project_id)
            cases = extracted_cases.get("cases")

            if cases is None:
                return ToolException("No test cases found in the extracted data.")

            extracted_cases_data = [
                {key: case.get(key, "N/A") for key in keys} for case in cases
            ]

            if not extracted_cases_data:
                return ToolException("No valid test case data found to format.")

            result = self._to_markup(extracted_cases_data, output_format)

            if invalid_keys:
                return f"{result}\n\nInvalid keys: {invalid_keys}"

            return result
        except StatusCodeError as e:
            return ToolException(f"Unable to extract testcases {e}")

    def get_cases_by_filter(
        self,
        project_id: str,
        json_case_arguments: Union[str, dict],
        output_format: str = "json",
        keys: Optional[List[str]] = None
    ) -> Union[str, ToolException]:
        """
        Extracts test cases from a specified project based on given case attributes.

        Args:
            project_id (str): The project ID to extract test cases from.
            json_case_arguments (Union[str, dict]): The filter attributes for case extraction.
                                                    Can be a JSON string or a dictionary.
            output_format (str): Desired output format. Options are 'json', 'csv', 'markdown'.
                                 Default is 'json'.
            keys (Optional[List[str]]): An optional list of case field keys to include in the data output.

        Returns:
            str: A representation of the test cases in the specified format.
        """
        if keys:
            invalid_keys = [key for key in keys if key not in SUPPORTED_KEYS]

        try:
            if isinstance(json_case_arguments, str):
                params = json.loads(json_case_arguments)
            elif isinstance(json_case_arguments, dict):
                params = json_case_arguments
            else:
                return ToolException(
                    "json_case_arguments must be a JSON string or dictionary."
                )

            extracted_cases = self._client.cases.get_cases(
                project_id=project_id, **params
            )

            cases = extracted_cases.get("cases")

            if cases is None:
                return ToolException("No test cases found in the extracted data.")

            if keys is None:
                return self._to_markup(cases, output_format)

            extracted_cases_data = [
                {key: case.get(key, "N/A") for key in keys} for case in cases
            ]

            if extracted_cases_data is None:
                return ToolException("No valid test case data found to format.")

            result = self._to_markup(extracted_cases_data, output_format)

            if invalid_keys:
                return f"{result}\n\nInvalid keys: {invalid_keys}"

            return result
        except StatusCodeError as e:
            return ToolException(f"Unable to extract test cases: {e}")
        except (ValueError, json.JSONDecodeError) as e:
            return ToolException(f"Invalid parameter for json_case_arguments: {e}")

    def update_case(self, case_id: str, case_properties: Optional[dict]):
        """Updates an existing test case (partial updates are supported, i.e.
        you can submit and update specific fields only).

        :param case_id: T
            he ID of the test case
        :param kwargs:
            :key title: str
                The title of the test case
            :key section_id: int
                The ID of the section (requires TestRail 6.5.2 or later)
            :key template_id: int
                The ID of the template (requires TestRail 5.2 or later)
            :key type_id: int
                The ID of the case type
            :key priority_id: int
                The ID of the case priority
            :key estimate: str
                The estimate, e.g. "30s" or "1m 45s"
            :key milestone_id: int
                The ID of the milestone to link to the test case
            :key refs: str
                A comma-separated list of references/requirements
        :return: response
        """
        try:
            updated_case = self._client.cases.update_case(
                case_id=case_id, **case_properties
            )
        except StatusCodeError as e:
            return ToolException(f"Unable to update testcase #{case_id} due to {e}")
        return (
            f"Test case #{case_id} has been updated at '{updated_case['updated_on']}')"
        )

    def _to_markup(self, data: List[Dict], output_format: str) -> str:
        """
        Converts the given data into the specified format: 'json', 'csv', or 'markdown'.

        Args:
            data (List[Dict]): The data to convert.
            output_format (str): Desired output format.

        Returns:
            str: The data in the specified format.
        """
        if output_format not in {"json", "csv", "markdown"}:
            return ToolException(
                f"Invalid format `{output_format}`. Supported formats: 'json', 'csv', 'markdown'."
            )

        if output_format == "json":
            return f"Extracted test cases:\n{data}"

        df = pd.DataFrame(data)

        if output_format == "csv":
            return df.to_csv(index=False)

        if output_format == "markdown":
            return df.to_markdown(index=False)

    def get_available_tools(self):
        return [
            {
                "name": "get_case",
                "ref": self.get_case,
                "description": self.get_case.__doc__,
                "args_schema": getCase,
            },
            {
                "name": "get_cases",
                "ref": self.get_cases,
                "description": self.get_cases.__doc__,
                "args_schema": getCases,
            },
            {
                "name": "get_cases_by_filter",
                "ref": self.get_cases_by_filter,
                "description": self.get_cases_by_filter.__doc__,
                "args_schema": getCasesByFilter,
            },
            {
                "name": "add_case",
                "ref": self.add_case,
                "description": self.add_case.__doc__,
                "args_schema": addCase,
            },
            {
                "name": "update_case",
                "ref": self.update_case,
                "description": self.update_case.__doc__,
                "args_schema": updateCase,
            },
        ]
