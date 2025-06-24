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
    description: str = ("Run and execute UI tests from the Carrier platform. Use this tool when user wants to run, execute, or start a UI test. "
                        "Provide either test ID or test name, or leave empty to see available tests. "
                        "Optionally provide custom parameters like loops, cpu_quota, memory_quota, cloud_settings, or custom_cmd.")
    args_schema: Type[BaseModel] = create_model(
        "RunUITestInput",
        test_id=(str, Field(default="", description="Test ID to execute")),
        test_name=(str, Field(default="", description="Test name to execute")),
        loops=(int, Field(default=None, description="Number of loops to run the test")),
        cpu_quota=(str, Field(default=None, description="CPU quota for the test runner")),
        memory_quota=(str, Field(default=None, description="Memory quota for the test runner")),
        cloud_settings=(str, Field(default=None, description="Cloud settings name for the test runner")),
        custom_cmd=(str, Field(default=None, description="Custom command to run with the test")),
    )
    
    def _run(self, test_id: str = "", test_name: str = "", loops: int = None, 
             cpu_quota: str = None, memory_quota: str = None, 
             cloud_settings: str = None, custom_cmd: str = None):
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
            
            # Check if custom parameters are provided
            has_custom_params = any([loops is not None, cpu_quota is not None, memory_quota is not None, 
                                   cloud_settings is not None, custom_cmd is not None])
            
            # If no custom parameters provided, show info message with default values and available options
            if not has_custom_params:
                return self._show_test_parameter_info(test_data, ui_test_id)
            
            # Get detailed test configuration for the POST request
            test_details = self._get_ui_test_details(ui_test_id)
            
            if not test_details:
                return f"Could not retrieve test details for test ID {ui_test_id}."
            
            # Prepare POST request data with custom parameters
            post_data = self._prepare_post_data_with_custom_params(test_details, loops, cpu_quota, memory_quota, cloud_settings, custom_cmd)
            
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
      
    def _show_test_parameter_info(self, test_data, test_id):
        """Show information about test parameters that can be changed."""
        try:
            # Get current default values from test data
            env_vars = test_data.get("env_vars", {})
            
            info_message = []
            info_message.append(f"Test '{test_data.get('name')}' (ID: {test_id}) found!")
            info_message.append("\nCurrent default parameters:")
            info_message.append(f"- loops: 1 (default override)")
            info_message.append(f"- cpu_quota: {env_vars.get('cpu_quota', 'Not set')}")
            info_message.append(f"- memory_quota: {env_vars.get('memory_quota', 'Not set')}")
            info_message.append(f"- cloud_settings: {env_vars.get('cloud_settings', 'Not set')}")
            info_message.append(f"- custom_cmd: {env_vars.get('custom_cmd', 'Not set')}")
              # Always try to get and display available cloud settings - this is critical information
            info_message.append("\n" + "="*60)
            info_message.append("🏃 AVAILABLE RUNNERS - CHOOSE ONE FOR cloud_settings:")
            info_message.append("="*60)
            
            try:
                locations_data = self.api_wrapper.get_locations()
                if not locations_data:
                    info_message.append("⚠️  Could not fetch locations data - API returned empty response")
                else:
                    cloud_regions = locations_data.get("cloud_regions", [])
                    public_regions = locations_data.get("public_regions", [])
                    project_regions = locations_data.get("project_regions", [])
                      # Add public regions information (these are the most commonly used)
                    info_message.append("\n🌐 PUBLIC REGIONS (use these names):")
                    if public_regions:
                        for region in public_regions:
                            info_message.append(f"  ✅ '{region}'")
                    else:
                        info_message.append("  ❌ No public regions available")
                    
                    # Add project regions information
                    if project_regions:
                        info_message.append("\n🏢 PROJECT REGIONS (use these names):")
                        for region in project_regions:
                            info_message.append(f"  ✅ '{region}'")
                    
                    # Add cloud regions information
                    if cloud_regions:
                        info_message.append("\n☁️  CLOUD REGIONS (advanced - use full names):")
                        for region in cloud_regions:
                            region_name = region.get("name", "Unknown")
                            info_message.append(f"  ✅ '{region_name}'")
                        
            except Exception as e:
                logger.error(f"Error fetching locations: {e}")
                info_message.append("❌ ERROR: Could not fetch available runners!")
                info_message.append(f"   Reason: {str(e)}")
                info_message.append("   Please check your API connection and try again.")
            
            info_message.append("="*60)            
            info_message.append("\n📋 HOW TO USE:")
            info_message.append("To run this test with custom parameters, specify the values you want to change.")
            info_message.append("\n💡 EXAMPLES:")
            info_message.append("  • Use default runner: cloud_settings='default'")
            info_message.append("  • Change loops: loops=5")
            info_message.append("  • Change resources: cpu_quota='2', memory_quota='4Gi'")
            info_message.append("  • Full example: loops=3, cloud_settings='default', cpu_quota='2'")
            info_message.append("\n📝 RUNNER TYPES:")
            info_message.append("  • Public regions: Use empty cloud_settings {}, location = runner name")
            info_message.append("  • Project regions: Use empty cloud_settings {}, location = runner name") 
            info_message.append("  • Cloud regions: Use full cloud configuration object")
            
            return "\n".join(info_message)
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error showing test parameter info: {stacktrace}")
            raise ToolException(stacktrace)
    
    def _prepare_post_data_with_custom_params(self, test_data, loops=None, cpu_quota=None, 
                                            memory_quota=None, cloud_settings=None, custom_cmd=None):
        """Prepare POST request data with custom parameters."""
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
            # Handle cloud_settings parameter and location
            final_cloud_settings = env_vars.get("cloud_settings")
            final_location = location  # Use original location as default
            
            if cloud_settings:
                try:
                    locations_data = self.api_wrapper.get_locations()
                    cloud_regions = locations_data.get("cloud_regions", [])
                    public_regions = locations_data.get("public_regions", [])
                    project_regions = locations_data.get("project_regions", [])
                    
                    # Check if it's a public region first
                    if cloud_settings in public_regions:
                        # For public regions, use empty cloud_settings and set location to the runner name
                        final_cloud_settings = {}
                        final_location = cloud_settings
                    # Check if it's a project region
                    elif cloud_settings in project_regions:
                        # For project regions, use empty cloud_settings and set location to the runner name
                        final_cloud_settings = {}
                        final_location = cloud_settings
                    else:
                        # Try to find exact match in cloud regions
                        found_match = False
                        for region in cloud_regions:
                            if region.get("name", "").lower() == cloud_settings.lower():
                                # Get the complete cloud_settings object and add the missing fields
                                region_cloud_settings = region.get("cloud_settings", {})
                                # Add the additional fields that are expected in the POST request
                                region_cloud_settings.update({
                                    "instance_type": "on-demand",
                                    "ec2_instance_type": "t2.xlarge", 
                                    "cpu_cores_limit": int(cpu_quota) if cpu_quota else env_vars.get("cpu_quota", 1),
                                    "memory_limit": int(memory_quota) if memory_quota else env_vars.get("memory_quota", 8),
                                    "concurrency": 1
                                })
                                final_cloud_settings = region_cloud_settings
                                final_location = location  # Keep original location for cloud regions
                                found_match = True
                                break
                        
                        # If no exact match in cloud regions, try partial match
                        if not found_match:
                            for region in cloud_regions:
                                if cloud_settings.lower() in region.get("name", "").lower():
                                    region_cloud_settings = region.get("cloud_settings", {})
                                    region_cloud_settings.update({
                                        "instance_type": "on-demand",
                                        "ec2_instance_type": "t2.xlarge",
                                        "cpu_cores_limit": int(cpu_quota) if cpu_quota else env_vars.get("cpu_quota", 1),
                                        "memory_limit": int(memory_quota) if memory_quota else env_vars.get("memory_quota", 8),
                                        "concurrency": 1
                                    })
                                    final_cloud_settings = region_cloud_settings
                                    final_location = location  # Keep original location for cloud regions
                                    found_match = True
                                    break
                        
                        # If still no match found, treat as public region fallback
                        if not found_match:
                            final_cloud_settings = {}
                            final_location = cloud_settings
                            
                except Exception as e:
                    logger.error(f"Error processing cloud_settings: {e}")
                    # Use the provided value as-is if we can't process it
                    final_cloud_settings = cloud_settings
                    final_location = location
            
            # Prepare the POST request body with custom parameters
            post_data = {
                "common_params": {
                    "name": find_param_by_name(test_parameters, "test_name"),
                    "test_type": find_param_by_name(test_parameters, "test_type"),
                    "env_type": find_param_by_name(test_parameters, "env_type"),
                    "env_vars": {
                        "cpu_quota": cpu_quota if cpu_quota is not None else env_vars.get("cpu_quota"),
                        "memory_quota": memory_quota if memory_quota is not None else env_vars.get("memory_quota"),
                        "cloud_settings": final_cloud_settings,
                        "ENV": "prod",  # Override as per reference code
                        "custom_cmd": custom_cmd if custom_cmd is not None else env_vars.get("custom_cmd", "")
                    },                    "parallel_runners": parallel_runners,
                    "location": final_location
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
                "loops": loops if loops is not None else 1,  # Use custom loops or default to 1
                "aggregation": aggregation
            }
            
            return post_data
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error preparing POST data with custom parameters: {stacktrace}")
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
