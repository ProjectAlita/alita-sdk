import json
import logging
from typing import Dict, List, Optional, Union, Any, Generator

import pandas as pd
from langchain_core.tools import ToolException
from openai import BadRequestError
from pydantic import SecretStr, create_model, model_validator
from pydantic.fields import Field, PrivateAttr
from testrail_api import StatusCodeError, TestRailAPI

from ..chunkers.code.constants import get_file_extension
from ..elitea_base import BaseVectorStoreToolApiWrapper, extend_with_vector_tools
from langchain_core.documents import Document

from ...runtime.utils.utils import IndexerKeywords
from ..utils.content_parser import parse_file_content

try:
    from alita_sdk.runtime.langchain.interfaces.llm_processor import get_embeddings
except ImportError:
    from alita_sdk.langchain.interfaces.llm_processor import get_embeddings

logger = logging.getLogger(__name__)

_case_properties_description="""
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
        """

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
    case_properties=(Optional[dict],Field(description=_case_properties_description, default={}),
    ),
)

addCases = create_model(
    "addCases",
    add_test_cases_data=(str, Field(description=("Json string with array of test cases to create in format [{section_id: str, title: str, case_properties: obj}, ...]"
                                           "Where:"
                                           "section_id (required) - Section id"
                                           "title (required) - Title"
                                           "case_properties (optional) - " + _case_properties_description + "default: {}"))
                         )
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


class TestrailAPIWrapper(BaseVectorStoreToolApiWrapper):
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

    def add_cases(self, add_test_cases_data: str):
        """Adds new test cases into Testrail per defined parameters.
                add_test_cases_data: str - JSON string which includes list of objects with following parameters:
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
        test_cases = json.loads(add_test_cases_data)
        return [self.add_case(test_case['section_id'], test_case['title'], test_case['case_properties']) for test_case in test_cases]

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

            # support old versions of testrail_api
            cases = extracted_cases.get("cases") if isinstance(extracted_cases, dict) else extracted_cases

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
            He ID of the test case
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

    def _base_loader(self, project_id: str,
                     suite_id: Optional[str] = None,
                     section_id: Optional[int] = None,
                     title_keyword: Optional[str] = None,
                     **kwargs: Any
                     ) -> Generator[Document, None, None]:
        self._include_attachments = kwargs.get('include_attachments', False)
        self._skip_attachment_extensions = kwargs.get('skip_attachment_extensions', [])

        try:
            if suite_id:
                resp = self._client.cases.get_cases(project_id=project_id, suite_id=int(suite_id))
                cases = resp.get('cases', [])
            else:
                resp = self._client.cases.get_cases(project_id=project_id)
                cases = resp.get('cases', [])
        except StatusCodeError as e:
            raise ToolException(f"Unable to extract test cases: {e}")
            # Apply filters
        if section_id is not None:
            cases = [case for case in cases if case.get('section_id') == section_id]
        if title_keyword is not None:
            cases = [case for case in cases if title_keyword.lower() in case.get('title', '').lower()]

        for case in cases:
            yield Document(page_content=json.dumps(case), metadata={
                'project_id': project_id,
                'title': case.get('title', ''),
                'suite_id': suite_id or case.get('suite_id', ''),
                'id': str(case.get('id', '')),
                IndexerKeywords.UPDATED_ON.value: case.get('updated_on') or -1,
                'labels': [lbl['title'] for lbl in case.get('labels', [])],
                'type': case.get('type_id') or -1,
                'priority': case.get('priority_id') or -1,
                'milestone': case.get('milestone_id') or -1,
                'estimate': case.get('estimate') or '',
                'automation_type': case.get('custom_automation_type') or -1,
                'section_id': case.get('section_id') or -1,
                'entity_type': 'test_case',
            })

    def _process_document(self, document: Document) -> Generator[Document, None, None]:
        """
        Process an existing base document to extract relevant metadata for full document preparation.
        Used for late processing of documents after we ensure that the document has to be indexed to avoid
        time-consuming operations for documents which might be useless.

        Args:
            document (Document): The base document to process.

        Returns:
            Generator[Document, None, None]: A generator yielding processed Document objects with metadata.
        """
        try:
            if not self._include_attachments:
                # If attachments are not included, return the document as is
                yield document
                return

            # get base data from the document required to extract attachments and other metadata
            base_data = json.loads(document.page_content)
            case_id = base_data.get("id")

            # get a list of attachments for the case
            attachments = self._client.attachments.get_attachments_for_case_bulk(case_id=case_id)

            # process each attachment to extract its content
            for attachment in attachments:
                if get_file_extension(attachment['filename']) in self._skip_attachment_extensions:
                    logger.info(f"Skipping attachment {attachment['filename']} with unsupported extension.")
                    continue

                attachment_id = f"attach_{attachment['id']}"
                # add attachment id to metadata of parent
                document.metadata.setdefault(IndexerKeywords.DEPENDENT_DOCS.value, []).append(attachment_id)
                # TODO: pass it to chunkers
                yield Document(page_content=self._process_attachment(attachment),
                                                     metadata={
                                                         'project_id': base_data.get('project_id', ''),
                                                         'id': str(attachment_id),
                                                         IndexerKeywords.PARENT.value: str(case_id),
                                                         'filename': attachment['filename'],
                                                         'filetype': attachment['filetype'],
                                                         'created_on': attachment['created_on'],
                                                         'entity_type': 'test_case_attachment',
                                                         'is_image': attachment['is_image'],
                                                     })
        except json.JSONDecodeError as e:
            raise ToolException(f"Failed to decode JSON from document: {e}")

    def _process_attachment(self, attachment: Dict[str, Any]) -> str:
        """
        Processes an attachment to extract its content.

        Args:
            attachment (Dict[str, Any]): The attachment data.

        Returns:
            str: string description of the attachment.
        """

        page_content = "This filetype is not supported."
        if attachment['filetype'] == 'txt' :
            page_content =  self._client.get(endpoint=f"get_attachment/{attachment['id']}")
        else:
            try:
                attachment_path = self._client.attachments.get_attachment(attachment_id=attachment['id'], path=f"./{attachment['filename']}")
                page_content = parse_file_content(file_name=attachment['filename'], file_content=attachment_path.read_bytes(), llm=self.llm, is_capture_image=True)
            except BadRequestError as ai_e:
                logger.error(f"Unable to parse page's content with type: {attachment['filetype']} due to AI service issues: {ai_e}")
            except Exception as e:
                logger.error(f"Unable to parse page's content with type: {attachment['filetype']}: {e}")
        return page_content

    def _index_tool_params(self):
        return {
            'project_id': (str, Field(description="TestRail project ID to index data from")),
            'suite_id': (Optional[str],
                         Field(default=None, description="Optional TestRail suite ID to filter test cases")),
            'section_id': (Optional[int], Field(default=None, description="Optional section ID to filter test cases")),
            'include_attachments': (Optional[bool],
                                    Field(description="Whether to include attachment content in indexing",
                                          default=False)),
            'skip_attachment_extensions': (Optional[List[str]], Field(
                description="List of file extensions to skip when processing attachments: i.e. ['.png', '.jpg']",
                default=[])),
        }

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

    @extend_with_vector_tools
    def get_available_tools(self):
        tools = [
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
                "name": "add_cases",
                "ref": self.add_cases,
                "description": self.add_cases.__doc__,
                "args_schema": addCases,
            },
            {
                "name": "update_case",
                "ref": self.update_case,
                "description": self.update_case.__doc__,
                "args_schema": updateCase,
            }
        ]
        return tools
