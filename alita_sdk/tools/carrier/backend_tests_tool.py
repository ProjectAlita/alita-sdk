import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper


logger = logging.getLogger(__name__)


class GetTestsTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_tests"
    description: str = "Get list of tests from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetTestsInput",
    )

    def _run(self):
        try:
            tests = self.api_wrapper.get_tests_list()

            # Fields to keep in each test
            base_fields = {
                "id", "name", "entrypoint", "runner", "location", "job_type", "source"
            }

            trimmed_tests = []
            for test in tests:

                # Keep only desired base fields
                trimmed = {k: test[k] for k in base_fields if k in test}

                # Simplify test_parameters from test_config
                trimmed["test_parameters"] = [
                    {"name": param["name"], "default": param["default"]}
                    for param in test.get("test_parameters", [])
                ]

                trimmed_tests.append(trimmed)

            return json.dumps(trimmed_tests)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error getting tests: {stacktrace}")
            raise ToolException(stacktrace)


class GetTestByIDTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "get_test_by_id"
    description: str = "Get test data from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "GetTestByIdInput",
        test_id=(str, Field(default="", description="Test id to retrieve")),
    )

    def _run(self, test_id: str):
        try:
            tests = self.api_wrapper.get_tests_list()
            test_data = {}
            for test in tests:
                if test_id == str(test["id"]):
                    test_data = test
                    break

            return json.dumps(test_data)
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Test not found: {stacktrace}")
            raise ToolException(stacktrace)


class RunTestByIDTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "run_test_by_id"
    description: str = "Execute test plan from the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "RunTestByIdInput",
        test_id=(str, Field(default="", description="Test id to execute")),
    )

    def _run(self, test_id: str):
        try:
            tests = self.api_wrapper.get_tests_list()
            test_data = {}
            for test in tests:
                if test_id == str(test["id"]):
                    test_data = test
                    break

            if not test_data:
                raise ValueError(f"Test with id {test_id} not found.")

            # Build common_params dictionary
            common_params = {
                param["name"]: param
                for param in test_data.get("test_parameters", [])
                if param["name"] in {"test_name", "test_type", "env_type"}
            }

            # Add env_vars, parallel_runners, and location to common_params
            common_params["env_vars"] = test_data.get("env_vars", {})
            common_params["parallel_runners"] = test_data.get("parallel_runners")
            common_params["location"] = test_data.get("location")

            json_body = {
                "common_params": common_params,
                "test_parameters": test_data.get("test_parameters", []),
                "integrations": test_data.get("integrations", {})
            }

            report_id = self.api_wrapper.run_test(test_id, json_body)
            return f"Test started. Report id: {report_id}. Link to report:" \
                   f" https://platform.getcarrier.io/-/performance/backend/results?result_id={report_id}"

        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Test not found: {stacktrace}")
            raise ToolException(stacktrace)
