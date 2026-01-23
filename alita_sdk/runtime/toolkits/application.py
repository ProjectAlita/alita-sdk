import logging
from typing import List, Any, Optional

from langgraph.store.base import BaseStore
from pydantic import create_model, BaseModel, Field
from langchain_community.agent_toolkits.base import BaseToolkit
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage
from ..tools.application import Application, applicationToolSchema

logger = logging.getLogger(__name__)


def build_dynamic_application_schema(variables: list, app_name: str = "Application") -> type[BaseModel]:
    """
    Build a dynamic Pydantic schema for an Application tool that includes agent variables.

    This enables swarm-compatible agents where the orchestrator LLM can see and pass
    variables to child agents as tool parameters.

    Args:
        variables: List of variable dicts from version_details['variables'].
                  Each dict should have 'name' and optionally 'value', 'description'.
        app_name: Name of the application (used for schema naming)

    Returns:
        A dynamically created Pydantic model class with task, chat_history, and variable fields.
    """
    # Base fields - always present
    fields = {
        'task': (str, Field(description="Task for Application")),
        'chat_history': (Optional[list[BaseMessage]], Field(
            description="Chat History relevant for Application",
            default=[]
        )),
    }

    # Add agent variables as optional fields with their default values
    if variables:
        for var in variables:
            if not isinstance(var, dict) or not var.get('name'):
                continue

            var_name = var['name']
            var_description = var.get('description') or f"Variable: {var_name}"
            default_value = var.get('value')

            # Variables are optional strings with default values from the agent config
            # If default_value is None or empty string, we use None as default
            if default_value is None or default_value == '':
                fields[var_name] = (Optional[str], Field(
                    description=var_description,
                    default=None
                ))
            else:
                fields[var_name] = (Optional[str], Field(
                    description=var_description,
                    default=default_value
                ))

        logger.info(f"[APP_SCHEMA] Built dynamic schema for '{app_name}' with {len(variables)} variables: "
                   f"{[v.get('name') for v in variables if isinstance(v, dict)]}")

    # Create a unique model name based on the application name
    # Clean the name to be a valid Python identifier
    safe_name = ''.join(c if c.isalnum() else '_' for c in app_name)
    model_name = f"{safe_name}Schema"

    return create_model(model_name, **fields)

class ApplicationToolkit(BaseToolkit):
    tools: List[BaseTool] = []
    
    @staticmethod
    def toolkit_config_schema() -> BaseModel:
        return create_model(
            "application",
            # client = (Any, FieldInfo(description="Client object", required=True, autopopulate=True)),

            application_id = (int, Field(description="Application id")),
            application_version_id = (int, Field(description="Application version id")),
            app_api_key = (Optional[str], Field(description="Application API Key", autopopulate=True, default=None))
        )
    
    @classmethod
    def get_toolkit(cls, client: 'AlitaClient', application_id: int, application_version_id: int,
                    selected_tools: list[str] = [], store: Optional[BaseStore] = None,
                    ignored_mcp_servers: Optional[list] = None, is_subgraph: bool = False,
                    mcp_tokens: Optional[dict] = None, project_id: int = None):
        """
        Get toolkit for an application.

        Args:
            project_id: Optional project ID where the application lives.
                       If not specified, uses the client's default project.
                       This is needed for public project agents added as participants.
        """
        logger.debug(f"[APP_TOOLKIT] get_toolkit called: app_id={application_id}, version_id={application_version_id}, "
                   f"project_id={project_id}, client.project_id={client.project_id}")

        # Check if accessing an application from a different project (public project)
        is_public_project = project_id is not None and project_id != client.project_id

        if is_public_project:
            # Use public application endpoint for cross-project access
            public_data = client.get_public_app_details(application_id)
            app_details = public_data  # Contains name, description, etc.
            version_details = public_data.get('version_details', {})
        else:
            # Use standard endpoints for same-project access
            app_details = client.get_app_details(application_id)
            version_details = client.get_app_version_details(application_id, application_version_id)
        model_settings = {
            "max_tokens": version_details['llm_settings']['max_tokens'],
            "reasoning_effort": version_details['llm_settings'].get('reasoning_effort'),
            "temperature": version_details['llm_settings']['temperature'],
        }

        app = client.application(application_id, application_version_id, store=store,
                                 llm=client.get_llm(version_details['llm_settings']['model_name'],
                                                    model_settings),
                                 ignored_mcp_servers=ignored_mcp_servers,
                                 mcp_tokens=mcp_tokens,
                                 version_details=version_details)  # Pass version_details to avoid re-fetching

        # Extract icon_meta from version_details meta field
        icon_meta = version_details.get('meta', {}).get('icon_meta', {})

        # Build dynamic args_schema that includes agent variables for swarm compatibility
        # This allows orchestrator LLMs to see and pass variables to child agents
        variables = version_details.get('variables', [])
        app_name = app_details.get("name", "Application")
        dynamic_schema = build_dynamic_application_schema(variables, app_name)

        # Extract variable defaults for use in Application._run()
        # This ensures default values are applied when variables are not explicitly passed
        variable_defaults = {}
        for var in variables:
            if isinstance(var, dict) and var.get('name'):
                default_val = var.get('value')
                if default_val is not None and default_val != '':
                    variable_defaults[var['name']] = default_val

        return cls(tools=[Application(name=app_name,
                                      description=app_details.get("description"),
                                      application=app,
                                      args_schema=dynamic_schema,
                                      return_type='str',
                                      client=client,
                                      metadata={'icon_meta': icon_meta} if icon_meta else {},
                                      is_subgraph=is_subgraph,
                                      variable_defaults=variable_defaults,  # Store defaults for _run()
                                      args_runnable={
                                          "application_id": application_id,
                                          "application_version_id": application_version_id,
                                          "store": store,
                                          "llm": client.get_llm(version_details['llm_settings']['model_name'], model_settings),
                                          "ignored_mcp_servers": ignored_mcp_servers,
                                          "is_subgraph": is_subgraph,  # Pass is_subgraph flag
                                          "mcp_tokens": mcp_tokens,
                                          "version_details": version_details,  # Include to avoid re-fetching (critical for public project apps)
                                      })])
            
    def get_tools(self):
        return self.tools
    