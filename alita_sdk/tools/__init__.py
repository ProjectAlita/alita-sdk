import logging
from copy import deepcopy
from importlib import import_module
from typing import Optional

from langchain_core.tools import ToolException
from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)

# Available tools and toolkits - populated by safe imports
AVAILABLE_TOOLS = {}
AVAILABLE_TOOLKITS = {}
FAILED_IMPORTS = {}


def _inject_toolkit_id(tool_conf: dict, toolkit_tools) -> None:
    """Inject `toolkit_id` into tools that expose `api_wrapper.toolkit_id`.

    This reads 'id' from the tool configuration and, if it is an integer,
    assigns it to the 'toolkit_id' attribute of the 'api_wrapper' for each
    tool in 'toolkit_tools' that supports it.

    Args:
        tool_conf: Raw tool configuration item from 'tools_list'.
        toolkit_tools: List of instantiated tools produced by a toolkit.
    """
    toolkit_id = tool_conf.get('id')
    if isinstance(toolkit_id, int):
        for t in toolkit_tools:
            if hasattr(t, 'api_wrapper') and hasattr(t.api_wrapper, 'toolkit_id'):
                t.api_wrapper.toolkit_id = toolkit_id
    else:
        logger.error(
            f"Toolkit ID is missing or not an integer for tool "
            f"`{tool_conf.get('type', '')}` with name `{tool_conf.get('name', '')}`"
        )


def _safe_import_tool(tool_name, module_path, get_tools_name=None, toolkit_class_name=None):
    """Safely import a tool module and register available functions/classes."""
    try:
        module = __import__(f'alita_sdk.tools.{module_path}', fromlist=[''])

        imported = {}
        if get_tools_name and hasattr(module, get_tools_name):
            imported['get_tools'] = getattr(module, get_tools_name)
        
        if hasattr(module, 'get_toolkit'):
            imported['get_toolkit'] = getattr(module, 'get_toolkit')

        if hasattr(module, 'get_toolkit_available_tools'):
            imported['get_toolkit_available_tools'] = getattr(module, 'get_toolkit_available_tools')

        if toolkit_class_name and hasattr(module, toolkit_class_name):
            imported['toolkit_class'] = getattr(module, toolkit_class_name)
            AVAILABLE_TOOLKITS[toolkit_class_name] = getattr(module, toolkit_class_name)

        if imported:
            AVAILABLE_TOOLS[tool_name] = imported
            logger.debug(f"Successfully imported {tool_name}")

    except Exception as e:
        FAILED_IMPORTS[tool_name] = str(e)
        logger.debug(f"Failed to import {tool_name}: {e}")


# Safe imports for all tools
_safe_import_tool('github', 'github', 'get_tools', 'AlitaGitHubToolkit')
_safe_import_tool('openapi', 'openapi', 'get_tools', 'AlitaOpenAPIToolkit')
_safe_import_tool('jira', 'jira', 'get_tools', 'JiraToolkit')
_safe_import_tool('confluence', 'confluence', 'get_tools', 'ConfluenceToolkit')
_safe_import_tool('service_now', 'servicenow', 'get_tools', 'ServiceNowToolkit')
_safe_import_tool('gitlab', 'gitlab', 'get_tools', 'AlitaGitlabToolkit')
_safe_import_tool('gitlab_org', 'gitlab_org', 'get_tools', 'AlitaGitlabSpaceToolkit')
_safe_import_tool('zephyr', 'zephyr', 'get_tools', 'ZephyrToolkit')
_safe_import_tool('browser', 'browser', 'get_tools', 'BrowserToolkit')
_safe_import_tool('report_portal', 'report_portal', 'get_tools', 'ReportPortalToolkit')
_safe_import_tool('bitbucket', 'bitbucket', 'get_tools', 'AlitaBitbucketToolkit')
_safe_import_tool('testrail', 'testrail', 'get_tools', 'TestrailToolkit')
_safe_import_tool('testio', 'testio', 'get_tools', 'TestIOToolkit')
_safe_import_tool('xray_cloud', 'xray', 'get_tools', 'XrayToolkit')
_safe_import_tool('sharepoint', 'sharepoint', 'get_tools', 'SharepointToolkit')
_safe_import_tool('qtest', 'qtest', 'get_tools', 'QtestToolkit')
_safe_import_tool('zephyr_scale', 'zephyr_scale', 'get_tools', 'ZephyrScaleToolkit')
_safe_import_tool('zephyr_enterprise', 'zephyr_enterprise', 'get_tools', 'ZephyrEnterpriseToolkit')
_safe_import_tool('ado', 'ado', 'get_tools')
_safe_import_tool('ado_repos', 'ado.repos', 'get_tools', 'AzureDevOpsReposToolkit')
_safe_import_tool('ado_plans', 'ado.test_plan', None, 'AzureDevOpsPlansToolkit')
_safe_import_tool('ado_boards', 'ado.work_item', None, 'AzureDevOpsWorkItemsToolkit')
_safe_import_tool('ado_wiki', 'ado.wiki', None, 'AzureDevOpsWikiToolkit')
_safe_import_tool('rally', 'rally', 'get_tools', 'RallyToolkit')
_safe_import_tool('sql', 'sql', 'get_tools', 'SQLToolkit')
_safe_import_tool('sonar', 'code.sonar', 'get_tools', 'SonarToolkit')
_safe_import_tool('google_places', 'google_places', 'get_tools', 'GooglePlacesToolkit')
_safe_import_tool('yagmail', 'yagmail', 'get_tools', 'AlitaYagmailToolkit')
_safe_import_tool('aws', 'cloud.aws', None, 'AWSToolkit')
_safe_import_tool('azure', 'cloud.azure', None, 'AzureToolkit')
_safe_import_tool('gcp', 'cloud.gcp', None, 'GCPToolkit')
_safe_import_tool('k8s', 'cloud.k8s', None, 'KubernetesToolkit')
# _safe_import_tool('custom_open_api', 'custom_open_api', None, 'OpenApiToolkit')
_safe_import_tool('elastic', 'elastic', None, 'ElasticToolkit')
_safe_import_tool('keycloak', 'keycloak', None, 'KeycloakToolkit')
_safe_import_tool('localgit', 'localgit', None, 'AlitaLocalGitToolkit')
# pandas toolkit removed - use Data Analysis internal tool instead
_safe_import_tool('azure_search', 'azure_ai.search', 'get_tools', 'AzureSearchToolkit')
_safe_import_tool('figma', 'figma', 'get_tools', 'FigmaToolkit')
_safe_import_tool('salesforce', 'salesforce', 'get_tools', 'SalesforceToolkit')
_safe_import_tool('carrier', 'carrier', 'get_tools', 'AlitaCarrierToolkit')
_safe_import_tool('ocr', 'ocr', 'get_tools', 'OCRToolkit')
_safe_import_tool('pptx', 'pptx', 'get_tools', 'PPTXToolkit')
_safe_import_tool('postman', 'postman', 'get_tools', 'PostmanToolkit')
_safe_import_tool('zephyr_squad', 'zephyr_squad', 'get_tools', 'ZephyrSquadToolkit')
_safe_import_tool('zephyr_essential', 'zephyr_essential', 'get_tools', 'ZephyrEssentialToolkit')
_safe_import_tool('slack', 'slack', 'get_tools', 'SlackToolkit')
_safe_import_tool('bigquery', 'google.bigquery', 'get_tools', 'BigQueryToolkit')
_safe_import_tool('delta_lake', 'aws.delta_lake', 'get_tools', 'DeltaLakeToolkit')

# Log import summary
available_count = len(AVAILABLE_TOOLS)
total_attempted = len(AVAILABLE_TOOLS) + len(FAILED_IMPORTS)
logger.info(f"Tool imports completed: {available_count}/{total_attempted} successful")

# Import community module to trigger community toolkit registration
try:
    from alita_sdk import community  # noqa: F401
    logger.debug("Community toolkits registered successfully")
except ImportError as e:
    logger.debug(f"Community module not available: {e}")


def get_tools(tools_list, alita, llm, store: Optional[BaseStore] = None, *args, **kwargs):
    tools = []

    for tool in tools_list:
        toolkit_tools = []
        settings = tool.get('settings')

        # Skip tools without settings early
        if not settings:
            logger.warning(f"Tool '{tool.get('type', '')}' has no settings, skipping...")
            continue

        # Validate tool names once
        selected_tools = settings.get('selected_tools', [])
        invalid_tools = [name for name in selected_tools if isinstance(name, str) and name.startswith('_')]
        if invalid_tools:
            raise ValueError(f"Tool names {invalid_tools} from toolkit '{tool.get('type', '')}' cannot start with '_'")

        # Cache tool type and add common settings
        tool_type = tool['type']
        settings['alita'] = alita
        settings['llm'] = llm
        settings['store'] = store

        # Set pgvector collection schema if present
        if settings.get('pgvector_configuration'):
            # Use tool id if available, otherwise use toolkit_name or type as fallback
            collection_id = tool.get('id') or tool.get('toolkit_name') or tool_type
            settings['pgvector_configuration']['collection_schema'] = str(collection_id)

        # Handle ADO special cases
        if tool_type in ['ado_boards', 'ado_wiki', 'ado_plans']:
            toolkit_tools.extend(AVAILABLE_TOOLS['ado']['get_tools'](tool_type, tool))
        elif tool_type in ['ado_repos', 'azure_devops_repos'] and 'ado_repos' in AVAILABLE_TOOLS:
            try:
                toolkit_tools.extend(AVAILABLE_TOOLS['ado_repos']['get_tools'](tool))
            except Exception as e:
                logger.error(f"Error getting ADO repos tools: {e}")
        elif tool_type == 'mcp':
            logger.debug(f"Skipping MCP toolkit '{tool.get('toolkit_name')}' - handled by runtime toolkit system")
        elif tool_type == 'planning':
            logger.debug(f"Skipping planning toolkit '{tool.get('toolkit_name')}' - handled by runtime toolkit system")
        elif tool_type in AVAILABLE_TOOLS and 'get_tools' in AVAILABLE_TOOLS[tool_type]:
            try:
                toolkit_tools.extend(AVAILABLE_TOOLS[tool_type]['get_tools'](tool))
            except Exception as e:
                logger.error(f"Error getting tools for {tool_type}: {e}")
                raise ToolException(f"Error getting tools for {tool_type}: {e}")
        elif settings.get("module"):
            try:
                mod = import_module(settings.pop("module"))
                tkitclass = getattr(mod, settings.pop("class"))
                get_toolkit_params = settings.copy()
                get_toolkit_params["name"] = tool.get("name")
                toolkit = tkitclass.get_toolkit(**get_toolkit_params)
                toolkit_tools.extend(toolkit.get_tools())
            except Exception as e:
                logger.error(f"Error in getting custom toolkit: {e}")
        else:
            if tool_type in FAILED_IMPORTS:
                logger.warning(f"Tool '{tool_type}' is not available: {FAILED_IMPORTS[tool_type]}")
            else:
                logger.warning(f"Unknown tool type: {tool_type}")
        #
        # Always inject toolkit_id to each tool 
        _inject_toolkit_id(tool, toolkit_tools)
        tools.extend(toolkit_tools)

    return tools

def get_toolkits():
    """Return toolkit configurations for all successfully imported toolkits."""
    toolkit_configs = []

    for toolkit_name, toolkit_class in AVAILABLE_TOOLKITS.items():
        try:
            if hasattr(toolkit_class, 'toolkit_config_schema'):
                toolkit_configs.append(toolkit_class.toolkit_config_schema())
            else:
                logger.debug(f"Toolkit {toolkit_name} does not have toolkit_config_schema method")
        except Exception as e:
            logger.error(f"Error getting config schema for {toolkit_name}: {e}")

    logger.info(f"Successfully loaded {len(toolkit_configs)} toolkit configurations")
    return toolkit_configs

def instantiate_toolkit(tool_config):
    """Instantiate a toolkit from its configuration."""
    tool_type = tool_config.get('type')
    
    if tool_type in AVAILABLE_TOOLS:
        tool_module = AVAILABLE_TOOLS[tool_type]
        
        if 'get_toolkit' in tool_module:
             return tool_module['get_toolkit'](tool_config)
             
    raise ValueError(f"Toolkit type '{tool_type}' does not support direct instantiation or is not available.")

def get_available_tools():
    """Return list of available tool types."""
    return list(AVAILABLE_TOOLS.keys())

def get_failed_imports():
    """Return dictionary of failed imports and their error messages."""
    return FAILED_IMPORTS.copy()

def get_available_toolkits():
    """Return list of available toolkit class names."""
    return list(AVAILABLE_TOOLKITS.keys())

def get_available_toolkit_models():
    """Return dict with available toolkit classes."""
    return deepcopy(AVAILABLE_TOOLS)


def get_toolkit_available_tools(toolkit_type: str, settings: dict) -> dict:
    """Return dynamic available tools + per-tool JSON schemas for a toolkit instance.

    This is the single SDK entrypoint used by backend services (e.g. indexer_worker)
    when the UI needs spec/instance-dependent tool enumeration. Toolkits that don't
    support dynamic enumeration should return an empty payload.

    Args:
        toolkit_type: toolkit type string (e.g. 'openapi')
        settings: persisted toolkit settings

    Returns:
        {
          "tools": [{"name": str, "description": str}],
          "args_schemas": {"tool_name": <json schema dict>}
        }
    """
    toolkit_type = (toolkit_type or '').strip().lower()
    if not isinstance(settings, dict):
        settings = {}

    tool_module = AVAILABLE_TOOLS.get(toolkit_type) or {}
    enumerator = tool_module.get('get_toolkit_available_tools')
    if not callable(enumerator):
        return {"tools": [], "args_schemas": {}}

    try:
        result = enumerator(settings)
        if not isinstance(result, dict):
            return {"tools": [], "args_schemas": {}, "error": "Invalid response from toolkit enumerator"}
        return result
    except Exception as e:  # pylint: disable=W0718
        logger.exception("Failed to compute available tools for toolkit_type=%s", toolkit_type)
        return {"tools": [], "args_schemas": {}, "error": str(e)}

def diagnose_imports():
    """Print diagnostic information about tool imports."""
    available_count = len(AVAILABLE_TOOLS)
    failed_count = len(FAILED_IMPORTS)
    total_count = available_count + failed_count

    print(f"=== Tool Import Diagnostic ===")
    print(f"Total tools: {total_count}")
    print(f"Successfully imported: {available_count}")
    print(f"Failed imports: {failed_count}")
    print(f"Success rate: {(available_count/total_count*100):.1f}%")

    if AVAILABLE_TOOLS:
        print(f"\n✅ Available tools ({len(AVAILABLE_TOOLS)}):")
        for tool_name in sorted(AVAILABLE_TOOLS.keys()):
            functions = []
            if 'get_tools' in AVAILABLE_TOOLS[tool_name]:
                functions.append('get_tools')
            if 'toolkit_class' in AVAILABLE_TOOLS[tool_name]:
                functions.append('toolkit')
            print(f"  - {tool_name}: {', '.join(functions)}")

    if FAILED_IMPORTS:
        print(f"\n❌ Failed imports ({len(FAILED_IMPORTS)}):")
        for tool_name, error in FAILED_IMPORTS.items():
            print(f"  - {tool_name}: {error}")

    if AVAILABLE_TOOLKITS:
        print(f"\n🔧 Available toolkits ({len(AVAILABLE_TOOLKITS)}):")
        for toolkit_name in sorted(AVAILABLE_TOOLKITS.keys()):
            print(f"  - {toolkit_name}")

# Export useful functions
__all__ = [
    'get_tools',
    'get_toolkits',
    'get_toolkit_available_tools',
    'get_available_tools',
    'get_failed_imports',
    'get_available_toolkits',
    'get_available_toolkit_models',
    'diagnose_imports'
]
