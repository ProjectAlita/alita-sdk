import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper
from .carrier_sdk import CarrierAPIError

logger = logging.getLogger(__name__)


class CreateUITestTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_ui_test"
    description: str = "Create a new UI test in the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "CreateUITestInput",
        message=(str, Field(description="User request message for creating UI test")),
        name=(str, Field(description="Test name (e.g., 'My UI Test')")),
        test_type=(str, Field(description="Test type (e.g., 'performance')")),
        env_type=(str, Field(description="Environment type (e.g., 'staging')")),
        entrypoint=(str, Field(description="Entry point file (e.g., 'my_test.js')")),
        runner=(str, Field(description="Test runner type. Available runners: Lighthouse-NPM_V12, Lighthouse-Nodejs, Lighthouse-NPM, Lighthouse-NPM_V11, Sitespeed (Browsertime), Sitespeed (New Entrypoint BETA), Sitespeed (New Version BETA), Sitespeed V36")),
        repo=(str, Field(description="Git repository URL (e.g., 'https://github.com/user/repo.git')")),
        branch=(str, Field(description="Git branch name (e.g., 'main')")),
        username=(str, Field(description="Git username")),
        password=(str, Field(description="Git password")),
        cpu_quota=(int, Field(description="CPU quota in cores (e.g., 2)")),
        memory_quota=(int, Field(description="Memory quota in GB (e.g., 5)")),
        parallel_runners=(int, Field(description="Number of parallel runners (e.g., 1)")),
        loops=(int, Field(description="Number of loops (e.g., 1)")),
        **{"custom_cmd": (str, Field(default="", description="Optional custom command (e.g., '--login=\"qwerty\"')"))}
    )

    def _run(self, **kwargs):
        try:
            # Create the UI test with provided parameters
            return self._create_ui_test(kwargs)
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error creating UI test: {stacktrace}")
            raise ToolException(stacktrace)

    def _parse_validation_error(self, error_message: str) -> str:
        """Parse validation error message and format it for user display."""
        try:
            # Try to extract JSON validation errors from the message
            import re
            json_match = re.search(r'\[.*\]', error_message)
            if json_match:
                json_str = json_match.group(0)
                try:
                    validation_errors = json.loads(json_str)
                    if isinstance(validation_errors, list):
                        formatted_errors = []
                        for error in validation_errors:
                            if isinstance(error, dict):
                                field = error.get("loc", ["unknown"])[0] if error.get("loc") else "unknown"
                                message = error.get("msg", "Invalid value")
                                formatted_errors.append(f"- **{field}**: {message}")
                        
                        if formatted_errors:
                            return "\n".join(formatted_errors)
                except json.JSONDecodeError:
                    pass
            
            # If we can't parse JSON, return the original message
            return error_message
            
        except Exception:
            return error_message

    def _create_ui_test(self, params):
        """Create UI test using the provided parameters."""
        try:
            # Construct the POST body
            post_body = {
                "common_params": {
                    "name": params["name"],
                    "test_type": params["test_type"],
                    "env_type": params["env_type"],
                    "entrypoint": params["entrypoint"],
                    "runner": params["runner"],
                    "source": {
                        "name": "git_https",
                        "repo": params["repo"],
                        "branch": params["branch"],
                        "username": params["username"],
                        "password": params["password"]
                    },                    "env_vars": {
                        "cpu_quota": params["cpu_quota"],
                        "memory_quota": params["memory_quota"],
                        "cloud_settings": {}
                    },
                    "parallel_runners": params["parallel_runners"],
                    "cc_env_vars": {},
                    "location": "default",
                    "loops": params["loops"],
                    "aggregation": "max"
                },
                "test_parameters": [],
                "integrations": {},
                "schedules": [],
                "run_test": False
            }
              # Add custom_cmd if provided
            if params.get("custom_cmd") and params["custom_cmd"].strip():
                post_body["common_params"]["env_vars"]["custom_cmd"] = params["custom_cmd"]
            
            # Make the API call to create the UI test using the API wrapper
            response = self.api_wrapper.create_ui_test(post_body)
            
            if response:
                test_id = response.get("id") if isinstance(response, dict) else "Unknown"
                
                return f"""# ✅ UI Test Created Successfully!

## Test Information:
- **Test ID:** `{test_id}`
- **Name:** `{params['name']}`
- **Type:** `{params['test_type']}`
- **Environment:** `{params['env_type']}`
- **Runner:** `{params['runner']}`
- **Repository:** `{params['repo']}`
- **Branch:** `{params['branch']}`
- **Entry Point:** `{params['entrypoint']}`

## Configuration:
- **CPU Quota:** {params['cpu_quota']} cores
- **Memory Quota:** {params['memory_quota']} GB
- **Parallel Runners:** {params['parallel_runners']}
- **Loops:** {params['loops']}
- **Aggregation:** max
{f"- **Custom Command:** `{params['custom_cmd']}`" if params.get('custom_cmd') else ""}

## 🎯 Next Steps:
- Your UI test has been created and is ready to run
- You can execute it using the UI test runner tools
- Configure schedules and integrations as needed"""
            else:
                return "❌ **Failed to create UI test. Please check your parameters and try again.**"
                
        except CarrierAPIError as api_error:
            # Handle API-specific errors with detailed validation messages
            error_message = str(api_error)
            logger.error(f"CarrierAPIError creating UI test: {error_message}")
              # Try to extract validation details from the error message
            if "400" in error_message:
                parsed_errors = self._parse_validation_error(error_message)
                return f"""# ❌ UI Test Creation Failed - Validation Error

## 🚫 Invalid Input Parameters:
The Carrier platform rejected your request due to validation errors.

## 📋 Validation Errors:
{parsed_errors}

## 💡 Common Issues:
- **Test name**: Only letters, numbers, and "_" are allowed
- **Repository URL**: Must be a valid Git repository URL
- **Runner**: Must be one of the available runner types: Lighthouse-NPM_V12, Lighthouse-Nodejs, Lighthouse-NPM, Lighthouse-NPM_V11, Sitespeed (Browsertime), Sitespeed (New Entrypoint BETA), Sitespeed (New Version BETA), Sitespeed V36
- **Numeric values**: CPU quota, memory quota, parallel runners, and loops must be positive integers

## 🔧 Please fix the validation errors above and try again."""
            else:
                return f"""# ❌ UI Test Creation Failed

## 🚫 API Error:
```
{error_message}
```

## 💡 Please check your parameters and try again."""
                
        except Exception as e:
            logger.error(f"Error creating UI test: {e}")
            raise ToolException(f"Failed to create UI test: {str(e)}")