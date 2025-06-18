import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper

logger = logging.getLogger("carrier_ui_reports_tool")

class GetUIReportsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_ui_reports"
    description: str = "Get list of UI test reports from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetUIReportsInput",
        tag_name=(str, Field(default="", description="Optional parameter. Tag name to filter UI reports")),
    )

    def _run(self, tag_name=""):
        try:
            reports = self.api_wrapper.get_ui_reports_list()

            # Fields to keep in each report
            base_fields = {
                "id", "name", "environment", "test_type", "browser", "browser_version", "test_status",
                "start_time", "end_time", "duration", "loops", "aggregation", "passed"
            }
            trimmed_reports = []
            for report in reports:
                # Filter by tag title if present
                tags = report.get("tags", [])
                if tag_name and not any(tag.get("title") == tag_name for tag in tags):
                    continue

                trimmed = {k: report[k] for k in base_fields if k in report}
                trimmed["tags"] = [tag["title"] for tag in tags]

                # Simplify test_parameters from test_config
                test_config = report.get("test_config", {})
                trimmed["test_parameters"] = [
                    {"name": param["name"], "default": param["default"]}
                    for param in test_config.get("test_parameters", [])
                ]

                # Extract source from test_config
                if "source" in test_config:
                    trimmed["source"] = test_config["source"]

                trimmed_reports.append(trimmed)

            return json.dumps(trimmed_reports)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error downloading UI reports: {stacktrace}")
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
