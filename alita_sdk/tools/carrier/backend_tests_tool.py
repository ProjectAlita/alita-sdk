import logging
import json
import traceback
from typing import Type, Optional, List, Dict, Union
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
        test_id=(
        int, Field(default=None, description="Test id to execute. Use test_id if user provide id in int format")),
        name=(
        str, Field(default=None, description="Test name to execute. Use name if user provide name in str format")),
        test_parameters=(list, Field(
            default=None,
            description=(
                "Test parameters to override. Provide as a list of dictionaries, "
                "e.g., [{'vUsers': '5', 'duration': '120'}]. Each dictionary should "
                "contain parameter names and their values."
            )
        )),
        location=(str, Field(
            default=None,
            description=(
                "Location to execute the test. Choose from public_regions, project_regions, "
                "or cloud_regions. For cloud_regions, additional parameters may be required."
            )
        )),
        cloud_settings=(dict, Field(
            default={},
            description=(
                "Additional parameters for cloud_regions. Provide as a dictionary, "
                "e.g., {'region_name': 'us-west-1', 'instance_type': 't2.large'}. "
                "Don't provide this parameter as string! It should be a dictionary!"
                "If no changes are needed, respond with 'use default'."
                "Ensure these settings are passed as a valid dictionary not string"
            )
        )),
    )

    def _run(self, test_id=None, name=None, test_parameters=None, location=None, cloud_settings=None):
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
                    "message": "The test requires confirmation or customization of the following parameters before execution.",
                    "default_test_parameters": default_test_parameters,
                    "instruction": (
                        "If the user has already indicated that default parameters should be used, "
                        "pass 'default_test_parameters' as 'test_parameters' and invoke the '_run' method again without prompting the user.\n"
                        "If the user wants to proceed with default parameters, respond with 'use default'.\n"
                        "In this case, the agent should pass 'default_test_parameters' as 'test_parameters' to the tool.\n"
                        "If the user provides specific overrides, parse them into a list of dictionaries in the following format:\n"
                        "[{'vUsers': '5', 'duration': '120'}].\n"
                        "Each dictionary should contain the parameter name and its desired value.\n"
                        "Ensure that you correctly parse and validate the user's input before invoking the '_run' method."
                    ),
                }

            # Normalize test_parameters if provided in an incorrect format
            test_parameters = self._normalize_test_parameters(test_parameters)

            # Apply user-provided test parameters
            updated_test_parameters = self._apply_test_parameters(default_test_parameters, test_parameters)

            # Fetch available locations
            available_locations = self.api_wrapper.get_available_locations()
            # If location is not provided, prompt the user with available options
            if not location:
                return {
                    "message": "Please select a location to execute the test.",
                    "available_locations": {
                        "public_regions": available_locations["public_regions"],
                        "project_regions": available_locations["project_regions"],
                        "cloud_regions": [region["name"] for region in available_locations["cloud_regions"]],
                    },
                    "instruction": (
                        "For public_regions and project_regions, provide the region name. "
                        "For cloud_regions, provide the region name and optionally override cloud_settings."
                    )
                }

            # Handle cloud_regions with additional parameters
            selected_cloud_region = next(
                (region for region in available_locations["cloud_regions"] if region["name"] == location),
                None
            )

            if selected_cloud_region:
                # Extract available cloud_settings from the selected cloud region
                available_cloud_settings = selected_cloud_region["cloud_settings"]

                # Add default values for instance_type and ec2_instance_type
                available_cloud_settings["instance_type"] = "spot"
                available_cloud_settings["ec2_instance_type"] = "t2.medium"

                # If cloud_settings are not provided, prompt the user with available parameters
                if not cloud_settings:
                    return {
                        "message": f"Please confirm or override the following cloud settings for the selected location: {location}",
                        "available_cloud_settings": available_cloud_settings,
                        "instruction": (
                            "Provide a dictionary to override cloud settings, e.g., "
                            "{'region_name': 'us-west-1', 'instance_type': 't2.large'}. "
                            "Don't provide this parameter as string! It should be a dictionary! "
                            "Ensure these settings are passed to the 'cloud_settings' argument, not 'test_parameters'."
                            "Ensure these settings are passed as a valid dictionary not string"
                        )
                    }

                # Validate and merge user-provided cloud_settings with available parameters
                cloud_settings = self._merge_cloud_settings(available_cloud_settings, cloud_settings)

            # Build common_params dictionary
            common_params = {
                param["name"]: param
                for param in default_test_parameters
                if param["name"] in {"test_name", "test_type", "env_type"}
            }

            # Add env_vars, parallel_runners, and location to common_params
            common_params["env_vars"] = test_data.get("env_vars", {})
            common_params["parallel_runners"] = test_data.get("parallel_runners")
            common_params["location"] = location
            common_params["env_vars"]["cloud_settings"] = cloud_settings or {}

            # Build the JSON body
            json_body = {
                "common_params": common_params,
                "test_parameters": updated_test_parameters,
                "integrations": test_data.get("integrations", {})
            }

            # Execute the test
            report_id = self.api_wrapper.run_test(test_data.get("id"), json_body)
            return f"Test started. Report id: {report_id}. Link to report:" \
                   f"{self.api_wrapper.url.rstrip('/')}/-/performance/backend/results?result_id={report_id}"

        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Test not found: {stacktrace}")
            raise ToolException(stacktrace)

    def _normalize_test_parameters(self, test_parameters):
        """
        Normalize test_parameters to ensure they are in the correct list-of-dictionaries format.
        If test_parameters are provided as a list of strings (e.g., ['vUsers=5', 'duration=120']),
        convert them to a list of dictionaries (e.g., [{'vUsers': '5', 'duration': '120'}]).
        """
        if isinstance(test_parameters, list):
            # Check if the list contains strings in the format "key=value"
            if all(isinstance(param, str) and "=" in param for param in test_parameters):
                normalized_parameters = []
                for param in test_parameters:
                    name, value = param.split("=", 1)
                    normalized_parameters.append({name.strip(): value.strip()})
                return normalized_parameters
            # Check if the list already contains dictionaries
            elif all(isinstance(param, dict) for param in test_parameters):
                return test_parameters
            else:
                raise ValueError(
                    "Invalid format for test_parameters. Provide as a list of 'key=value' strings "
                    "or a list of dictionaries."
                )
        elif isinstance(test_parameters, dict):
            # Convert a single dictionary to a list of dictionaries
            return [test_parameters]
        else:
            raise ValueError(
                "Invalid format for test_parameters. Provide as a list of 'key=value' strings "
                "or a list of dictionaries."
            )

    def _apply_test_parameters(self, default_test_parameters, user_parameters):
        """
        Apply user-provided parameters to the default test parameters.
        """
        updated_parameters = []
        for param in default_test_parameters:
            name = param["name"]
            # Find the matching user parameter
            user_param = next((p for p in user_parameters if name in p), None)
            if user_param:
                # Override the parameter value with the user-provided value
                param["default"] = user_param[name]
            # Ensure the parameter structure remains consistent
            updated_parameters.append({
                "name": param["name"],
                "type": param["type"],
                "description": param["description"],
                "default": param["default"]
            })
        return updated_parameters

    def _merge_cloud_settings(self, available_cloud_settings, user_cloud_settings):
        """
        Merge user-provided cloud settings with available cloud settings.
        Ensure that user-provided values override the defaults.
        """
        if not user_cloud_settings:
            return available_cloud_settings

        # Validate user-provided keys against available keys
        invalid_keys = [key for key in user_cloud_settings if key not in available_cloud_settings]
        if invalid_keys:
            raise ValueError(
                f"Invalid keys in cloud settings: {invalid_keys}. Allowed keys: {list(available_cloud_settings.keys())}")

        # Merge the settings
        merged_settings = {**available_cloud_settings, **user_cloud_settings}
        return merged_settings


class CreateBackendTestInput(BaseModel):
    test_name: str = Field(..., description="Test name")
    test_type: str = Field(..., description="Test type")
    env_type: str = Field(..., description="Env type")
    entrypoint: str = Field(..., description="Entrypoint for the test (JMeter script path or Gatling simulation path)")
    custom_cmd: str = Field(...,
                            description="Custom command line to execute the test (e.g., -l /tmp/reports/jmeter.jtl -e -o /tmp/reports/html_report)")
    runner: str = Field(..., description="Test runner (Gatling or JMeter)")
    source: Optional[Dict[str, Optional[str]]] = Field(
        None,
        description=(
            "Test source configuration (Git repo). The dictionary should include the following keys:\n"
            "- 'name' (required): The type of source (e.g., 'git_https').\n"
            "- 'repo' (required): The URL of the Git repository.\n"
            "- 'branch' (optional): The branch of the repository to use.\n"
            "- 'username' (optional): The username for accessing the repository.\n"
            "- 'password' (optional): The password or token for accessing the repository."
        ),
        example={
            "name": "git_https",
            "repo": "https://your_git_repo.git",
            "branch": "main",
            "username": "your_username",
            "password": "your_password",
        },
    )
    test_parameters: Optional[List[Dict[str, str]]] = Field(
        None,
        description=(
            "Test parameters as a list of dictionaries. Each dictionary should include the following keys:\n"
            "- 'name' (required): The name of the parameter (e.g., 'VUSERS').\n"
            "- 'default' (required): The value of the parameter (e.g., '5')."
        ),
        example=[
            {"name": "VUSERS", "default": "5"},
            {"name": "DURATION", "default": "60"},
            {"name": "RAMP_UP", "default": "30"},
        ],
    )
    email_integration: Optional[Dict[str, Optional[Union[int, List[str]]]]] = Field(
        None,
        description=(
            "Email integration configuration. The dictionary should include the following keys:\n"
            "- 'integration_id' (required): The ID of the selected email integration (integer).\n"
            "- 'recipients' (required): A list of email addresses to receive notifications."
        ),
        example={
            "integration_id": 1,
            "recipients": ["example@example.com", "user@example.com"],
        },
    )


class CreateBackendTestTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_backend_test"
    description: str = "Create a new backend test plan in the Carrier platform."
    args_schema: Type[BaseModel] = CreateBackendTestInput

    def _run(self, test_name=None, test_type=None, env_type=None, entrypoint=None, custom_cmd=None, runner=None,
             source=None, test_parameters=None, email_integration=None):
        try:
            # Validate required fields
            if not test_name:
                return {"message": "Please provide test name"}
            if not test_type:
                return {
                    "message": "Please provide performance test type (capacity, baseline, response time, stable, stress, etc)"}
            if not env_type:
                return {"message": "Please provide test env (stage, prod, dev, etc)"}
            if not entrypoint:
                return {"message": "Please provide test entrypoint (JMeter script path or Gatling simulation path)"}
            if not custom_cmd:
                return {
                    "message": "Please provide custom_cmd. This parameter is optional. (e.g., -l /tmp/reports/jmeter.jtl -e -o /tmp/reports/html_report)"}

            # Validate runner
            available_runners = {
                "JMeter_v5.6.3": "v5.6.3",
                "JMeter_v5.5": "v5.5",
                "Gatling_v3.7": "v3.7",
                "Gatling_maven": "maven",
            }

            if not runner:
                return {
                    "message": (
                        "Please provide a valid test runner. The test runner specifies the tool and version to use for running the test."
                    ),
                    "instructions": (
                        "You can choose a test runner by providing either the key or the value from the available options below. "
                        "For example, you can provide 'JMeter_v5.5' or 'v5.5'."
                    ),
                    "available_runners": available_runners,
                    "example": "For JMeter 5.5, you can provide either 'JMeter_v5.5' or 'v5.5'.",
                }

            # Normalize the runner input to ensure we always use the value in the final data
            if runner in available_runners:
                runner_value = available_runners[runner]  # User provided the key (e.g., 'JMeter_v5.5')
            elif runner in available_runners.values():
                runner_value = runner  # User provided the value directly (e.g., 'v5.5')
            else:
                return {
                    "message": (
                        "Invalid test runner provided. Please choose a valid test runner from the available options."
                    ),
                    "instructions": (
                        "You can choose a test runner by providing either the key or the value from the available options below. "
                        "For example, you can provide 'JMeter_v5.5' or 'v5.5'."
                    ),
                    "available_runners": available_runners,
                    "example": "For JMeter 5.5, you can provide either 'JMeter_v5.5' or 'v5.5'.",
                }

            # Validate source
            if not source:
                return {
                    "message": (
                        "Please provide the test source configuration. The source configuration is required to specify "
                        "the Git repository details for the test. Ensure all fields are provided in the correct format."
                    ),
                    "instructions": (
                        "The 'source' parameter should be a dictionary with the following keys:\n"
                        "- 'name' (required): The type of source (e.g., 'git_https').\n"
                        "- 'repo' (required): The URL of the Git repository.\n"
                        "- 'branch' (optional): The branch of the repository to use.\n"
                        "- 'username' (optional): The username for accessing the repository.\n"
                        "- 'password' (optional): The password or token for accessing the repository."
                    ),
                    "example_source": {
                        "name": "git_https",
                        "repo": "https://your_git_repo.git",
                        "branch": "main",
                        "username": "",
                        "password": "",
                    },
                }

            # Validate test_parameters
            if test_parameters is None:
                return {
                    "message": (
                        "Do you want to add test parameters? Test parameters allow you to configure the test with specific values."
                    ),
                    "instructions": (
                        "Provide test parameters as a list of dictionaries in the format:\n"
                        "- {'name': 'VUSERS', 'default': '5'}\n"
                        "- {'name': 'DURATION', 'default': '60'}\n"
                        "- {'name': 'RAMP_UP', 'default': '30'}\n"
                        "You can provide multiple parameters as a list, e.g., [{'name': 'VUSERS', 'default': '5'}, {'name': 'DURATION', 'default': '60'}].\n"
                        "If no parameters are needed, respond with 'no'."
                    ),
                    "example_parameters": [
                        {"name": "VUSERS", "default": "5"},
                        {"name": "DURATION", "default": "60"},
                        {"name": "RAMP_UP", "default": "30"},
                    ],
                }

            # Ensure test_parameters is an empty list if the user indicates no parameters are needed
            if isinstance(test_parameters, str) and test_parameters.lower() == "no":
                test_parameters = []

            # Fetch available integrations
            integrations_list = self.api_wrapper.get_integrations(name="reporter_email")

            # Validate email_integration
            if email_integration is None:
                # Return instructions for configuring email integration
                return {
                    "message": "Do you want to configure email integration?",
                    "instructions": (
                        "If the user indicates no integrations are needed make sure to pass email_integration"
                        " as empty dict to _run method and invoke it ones again with email_integration={}."
                        "If yes, select an integration from the available options below and provide email recipients.\n"
                        "If no, respond with 'no'. "

                    ),
                    "available_integrations": [
                        {
                            "id": integration["id"],
                            "name": integration["config"]["name"],
                            "description": integration["section"]["integration_description"],
                        }
                        for integration in integrations_list
                    ],
                    "example_response": {
                        "integration_id": 1,
                        "recipients": ["example@example.com", "user@example.com"],
                    },
                }

            # Ensure email_integrations is an empty dict if the user indicates no integrations are needed
            if isinstance(email_integration, str) and email_integration.lower() == "no":
                email_integration = {}
            elif (
                    len(integrations_list) > 0
                    and isinstance(email_integration, dict)
                    and "integration_id" in email_integration
                    and "recipients" in email_integration
            ):
                email_integration = {
                    "reporters": {
                        "reporter_email": {
                            "id": email_integration["integration_id"],
                            "is_local": True,
                            "project_id": integrations_list[0]["project_id"],
                            "recipients": email_integration["recipients"],
                        }
                    }
                }
            else:
                email_integration = {}

            # Prepare the final data dictionary
            data = {
                "common_params": {
                    "name": test_name,
                    "test_type": test_type,
                    "env_type": env_type,
                    "entrypoint": entrypoint,
                    "runner": runner_value,
                    "source": source,
                    "env_vars": {
                        "cpu_quota": 1,
                        "memory_quota": 4,
                        "cloud_settings": {},
                        "custom_cmd": custom_cmd,
                    },
                    "parallel_runners": 1,
                    "cc_env_vars": {},
                    "customization": {},
                    "location": "default",  # TODO update location
                },
                "test_parameters": test_parameters,
                "integrations": email_integration,
                "scheduling": [],
                "run_test": False,
            }

            response = self.api_wrapper.create_test(data)
            try:
                info = "Test created successfully"
                test_info = response.json()
            except:
                info = "Failed to create the test"
                test_info = response.text
            return f"{info}. {test_info}"

        except Exception as e:
            stacktrace = traceback.format_exc()
            logger.error(f"Error while creating test: {stacktrace}")
            raise ToolException(stacktrace)
