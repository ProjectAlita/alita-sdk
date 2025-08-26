import logging

logger = logging.getLogger(__name__)

AVAILABLE_CONFIGURATIONS = {}
AVAILABLE_CLASS_CONFIGURATIONS = {}
FAILED_IMPORTS = {}


def _safe_import_configuration(
    configuration_name, module_path, configuration_class_name
):
    """Safely import a configuration module and register available functions/classes."""
    try:
        module = __import__(f'alita_sdk.configurations.{module_path}', fromlist=[''])
        configuration_class = getattr(module, configuration_class_name)
        AVAILABLE_CONFIGURATIONS[configuration_name] = configuration_class.model_json_schema()
        AVAILABLE_CLASS_CONFIGURATIONS[configuration_name] = configuration_class
        logger.debug(f"Successfully imported {configuration_name}")
    except Exception as e:
        FAILED_IMPORTS[configuration_name] = str(e)
        logger.debug(f"Failed to import {configuration_name}: {e}")

# Safe imports for all tools
_safe_import_configuration('github', 'github', 'GithubConfiguration')
_safe_import_configuration('pgvector', 'pgvector', 'PgVectorConfiguration')
_safe_import_configuration('ado', 'ado', 'AdoConfiguration')
_safe_import_configuration('ado_repos', 'ado', 'AdoReposConfiguration')
_safe_import_configuration('gitlab', 'gitlab', 'GitlabConfiguration')
_safe_import_configuration('qtest', 'qtest', 'QtestConfiguration')
_safe_import_configuration('bitbucket', 'bitbucket', 'BitbucketConfiguration')
_safe_import_configuration('confluence', 'confluence', 'ConfluenceConfiguration')
_safe_import_configuration('jira', 'jira', 'JiraConfiguration')
_safe_import_configuration('postman', 'postman', 'PostmanConfiguration')
_safe_import_configuration('service_now', 'service_now', 'ServiceNowConfiguration')
_safe_import_configuration('testrail', 'testrail', 'TestRailConfiguration')
_safe_import_configuration('slack', 'slack', 'SlackConfiguration')
_safe_import_configuration('azure_search', 'azure_search', 'AzureSearchConfiguration')
_safe_import_configuration('delta_lake', 'delta_lake', 'DeltaLakeConfiguration')
_safe_import_configuration('bigquery', 'bigquery', 'BigQueryConfiguration')
_safe_import_configuration('xray', 'xray', 'XrayConfiguration')
_safe_import_configuration('zephyr', 'zephyr', 'ZephyrConfiguration')
_safe_import_configuration('zephyr_enterprise', 'zephyr_enterprise', 'ZephyrEnterpriseConfiguration')
_safe_import_configuration('zephyr_essential', 'zephyr_essential', 'ZephyrEssentialConfiguration')
_safe_import_configuration('figma', 'figma', 'FigmaConfiguration')
_safe_import_configuration('rally', 'rally', 'RallyConfiguration')
_safe_import_configuration('sonar', 'sonar', 'SonarConfiguration')
_safe_import_configuration('sql', 'sql', 'SqlConfiguration')
_safe_import_configuration('google_places', 'google_places', 'GooglePlacesConfiguration')
_safe_import_configuration('salesforce', 'salesforce', 'SalesforceConfiguration')
_safe_import_configuration('browser', 'browser', 'BrowserConfiguration')
_safe_import_configuration('sharepoint', 'sharepoint', 'SharepointConfiguration')
_safe_import_configuration('carrier', 'carrier', 'CarrierConfiguration')
_safe_import_configuration('report_portal', 'report_portal', 'ReportPortalConfiguration')
_safe_import_configuration('testio', 'testio', 'TestIOConfiguration')

# Log import summary
available_count = len(AVAILABLE_CONFIGURATIONS)
total_attempted = len(AVAILABLE_CONFIGURATIONS) + len(FAILED_IMPORTS)
logger.info(f"Configuration imports completed: {available_count}/{total_attempted} successful")


def get_configurations():
    """Return all available configuration schemas."""
    return AVAILABLE_CONFIGURATIONS.copy()


def get_class_configurations():
    """Return all available configuration classes."""
    return AVAILABLE_CLASS_CONFIGURATIONS.copy()


def get_available_configurations():
    """Return list of available configuration class names."""
    return list(AVAILABLE_CONFIGURATIONS.keys())


__all__ = [
    'get_configurations',
    'get_available_configurations',
]
