import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper
from .utils import get_latest_log_file, calculate_thresholds
import os


logger = logging.getLogger(__name__)


class GetReportsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_reports"
    description: str = "Get list of reports from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetReportsInput",
        tag_name=(str, Field(default="", description="Optional parameter. Tag name to filter reports")),
    )

    def _run(self, tag_name=""):
        try:
            reports = self.api_wrapper.get_reports_list()

            # Fields to keep in each report
            base_fields = {
                "id", "build_id", "name", "environment", "type", "vusers", "test_status",
                "start_time", "end_time", "duration"
            }

            trimmed_reports = []
            for report in reports:
                # Filter by tag title
                tags = report.get("tags", [])
                if tag_name and not any(tag.get("title") == tag_name for tag in tags):
                    continue  # Skip reports that don't contain the specified tag

                # Keep only desired base fields
                trimmed = {k: report[k] for k in base_fields if k in report}

                # Simplify tags to list of titles
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
            logger.error(f"Error downloading reports: {stacktrace}")
            raise ToolException(stacktrace)


class GetReportByIDTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_report_by_id"
    description: str = "Get report data from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetReportByIdInput",
        report_id=(str, Field(default="", description="Report id to retrieve")),
    )

    def _run(self, report_id: str):
        try:
            reports = self.api_wrapper.get_reports_list()
            report_data = {}
            for report in reports:
                if report_id == str(report["id"]):
                    report_data = report
                    break

            return json.dumps(report_data)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error downloading reports: {stacktrace}")
            raise ToolException(stacktrace)


class CreateExcelReportTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_excel_report"
    description: str = "Create excel report by report ID from Carrier."
    args_schema: Type[BaseModel] = create_model(
        "CreateExcelReportInput",
        report_id=(str, Field(description="Report ID to retrieve"))
    )

    def _run(self, report_id: str):
        try:
            report, file_path = self.api_wrapper.get_report_file_name(report_id)

            #
            from .excel_reporter import GatlingReportParser, JMeterReportParser, ExcelReporter

            # TODO get think_time, thresholds, pct from parameters
            think_time = "2,0-5,0"
            pct = "95Pct"
            thresholds = []
            carrier_report = f"https://platform.getcarrier.io/-/performance/backend/results?result_id={report_id}"

            lg_type = report.get("lg_type")
            if lg_type == "gatling":
                report_file = get_latest_log_file(file_path, "simulation.log")
                gatling_parser = GatlingReportParser(report_file, think_time)
                result_stats_j = gatling_parser.parse()
                result_stats_j['requests'].update(result_stats_j['groups'])
            elif lg_type == "jmeter":
                report_file = f"{file_path}/jmeter.jtl"
                jmeter_parser = JMeterReportParser(report_file, think_time)
                result_stats_j = jmeter_parser.parse()
            else:
                return "Unsupported type of backend report"


            try:
                calc_thr_j = calculate_thresholds(result_stats_j, pct, thresholds)
            except Exception as e:
                print(e)
                calc_thr_j = []

            excel_report_file_name = f'/tmp/reports_test_results_{report["build_id"]}_excel_report.xlsx'
            excel_reporter_object = ExcelReporter(report_path=excel_report_file_name)
            excel_reporter_object.prepare_headers_and_titles()
            excel_reporter_object.write_to_excel(result_stats_j, carrier_report, calc_thr_j, pct)

            bucket_name = report["name"].replace("_", "").replace(" ", "").lower()

            self.api_wrapper.upload_excel_report(bucket_name, excel_report_file_name)

            # Clean up

            import shutil
            try:
                shutil.rmtree(file_path)
            except Exception as e:
                print(e)
            if os.path.exists(excel_report_file_name):
                os.remove(excel_report_file_name)

            return f"Excel report generated and uploaded to bucket {bucket_name}, report name: {excel_report_file_name.replace('/tmp/', '')}"
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error retrieving report file: {stacktrace}")
            raise ToolException(stacktrace)
