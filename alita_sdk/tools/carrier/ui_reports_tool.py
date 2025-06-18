import logging
import json
import traceback
import datetime
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper

logger = logging.getLogger("carrier_ui_reports_tool")

class GetUIReportsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_ui_reports"
    description: str = "Get list of UI test reports from the Carrier platform. Optionally filter by tag and time range."
    args_schema: Type[BaseModel] = create_model(
        "GetUIReportsInput",
        report_id=(str, Field(description="UI Report id to retrieve")),
        current_date=(str, Field(default=datetime.datetime.now().strftime("%Y-%m-%d"), description="Current date in YYYY-MM-DD format (auto-filled)")),
        **{
            "name": (str, Field(default=None, description="Optional. Filter reports by name (case-insensitive, partial match)")),
            "start_time": (str, Field(default=None, description="Start date/time for filtering reports (YYYY-MM-DD or ISO format)")),
            "end_time": (str, Field(default=None, description="End date/time for filtering reports (YYYY-MM-DD or ISO format)")),
        }
    )

    def _run(self, name=None, start_time=None, end_time=None, **kwargs):
        # Only prompt if all parameters are missing
        if not (name or start_time or end_time):
            return self._missing_input_response()
        # If only name is provided, use the dedicated search_by_name method
        if name and not (start_time or end_time):
            return self.search_by_name(name)
        try:
            reports = self.api_wrapper.get_ui_reports_list()
            base_fields = {
                "id", "name", "environment", "test_type", "browser", "browser_version", "test_status",
                "start_time", "end_time", "duration", "loops", "aggregation", "passed"
            }
            # Parse time filters (if any provided)
            start_dt, end_dt = self._parse_time_filters(start_time, end_time)
            trimmed_reports = []
            for report in reports:
                # Filter by name if provided (with date filters)
                if name and name.lower() not in report.get("name", "").lower():
                    continue
                # Filter by start_time if any time filter is provided
                report_start = report.get("start_time")
                if (start_dt or end_dt) and report_start:
                    try:
                        report_dt = datetime.datetime.fromisoformat(report_start)
                    except Exception:
                        continue
                    if start_dt and report_dt < start_dt:
                        continue
                    if end_dt and report_dt > end_dt:
                        continue
                trimmed = {k: report[k] for k in base_fields if k in report}
                test_config = report.get("test_config", {})
                trimmed["test_parameters"] = [
                    {"name": param["name"], "default": param["default"]}
                    for param in test_config.get("test_parameters", [])
                ]
                if "source" in test_config:
                    trimmed["source"] = test_config["source"]
                trimmed_reports.append(trimmed)
            return json.dumps(trimmed_reports)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error downloading UI reports: {stacktrace}")
            raise ToolException(stacktrace)

    def _missing_input_response(self):
        """Response when required input is missing."""
        return {
            "message": (
                "⚠️ Please provide at least one filter parameter to search UI reports!\n\n"
                "**Available filters:** 🕵️\n"
                "- `name`\n"
                "- `start_time`\n"
                "- `end_time`\n\n"
                "**Example:**\n"
                "- start_time='2025-06-01'\n"
                "- end_time='2025-06-18'\n"
                "- name='My-Test'"
            ),
            "parameters": {
                "name": None,
                "start_time": None,
                "end_time": None,
            },
        }

    def _parse_time_filters(self, start_time, end_time):
        """Parse time filters from input. Only accept formatted YYYY-MM-DD for start_time and end_time."""
        start_dt = end_dt = None
        if start_time:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
            except Exception:
                try:
                    start_dt = datetime.datetime.strptime(start_time, "%Y-%m-%d")
                except Exception:
                    start_dt = None
        if end_time:
            try:
                end_dt = datetime.datetime.fromisoformat(end_time)
            except Exception:
                try:
                    end_dt = datetime.datetime.strptime(end_time, "%Y-%m-%d")
                except Exception:
                    end_dt = None
        return start_dt, end_dt

    def search_by_name(self, name):
        """Return all UI reports that match the given name (case-insensitive, partial match)."""
        try:
            reports = self.api_wrapper.get_ui_reports_list()
            base_fields = {
                "id", "name", "environment", "test_type", "browser", "browser_version", "test_status",
                "start_time", "end_time", "duration", "loops", "aggregation", "passed"
            }
            matched_reports = []
            for report in reports:
                if name and name.lower() in report.get("name", "").lower():
                    trimmed = {k: report[k] for k in base_fields if k in report}
                    test_config = report.get("test_config", {})
                    trimmed["test_parameters"] = [
                        {"name": param["name"], "default": param["default"]}
                        for param in test_config.get("test_parameters", [])
                    ]
                    if "source" in test_config:
                        trimmed["source"] = test_config["source"]
                    matched_reports.append(trimmed)
            return json.dumps(matched_reports)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error searching UI reports by name: {stacktrace}")
            raise ToolException(stacktrace)

class GetUIReportByIDTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_ui_report_by_id"
    description: str = "Get UI report data from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetUIReportByIdInput",
        report_id=(str, Field(description="UI Report id to retrieve")),
    )

    def _run(self, report_id: str):
        try:
            reports = self.api_wrapper.get_ui_reports_list()
            report_data = {}
            for report in reports:
                if report_id == str(report["id"]):
                    report_data = report
                    break

            # Step 1: Get uid from report_data
            uid = report_data.get("uid")
            report_links = []
            if uid:
                # Step 2: Fetch report links using the new API wrapper method
                report_links = self.api_wrapper.get_ui_report_links(uid)
            report_data["report_links"] = report_links

            return json.dumps(report_data)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error downloading UI report: {stacktrace}")
            raise ToolException(stacktrace)
