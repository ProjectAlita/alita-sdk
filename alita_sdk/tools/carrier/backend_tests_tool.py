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
        test_id=(str, Field(description="Test id to retrieve")),
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
        test_id=(str, Field(default=None, description="Test id to execute")),
        name=(str, Field(default=None, description="Test name to execute")),
        test_parameters=(dict, Field(default=None, description="Test parameters to override")),
    )

    def _run(self, test_id=None, name=None, test_parameters=None):
        try:
            if not test_id and not name:
                return {"message": "Please provide test id or test name to start"}

            # Fetch test data
            tests = self.api_wrapper.get_tests_list()

            # Find the test data based on test_id or name
            test_data = next(
                (test for test in tests if
                 (test_id and str(test["id"]) == test_id) or (name and str(test["name"]) == name)),
                None
            )

            if not test_data:
                raise ValueError(f"Test with id {test_id} or name {name} not found.")

            # Default test parameters
            default_test_parameters = test_data.get("test_parameters", [])

            # If no test_parameters are provided, return the default ones for confirmation
            if test_parameters is None:
                return {
                    "message": "Please confirm or override the following test parameters to proceed with the test execution.",
                    "default_test_parameters": default_test_parameters,
                    "instruction": "To override parameters, provide a dictionary of updated values for 'test_parameters'.",
                }

            # Apply user-provided test parameters
            updated_test_parameters = self._apply_test_parameters(default_test_parameters, test_parameters)

            # Build common_params dictionary
            common_params = {
                param["name"]: param
                for param in default_test_parameters
                if param["name"] in {"test_name", "test_type", "env_type"}
            }

            # Add env_vars, parallel_runners, and location to common_params
            common_params["env_vars"] = test_data.get("env_vars", {})
            common_params["parallel_runners"] = test_data.get("parallel_runners")
            common_params["location"] = test_data.get("location")

            # Build the JSON body
            json_body = {
                "common_params": common_params,
                "test_parameters": updated_test_parameters,
                "integrations": test_data.get("integrations", {})
            }

            # Execute the test
            report_id = self.api_wrapper.run_test(test_id, json_body)
            return f"Test started. Report id: {report_id}. Link to report:" \
                   f"{self.api_wrapper.url.rstrip('/')}/-/performance/backend/results?result_id={report_id}"

        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Test not found: {stacktrace}")
            raise ToolException(stacktrace)

    def _apply_test_parameters(self, default_test_parameters, user_parameters):
        """
        Apply user-provided parameters to the default test parameters.
        """
        updated_parameters = []
        for param in default_test_parameters:
            name = param["name"]
            if name in user_parameters:
                # Override the parameter value with the user-provided value
                param["default"] = user_parameters[name]
            updated_parameters.append(param)
        return updated_parameters
