import logging
import json
import traceback
from typing import Type, Optional, List, Dict
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


class CreateBackendTestInput(BaseModel):
    test_name: str = Field(..., description="Test name")
    test_type: str = Field(..., description="Test type")
    env_type: str = Field(..., description="Env type")
    entrypoint: str = Field(..., description="Entrypoint for the test (JMeter script path or Gatling simulation path)")
    custom_cmd: str = Field(..., description="Custom command line to execute the test (e.g., -l /tmp/reports/jmeter.jtl -e -o /tmp/reports/html_report)")
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
    test_parameters: Optional[List[str]] = Field(
        None,
        description="Test parameters in the format 'name=default_value'. For example: ['VUSERS=5', 'DURATION=60']",
    )


class CreateBackendTestTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_backend_test"
    description: str = "Create a new backend test plan in the Carrier platform."
    args_schema: Type[BaseModel] = CreateBackendTestInput

    def _run(self, test_name=None, test_type=None, env_type=None, entrypoint=None, custom_cmd=None, runner=None,
             source=None, test_parameters=None):
        try:
            # Validate required fields
            if not test_name:
                return {"message": "Please provide test name"}
            if not test_type:
                return {"message": "Please provide performance test type (capacity, baseline, response time, stable, stress, etc)"}
            if not env_type:
                return {"message": "Please provide test env (stage, prod, dev, etc)"}
            if not entrypoint:
                return {"message": "Please provide test entrypoint (JMeter script path or Gatling simulation path)"}
            if not custom_cmd:
                return {"message": "Please provide custom_cmd. This parameter is optional. (e.g., -l /tmp/reports/jmeter.jtl -e -o /tmp/reports/html_report)"}

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

            # Validate required fields in the source dictionary
            required_source_fields = ["name", "repo"]
            missing_fields = [field for field in required_source_fields if field not in source or not source[field]]

            if missing_fields:
                return {
                    "message": (
                        f"The following required fields are missing or empty in the 'source' configuration: {', '.join(missing_fields)}."
                    ),
                    "instructions": (
                        "Ensure the 'source' parameter is a dictionary with the following keys:\n"
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

            # Ensure optional fields are present in the source dictionary
            source = {
                "name": source.get("name"),
                "repo": source.get("repo"),
                "branch": source.get("branch", ""),  # Default to empty string if not provided
                "username": source.get("username", ""),  # Default to empty string if not provided
                "password": source.get("password", ""),  # Default to empty string if not provided
            }

            # Validate test_parameters
            if test_parameters is None:
                return {
                    "message": (
                        "Do you want to add test parameters? Test parameters allow you to configure the test with specific values."
                    ),
                    "instructions": (
                        "Provide test parameters in the format 'name=default_value'. For example:\n"
                        "- VUSERS=5\n"
                        "- DURATION=60\n"
                        "You can provide multiple parameters separated by commas, e.g., 'VUSERS=5, DURATION=60'.\n"
                        "If no parameters are needed, respond with 'no'."
                    ),
                    "example_parameters": [
                        {"name": "VUSERS", "default": "5", "type": "string", "description": "", "action": ""},
                        {"name": "DURATION", "default": "60", "type": "string", "description": "", "action": ""},
                    ],
                }

            # Parse test_parameters
            parsed_test_parameters = []
            if isinstance(test_parameters, list):
                for param in test_parameters:
                    if "=" in param:
                        name, default = param.split("=", 1)
                        parsed_test_parameters.append({
                            "name": name.strip(),
                            "default": default.strip(),
                            "type": "string",
                            "description": "",
                            "action": "",
                        })

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
                "test_parameters": parsed_test_parameters,
                "integrations": {},
                "scheduling": [],
                "run_test": False,
            }

            # Debugging output
            print("*********************************")
            print("Final data:")
            print(data)
            print("*********************************")

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

# data = {"common_params":{"name":"toolkit_demo","test_type":"toolkit_demo","env_type":"toolkit_demo",
#                                      "entrypoint":"tests/BasicEcommerceWithTransaction.jmx","runner":"v5.6.3",
#                                      "source":{"name":"git_https","repo":"https://git.epam.com/epm-perf/boilerplate.git",
#                                                "branch":"jmeter","username":"mykhailo_hunko@epam.com",
#                                                "password":"{{secret.mykhailo_gitlab}}"},
#                                      "env_vars":{"cpu_quota":2,"memory_quota":6,"cloud_settings":{},
#                                                  "custom_cmd":"-l /tmp/reports/jmeter.jtl -e -o /tmp/reports/html_report"},
#                                      "parallel_runners":1,"cc_env_vars":{},"customization":{},"location":"default"},
#                     "test_parameters":[{"name":"VUSERS","default":"5","type":"string","description":"","action":""},
#                                        {"name":"DURATION","default":"60","type":"string","description":"","action":""}],
#                     "integrations":{"reporters":{"reporter_email":{"id":1,"is_local":True,"project_id":36,
#                                                                    "recipients":["mykhailo_hunko@epam.com"]}}},
#                     "scheduling":[],"run_test":True}