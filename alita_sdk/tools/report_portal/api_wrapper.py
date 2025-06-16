import logging
from typing import Any, Optional

import pymupdf
from pydantic import BaseModel, Field, PrivateAttr, create_model, model_validator, SecretStr

from .report_portal_client import RPClient
from ..elitea_base import BaseToolApiWrapper

logger = logging.getLogger(__name__)

PageNumberField = (Optional[int], Field(default=1,
                                        description="Number of page to retrieve. Pass if page.totalPages > 1."))
PaginatedResults = create_model(
    "PaginatedResultsModel",
    page_number=PageNumberField,
)
GetExtendedLaunchData = create_model(
    "GetExtendedLaunchData",
    launch_id=(str, Field(description="Launch ID of the launch to export."))
)
GetExtendedLaunchDataAsRaw = create_model(
    "GetExtendedLaunchDataAsRaw",
    launch_id=(str, Field(description="Launch ID of the launch to export.")),
    format=(Optional[str], Field(default="html",
                                 description="format of the exported data. may be one of 'pdf' or 'html'"))
)
GetLaunchDetails = create_model(
    "GetLaunchDetailsModel",
    launch_id=(str, Field(description="Launch ID of the launch to get details for.")),
)
FindTestItemById = create_model(
    "FindTestItemByIdModel",
    item_id=(str, Field(description="Item ID of the item to get details for.")),
)
GetTestItemsForLaunch = create_model(
    "GetTestItemsForLaunchModel",
    launch_id=(str, Field(description="Launch ID of the launch to get test items for.")),
    page_number=PageNumberField,
)
GetLogsForTestItem = create_model(
    "GetLogsForTestItemModel",
    item_id=(str, Field(description="Item ID of the item to get logs for.")),
    page_number=PageNumberField,
)
GetUserInformation = create_model(
    "GetUserInformationModel",
    username=(str, Field(description="Username of the user to get information for.")),
)
GetDashboardData = create_model(
    "GetDashboardDataModel",
    dashboard_id=(str, Field(description="Dashboard ID of the dashboard to get data for.")),
)


class ReportPortalApiWrapper(BaseToolApiWrapper):
    endpoint: str
    api_key: SecretStr
    project: str
    _client: Optional[RPClient] = PrivateAttr()

    @model_validator(mode='before')
    @classmethod
    def validate_toolkit(cls, values):
        endpoint = values.get('endpoint')
        api_key = values.get('api_key')
        project = values.get('project')
        cls._client = RPClient(endpoint=endpoint, api_key=api_key, project=project)
        return values

    def get_extended_launch_data_as_raw(self, launch_id: str, format: str = 'html') -> str | None:
        """
        Get Launch details as a raw
        """
        response = self._client.export_specified_launch(launch_id, format)
        if not response.headers['Content-Disposition']:
            logger.warning(f"Exported data for launch {launch_id} is empty.")
            return None
        return response.content

    def get_extended_launch_data(self, launch_id: str) -> str | None:
        """
        Use the exported data from a specific launch to generate a comprehensive test report for management.
        The AI can analyze the results, highlight key metrics, and provide insights into test coverage,
        defect density, and test execution trends.
        Returns content of the report.
        """
        format: str = 'html'
        response = self._client.export_specified_launch(launch_id, format)

        if not response.headers['Content-Disposition']:
            logger.warning(f"Exported data for launch {launch_id} is empty.")
            return None

        if response.headers['Content-Type'] in ['application/pdf', 'text/html']:
            with pymupdf.open(stream=response.content, filetype=format) as report:
                text_content = ''
                for page_num in range(len(report)):
                    page = report[page_num]
                    text_content += page.get_text()

                return text_content
        else:
            logger.warning(f"Exported data for launch {launch_id} is in an unsupported format.")
            return None

    def get_launch_details(self, launch_id: str) -> dict:
        """
        Retrieve detailed information about a launch to perform a root cause analysis of failures.
        By analyzing the launch details, the AI can identify patterns in test failures and suggest areas
        of the application that may require additional attention or testing.
        """
        return self._client.get_launch_details(launch_id)

    def get_all_launches(self, page_number: int = 1) -> dict:
        """
        Analyze the data from all launches to track the progress of testing activities over time.
        It can generate visualizations and trend analyzes to help teams understand testing velocity,
        stability, and the impact of new code changes on the overall quality.
        if page.totalPages > 1, you can use page_number to get the next page.
        """
        return self._client.get_all_launches(page_number)

    def find_test_item_by_id(self, item_id: str) -> dict:
        """
        Fetch specific test items to perform detailed analysis on individual test cases. It can evaluate
        the historical performance of the test, identify flaky tests, and suggest improvements
        or optimizations to the test suite.
        """
        return self._client.find_test_item_by_id(item_id)

    def get_test_items_for_launch(self, launch_id: str, page_number: int = 1) -> dict:
        """
        Compile all test items from a launch to create a test execution summary.
        It can categorize tests by outcome, identify areas with high failure rates,
        and provide recommendations for test prioritization in future test cycles.
        if page.totalPages > 1, you can use page_number to get the next page.
        """
        return self._client.get_test_items_for_launch(launch_id, page_number)

    def get_logs_for_test_items(self, item_id: str, page_number: int = 1) -> dict:
        """
        Process the logs for test items to assist in automated debugging.
        By applying natural language processing, the AI can extract meaningful information from logs,
        correlate errors with source code changes, and assist developers in pinpointing issues.
        if page.totalPages > 1, you can use page_number to get the next page.
        """
        return self._client.get_logs_for_test_items(item_id, page_number)

    def get_user_information(self, username: str) -> dict:
        """
        Use user information to personalize dashboards and reports. It can also analyze user activity to optimize
        test assignment and load balancing among QA team members based on their expertise and past performance.
        """
        return self._client.get_user_information(username)

    def get_dashboard_data(self, dashboard_id: str) -> dict:
        """
        Analyze dashboard data to create executive summaries that highlight key performance indicators (KPIs),
        overall project health, and areas requiring immediate attention.
        It can also provide predictive analytics for future test planning.
        """
        return self._client.get_dashboard_data(dashboard_id)

    def get_available_tools(self):
        return [
            {
                "name": "get_extended_launch_data_as_raw",
                "description": self.get_extended_launch_data_as_raw.__doc__,
                "args_schema": GetExtendedLaunchDataAsRaw,
                "ref": self.get_extended_launch_data_as_raw,
            },
            {
                "name": "get_extended_launch_data",
                "description": self.get_extended_launch_data.__doc__,
                "args_schema": GetExtendedLaunchData,
                "ref": self.get_extended_launch_data,
            },
            {
                "name": "get_launch_details",
                "description": self.get_launch_details.__doc__,
                "args_schema": GetLaunchDetails,
                "ref": self.get_launch_details,
            },
            {
                "name": "get_all_launches",
                "description": self.get_all_launches.__doc__,
                "args_schema": PaginatedResults,
                "ref": self.get_all_launches,
            },
            {
                "name": "find_test_item_by_id",
                "description": self.find_test_item_by_id.__doc__,
                "args_schema": FindTestItemById,
                "ref": self.find_test_item_by_id,
            },
            {
                "name": "get_test_items_for_launch",
                "description": self.get_test_items_for_launch.__doc__,
                "args_schema": GetTestItemsForLaunch,
                "ref": self.get_test_items_for_launch,
            },
            {
                "name": "get_logs_for_test_items",
                "description": self.get_logs_for_test_items.__doc__,
                "args_schema": GetLogsForTestItem,
                "ref": self.get_logs_for_test_items,
            },
            {
                "name": "get_user_information",
                "description": self.get_user_information.__doc__,
                "args_schema": GetUserInformation,
                "ref": self.get_user_information,
            },
            {
                "name": "get_dashboard_data",
                "description": self.get_dashboard_data.__doc__,
                "args_schema": GetDashboardData,
                "ref": self.get_dashboard_data,
            }
        ]