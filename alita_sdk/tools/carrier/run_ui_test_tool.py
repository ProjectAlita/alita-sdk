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
                        "When no custom parameters are provided, the tool will show default configuration and ask for confirmation. "
                        "You can override parameters like cpu_quota, memory_quota, cloud_settings, custom_cmd, or loops. "
                        )
    args_schema: Type[BaseModel] = create_model(
        "RunUITestInput",
        test_id=(str, Field(default="", description="Test ID to execute")),
        test_name=(str, Field(default="", description="Test name to execute")),
        cpu_quota=(str, Field(default=None, description="CPU quota for the test runner")),
        memory_quota=(str, Field(default=None, description="Memory quota for the test runner")),
        cloud_settings=(str, Field(default=None, description="Cloud settings name for the test runner")),
        custom_cmd=(str, Field(default=None, description="Custom command to run with the test")),
        loops=(str, Field(default=None, description="Number of loops to run the test")),
        proceed_with_defaults=(bool, Field(default=False, description="Proceed with default configuration. True ONLY when user directly wants to run the test with default parameters." \
        " If cpu_quota, memory_quota, cloud_settings, custom_cmd, or loops are provided, proceed_with_defaults must be False")),
    )
    
    def _run(self, test_id: str = "", test_name: str = "", 
             cpu_quota: str = None, memory_quota: str = None, 
             cloud_settings: str = None, custom_cmd: str = None, loops: str = None,
             proceed_with_defaults: bool = False):
        try:
            # Check if neither test_id nor test_name is provided
            if (not test_id or test_id.strip() == "") and (not test_name or test_name.strip() == ""):
                return self._missing_input_response()
              
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
                
                available_locations = self._get_available_locations()
                
                search_criteria = []
                if test_id:
                    search_criteria.append(f"ID: {test_id}")
                if test_name:
                    search_criteria.append(f"Name: {test_name}")
                
                error_message = []
                error_message.append(f"Test not found for {' or '.join(search_criteria)}.")
                error_message.append("")
                error_message.append("Available UI tests:")
                error_message.extend(available_tests)
                error_message.append("")
                error_message.append("Available runners/locations:")
                error_message.extend(available_locations)
                
                return "\n".join(error_message)
            
            # Check if custom parameters are provided (including cloud_settings)
            has_custom_params = any([cpu_quota is not None, memory_quota is not None, 
                                   cloud_settings is not None, custom_cmd is not None, loops is not None])
            
            if has_custom_params:
                proceed_with_defaults = False  # If any custom params are provided, do not proceed with defaults

            # Get detailed test configuration from API (not from UI tests list)
            test_details = self.api_wrapper.get_ui_test_details(str(ui_test_id))
            
            if not test_details:
                return f"Could not retrieve test details for test ID {ui_test_id}."
            
            # Validate cloud_settings location if provided
            if cloud_settings and not self._validate_cloud_settings_location(cloud_settings):
                available_locations = self._get_available_locations()
                error_message = []
                error_message.append(f"❌ Invalid location/cloud_settings: '{cloud_settings}'")
                error_message.append("")
                error_message.append("Available runners/locations:")
                error_message.extend(available_locations)
                error_message.append("")
                error_message.append("Please choose a valid location name from the list above.")
                return "\n".join(error_message)
            
            # If no custom parameters provided, check if user wants to proceed with defaults
            if not has_custom_params:
                if not proceed_with_defaults:
                    # Show default configuration and ask user if they want to change anything
                    default_message = self._show_default_configuration_message(test_details)
                    if isinstance(default_message, dict) and "message" in default_message:
                        message_str = "\n".join(default_message["message"])
                    else:
                        message_str = str(default_message)
                    return message_str + "\n\nTo proceed with default configuration, type `Run test with default configuration` or specify any parameters you want to override."
                else:
                    # User confirmed to proceed with defaults
                    post_data = self._prepare_post_data_default(test_details)
            else:
                # Prepare POST request data with custom parameters or cloud settings
                post_data = self._prepare_post_data_with_overrides(test_details, cpu_quota, memory_quota, cloud_settings, custom_cmd, loops)
            
            # Execute the UI test
            result_id = self.api_wrapper.run_ui_test(str(ui_test_id), post_data)
            
            # Show location info in success message
            location_used = "default"
            if cloud_settings:
                location_used = cloud_settings
            elif post_data.get("common_params", {}).get("location"):
                location_used = post_data["common_params"]["location"]
            
            return f"✅ UI test started successfully!\n" \
                   f"Result ID: {result_id}\n" \
                   f"Location used: {location_used}\n" \
                   f"Link to report: {self.api_wrapper._client.credentials.url.rstrip('/')}/-/performance/ui/results?result_id={result_id}"
            
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
    
    def _prepare_post_data_default(self, test_details):
        """Prepare POST request data with default parameters."""
        try:
            # Extract values from the test details
            test_parameters = test_details.get("test_parameters", [])
            env_vars = test_details.get("env_vars", {})
            integrations = test_details.get("integrations", {})
            location = test_details.get("location", "")
            parallel_runners = test_details.get("parallel_runners", 1)
            aggregation = test_details.get("aggregation", "max")
            loops = test_details.get("loops", 1)
            
            # Find specific test parameters by name
            def find_param_by_name(params, name):
                for param in params:
                    if param.get("name") == name:
                        return param
                return {}
            
            # Extract S3 integration
            s3_integration = integrations.get("system", {}).get("s3_integration", {})
            
            # Get actual cloud_settings from test details (could be empty {} or have actual settings)
            actual_cloud_settings = env_vars.get("cloud_settings", {})
            
            # Prepare the POST request body with default parameters
            post_data = {
                "common_params": {
                    "name": find_param_by_name(test_parameters, "test_name"),
                    "test_type": find_param_by_name(test_parameters, "test_type"),
                    "env_type": find_param_by_name(test_parameters, "env_type"),
                    "env_vars": {
                        "cpu_quota": env_vars.get("cpu_quota"),
                        "memory_quota": env_vars.get("memory_quota"),
                        "cloud_settings": actual_cloud_settings,  # Use actual cloud settings from test details
                        "ENV": env_vars.get("ENV", "prod"),
                        "custom_cmd": env_vars.get("custom_cmd", "")
                    },
                    "parallel_runners": parallel_runners,
                    "location": location
                },
                "test_parameters": test_parameters,
                "integrations": {
                    "system": {
                        "s3_integration": {
                            "integration_id": s3_integration.get("integration_id"),
                            "is_local": s3_integration.get("is_local")
                        }
                    }
                },
                "loops": loops,
                "aggregation": aggregation
            }
            
            return post_data
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error preparing default POST data: {stacktrace}")
            raise ToolException(stacktrace)

    def _prepare_post_data_with_overrides(self, test_details, cpu_quota=None, 
                                         memory_quota=None, cloud_settings=None, custom_cmd=None, loops=None):
        """Prepare POST request data with overrides or cloud settings."""
        try:
            # Extract values from the test details
            test_parameters = test_details.get("test_parameters", [])
            env_vars = test_details.get("env_vars", {})
            integrations = test_details.get("integrations", {})
            location = test_details.get("location", "")
            parallel_runners = test_details.get("parallel_runners", 1)
            aggregation = test_details.get("aggregation", "max")
            default_loops = test_details.get("loops", 1)
            # Use provided loops parameter or default
            final_loops = loops if loops is not None else default_loops
            
            # Find specific test parameters by name
            def find_param_by_name(params, name):
                for param in params:
                    if param.get("name") == name:
                        return param
                return {}
            
            # Extract S3 integration
            s3_integration = integrations.get("system", {}).get("s3_integration", {})
            
            # Handle cloud_settings parameter and determine the scenario
            final_cloud_settings = {}
            final_location = location
            
            if cloud_settings:
                try:
                    locations_data = self.api_wrapper.get_locations()
                    cloud_regions = locations_data.get("cloud_regions", [])
                    public_regions = locations_data.get("public_regions", [])
                    project_regions = locations_data.get("project_regions", [])
                    
                    # Check if it's a public or project region (scenario 1)
                    if cloud_settings in public_regions or cloud_settings in project_regions:
                        # For public/project regions, use empty cloud_settings and set location
                        final_cloud_settings = {}
                        final_location = cloud_settings
                    else:
                        # Check if it's a cloud region (scenario 2)
                        found_cloud_region = None
                        for region in cloud_regions:
                            if region.get("name", "").lower() == cloud_settings.lower():
                                found_cloud_region = region
                                break
                        
                        # If not exact match, try partial match
                        if not found_cloud_region:
                            for region in cloud_regions:
                                if cloud_settings.lower() in region.get("name", "").lower():
                                    found_cloud_region = region
                                    break
                        
                        if found_cloud_region:
                            # Extract cloud settings details for scenario 2
                            # cloud_name = found_cloud_region.get("name", "")
                            cloud_config = found_cloud_region.get("cloud_settings", {})
                            final_cloud_settings = {
                                "integration_name": cloud_config.get("integration_name"),
                                "id": cloud_config.get("id"),
                                "project_id": cloud_config.get("project_id"),
                                "aws_access_key": cloud_config.get("aws_access_key"),
                                "aws_secret_access_key": cloud_config.get("aws_secret_access_key", {}),
                                "region_name": cloud_config.get("region_name"),
                                "security_groups": cloud_config.get("security_groups"),
                                "image_id": cloud_config.get("image_id"),
                                "key_name": cloud_config.get("key_name", ""),
                                "instance_type": "spot",
                                "ec2_instance_type": "t2.xlarge"
                            }
                            final_location = found_cloud_region.get("name")
                        else:
                            # If no match found, treat as public region fallback
                            final_cloud_settings = {}
                            final_location = cloud_settings
                            
                except Exception as e:
                    logger.error(f"Error processing cloud_settings: {e}")
                    # Use empty cloud_settings as fallback
                    final_cloud_settings = {}
                    final_location = cloud_settings if cloud_settings else location
            else:
                # If no cloud_settings provided, use default from test details
                final_cloud_settings = env_vars.get("cloud_settings", {})

            # Prepare the POST request body with overrides
            post_data = {
                "common_params": {
                    "name": find_param_by_name(test_parameters, "test_name"),
                    "test_type": find_param_by_name(test_parameters, "test_type"),
                    "env_type": find_param_by_name(test_parameters, "env_type"),
                    "env_vars": {
                        "cpu_quota": cpu_quota if cpu_quota is not None else env_vars.get("cpu_quota"),
                        "memory_quota": memory_quota if memory_quota is not None else env_vars.get("memory_quota"),
                        "cloud_settings": final_cloud_settings,
                        "ENV": env_vars.get("ENV", "prod"),
                        "custom_cmd": custom_cmd if custom_cmd is not None else env_vars.get("custom_cmd", "")
                    },
                    "parallel_runners": parallel_runners,
                    "location": final_location
                },
                "test_parameters": test_parameters,
                "integrations": {
                    "system": {
                        "s3_integration": {
                            "integration_id": s3_integration.get("integration_id"),
                            "is_local": s3_integration.get("is_local")
                        }
                    }
                },
                "loops": final_loops,
                "aggregation": aggregation
            }
            
            return post_data
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error preparing POST data with overrides: {stacktrace}")
            raise ToolException(stacktrace)

    def _missing_input_response(self):
        """Response when required input is missing."""
        try:
            available_tests = self._show_ui_tests_list()
            available_locations = self._get_available_locations()
            
            location_info = "Available runners/locations for cloud_settings:\n" + "\n".join(available_locations)
            
            return {
                "message": {
                    "text": (
                        "Please provide test ID or test name of your UI test.\n\n"
                        "Available UI tests:\n" + available_tests + "\n\n"
                        "Available runners/locations for cloud_settings:\n" + location_info
                    ),
                },
                "parameters": {
                    "test_id": None,
                    "test_name": None,
                }
            }
        except Exception:
            return {
                "message": "Please provide test ID or test name of your UI test.",
                "parameters": {
                    "test_id": None,
                    "test_name": None,
                },
                "available_tests": "Error fetching available tests.",
                "available_locations": "Error fetching available locations."
            }
    
    def _show_default_configuration_message(self, test_details):
        """Show information about default configuration and available override parameters."""
        try:
            env_vars = test_details.get("env_vars", {})
            test_name = test_details.get("name", "Unknown")
            loops = test_details.get("loops", 1)
            
            # Get available locations
            available_locations = self._get_available_locations()
            
            message = []
            message.append("Current default parameters:")
            message.append(f"  • CPU Quota: {env_vars.get('cpu_quota', 'Not set')}")
            message.append(f"  • Memory Quota: {env_vars.get('memory_quota', 'Not set')}")
            message.append(f"  • Custom Command: {env_vars.get('custom_cmd', 'Not set')}")
            message.append(f"  • Loops: {loops}")
            message.append(f"  • Cloud Settings: Default location")
            message.append("")
            message.append("Available parameters to override:")
            message.append("  • cpu_quota - Set CPU quota for the test runner")
            message.append("  • memory_quota - Set memory quota for the test runner")
            message.append("  • custom_cmd - Set custom command to run with the test")
            message.append("  • loops - Set number of loops to run the test")
            message.append("  • cloud_settings - Set cloud settings name for the test runner")
            message.append("")
            message.append("Available runners/locations:")
            message.extend(available_locations)
            
            return {"message": message}
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error showing default configuration: {stacktrace}")
            return "Default configuration available for this test."
    
    def _get_available_locations(self):
        """Get formatted list of available locations for user selection."""
        try:
            locations_data = self.api_wrapper.get_locations()
            location_list = []
            
            # Add public regions
            public_regions = locations_data.get("public_regions", [])
            if public_regions:
                location_list.append("  Public Regions:")
                for region in public_regions:
                    location_list.append(f"    - {region}")
            
            # Add project regions
            project_regions = locations_data.get("project_regions", [])
            if project_regions:
                location_list.append("  Project Regions:")
                for region in project_regions:
                    location_list.append(f"    - {region}")
            
            # Add cloud regions
            cloud_regions = locations_data.get("cloud_regions", [])
            if cloud_regions:
                location_list.append("  Cloud Regions:")
                for region in cloud_regions:
                    region_name = region.get("name", "Unknown")
                    cloud_config = region.get("cloud_settings", {})
                    aws_region = cloud_config.get("region_name", "")
                    location_list.append(f"    - {region_name} ({aws_region})")
            
            if not location_list:
                location_list.append("  No locations available")
                
            return location_list
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error getting available locations: {stacktrace}")
            return ["  Error loading locations"]

    def _validate_cloud_settings_location(self, cloud_settings):
        """Validate if the provided cloud_settings location exists and is available."""
        try:
            if not cloud_settings:
                return True  # No cloud_settings provided, use default
                
            locations_data = self.api_wrapper.get_locations()
            
            # Check in public regions
            public_regions = locations_data.get("public_regions", [])
            if cloud_settings in public_regions:
                return True
            
            # Check in project regions
            project_regions = locations_data.get("project_regions", [])
            if cloud_settings in project_regions:
                return True
            
            # Check in cloud regions (by name)
            cloud_regions = locations_data.get("cloud_regions", [])
            for region in cloud_regions:
                region_name = region.get("name", "")
                if region_name.lower() == cloud_settings.lower():
                    return True
                # Also check partial match
                if cloud_settings.lower() in region_name.lower():
                    return True
            
            return False
            
        except Exception:
            stacktrace = traceback.format_exc()
            logger.error(f"Error validating cloud settings location: {stacktrace}")
            return True  # Allow execution if validation fails
