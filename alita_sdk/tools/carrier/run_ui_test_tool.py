import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper


logger = logging.getLogger(__name__)


class RunUITestTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "run_ui_test"
    description: str = "Run and execute UI tests from the Carrier platform. Use this tool when user wants to run, execute, or start a UI test. Provide either test ID or test name, or leave empty to see available tests."
    args_schema: Type[BaseModel] = create_model(
        "RunUITestInput",
        test_id=(str, Field(default="", description="Test ID to execute")),
        test_name=(str, Field(default="", description="Test name to execute")),
    )
    
    def _run(self, test_id: str = "", test_name: str = ""):
        try:
            # Check if neither test_id nor test_name is provided
            if (not test_id or test_id.strip() == "") and (not test_name or test_name.strip() == ""):
                return self._missing_input_response()
            
            # Check if user wants to see the list of tests (can be in test_name field)
            if test_name.lower() in ["show me the list of ui tests", "list ui tests", "show ui tests"]:
                return self._show_ui_tests_list()
              # Get UI tests list only when we need to search for and run a test
            ui_tests = self.api_wrapper.get_ui_tests_list()
            
            # Find the test by ID or name
            test_data = None
            ui_test_id = None
            
            # Try to find by ID first (if test_id is provided and numeric)
            if test_id and test_id.strip() and test_id.isdigit():
                test_id_int = int(test_id)
                for test in ui_tests:
                    if test.get("id") == test_id_int:
                        test_data = test
                        ui_test_id = test_id_int
                        break
            
            # If not found by ID, try to find by name (if test_name is provided)
            if not test_data and test_name and test_name.strip():
                for test in ui_tests:
                    if test.get("name", "").lower() == test_name.lower():
                        test_data = test
                        ui_test_id = test.get("id")
                        break
                        
                # If exact match not found, try partial match
                if not test_data:
                    for test in ui_tests:
                        if test_name.lower() in test.get("name", "").lower():
                            test_data = test
                            ui_test_id = test.get("id")
                            break
            
            # If still not found and test_id was provided but not numeric, try as name
            if not test_data and test_id and test_id.strip() and not test_id.isdigit():
                for test in ui_tests:
                    if test.get("name", "").lower() == test_id.lower():
                        test_data = test
                        ui_test_id = test.get("id")
                        break
                        
                # If exact match not found, try partial match
                if not test_data:
                    for test in ui_tests:
                        if test_id.lower() in test.get("name", "").lower():
                            test_data = test
                            ui_test_id = test.get("id")
                            break
            
            if not test_data:
                available_tests = []
                for test in ui_tests:
                    available_tests.append(f"ID: {test.get('id')}, Name: {test.get('name')}")
                
                search_criteria = []
                if test_id:
                    search_criteria.append(f"ID: {test_id}")
                if test_name:
                    search_criteria.append(f"Name: {test_name}")
                
                return f"Test not found for {' or '.join(search_criteria)}. Available UI tests:\n" + "\n".join(available_tests)
            
            # Get detailed test configuration for the POST request
            test_details = self._get_ui_test_details(ui_test_id)
            
            if not test_details:
                return f"Could not retrieve test details for test ID {ui_test_id}."
            
            # Prepare POST request data based on the reference code
            post_data = self._prepare_post_data(test_details)
            
            # Execute the UI test
            result_id = self.api_wrapper.run_ui_test(str(ui_test_id), post_data)
            
            return f"UI test started successfully. Result ID: {result_id}. " \
                   f"Link to report: {self.api_wrapper.url.rstrip('/')}/-/performance/ui/results?result_id={result_id}"
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error running UI test: {stacktrace}")
            raise ToolException(stacktrace)
    
    def _show_ui_tests_list(self):
        """Show the list of available UI tests."""
        try:
            ui_tests = self.api_wrapper.get_ui_tests_list()
            
            if not ui_tests:
                return "No UI tests found."
            
            test_list = ["Available UI Tests:"]
            for test in ui_tests:
                test_list.append(f"- ID: {test.get('id')}, Name: {test.get('name')}, Runner: {test.get('runner')}")
            
            return "\n".join(test_list)
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error fetching UI tests list: {stacktrace}")
            raise ToolException(stacktrace)
    
    def _get_ui_test_details(self, test_id: int):
        """Get detailed test configuration from the UI tests list."""
        try:
            ui_tests = self.api_wrapper.get_ui_tests_list()
            
            for test in ui_tests:
                if test.get("id") == test_id:
                    return test
            
            return None
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error getting UI test details: {stacktrace}")
            return None
    
    def _prepare_post_data(self, test_data):
        """Prepare POST request data based on the reference code."""
        try:
            # Extract values from the test data
            test_parameters = test_data.get("test_parameters", [])
            env_vars = test_data.get("env_vars", {})
            integrations = test_data.get("integrations", {})
            location = test_data.get("location", "")
            parallel_runners = test_data.get("parallel_runners", 1)
            aggregation = test_data.get("aggregation", "max")
            
            # Extract reporter email for integrations
            reporter_email = integrations.get("reporters", {}).get("reporter_email", {})
            
            # Extract S3 integration
            s3_integration = integrations.get("system", {}).get("s3_integration", {})
            
            # Find specific test parameters by name
            def find_param_by_name(params, name):
                for param in params:
                    if param.get("name") == name:
                        return param
                return {}
            
            # Prepare the POST request body
            post_data = {
                "common_params": {
                    "name": find_param_by_name(test_parameters, "test_name"),
                    "test_type": find_param_by_name(test_parameters, "test_type"),
                    "env_type": find_param_by_name(test_parameters, "env_type"),
                    "env_vars": {
                        "cpu_quota": env_vars.get("cpu_quota"),
                        "memory_quota": env_vars.get("memory_quota"),
                        "cloud_settings": env_vars.get("cloud_settings"),
                        "ENV": "prod",  # Override as per reference code
                        "custom_cmd": env_vars.get("custom_cmd")
                    },
                    "parallel_runners": parallel_runners,
                    "location": location
                },
                "test_parameters": test_parameters,
                "integrations": {
                    "reporters": {
                        "reporter_email": {
                            "id": reporter_email.get("id"),
                            "is_local": reporter_email.get("is_local"),
                            "project_id": reporter_email.get("project_id"),
                            "recipients": reporter_email.get("recipients")
                        }
                    },
                    "system": {
                        "s3_integration": {
                            "integration_id": s3_integration.get("integration_id"),
                            "is_local": s3_integration.get("is_local")
                        }
                    }
                },
                "loops": 1,  # Override the loops value to 1 as per reference code
                "aggregation": aggregation
            }
            
            return post_data
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error preparing POST data: {stacktrace}")
            raise ToolException(stacktrace)
    
    def _missing_input_response(self):
        """Response when required input is missing."""
        try:
            available_tests = self._show_ui_tests_list()
            return {
                "message": "Please provide test ID or test name of your UI test.",
                "parameters": {
                    "test_id": None,
                    "test_name": None,
                },
                "available_tests": available_tests
            }
        except Exception:
            return {
                "message": "Please provide test ID or test name of your UI test.",
                "parameters": {
                    "test_id": None,
                    "test_name": None,
                },
                "available_tests": "Error fetching available tests."
            }
