import logging
import json
import traceback
from typing import Type
from langchain_core.tools import BaseTool, ToolException
from pydantic.fields import Field
from pydantic import create_model, BaseModel
from .api_wrapper import CarrierAPIWrapper

logger = logging.getLogger(__name__)


class CreateUITestTool(BaseTool):
    api_wrapper: CarrierAPIWrapper = Field(..., description="Carrier API Wrapper instance")
    name: str = "create_ui_test"
    description: str = "Create a new UI test in the Carrier platform."
    args_schema: Type[BaseModel] = create_model(
        "CreateUITestInput",
        **{
            "name": (str, Field(default="", description="Test name")),
            "test_type": (str, Field(default="", description="Test type")),
            "env_type": (str, Field(default="", description="Environment type")),
            "entrypoint": (str, Field(default="", description="Entry point file (e.g., my_test.js)")),
            "runner": (str, Field(default="", description="Test runner type")),
            "repo": (str, Field(default="", description="Git repository URL")),
            "branch": (str, Field(default="", description="Git branch name")),
            "username": (str, Field(default="", description="Git username")),
            "password": (str, Field(default="", description="Git password")),
            "cpu_quota": (int, Field(default=2, description="CPU quota (cores)")),
            "memory_quota": (int, Field(default=5, description="Memory quota (GB)")),
            "custom_cmd": (str, Field(default="", description="Optional custom command")),
            "parallel_runners": (int, Field(default=1, description="Number of parallel runners")),
            "loops": (int, Field(default=1, description="Number of loops")),
            "aggregation": (str, Field(default="max", description="Aggregation method (max, min, avg)")),
        }
    )

    def _run(self, **kwargs):
        try:
            # Check if all required parameters are provided
            required_params = ["name", "test_type", "env_type", "entrypoint", "runner", "repo", "branch", "username", "password"]
            missing_params = []
            
            for param in required_params:
                if not kwargs.get(param) or kwargs.get(param).strip() == "":
                    missing_params.append(param)
            
            if missing_params:
                return self._missing_parameters_response(missing_params)
            
            # Create the UI test
            return self._create_ui_test(kwargs)
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error creating UI test: {stacktrace}")
            raise ToolException(stacktrace)

    def _missing_parameters_response(self, missing_params=None):
        """Response when required parameters are missing."""
        available_runners = [
            "Lighthouse-NPM_V12",
            "Lighthouse-Nodejs", 
            "Lighthouse-NPM",
            "Lighthouse-NPM_V11",
            "Sitespeed (Browsertime)",
            "Sitespeed (New Entrypoint BETA)",
            "Sitespeed (New Version BETA)",
            "Sitespeed V36"
        ]
        
        message = [
            "# 📝 Create UI Test - Required Parameters",
            "",
            "To create a new UI test, please provide the following parameters:",
            "",
            "## 🔴 Required Parameters:",
            "- **name**: Test name (e.g., 'My UI Test')",
            "- **test_type**: Test type (e.g., 'performance')",
            "- **env_type**: Environment type (e.g., 'staging')",
            "- **entrypoint**: Entry point file (e.g., 'my_test.js')",
            "- **runner**: Test runner (see available options below)",
            "- **repo**: Git repository URL (e.g., 'https://github.com/user/repo.git')",
            "- **branch**: Git branch name (e.g., 'main')",
            "- **username**: Git username",
            "- **password**: Git password",
            "",
            "## 🟡 Optional Parameters:",
            "- **cpu_quota**: CPU quota in cores (default: 2)",
            "- **memory_quota**: Memory quota in GB (default: 5)",            "- **custom_cmd**: Optional custom command (e.g., '--login=\"qwerty\"')",
            "- **parallel_runners**: Number of parallel runners (default: 1)",
            "- **loops**: Number of loops (default: 1)",
            "",
            "## 🚀 Available Runners:",
        ]
        
        for runner in available_runners:
            message.append(f"- {runner}")
        
        message.extend([
            "",
            "## 💡 Example:",
            "```",
            "name: 'My Performance Test'",
            "test_type: 'performance'",
            "env_type: 'staging'",
            "entrypoint: 'lighthouse_test.js'",
            "runner: 'Lighthouse-NPM_V12'",
            "repo: 'https://github.com/mycompany/tests.git'",            "branch: 'main'",
            "username: 'myusername'",
            "password: 'mypassword'",
            "```",
            "",
            "**Note:** Aggregation method is automatically set to 'max'."
        ])
        
        if missing_params:
            message.insert(2, f"❌ **Missing parameters:** {', '.join(missing_params)}")
            message.insert(3, "")
        
        return {
            "message": "\n".join(message)
        }

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
                    },
                    "env_vars": {
                        "cpu_quota": params.get("cpu_quota", 2),
                        "memory_quota": params.get("memory_quota", 5),
                        "cloud_settings": {}
                    },
                    "parallel_runners": params.get("parallel_runners", 1),
                    "cc_env_vars": {},
                    "location": "default",
                    "loops": params.get("loops", 1),
                    "aggregation": params.get("aggregation", "max")
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
- **CPU Quota:** {params.get('cpu_quota', 2)} cores
- **Memory Quota:** {params.get('memory_quota', 5)} GB
- **Parallel Runners:** {params.get('parallel_runners', 1)}
- **Loops:** {params.get('loops', 1)}
- **Aggregation:** {params.get('aggregation', 'max')}
{f"- **Custom Command:** `{params['custom_cmd']}`" if params.get('custom_cmd') else ""}

## 🎯 Next Steps:
- Your UI test has been created and is ready to run
- You can execute it using the UI test runner tools
- Configure schedules and integrations as needed"""
            else:
                return "❌ **Failed to create UI test. Please check your parameters and try again.**"
                
        except Exception as e:
            logger.error(f"Error creating UI test: {e}")
            raise ToolException(f"Failed to create UI test: {str(e)}")
