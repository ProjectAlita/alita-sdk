import logging
from datetime import datetime
import json
import zipfile
from itertools import islice
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper
from .utils import get_latest_log_file, calculate_thresholds
import os
from .excel_reporter import GatlingReportParser, JMeterReportParser, ExcelReporter


logger = logging.getLogger(__name__)


class GetReportsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_reports"
    description: str = "Get list of reports from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetReportsInput",
        name=(str, Field(default="", description="Optional parameter. Report name to filter reports")),
        tag_name=(str, Field(default="", description="Optional parameter. Tag name to filter reports")),
    )

    def _run(self, name="", tag_name=""):
        try:
            reports = self.api_wrapper.get_reports_list()

            # Fields to keep in each report
            base_fields = {
                "id", "build_id", "name", "environment", "type", "vusers", "test_status",
                "start_time", "end_time", "duration"
            }

            trimmed_reports = []
            for report in reports:
                # Filter reports by name
                if name and not name == report["name"]:
                    continue

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
        report_id=(str, Field(description="Report id to retrieve")),
    )

    def _run(self, report_id: str):
        try:
            report, test_log_file_path, errors_log_file_path = self.api_wrapper.get_report_file_name(report_id)
            try:
                with open(errors_log_file_path, mode='r') as f:
                    # Use islice to read up to 100 lines
                    errors = list(islice(f, 100))
                report["errors_log"] = errors
                # Archive with errors log file path
                zip_file_path = f'/tmp/{report["build_id"]}_error_log_archive.zip'

                # Create zip archive
                with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    arcname = os.path.basename(errors_log_file_path)
                    zipf.write(errors_log_file_path, arcname)

                bucket_name = report["name"].replace("_", "").replace(" ", "").lower()
                self.api_wrapper.upload_file(bucket_name, zip_file_path)
                report["link_to_errors_file"] = f"{self.api_wrapper.url.rstrip('/')}/api/v1/artifacts/artifact/default/" \
                                                f"{self.api_wrapper.project_id}/{bucket_name}/" \
                                                f"{zip_file_path.replace('/tmp/', '')}"
            except Exception as e:
                logger.error(e)
                report["errors_log"] = []
                report["link_to_errors_file"] = "link is not available"

            return json.dumps(report)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error downloading reports: {stacktrace}")
            raise ToolException(stacktrace)


class AddTagToReportTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "add_tag_to_report"
    description: str = "Add tag to backend report"
    args_schema: Type[BaseModel] = create_model(
        "AddTagToReportInput",
        report_id=(str, Field(description="Report id to update")),
        tag_name=(str, Field(description="Tag name to add to report")),
    )

    def _run(self, report_id: str, tag_name: str):
        try:
            res = self.api_wrapper.add_tag_to_report(report_id, tag_name)
            if "Tags was updated" in res.text:
                return f"Added tag {tag_name} to report id {report_id}"
            else:
                return f"Failed to add new tag to report id {report_id}"
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
        report_id=(str, Field(default=None, description="Report ID to retrieve")),
        bucket=(str, Field(default=None, description="Bucket with jtl/log file")),
        file_name=(str, Field(default=None, description="File name for .jtl or .log report")),
        **{
            "think_time": (str, Field(default=None, description="Think time parameter")),
            "pct": (str, Field(default=None, description="Percentile parameter")),
            "tp_threshold": (int, Field(default=None, description="Throughput threshold")),
            "rt_threshold": (int, Field(default=None, description="Response time threshold")),
            "er_threshold": (int, Field(default=None, description="Error rate threshold")),
        }
    )

    def _run(self, report_id=None, bucket=None, file_name=None, **kwargs):
        # Validate input
        if not report_id and not all([bucket, file_name]):
            return self._missing_input_response()

        # Default parameters
        default_parameters = self._get_default_parameters()
        if not kwargs:
            return self._request_parameter_confirmation(default_parameters)

        # Merge default parameters with user-provided values
        parameters = {**default_parameters, **kwargs}

        try:
            # Process report based on input type
            if report_id:
                return self._process_report_by_id(report_id, parameters)
            else:
                return self._process_report_by_file(bucket, file_name, parameters)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error retrieving report file: {stacktrace}")
            raise ToolException(stacktrace)

    def _missing_input_response(self):
        """Response when required input is missing."""
        return {
            "message": "Please provide report ID or bucket and .jtl/.log file name.",
            "parameters": {
                "report_id": None,
                "bucket": None,
                "file_name": None,
            },
        }

    def _get_default_parameters(self):
        """Return default parameters."""
        return {
            "think_time": "2,0-5,0",
            "pct": "95Pct",
            "tp_threshold": 10,
            "rt_threshold": 500,
            "er_threshold": 5,
        }

    def _request_parameter_confirmation(self, default_parameters):
        """Ask user to confirm or override default parameters."""
        return {
            "message": "Please confirm or override the following parameters to proceed with the report generation.",
            "parameters": default_parameters,
        }

    def _process_report_by_id(self, report_id, parameters):
        """Process report using report ID."""
        report, test_log_file_path, errors_log_file_path = self.api_wrapper.get_report_file_name(report_id)
        carrier_report = f"{self.api_wrapper.url.rstrip('/')}/-/performance/backend/results?result_id={report_id}"
        lg_type = report.get("lg_type")
        excel_report_file_name = f'/tmp/reports_test_results_{report["build_id"]}_excel_report.xlsx'
        bucket_name = report["name"].replace("_", "").replace(" ", "").lower()

        result_stats_j = self._parse_report(test_log_file_path, lg_type, parameters["think_time"], is_absolute_file_path=True)
        calc_thr_j = self._calculate_thresholds(result_stats_j, parameters)

        return self._generate_and_upload_report(
            result_stats_j, carrier_report, calc_thr_j, parameters, excel_report_file_name, bucket_name, test_log_file_path
        )

    def _process_report_by_file(self, bucket, file_name, parameters):
        """Process report using bucket and file name."""
        file_path = self.api_wrapper.get_report_file_log(bucket, file_name)
        carrier_report = "not specified"
        lg_type = "jmeter" if "jtl" in file_name else "gatling"
        current_date = datetime.now().strftime('%Y-%m-%d')
        excel_report_file_name = f'{file_path}_{current_date}.xlsx'
        bucket_name = bucket

        result_stats_j = self._parse_report(file_path, lg_type, parameters["think_time"], is_absolute_file_path=True)
        calc_thr_j = self._calculate_thresholds(result_stats_j, parameters)

        return self._generate_and_upload_report(
            result_stats_j, carrier_report, calc_thr_j, parameters, excel_report_file_name, bucket_name, file_path
        )

    def _parse_report(self, file_path, lg_type, think_time, is_absolute_file_path=False):
        """Parse the report based on its type."""
        if lg_type == "gatling":
            if is_absolute_file_path:
                report_file = file_path
            else:
                report_file = get_latest_log_file(file_path, "simulation.log")
            parser = GatlingReportParser(report_file, think_time)
            result_stats_j = parser.parse()
            result_stats_j["requests"].update(result_stats_j["groups"])
        elif lg_type == "jmeter":
            if is_absolute_file_path:
                report_file = file_path
            else:
                report_file = f"{file_path}/jmeter.jtl"
            parser = JMeterReportParser(report_file, think_time)
            result_stats_j = parser.parse()
        else:
            raise ToolException("Unsupported type of backend report")
        return result_stats_j

    def _calculate_thresholds(self, result_stats_j, parameters):
        """Calculate thresholds."""
        thresholds = {
            "tp_threshold": parameters["tp_threshold"],
            "rt_threshold": parameters["rt_threshold"],
            "er_threshold": parameters["er_threshold"],
        }
        try:
            return calculate_thresholds(result_stats_j, parameters["pct"], thresholds)
        except Exception as e:
            logger.error(e)
            return []

    def _generate_and_upload_report(self, result_stats_j, carrier_report, calc_thr_j, parameters, excel_report_file_name, bucket_name, file_path):
        """Generate and upload the Excel report."""
        excel_reporter_object = ExcelReporter(report_path=excel_report_file_name)
        excel_reporter_object.prepare_headers_and_titles()
        excel_reporter_object.write_to_excel(result_stats_j, carrier_report, calc_thr_j, parameters["pct"])

        self.api_wrapper.upload_file(bucket_name, excel_report_file_name)

        # Clean up
        self._cleanup(file_path, excel_report_file_name)

        excel_report = excel_report_file_name.replace('/tmp/', '')
        return f"Excel report generated and uploaded to bucket {bucket_name}, " \
               f"report name: {excel_report}, " \
               f"link to download report from Carrier: " \
               f"{self.api_wrapper.url.rstrip('/')}/api/v1/artifacts/artifact/default/{self.api_wrapper.project_id}/{bucket_name}/{excel_report}"

    def _cleanup(self, file_path, excel_report_file_name):
        """Clean up temporary files."""
        import shutil
        try:
            shutil.rmtree(file_path)
        except Exception as e:
            logger.error(e)
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(excel_report_file_name):
            os.remove(excel_report_file_name)
